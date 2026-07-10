"""Vision analysis: per-photo calls (default) or grouped calls (quota
fallback), plus the per-listing text-only synthesis call.

Free-tier shaped: RPM pacing, exponential backoff on 429, one malformed-JSON
repair retry, then the listing fails — never the batch.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from condition_scout.gemini import GeminiError, ImagePart, RateLimitError, mime_type_for
from condition_scout.manifest import ManifestListing
from condition_scout.pacing import RatePacer
from condition_scout.prompts import PromptPack, fill_template
from condition_scout.schema import (
    ConditionAnalysis,
    PhotoManifest,
    PhotoRecord,
    SynthesisResult,
)

# Rolling Flash-Lite alias: the pinned "gemini-2.5-flash-lite" 404'd for new
# API projects at the 2026-07-10 live smoke ("no longer available to new
# users"), exactly the model-name churn the Engineering Plan predicted.
# Provisional delta, flagged in the Build Log: name a class, not a pin.
DEFAULT_MODEL = "gemini-flash-lite-latest"

REPAIR_INSTRUCTION = (
    "Your previous reply was not valid JSON matching the required schema. "
    "Reply again with ONLY valid JSON matching the schema — no prose, no "
    "markdown fences."
)


@dataclass
class AnalyzerConfig:
    model: str = DEFAULT_MODEL
    photos_per_call: int = 1
    rpm: int = 10
    max_rate_limit_retries: int = 4
    backoff_base_s: float = 2.0


@dataclass
class CallStats:
    """Counts every request attempt (retries included — they burn quota)."""

    calls: int = 0


class AnalysisFailure(Exception):
    """This listing's analysis failed; the batch continues."""

    def __init__(self, stage: str, reason: str):
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _photo_record_schema(with_photo: bool) -> dict:
    schema = PhotoRecord.model_json_schema()
    if not with_photo:
        schema["properties"].pop("photo")
        schema["required"] = [r for r in schema["required"] if r != "photo"]
    return schema


