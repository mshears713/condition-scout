"""Batch orchestrator: manifest in, cohort-research artifacts out.

Per-cohort errors are recorded in run_summary.json and skipped — never
fatal to the batch, mirroring Condition Scout's per-listing isolation.

Exit codes (CLI): 0 = every cohort processed; 1 = at least one cohort
failed; 2 = manifest/setup error.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from valuation_research_scout import PROMPT_VERSION
from valuation_research_scout.artifacts import (
    build_cohort_research,
    utc_now_iso,
    write_cohort_research,
    write_raw_response,
    write_run_summary,
)
from valuation_research_scout.manifest import (
    ManifestError,
    ensure_cohort_skeleton,
    load_manifest,
)
from valuation_research_scout.prompts import PromptError, fill_template, load_research_prompt
from valuation_research_scout.schema import CohortFailure, RunSummary, tavily_output_schema
from valuation_research_scout.tavily import TavilyError

logger = logging.getLogger(__name__)

VALID_MODELS = ("mini", "pro", "auto")


class CohortRunFailure(Exception):
    """This cohort's research failed; the batch continues."""

    def __init__(self, stage: str, reason: str):
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


@dataclass
class RunConfig:
    model: str = "auto"
    poll_interval_s: float = 5.0
    timeout_s: float = 900.0


def run_batch(
    run_dir: Path,
    *,
    tavily,
    config: RunConfig | None = None,
    prompts_dir: Path | None = None,
    sleep=time.sleep,
    clock=time.monotonic,
) -> RunSummary:
    config = config or RunConfig()
    if config.model not in VALID_MODELS:
        raise ManifestError(f"invalid model {config.model!r}; must be one of {VALID_MODELS}")
    template, prompt_version = load_research_prompt(prompts_dir)
    if prompt_version != PROMPT_VERSION:
        logger.warning(
            "prompt file is v%s but the package pins v%s - artifacts will "
            "record the file version", prompt_version, PROMPT_VERSION,
        )
    manifest = load_manifest(run_dir)
    source_platform_context = manifest.source_platform_context
    if source_platform_context is None:
        from valuation_research_scout.manifest import DEFAULT_SOURCE_PLATFORM_CONTEXT

        source_platform_context = DEFAULT_SOURCE_PLATFORM_CONTEXT

    started_at = utc_now_iso()
    processed: list[str] = []
    failed: list[CohortFailure] = []
    api_calls_used = 0

    output_schema = tavily_output_schema()

    for cohort in manifest.cohorts:
        cid = cohort.cohort_id
        folder = ensure_cohort_skeleton(run_dir, cohort)
        try:
            prompt = fill_template(
                template,
                cohort_summary=cohort.cohort_summary_line(),
                source_platform_context=source_platform_context,
            )
            try:
                result = tavily.run(
                    input=prompt,
                    model=config.model,
                    output_schema=output_schema,
                    poll_interval_s=config.poll_interval_s,
                    timeout_s=config.timeout_s,
                    sleep=sleep,
                    clock=clock,
                )
            except TavilyError as exc:
                raise CohortRunFailure("request", str(exc)) from exc
            api_calls_used += 1
            # Preserve the raw response as soon as Tavily itself succeeds,
            # before attempting contract validation — a validation failure
            # is exactly when this evidence is most needed for debugging.
            write_raw_response(folder, result.raw)

            try:
                research = build_cohort_research(
                    cohort, result, model=config.model, prompt_version=prompt_version,
                )
            except Exception as exc:  # noqa: BLE001 — contract violation, not a bug
                raise CohortRunFailure(
                    "write", f"Tavily response failed contract validation: {exc}"
                ) from exc

            write_cohort_research(folder, research, result.raw)
            processed.append(cid)
            logger.info("%s: research complete (%d sources)", cid, len(result.sources))
        except CohortRunFailure as exc:
            failed.append(CohortFailure(cohort_id=cid, stage=exc.stage, reason=exc.reason))
            logger.warning("%s: %s failed - %s", cid, exc.stage, exc.reason)
        except Exception as exc:  # noqa: BLE001 — batch isolation is the contract
            failed.append(CohortFailure(cohort_id=cid, stage="unexpected", reason=repr(exc)))
            logger.exception("%s: unexpected failure", cid)

    finished_at = utc_now_iso()
    summary = RunSummary(
        run_id=manifest.run_id,
        started_at=started_at,
        finished_at=finished_at,
        cohorts_total=len(manifest.cohorts),
        processed=processed,
        failed=failed,
        api_calls_used=api_calls_used,
    )
    write_run_summary(run_dir, summary)
    return summary


def run_from_cli(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_dir: Path = args.run_dir

    config = RunConfig()
    if args.model:
        config.model = args.model
    if args.poll_interval:
        config.poll_interval_s = args.poll_interval
    if args.timeout:
        config.timeout_s = args.timeout

    if args.fake_network:
        from valuation_research_scout.fakenet import FakeNetworkTavily

        tavily = FakeNetworkTavily()
    else:
        from valuation_research_scout.tavily import RealTavilyClient, TavilyError

        try:
            tavily = RealTavilyClient()
        except TavilyError as exc:
            print(f"error: {exc}")
            return 2

    try:
        summary = run_batch(run_dir, tavily=tavily, config=config)
    except (ManifestError, PromptError) as exc:
        print(f"error: {exc}")
        return 2

    print(
        f"run {summary.run_id}: {len(summary.processed)} processed, "
        f"{len(summary.failed)} failed ({summary.api_calls_used} Tavily calls) "
        "- see run_summary.json"
    )
    for failure in summary.failed:
        print(f"  FAILED {failure.cohort_id} at {failure.stage}: {failure.reason}")
    return 1 if summary.failed else 0
