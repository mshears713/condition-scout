"""Fake Tavily backend for `--fake-network` CLI acceptance-testing mode.

Deterministic, no network. A stand-in for plumbing checks — its content is
not meant to look like real research output, only to satisfy the
ResearchContent contract shape."""

from __future__ import annotations

from valuation_research_scout.tavily import TavilyResult


class FakeNetworkTavily:
    def __init__(self):
        self.calls = 0

    def run(self, *, input: str, model: str, output_schema: dict, **_kwargs) -> TavilyResult:
        self.calls += 1
        request_id = f"fake-network-request-{self.calls:03d}"
        content = {
            "cohort_summary": "Fake-network cohort summary for plumbing checks only.",
            "source_platform_analysis": {
                "platform": "Fake Platform",
                "same_platform_evidence_found": False,
                "evidence_summary": "No real evidence — fake-network mode.",
                "observed_value_pattern": "None — fake-network mode.",
                "influence_on_auction_range": "None — fake-network mode.",
                "confidence": "low",
            },
            "commercial_market": {
                "value_range_low": 1000.0,
                "value_range_high": 2000.0,
                "rationale": "Fake-network placeholder range.",
                "confidence": "low",
            },
            "fleet_auction_market": {
                "value_range_low": 500.0,
                "value_range_high": 1000.0,
                "rationale": "Fake-network placeholder range.",
                "confidence": "low",
            },
            "mileage_patterns": [],
            "model_year_patterns": [],
            "important_modifiers": [],
            "representative_comparables": [],
            "major_caveats": ["This is fake-network output — not real research."],
            "overall_confidence": "low",
            "research_summary": "Fake-network placeholder — plumbing checks only, not real research.",
        }
        return TavilyResult(
            request_id=request_id,
            content=content,
            sources=[{"title": "Fake Source", "url": "https://example.com/fake", "favicon": None}],
            raw={"request_id": request_id, "status": "completed", "content": content},
        )