def _call(
    client,
    *,
    model: str,
    parts: list,
    response_schema: dict,
    pacer: RatePacer,
    stats: CallStats,
    config: AnalyzerConfig,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """One logical request with RPM pacing and 429 exponential backoff."""
    attempt = 0
    while True:
        pacer.wait()
        stats.calls += 1
        try:
            return client.generate(
                model=model, parts=parts, response_schema=response_schema
            )
        except RateLimitError as exc:
            if attempt >= config.max_rate_limit_retries:
                raise AnalysisFailure(
                    "analyze", f"rate-limited after {attempt + 1} attempts: {exc}"
                ) from exc
            sleep(config.backoff_base_s * (2**attempt))
            attempt += 1
        except GeminiError as exc:
            raise AnalysisFailure("analyze", f"Gemini call failed: {exc}") from exc


def _call_validated(
    client,
    *,
    parts: list,
    response_schema: dict,
    validate: Callable[[str], object],
    pacer: RatePacer,
    stats: CallStats,
    config: AnalyzerConfig,
    sleep: Callable[[float], None] = time.sleep,
):
    """Call once; on malformed/truncated JSON retry once with a repair
    instruction appended, then fail the listing."""
    kwargs = dict(
        model=config.model,
        response_schema=response_schema,
        pacer=pacer,
        stats=stats,
        config=config,
        sleep=sleep,
    )
    text = _call(client, parts=parts, **kwargs)
    try:
        return validate(text)
    except (json.JSONDecodeError, ValidationError) as first_error:
        repair_parts = list(parts) + [REPAIR_INSTRUCTION]
        text = _call(client, parts=repair_parts, **kwargs)
        try:
            return validate(text)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AnalysisFailure(
                "analyze",
                f"response failed validation twice (first: {first_error}; "
                f"after repair retry: {exc})",
            ) from exc


def _validate_single(text: str) -> PhotoRecord:
    data = json.loads(text)
    if isinstance(data, dict):
        # single mode omits `photo` from the response schema; the tool stamps
        # the real filename after validation
        data.setdefault("photo", "unstamped")
    return PhotoRecord.model_validate(data)


def _validate_batch(expected: int) -> Callable[[str], list[PhotoRecord]]:
    def validate(text: str) -> list[PhotoRecord]:
        data = json.loads(text)
        records = [PhotoRecord.model_validate(item) for item in data]
        if len(records) != expected:
            # a missing record is a contract violation -> repair/fail path
            raise ValidationError.from_exception_data(
                "PhotoRecordBatch",
                [
                    {
                        "type": "value_error",
                        "loc": ("records",),
                        "input": len(records),
                        "ctx": {"error": f"expected {expected} records, got {len(records)}"},
                    }
                ],
            )
        return records

    return validate


def _chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def analyze_photos(
    listing: ManifestListing,
    photo_manifest: PhotoManifest,
    listing_folder: Path,
    client,
    prompts: PromptPack,
    config: AnalyzerConfig,
    *,
    pacer: RatePacer | None = None,
    stats: CallStats | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[PhotoRecord]:
    """One independent vision call per photo (or per group when
    photos_per_call > 1). Returns one PhotoRecord per photo, filenames
    stamped from the photo manifest (never trusted from the model)."""
    pacer = pacer or RatePacer.per_minute(config.rpm)
    stats = stats or CallStats()
    prompt = fill_template(
        prompts.photo_template,
        year=listing.year,
        platform=listing.platform,
        mileage=listing.mileage,
    )
    before, _, after = prompt.partition("[PHOTO]")

    photos_dir = listing_folder / "photos"
    records: list[PhotoRecord] = []

    if config.photos_per_call <= 1:
        for entry in photo_manifest.photos:
            image = ImagePart(
                data=(photos_dir / entry.filename).read_bytes(),
                mime_type=mime_type_for(entry.filename),
            )
            parts = [
                before.strip() + f"\n\nThis photo's filename: {entry.filename}",
                image,
                after.strip(),
            ]
            record = _call_validated(
                client,
                parts=parts,
                response_schema=_photo_record_schema(with_photo=False),
                validate=_validate_single,
                pacer=pacer,
                stats=stats,
                config=config,
                sleep=sleep,
            )
            records.append(record.model_copy(update={"photo": entry.filename}))
        return records

    # Grouped fallback mode: several photos per call, one record each.
    batch_schema = {
        "type": "array",
        "items": _photo_record_schema(with_photo=True),
    }
    for batch in _chunks(list(photo_manifest.photos), config.photos_per_call):
        parts: list = [
            before.strip()
            + "\n\nThis call contains "
            + str(len(batch))
            + " photos. Analyze each photo independently and return a JSON "
            "array with exactly one record per photo, in the order given, "
            "each echoing that photo's filename in its 'photo' field.",
        ]
        for entry in batch:
            parts.append(f"Photo filename: {entry.filename}")
            parts.append(
                ImagePart(
                    data=(photos_dir / entry.filename).read_bytes(),
                    mime_type=mime_type_for(entry.filename),
                )
            )
        parts.append(after.strip())
        batch_records = _call_validated(
            client,
            parts=parts,
            response_schema=batch_schema,
            validate=_validate_batch(len(batch)),
            pacer=pacer,
            stats=stats,
            config=config,
            sleep=sleep,
        )
        records.extend(
            record.model_copy(update={"photo": entry.filename})
            for entry, record in zip(batch, batch_records)
        )
    return records


def synthesize(
    listing: ManifestListing,
    records: list[PhotoRecord],
    client,
    prompts: PromptPack,
    config: AnalyzerConfig,
    *,
    pacer: RatePacer | None = None,
    stats: CallStats | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> SynthesisResult:
    """One text-only synthesis call per listing: merges observations into
    findings. Never sees a photo; nothing new may appear at synthesis."""
    pacer = pacer or RatePacer.per_minute(config.rpm)
    stats = stats or CallStats()
    prompt = fill_template(
        prompts.synthesis_template,
        year=listing.year,
        platform=listing.platform,
        mileage=listing.mileage,
    )
    observations_json = json.dumps(
        [json.loads(r.model_dump_json()) for r in records], indent=2
    )
    prompt = prompt.replace("[PHOTO_OBSERVATIONS]", observations_json)

    def validate(text: str) -> SynthesisResult:
        return SynthesisResult.model_validate(json.loads(text))

    try:
        return _call_validated(
            client,
            parts=[prompt],
            response_schema=SynthesisResult.model_json_schema(),
            validate=validate,
            pacer=pacer,
            stats=stats,
            config=config,
            sleep=sleep,
        )
    except AnalysisFailure as exc:
        raise AnalysisFailure("synthesize", exc.reason) from exc


def has_valid_analysis(listing_folder: Path) -> bool:
    """Resume-skip: a listing with an existing valid condition_analysis.json
    is not re-analyzed (a quota-exhausted run continues tomorrow)."""
    path = listing_folder / "condition_analysis.json"
    if not path.is_file():
        return False
    try:
        ConditionAnalysis.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError, OSError):
        return False
    return True
