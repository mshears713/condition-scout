"""Live-smoke test (CI live-smoke job only): `pytest -m live`.

One real Tavily Research call against the actual production output_schema
(tavily_output_schema()) — proves structured-output adherence end to end,
the same role test_live.py's Gemini test plays for Condition Scout.

Skip rule: skips cleanly when TAVILY_API_KEY is absent (the affected item
reverts to Deferred — a finding, not a failure).

Secret hygiene: nothing here prints response bodies or the key.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not os.environ.get("TAVILY_API_KEY"),
    reason="TAVILY_API_KEY absent — live Tavily smoke reverts to Deferred",
)
def test_live_tavily_structured_output_single_cohort(tmp_path):
    """One real mini-model Tavily research call against the full
    ResearchContent output_schema, validated by build_cohort_research —
    pydantic validation succeeding IS the structured-output proof."""
    import json

    from valuation_research_scout.orchestrator import RunConfig, run_batch
    from valuation_research_scout.tavily import RealTavilyClient

    (tmp_path / "run_manifest.json").write_text(
        json.dumps({
            "run_id": "live-smoke",
            "cohorts": [{
                "cohort_id": "live-smoke-cohort",
                "vehicle_family": "Chevrolet Express 2500 cargo van",
                "model_year_min": 2017,
                "model_year_max": 2018,
                "source_platform": "JJ Kane",
                "listing_ids": ["live-smoke"],
            }],
        }),
        encoding="utf-8",
    )
    summary = run_batch(
        tmp_path,
        tavily=RealTavilyClient(),
        config=RunConfig(model="mini", timeout_s=300.0),
    )
    assert summary.processed == ["live-smoke-cohort"]
    assert summary.failed == []
    research_path = tmp_path / "cohorts" / "live-smoke-cohort" / "cohort_research.json"
    assert research_path.is_file()  # pydantic validation inside build_cohort_research IS the proof
