"""Cohort manifest contract: loading, rejection, cohort-folder skeleton,
and the code-computed COHORT_SUMMARY rendering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from valuation_research_scout.manifest import (
    Cohort,
    ManifestError,
    RunManifest,
    ensure_cohort_skeleton,
    load_manifest,
)


def minimal_manifest() -> dict:
    return {
        "run_id": "valuation_research_run_2026-07-12",
        "cohorts": [
            {
                "cohort_id": "wpb-express-savana-2500-2017-2018",
                "vehicle_family": "Chevrolet Express / GMC Savana 2500 cargo van",
                "model_year_min": 2017,
                "model_year_max": 2018,
                "mileage_min": 51689,
                "mileage_max": 163753,
                "primary_geography": "Florida",
                "source_platform": "JJ Kane",
                "listing_count": 8,
                "listing_ids": ["1604992", "1615297"],
            }
        ],
    }


def write_manifest(tmp_path: Path, data) -> Path:
    (tmp_path / "run_manifest.json").write_text(
        data if isinstance(data, str) else json.dumps(data), encoding="utf-8"
    )
    return tmp_path


def test_load_manifest_ok(tmp_path):
    manifest = load_manifest(write_manifest(tmp_path, minimal_manifest()))
    assert manifest.run_id == "valuation_research_run_2026-07-12"
    assert manifest.cohorts[0].cohort_id == "wpb-express-savana-2500-2017-2018"
    assert manifest.source_platform_context is None  # optional, falls back


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
        lambda m: m["cohorts"][0].pop("cohort_id"),
        lambda m: m["cohorts"][0].pop("vehicle_family"),
        lambda m: m["cohorts"][0].pop("source_platform"),
        lambda m: m["cohorts"][0].update(listing_ids=[]),  # empty -> rejected
        lambda m: m["cohorts"][0].update(unexpected_field=1),
    ],
)
def test_load_manifest_rejects_malformed(tmp_path, mutate):
    data = minimal_manifest()
    mutate(data)
    with pytest.raises(ManifestError, match="failed validation"):
        load_manifest(write_manifest(tmp_path, data))


def test_ensure_cohort_skeleton(tmp_path):
    cohort = Cohort.model_validate(minimal_manifest()["cohorts"][0])
    folder = ensure_cohort_skeleton(tmp_path, cohort)
    assert folder == tmp_path / "cohorts" / "wpb-express-savana-2500-2017-2018"
    snapshot = json.loads((folder / "cohort_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["cohort_id"] == "wpb-express-savana-2500-2017-2018"
    # idempotent: second call must not clobber
    (folder / "cohort_snapshot.json").write_text('{"cohort_id": "edited"}', encoding="utf-8")
    ensure_cohort_skeleton(tmp_path, cohort)
    assert json.loads((folder / "cohort_snapshot.json").read_text(encoding="utf-8"))["cohort_id"] == "edited"


def test_cohort_summary_line_renders_all_supplied_fields():
    cohort = Cohort(
        cohort_id="wpb-express-savana-2500-2017-2018",
        vehicle_family="Chevrolet Express / GMC Savana 2500 cargo van",
        series_or_weight_class="2500 full-size cargo van",
        body_configuration="cargo van, no side windows",
        model_year_min=2017,
        model_year_max=2018,
        mileage_min=51689,
        mileage_max=163753,
        use_context="commercial/fleet cargo van",
        primary_geography="Florida",
        secondary_geography="Southeast US",
        source_platform="JJ Kane",
        listing_count=8,
        listing_ids=["1604992", "1615297", "1608490", "1601998", "1614587", "1614586", "1615299", "1608489"],
    )
    summary = cohort.cohort_summary_line()
    assert "Chevrolet Express / GMC Savana 2500 cargo van" in summary
    assert "2017-2018" in summary
    assert "51,689-163,753 miles" in summary
    assert "Florida / Southeast US" in summary
    assert "JJ Kane" in summary
    assert "8 listings" in summary


def test_cohort_summary_line_falls_back_when_optional_fields_missing():
    cohort = Cohort(
        cohort_id="c1",
        vehicle_family="Ford Transit 250",
        source_platform="PublicSurplus",
        listing_ids=["1"],
    )
    summary = cohort.cohort_summary_line()
    assert "model years unspecified" in summary
    assert "mileage range unspecified" in summary
    assert "geography unspecified" in summary


def test_run_manifest_golden_round_trip():
    data = minimal_manifest()
    model = RunManifest.model_validate(data)
    assert json.loads(model.model_dump_json())["run_id"] == data["run_id"]
