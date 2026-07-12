"""Golden round-trip and contract-shape tests for the v0.2 output_schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.fake_tavily import sample_research_content_dict
from valuation_research_scout.schema import (
    CohortResearch,
    ResearchContent,
    RunSummary,
    tavily_output_schema,
)

GOLDEN = Path(__file__).parent / "golden"


def load_golden(name: str) -> dict:
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


def test_cohort_research_golden_round_trip():
    data = load_golden("cohort_research.json")
    model = CohortResearch.model_validate(data)
    assert json.loads(model.model_dump_json()) == data


def test_research_content_matches_sample_shape():
    ResearchContent.model_validate(sample_research_content_dict())


def test_research_content_rejects_extra_field():
    data = sample_research_content_dict()
    data["adjustment_categories"] = []  # never allowed anywhere in this system
    with pytest.raises(ValidationError):
        ResearchContent.model_validate(data)


def test_research_content_rejects_missing_required_field():
    data = sample_research_content_dict()
    del data["overall_confidence"]
    with pytest.raises(ValidationError):
        ResearchContent.model_validate(data)


def test_representative_comparable_requires_nullable_fields_present():
    data = sample_research_content_dict()
    del data["representative_comparables"][0]["location"]  # key must be present, even if null
    with pytest.raises(ValidationError):
        ResearchContent.model_validate(data)


def test_output_schema_has_properties_and_required():
    schema = ResearchContent.model_json_schema()
    assert "properties" in schema
    assert set(schema["required"]) == {
        "cohort_summary", "source_platform_analysis", "commercial_market",
        "fleet_auction_market", "mileage_patterns", "model_year_patterns",
        "important_modifiers", "representative_comparables", "major_caveats",
        "overall_confidence", "research_summary",
    }


def _assert_no_refs_and_every_property_described(node):
    """Recursively assert the schema matches Tavily's live constraints:
    no $ref/$defs/title/additionalProperties anywhere, and every property
    carries a description."""
    if isinstance(node, dict):
        assert "$ref" not in node
        assert "$defs" not in node
        assert "title" not in node
        assert "additionalProperties" not in node
        if "properties" in node:
            for name, prop in node["properties"].items():
                assert "description" in prop, f"property {name!r} missing description"
        for value in node.values():
            _assert_no_refs_and_every_property_described(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_refs_and_every_property_described(item)


def test_tavily_output_schema_matches_live_api_constraints():
    # Confirmed against the real Tavily API on 2026-07-12: output_schema may
    # only contain "properties"/"required" at the top level (no "type",
    # "$defs", "title"), $ref/$defs are rejected outright, and every
    # property - including nested objects - must carry "description".
    schema = tavily_output_schema()
    assert set(schema.keys()) == {"properties", "required"}
    assert set(schema["required"]) == set(ResearchContent.model_json_schema()["required"])
    _assert_no_refs_and_every_property_described(schema)
    # nested object types (resolved from $ref) kept their own description
    assert "description" in schema["properties"]["source_platform_analysis"]
    assert "description" in schema["properties"]["commercial_market"]
    # array item schemas (also resolved from $ref) are fully inlined too
    comparable_items = schema["properties"]["representative_comparables"]["items"]
    assert "$ref" not in comparable_items
    assert "description" in comparable_items["properties"]["vehicle"]
    # CONTRACT CONFLICT: the approved schema types nullable fields as
    # "type": ["integer", "null"], but Tavily's live API rejects list-type
    # "type" outright ("Union types ... are not supported - use a single
    # type", confirmed 2026-07-12). Collapsed to a single type for the wire
    # request; see the long comment in schema._inline_refs for the full story.
    assert comparable_items["properties"]["year"]["type"] == "integer"
    assert "anyOf" not in comparable_items["properties"]["year"]


def test_run_summary_round_trip():
    summary = RunSummary(
        run_id="r1", started_at="2026-07-12T00:00:00Z", finished_at="2026-07-12T00:05:00Z",
        cohorts_total=1, processed=["c1"], failed=[], api_calls_used=1,
    )
    assert json.loads(summary.model_dump_json())["schema_version"] == "0.2"
