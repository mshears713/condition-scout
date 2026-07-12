"""run_manifest.json contract and run-folder skeleton.

The manifest is written by Claude CoWork; this module is the tool-side
contract pin (the Engineering Plan left exact field names to Stage 3):

{
  "run_id": "valuation_run_2026-07-10",
  "created_at": "2026-07-10T12:00:00Z",          // optional
  "listings": [
    {
      "listing_id": "1619602",
      "source": "JJ Kane",       // "JJ Kane" | "PublicSurplus" | "Purple Wave"
                                 //  | "GovDeals" | anything else
      "listing_url": "https://...",
      "year": 2016,
      "platform": "Ford Transit 250",
      "mileage": 128000,
      "auction_id": "20260715",  // optional; Purple Wave lots when the
                                 // auction id is not parseable from the URL
      "photo_urls": ["https://..."]  // optional pre-resolved override;
                                     // REQUIRED for GovDeals and any
                                     // unrecognized source
    }
  ]
}

Unknown source without override URLs => the listing is skipped (recorded in
run_summary), never fatal to the batch.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Sources with a built-in resolver. Names are matched case-insensitively and
# ignoring internal spaces ("publicsurplus" == "PublicSurplus").
RESOLVABLE_SOURCES = ("JJ Kane", "PublicSurplus", "Purple Wave")


def normalize_source(source: str) -> str:
    return "".join(source.lower().split())


class ManifestListing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    listing_url: str
    year: int | None = None
    platform: str | None = None
    mileage: int | None = None
    auction_id: str | None = None
    photo_urls: list[str] | None = None

    def context_line(self) -> str:
        """The minimal listing context handed to the vision calls — by design
        never Red Flags or AI Notes, to keep photo evidence independent."""
        year = str(self.year) if self.year is not None else "unknown-year"
        platform = self.platform or "unknown-platform"
        mileage = f"{self.mileage:,}" if self.mileage is not None else "unknown"
        return f"{year} {platform} cargo van, listed at {mileage} miles"


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    created_at: str | None = None
    # Deal-specific framing for this run — what kind of vehicle this is and
    # what the buyer's process cares about. Optional: falls back to the
    # historical work-van/camper-conversion framing (see prompts.py) when a
    # manifest doesn't supply it, so this never needs to be baked into the
    # prompt files themselves as new vehicle types/deals come through.
    vehicle_context: str | None = None
    buyer_calibration: str | None = None
    listings: list[ManifestListing]


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


def listing_dir(run_dir: Path, listing_id: str) -> Path:
    return run_dir / "listings" / listing_id


def ensure_listing_skeleton(run_dir: Path, listing: ManifestListing) -> Path:
    """Create listings/<id>/ with photos/ and listing_snapshot.json (the
    manifest entry, denormalized so each listing folder is self-contained)."""
    folder = listing_dir(run_dir, listing.listing_id)
    (folder / "photos").mkdir(parents=True, exist_ok=True)
    snapshot = folder / "listing_snapshot.json"
    if not snapshot.exists():
        snapshot.write_text(
            listing.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return folder
