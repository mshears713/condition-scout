"""Artifact assembly, golden-file regression, and the no-buy/bid/pass
language prohibition rule (mirrors condition-scout's artifact tests)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.fake_tavily import sample_research_content_dict
from valuation_research_scout.artifacts import (
    build_cohort_research,
    render_markdown,
    write_cohort_research,
    write_run_summary,
)
from valuation_research_scout.manifest import Cohort
from valuation_research_scout.schema import CohortResearch, RunSummary
from valuation_research_scout.tavily import TavilyResult

GOLDEN = Path(__file__).parent / "golden"


def golden_research() -> CohortResearch:
    return CohortResearch.model_validate(
        json.loads((GOLDEN / "cohort_research.json").read_text(encoding="utf-8"))
    )


def sample_cohort() -> Cohort:
    return Cohort(
        cohort_id="wpb-express-savana-2500-2017-2018",
        vehicle_family="Chevrolet Express / GMC Savana 2500 cargo van",
        model_year_min=2017,
        model_year_max=2018,
        mileage_min=51689,
        mileage_max=163753,
        primary_geography="Florida",
        source_platform="JJ Kane",
        listing_count=8,
        listing_ids=["1604992", "1615297"],
    )


def sample_result() -> TavilyResult:
    return TavilyResult(
        request_id="req-golden-001",
        content=sample_research_content_dict(),
        sources=[{"title": "JJ Kane Archived Catalog 297380", "url": "https://proxibid.com/example-lot"}],
        raw={"request_id": "req-golden-001", "status": "completed"},
    )


# --- golden regression --------------------------------------------------------

def test_markdown_golden_regression():
    expected = (GOLDEN / "cohort_research.md").read_text(encoding="utf-8")
    assert render_markdown(golden_research()) == expected


# --- assembly -------------------------------------------------------------------

def test_build_cohort_research_stamps_and_validates():
    research = build_cohort_research(
        sample_cohort(), sample_result(), model="mini", prompt_version="0.2",
        analyzed_at="2026-07-12T18:00:00Z",
    )
    assert research.cohort_id == "wpb-express-savana-2500-2017-2018"
    assert research.model == "mini"
    assert research.request_id == "req-golden-001"
    assert research.content.overall_confidence.value == "medium"
    assert research.sources[0].title == "JJ Kane Archived Catalog 297380"


def test_write_cohort_research_round_trips(tmp_path):
    research = build_cohort_research(
        sample_cohort(), sample_result(), model="mini", prompt_version="0.2",
        analyzed_at="2026-07-12T18:00:00Z",
    )
    write_cohort_research(tmp_path, research, sample_result().raw)
    reloaded = CohortResearch.model_validate(
        json.loads((tmp_path / "cohort_research.json").read_text(encoding="utf-8"))
    )
    assert reloaded == research
    md = (tmp_path / "cohort_research.md").read_text(encoding="utf-8")
    assert md.startswith("# Cohort Research — wpb-express-savana-2500-2017-2018")
    raw = json.loads((tmp_path / "tavily_raw_response.json").read_text(encoding="utf-8"))
    assert raw["request_id"] == "req-golden-001"


def test_write_run_summary(tmp_path):
    summary = RunSummary(
        run_id="r1", started_at="2026-07-12T00:00:00Z", finished_at="2026-07-12T00:05:00Z",
        cohorts_total=1, processed=["c1"], failed=[], api_calls_used=1,
    )
    path = write_run_summary(tmp_path, summary)
    assert json.loads(path.read_text(encoding="utf-8"))["run_id"] == "r1"


# --- prohibition rule ------------------------------------------------------------

def test_artifacts_never_recommend_buy_bid_or_max_bid():
    # Unlike Condition Scout, this tool cannot strip words like "bid" from
    # Tavily's own market-research prose (the approved prompt itself uses
    # "current live bid" descriptively). This test guards against actual
    # recommendation language, not the presence of auction vocabulary.
    md = render_markdown(golden_research())
    raw_json = (GOLDEN / "cohort_research.json").read_text(encoding="utf-8")
    for text in (md, raw_json):
        for phrase in ("buy this", "you should bid", "maximum bid", "pass on this", "recommend bidding"):
            assert phrase.lower() not in text.lower(), phrase
