"""M4 artifact tests: assembly, golden-file regression, schema validation
on write, and the no-dollar/no-decision language rule."""

from __future__ import annotations

import json
import re
from pathlib import Path

from condition_scout.artifacts import (
    build_condition_analysis,
    render_markdown,
    write_condition_analysis,
    write_run_summary,
)
from condition_scout.manifest import ManifestListing
from condition_scout.schema import (
    ConditionAnalysis,
    PhotoRecord,
    RunSummary,
    SynthesisResult,
    Zone,
)
from tests.fake_gemini import photo_record_dict, synthesis_result_dict

GOLDEN = Path(__file__).parent / "golden"


def golden_analysis() -> ConditionAnalysis:
    return ConditionAnalysis.model_validate(
        json.loads((GOLDEN / "condition_analysis.json").read_text(encoding="utf-8"))
    )


def listing() -> ManifestListing:
    return ManifestListing(
        listing_id="1619602",
        source="JJ Kane",
        listing_url="https://www.jjkane.com/item/1619602",
        year=2016,
        platform="Ford Transit 250",
        mileage=128000,
    )


def sample_records() -> list[PhotoRecord]:
    views = ["exterior_front", "exterior_sides", "cab_interior — driver seat area"]
    return [
        PhotoRecord.model_validate(
            {**photo_record_dict(view=v if " " not in v else "cab_interior"),
             "view": v, "photo": f"photo_{i:03d}.jpg"}
        )
        for i, v in enumerate(views, start=1)
    ]


def sample_synthesis() -> SynthesisResult:
    return SynthesisResult.model_validate(synthesis_result_dict())


# --- golden regression --------------------------------------------------------

def test_markdown_golden_regression():
    expected = (GOLDEN / "condition_analysis.md").read_text(encoding="utf-8")
    assert render_markdown(golden_analysis()) == expected


# --- assembly -------------------------------------------------------------------

def test_build_condition_analysis_stamps_and_computes():
    analysis = build_condition_analysis(
        listing(),
        sample_records(),
        sample_synthesis(),
        model="gemini-2.5-flash-lite",
        prompt_version="0.2",
        analyzed_at="2026-07-10T15:00:00Z",
    )
    assert analysis.schema_version == "0.2"
    assert analysis.prompt_version == "0.2"
    assert analysis.listing_id == "1619602"
    # coverage computed from the records' view fields, not model-asserted
    assert analysis.photo_coverage.photos_analyzed == 3
    assert Zone.cab_interior in analysis.photo_coverage.zones_covered
    assert analysis.photo_coverage.coverage_quality.value == "poor"
    # synthesis fields carried through
    assert analysis.findings[0].image_refs == ["photo_001.jpg"]


def test_write_condition_analysis_round_trips(tmp_path):
    analysis = build_condition_analysis(
        listing(), sample_records(), sample_synthesis(),
        model="gemini-2.5-flash-lite", prompt_version="0.2",
        analyzed_at="2026-07-10T15:00:00Z",
    )
    write_condition_analysis(tmp_path, analysis)
    reloaded = ConditionAnalysis.model_validate(
        json.loads((tmp_path / "condition_analysis.json").read_text(encoding="utf-8"))
    )
    assert reloaded == analysis
    md = (tmp_path / "condition_analysis.md").read_text(encoding="utf-8")
    assert md.startswith("# Condition Analysis — JJ Kane listing 1619602")
    assert "prompt v0.2" in md


def test_write_run_summary(tmp_path):
    summary = RunSummary.model_validate(
        json.loads((GOLDEN / "run_summary.json").read_text(encoding="utf-8"))
    )
    path = write_run_summary(tmp_path, summary)
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(
        (GOLDEN / "run_summary.json").read_text(encoding="utf-8")
    )


# --- prohibition rule ------------------------------------------------------------

def test_artifacts_contain_no_dollar_or_decision_language():
    md = render_markdown(golden_analysis())
    raw_json = (GOLDEN / "condition_analysis.json").read_text(encoding="utf-8")
    for text in (md, raw_json):
        assert "$" not in text
        for word in ("buy", "bid", "pass on", "worth", "value estimate"):
            # \b keeps 'passed'/'bidirectional' style false-positives away
            assert not re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE), word
