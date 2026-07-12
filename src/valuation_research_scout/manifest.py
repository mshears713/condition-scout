"""run_manifest.json contract and run-folder skeleton.

The manifest is written by Claude CoWork after it derives valuation
cohort(s) from the Stage 5 queue. This module is the tool-side contract pin
for the v0.2 Input Contract direction (exact field names left to
implementation by the Valuation Research Scout record):

{
  "run_id": "valuation_research_run_2026-07-12",
  "created_at": "2026-07-12T12:00:00Z",           // optional
  "source_platform_context": "JJ Kane is a true no-reserve absolute
    Proxibid auction...",                          // optional, run-level
  "cohorts": [
    {
      "cohort_id": "wpb-express-savana-2500-2017-2018",
      "vehicle_family": "Chevrolet Express / GMC Savana 2500 cargo van",
      "series_or_weight_class": "2500 full-size cargo van",
      "body_configuration": "cargo van, no side windows",
      "model_year_min": 2017,
      "model_year_max": 2018,
      "mileage_min": 51689,
      "mileage_max": 163753,
      "use_context": "commercial/fleet cargo van",
      "primary_geography": "Florida",
      "secondary_geography": "Southeast US",        // optional
      "source_platform": "JJ Kane",
      "listing_count": 8,
      "listing_ids": ["1604992", "1615297", ...]
    }
  ]
}

Claude CoWork owns cohort formation (which listings belong together) and
source-platform context; this tool only validates the shape and renders it
into the standing research prompt. A cohort with no listing_ids is a
malformed manifest, rejected the same as a missing required field.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Fallback framing when a manifest doesn't supply source_platform_context —
# mirrors condition_scout.prompts' vehicle_context/buyer_calibration pattern
# so this never has to be re-baked into the prompt file for a different deal.
DEFAULT_SOURCE_PLATFORM_CONTEXT = (
    "No additional source-platform context was supplied for this batch. "
    "Research the stated source platform on its own merits."
)


class Cohort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cohort_id: str = Field(min_length=1)
    vehicle_family: str = Field(min_length=1)
    series_or_weight_class: str | None = None
    body_configuration: str | None = None
    model_year_min: int | None = None
    model_year_max: int | None = None
    mileage_min: int | None = None
    mileage_max: int | None = None
    use_context: str | None = None
    primary_geography: str | None = None
    secondary_geography: str | None = None
    source_platform: str = Field(min_length=1)
    listing_count: int | None = None
    listing_ids: list[str] = Field(min_length=1)

    def cohort_summary_line(self) -> str:
        """Render the cohort fields into the {COHORT_SUMMARY} prompt block —
        computed in code, never model-asked, mirrors ManifestListing's
        context_line() in condition_scout."""
        years = (
            f"{self.model_year_min}-{self.model_year_max}"
            if self.model_year_min is not None and self.model_year_max is not None
            else "model years unspecified"
        )
        mileage = (
            f"{self.mileage_min:,}-{self.mileage_max:,} miles"
            if self.mileage_min is not None and self.mileage_max is not None
            else "mileage range unspecified"
        )
        geography = self.primary_geography or "geography unspecified"
        if self.secondary_geography:
            geography = f"{geography} / {self.secondary_geography}"
        lines = [
            f"Vehicle family: {self.vehicle_family}",
            f"Years: {years}",
        ]
        if self.series_or_weight_class:
            lines.append(f"Series / weight class: {self.series_or_weight_class}")
        if self.body_configuration:
            lines.append(f"Body configuration: {self.body_configuration}")
        lines.append(f"Mileage span: {mileage}")
        lines.append(f"Use context: {self.use_context or 'commercial/fleet vehicle'}")
        lines.append(f"Region: {geography}")
        lines.append(
            f"Batch size: {self.listing_count or len(self.listing_ids)} listings "
            f"from source platform {self.source_platform}"
        )
        return "\n".join(lines)


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    created_at: str | None = None
    source_platform_context: str | None = None
    cohorts: list[Cohort]


class ManifestError(Exception):
    """Raised when run_manifest.json is missing, unparseable, or invalid."""


def load_manifest(run_dir: Path) -> RunManifest:
    path = run_dir / "run_manifest.json"
    if not path.is_file():
        raise ManifestError(f"no run_manifest.json in {run_dir}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path.name} is not valid JSON: {exc}") from exc
    try:
        return RunManifest.model_validate(data)
    except ValidationError as exc:
        raise ManifestError(f"{path.name} failed validation:\n{exc}") from exc


def cohort_dir(run_dir: Path, cohort_id: str) -> Path:
    return run_dir / "cohorts" / cohort_id


def ensure_cohort_skeleton(run_dir: Path, cohort: Cohort) -> Path:
    """Create cohorts/<cohort_id>/ and cohort_snapshot.json (the manifest
    entry, denormalized so each cohort folder is self-contained)."""
    folder = cohort_dir(run_dir, cohort.cohort_id)
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = folder / "cohort_snapshot.json"
    if not snapshot.exists():
        snapshot.write_text(cohort.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return folder
