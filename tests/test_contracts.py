"""M1 contract tests: golden round-trips, malformed-manifest rejection,
run-folder skeleton, coverage computation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from condition_scout.manifest import (
    ManifestError,
    ManifestListing,
    RunManifest,
    ensure_listing_skeleton,
    load_manifest,
    normalize_source,
)
from condition_scout.schema import (
    ConditionAnalysis,
    Finding,
    PhotoRecord,
    RunSummary,
    Zone,
    compute_coverage,
    zone_of_view,
)

GOLDEN = Path(__file__).parent / "golden"


def load_golden(name: str) -> dict:
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


# --- golden round-trips ----------------------------------------------------

def test_condition_analysis_golden_round_trip():
    data = load_golden("condition_analysis.json")
    model = ConditionAnalysis.model_validate(data)
    assert json.loads(model.model_dump_json()) == data


def test_run_summary_golden_round_trip():
    data = load_golden("run_summary.json")
    model = RunSummary.model_validate(data)
    assert json.loads(model.model_dump_json()) == data


def test_run_manifest_golden_round_trip():
    data = load_golden("run_manifest.json")
    model = RunManifest.model_validate(data)
    assert json.loads(model.model_dump_json()) == data
    assert model.listings[3].photo_urls  # GovDeals row carries override URLs


# --- manifest loading and rejection ----------------------------------------

def write_manifest(tmp_path: Path, data) -> Path:
    (tmp_path / "run_manifest.json").write_text(
        data if isinstance(data, str) else json.dumps(data), encoding="utf-8"
    )
    return tmp_path


def minimal_manifest() -> dict:
    return {
        "run_id": "valuation_run_2026-07-10",
        "listings": [
            {
                "listing_id": "1619602",
                "source": "JJ Kane",
                "listing_url": "https://www.jjkane.com/item/1619602",
            }
        ],
    }


def test_load_manifest_ok(tmp_path):
    manifest = load_manifest(write_manifest(tmp_path, minimal_manifest()))
    assert manifest.run_id == "valuation_run_2026-07-10"
    assert manifest.listings[0].year is None  # optional fields optional


def test_load_manifest_missing_file(tmp_path):
    with pytest.raises(ManifestError, match="no run_manifest.json"):
        load_manifest(tmp_path)


def test_load_manifest_bad_json(tmp_path):
    with pytest.raises(ManifestError, match="not valid JSON"):
        load_manifest(write_manifest(tmp_path, "{not json"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.pop("run_id"),
        lambda m: m["listings"][0].pop("listing_id"),
        lambda m: m["listings"][0].pop("source"),
        lambda m: m["listings"][0].pop("listing_url"),
        lambda m: m["listings"][0].update(listing_id=""),
        lambda m: m["listings"][0].update(unexpected_field=1),
        lambda m: m["listings"][0].update(year="not-a-number"),
    ],
)
def test_load_manifest_rejects_malformed(tmp_path, mutate):
    data = minimal_manifest()
    mutate(data)
    with pytest.raises(ManifestError, match="failed validation"):
        load_manifest(write_manifest(tmp_path, data))


def test_normalize_source():
    assert normalize_source("Public Surplus") == normalize_source("PublicSurplus")
    assert normalize_source("JJ KANE") == "jjkane"


def test_listing_context_line_never_includes_judgments():
    listing = ManifestListing(
        listing_id="x",
        source="JJ Kane",
        listing_url="https://example.com",
        year=2016,
        platform="Ford Transit 250",
        mileage=128000,
    )
    assert listing.context_line() == "2016 Ford Transit 250 cargo van, listed at 128,000 miles"


# --- run-folder skeleton -----------------------------------------------------

def test_ensure_listing_skeleton(tmp_path):
    listing = ManifestListing(
        listing_id="1619602",
        source="JJ Kane",
        listing_url="https://www.jjkane.com/item/1619602",
    )
    folder = ensure_listing_skeleton(tmp_path, listing)
    assert folder == tmp_path / "listings" / "1619602"
    assert (folder / "photos").is_dir()
    snapshot = json.loads((folder / "listing_snapshot.json").read_text())
    assert snapshot["listing_id"] == "1619602"
    # idempotent: second call must not clobber
    (folder / "listing_snapshot.json").write_text('{"listing_id": "edited"}')
    ensure_listing_skeleton(tmp_path, listing)
    assert json.loads((folder / "listing_snapshot.json").read_text())["listing_id"] == "edited"


# --- evidence citation rule --------------------------------------------------

def test_finding_requires_image_refs():
    with pytest.raises(ValidationError):
        Finding(
            zone=Zone.cab_interior,
            polarity="negative",
            description="torn seat",
            severity="heavy",
            confidence="high",
            image_refs=[],
        )


# --- coverage computation ----------------------------------------------------

def record(view: str) -> PhotoRecord:
    return PhotoRecord(photo="p.jpg", view=view, photo_quality="clear", observations=[])


def test_zone_of_view_extracts_decorated_views():
    assert zone_of_view("cab_interior — driver seat area") == Zone.cab_interior
    assert zone_of_view("exterior_sides") == Zone.exterior_sides
    assert zone_of_view("something else entirely") is None


def test_compute_coverage_thresholds():
    nine = [record(z) for z in (
        "exterior_front", "exterior_sides", "exterior_rear", "roof",
        "tires_wheels", "engine_bay", "cab_interior", "dash_instruments",
        "cargo_area",
    )]
    coverage = compute_coverage(nine)
    assert coverage.coverage_quality == "good"
    assert coverage.zones_missing == [Zone.underbody]
    assert coverage.photos_analyzed == 9

    five = [record(z) for z in (
        "exterior_front", "exterior_sides", "exterior_rear", "roof", "tires_wheels",
    )]
    assert compute_coverage(five).coverage_quality == "partial"

    assert compute_coverage([record("exterior_front")]).coverage_quality == "poor"
    assert compute_coverage([]).coverage_quality == "poor"


def test_compute_coverage_ignores_unknown_views_but_counts_photos():
    coverage = compute_coverage([record("exterior_front"), record("???")])
    assert coverage.photos_analyzed == 2
    assert coverage.zones_covered == [Zone.exterior_front]
