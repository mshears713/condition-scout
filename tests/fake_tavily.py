"""FakeTavily: a scripted Tavily client for behavior-matrix tests.

`run_script` entries are either a status dict (returned from a simulated
poll) or an exception instance (raised). Every create_task/get_status call
is recorded so tests can assert on request assembly."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecordedCreate:
    input: str
    model: str
    output_schema: dict


@dataclass
class FakeTavily:
    """Scripts the sequence of GET /research/{id} responses returned after
    one create_task call. `poll_script` entries are status dicts (e.g.
    {"status": "pending"}, then {"status": "completed", "content": ...,
    "sources": [...]}) or exception instances (raised)."""

    poll_script: list = field(default_factory=list)
    request_id: str = "fake-request-id-001"
    creates: list = field(default_factory=list)
    polls: int = 0

    def create_task(self, *, input: str, model: str, output_schema: dict) -> str:
        self.creates.append(RecordedCreate(input, model, output_schema))
        return self.request_id

    def get_status(self, request_id: str) -> dict:
        self.polls += 1
        if not self.poll_script:
            raise AssertionError("FakeTavily poll_script exhausted")
        outcome = self.poll_script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def run(self, *, input, model, output_schema, poll_interval_s=0.0,
            timeout_s=60.0, sleep=lambda s: None, clock=None):
        from valuation_research_scout.tavily import (
            TavilyResult,
            TavilyTaskFailed,
            TavilyTimeout,
        )

        request_id = self.create_task(input=input, model=model, output_schema=output_schema)
        attempts = 0
        while True:
            data = self.get_status(request_id)
            status = data.get("status")
            if status == "completed":
                return TavilyResult(
                    request_id=request_id,
                    content=data.get("content"),
                    sources=data.get("sources", []),
                    raw=data,
                )
            if status == "failed":
                raise TavilyTaskFailed(f"Tavily research task {request_id} failed: {data}")
            attempts += 1
            if attempts > 1000:
                raise TavilyTimeout(f"Tavily research task {request_id} timed out")
            sleep(poll_interval_s)


def completed_status(content: dict, sources: list[dict] | None = None) -> dict:
    return {
        "request_id": "fake-request-id-001",
        "created_at": "2026-07-12T12:00:00Z",
        "status": "completed",
        "content": content,
        "sources": sources or [],
        "response_time": 12.5,
    }


def failed_status() -> dict:
    return {"request_id": "fake-request-id-001", "status": "failed", "response_time": 3.0}


def sample_research_content_dict() -> dict:
    return {
        "cohort_summary": "2017-2018 Chevrolet Express/GMC Savana 2500 cargo vans, FL/Southeast, 51k-164k miles.",
        "source_platform_analysis": {
            "platform": "JJ Kane",
            "same_platform_evidence_found": True,
            "evidence_summary": "Archived Proxibid catalogs show hammer prices for comparable fleet vans.",
            "observed_value_pattern": "Running fleet vans with cosmetic wear cleared $700-2,600 in recent regional sales.",
            "influence_on_auction_range": "Moderate — small sample size but directly on-platform.",
            "confidence": "medium",
        },
        "commercial_market": {
            "value_range_low": 7000,
            "value_range_high": 11000,
            "rationale": "Asking prices on CommercialTruckTrader for comparable Express/Savana 2500 vans in this mileage band.",
            "confidence": "medium",
        },
        "fleet_auction_market": {
            "value_range_low": 2500,
            "value_range_high": 5500,
            "rationale": "JJ Kane archived catalog hammer prices for comparable fleet vehicles.",
            "confidence": "medium",
        },
        "mileage_patterns": [
            {
                "mileage_range": "50,000-100,000",
                "observed_pattern": "Higher end of the auction range.",
                "rationale": "Lower-mileage comparables cleared closer to the top of the range.",
            }
        ],
        "model_year_patterns": [],
        "important_modifiers": [],
        "representative_comparables": [
            {
                "vehicle": "2017 Chevrolet Express 2500 Cargo Van",
                "year": 2017,
                "mileage": 98000,
                "price": 3200,
                "evidence_type": "auction_clearing",
                "source_platform": "JJ Kane",
                "location": "Louisiana",
                "source_url": "https://proxibid.com/example-lot",
                "condition_context": "typical_used_fleet",
                "condition_notes": "Runs and moves, interior wear consistent with fleet use.",
                "relevance": "high",
                "relevance_notes": "Same source platform, comparable year and mileage.",
                "limitations": "Different region (LA vs FL).",
            }
        ],
        "major_caveats": ["Small same-platform sample size."],
        "overall_confidence": "medium",
        "research_summary": "Fleet-auction clearing values run well below commercial asking prices for this cohort.",
    }
