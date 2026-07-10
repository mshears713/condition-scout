"""Batch orchestrator: manifest in, condition artifacts out.

Per-listing errors are recorded in run_summary.json and skipped — never
fatal to the batch. Re-running a run folder resumes: existing photos are
kept and listings with a valid condition_analysis.json are not re-analyzed.

Exit codes (CLI): 0 = every listing processed or skipped-by-design;
1 = at least one listing failed; 2 = manifest/setup error.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from condition_scout import PROMPT_VERSION
from condition_scout.analyzer import (
    AnalysisFailure,
    AnalyzerConfig,
    CallStats,
    analyze_photos,
    has_valid_analysis,
    synthesize,
)
from condition_scout.artifacts import (
    build_condition_analysis,
    utc_now_iso,
    write_condition_analysis,
    write_run_summary,
)
from condition_scout.download import (
    DEFAULT_DOWNLOAD_INTERVAL_S,
    DownloadError,
    download_photos,
)
from condition_scout.manifest import (
    ManifestError,
    ensure_listing_skeleton,
    load_manifest,
)
from condition_scout.pacing import RatePacer
from condition_scout.prompts import PromptError, load_prompts
from condition_scout.resolvers import ResolveError, SkipListing, resolve_photo_urls
from condition_scout.schema import ListingFailure, ListingSkip, RunSummary

logger = logging.getLogger(__name__)


def run_batch(
    run_dir: Path,
    *,
    http,
    gemini,
    config: AnalyzerConfig | None = None,
    prompts_dir: Path | None = None,
    download_interval_s: float = DEFAULT_DOWNLOAD_INTERVAL_S,
    sleep=time.sleep,
    clock=time.monotonic,
) -> RunSummary:
    config = config or AnalyzerConfig()
    prompts = load_prompts(prompts_dir)
    if prompts.version != PROMPT_VERSION:
        logger.warning(
            "prompt files are v%s but the package pins v%s — artifacts will "
            "record the file version", prompts.version, PROMPT_VERSION,
        )
    manifest = load_manifest(run_dir)

    download_pacer = RatePacer(download_interval_s, clock=clock, sleep=sleep)
    api_pacer = RatePacer.per_minute(config.rpm, clock=clock, sleep=sleep)
    stats = CallStats()
    started_at = utc_now_iso()

    processed: list[str] = []
    failed: list[ListingFailure] = []
    skipped: list[ListingSkip] = []

    for listing in manifest.listings:
        lid = listing.listing_id
        folder = ensure_listing_skeleton(run_dir, listing)
        try:
            if has_valid_analysis(folder):
                logger.info("%s: valid condition_analysis.json exists — resume-skip", lid)
                processed.append(lid)
                continue

            urls = resolve_photo_urls(listing, http)
            photo_manifest = download_photos(
                listing, urls, folder, http, download_pacer
            )
            records = analyze_photos(
                listing, photo_manifest, folder, gemini, prompts, config,
                pacer=api_pacer, stats=stats, sleep=sleep,
            )
            synthesis = synthesize(
                listing, records, gemini, prompts, config,
                pacer=api_pacer, stats=stats, sleep=sleep,
            )
            analysis = build_condition_analysis(
                listing, records, synthesis,
                model=config.model, prompt_version=prompts.version,
            )
            write_condition_analysis(folder, analysis)
            processed.append(lid)
            logger.info("%s: analyzed %d photos", lid, len(records))
        except SkipListing as exc:
            skipped.append(ListingSkip(listing_id=lid, reason=str(exc)))
            logger.info("%s: skipped — %s", lid, exc)
        except ResolveError as exc:
            failed.append(ListingFailure(listing_id=lid, stage="resolve", reason=str(exc)))
            logger.warning("%s: resolve failed — %s", lid, exc)
        except DownloadError as exc:
            failed.append(ListingFailure(listing_id=lid, stage="download", reason=str(exc)))
            logger.warning("%s: download failed — %s", lid, exc)
        except AnalysisFailure as exc:
            failed.append(ListingFailure(listing_id=lid, stage=exc.stage, reason=exc.reason))
            logger.warning("%s: %s failed — %s", lid, exc.stage, exc.reason)
        except Exception as exc:  # noqa: BLE001 — batch isolation is the contract
            failed.append(ListingFailure(listing_id=lid, stage="unexpected", reason=repr(exc)))
            logger.exception("%s: unexpected failure", lid)

    summary = RunSummary(
        run_id=manifest.run_id,
        started_at=started_at,
        finished_at=utc_now_iso(),
        listings_total=len(manifest.listings),
        processed=processed,
        failed=failed,
        skipped=skipped,
        api_calls_used=stats.calls,
    )
    write_run_summary(run_dir, summary)
    return summary


def run_from_cli(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_dir: Path = args.run_dir

    config = AnalyzerConfig()
    if args.model:
        config.model = args.model
    if args.photos_per_call:
        config.photos_per_call = args.photos_per_call
    if args.rpm:
        config.rpm = args.rpm

    if args.fake_network:
        from condition_scout.fakenet import FakeNetworkGemini, FakeNetworkHttp

        http, gemini = FakeNetworkHttp(), FakeNetworkGemini()
        download_interval = 0.0
        config.rpm = 100000  # no point pacing a fake
    else:
        from condition_scout.gemini import GeminiError, RealGeminiClient
        from condition_scout.http import RequestsHttpClient

        http = RequestsHttpClient()
        try:
            gemini = RealGeminiClient()
        except GeminiError as exc:
            print(f"error: {exc}")
            return 2
        download_interval = DEFAULT_DOWNLOAD_INTERVAL_S

    try:
        summary = run_batch(
            run_dir,
            http=http,
            gemini=gemini,
            config=config,
            download_interval_s=download_interval,
        )
    except (ManifestError, PromptError) as exc:
        print(f"error: {exc}")
        return 2

    print(
        f"run {summary.run_id}: {len(summary.processed)} processed, "
        f"{len(summary.failed)} failed, {len(summary.skipped)} skipped "
        f"({summary.api_calls_used} API calls) — see run_summary.json"
    )
    for failure in summary.failed:
        print(f"  FAILED {failure.listing_id} at {failure.stage}: {failure.reason}")
    for skip in summary.skipped:
        print(f"  SKIPPED {skip.listing_id}: {skip.reason}")
    return 1 if summary.failed else 0
