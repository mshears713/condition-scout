"""Contracts: condition_analysis v0.2, photo_manifest, run_summary.

These schemas are the CoWork-facing promise of the tool. Zone/severity
structure follows the Tool page's v0.2 placeholder; grading anchors live in
the Analysis Prompt Spec, not here. Severity bands and grades are words, not
numbers, so the future condition-adjustment matrix can map zone x band to
dollar bands outside this tool.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.2"

# The 10 photo zones. `view` strings must start with one of these; anything
# after the zone token (e.g. "cab_interior — driver seat area") is free text.
ZONES = (
    "exterior_front",
    "exterior_sides",
    "exterior_rear",
    "roof",
    "tires_wheels",
    "engine_bay",
    "cab_interior",
    "dash_instruments",
    "cargo_area",
    "underbody",
)


class Zone(str, Enum):
    exterior_front = "exterior_front"
    exterior_sides = "exterior_sides"
    exterior_rear = "exterior_rear"
    roof = "roof"
    tires_wheels = "tires_wheels"
    engine_bay = "engine_bay"
    cab_interior = "cab_interior"
    dash_instruments = "dash_instruments"
    cargo_area = "cargo_area"
    underbody = "underbody"


class Severity(str, Enum):
    none = "none"
    minor = "minor"
    moderate = "moderate"
    heavy = "heavy"
    severe = "severe"


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Polarity(str, Enum):
    positive = "positive"
    negative = "negative"


class PhotoQuality(str, Enum):
    clear = "clear"
    blurry = "blurry"
    dark = "dark"
    partial = "partial"


class VisualGrade(str, Enum):
    """Mike-process-relative, NOT retail; deliberately distinct from the
    Stage 4 Vehicle Quality vocabulary (Great/Good/Fair/Poor/Very Poor)."""

    excellent = "excellent"
    good = "good"
    serviceable = "serviceable"
    rough = "rough"
    poor = "poor"


class CoverageQuality(str, Enum):
    good = "good"
    partial = "partial"
    poor = "poor"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Observation(_Contract):
    noticed: str
    zone: Zone
    polarity: Polarity
    severity: Severity
    confidence: Confidence


class PhotoRecord(_Contract):
    """One record per photo — the per-photo audit trail.

    This is also the shape the per-photo vision call returns (minus `photo`,
    which the tool stamps from the request). The dash/mismatch fields are only
    populated when the photo warranted them (prompt questions 4-5)."""

    photo: str
    view: str
    photo_quality: PhotoQuality
    observations: list[Observation]
    dash_warning_lights: list[str] | None = None
    odometer_contradiction: str | None = None
    mismatch_note: str | None = None


class PhotoCoverage(_Contract):
    """Computed in code from the per-photo `view` fields — never model-asked."""

    photos_analyzed: int
    zones_covered: list[Zone]
    zones_missing: list[Zone]
    coverage_quality: CoverageQuality


class Finding(_Contract):
    zone: Zone
    polarity: Polarity
    description: str
    severity: Severity
    confidence: Confidence
    image_refs: list[str] = Field(min_length=1)  # evidence citation rule
    red_flag_hint: str | None = None


class Positive(_Contract):
    description: str
    confidence: Confidence
    image_refs: list[str] = Field(min_length=1)


class AdjustmentCategory(_Contract):
    zone: Zone
    band: Severity


class DashEvidence(_Contract):
    warning_lights: list[str]
    odometer_visible: bool
    odometer_reading: str | None = None
    image_refs: list[str]


class Overall(_Contract):
    visual_grade: VisualGrade
    summary: str
    confidence: Confidence


class SynthesisResult(_Contract):
    """What the per-listing synthesis call returns (text-only call)."""

    findings: list[Finding]
    positives: list[Positive]
    adjustment_categories: list[AdjustmentCategory]
    dash_evidence: DashEvidence
    mismatch_flags: list[str]
    overall: Overall


class ConditionAnalysis(_Contract):
    """condition_analysis.json — assembled in code from per-photo records,
    computed coverage, and the synthesis result."""

    listing_id: str
    source: str
    analyzed_at: str
    model: str
    schema_version: str = SCHEMA_VERSION
    prompt_version: str
    photo_observations: list[PhotoRecord]
    photo_coverage: PhotoCoverage
    findings: list[Finding]
    positives: list[Positive]
    adjustment_categories: list[AdjustmentCategory]
    dash_evidence: DashEvidence
    mismatch_flags: list[str]
    overall: Overall


class PhotoManifestEntry(_Contract):
    order: int
    filename: str
    url: str


class PhotoManifest(_Contract):
    """photo_manifest.json — source URL, local filename, order."""

    listing_id: str
    source: str
    downloaded_at: str
    photos: list[PhotoManifestEntry]


class ListingFailure(_Contract):
    listing_id: str
    stage: str  # resolve | download | analyze | synthesize | write
    reason: str


class ListingSkip(_Contract):
    listing_id: str
    reason: str


class RunSummary(_Contract):
    """run_summary.json — run-level outcome CoWork reads first."""

    run_id: str
    started_at: str
    finished_at: str
    schema_version: str = SCHEMA_VERSION
    listings_total: int
    processed: list[str]
    failed: list[ListingFailure]
    skipped: list[ListingSkip]
    api_calls_used: int


class RunHistoryEntry(_Contract):
    """One line of run_history.jsonl — one entry per CLI invocation of a run
    folder. run_summary.json reflects only the latest invocation's state;
    this is the append-only log that preserves the full timeline across
    resumed/multi-invocation batches (same-day tuning, or resume-next-day
    after quota exhaustion)."""

    invocation_started_at: str
    invocation_finished_at: str
    newly_processed: list[str]
    resumed: list[str]
    failed: list[ListingFailure]
    skipped: list[ListingSkip]
    api_calls_used: int


def zone_of_view(view: str) -> Zone | None:
    """Extract the zone token from a `view` string ("cab_interior — driver
    seat area" -> cab_interior). Returns None for unrecognizable views."""
    token = view.strip().split()[0].rstrip("—-–:").strip() if view.strip() else ""
    for zone in ZONES:
        if token == zone or view.strip().startswith(zone):
            return Zone(zone)
    return None


def compute_coverage(records: list[PhotoRecord]) -> PhotoCoverage:
    """Coverage from `view` fields: 8+ zones = good, 5-7 = partial, <5 = poor.

    Thresholds are a code-level placeholder (the Tool page defines the words
    but not the cutoffs); expected to tune via Debrief."""
    covered = sorted(
        {z for r in records if (z := zone_of_view(r.view)) is not None},
        key=lambda z: ZONES.index(z.value),
    )
    n = len(covered)
    quality = (
        CoverageQuality.good if n >= 8
        else CoverageQuality.partial if n >= 5
        else CoverageQuality.poor
    )
    return PhotoCoverage(
        photos_analyzed=len(records),
        zones_covered=covered,
        zones_missing=[Zone(z) for z in ZONES if Zone(z) not in covered],
        coverage_quality=quality,
    )
