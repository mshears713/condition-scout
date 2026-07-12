"""Contracts: the v0.2 Tavily structured output_schema, the returned
sources[], and the cohort_research.json artifact envelope.

`ResearchContent` is a pydantic mirror of the verbatim JSON Schema on the
Valuation Research Scout v0.2 AI-OS record — field names, types, enums,
per-field descriptions, and required lists match that page exactly. Field
descriptions are part of the real contract, not decoration: they're sent to
Tavily as `output_schema` and guide what the research model fills into each
field, so `ResearchContent.model_json_schema()` is what actually gets sent
as the request payload's output_schema — contract and request can never
drift apart.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from valuation_research_scout import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION", "tavily_output_schema"]  # re-exported so callers need only import schema


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class EvidenceType(str, Enum):
    asking = "asking"
    sold = "sold"
    auction_clearing = "auction_clearing"
    wholesale = "wholesale"
    live_auction_context = "live_auction_context"
    other = "other"


class ConditionContext(str, Enum):
    clean = "clean"
    typical_used_fleet = "typical_used_fleet"
    rough = "rough"
    major_stated_issues = "major_stated_issues"
    unknown = "unknown"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourcePlatformAnalysis(_Contract):
    """Analysis of same-platform / same-disposal-ecosystem comparable evidence."""

    platform: str = Field(
        description="The source platform or disposal ecosystem associated with the subject batch."
    )
    same_platform_evidence_found: bool = Field(
        description="Whether useful comparable evidence was found from the same source platform."
    )
    evidence_summary: str = Field(
        description="Summary of same-platform comparable evidence found, including completed results, active listings, or evidence limitations."
    )
    observed_value_pattern: str = Field(
        description="Any supported pricing or clearing-value pattern observed on the source platform."
    )
    influence_on_auction_range: str = Field(
        description="How strongly same-platform evidence influenced the fleet or auction market conclusion."
    )
    confidence: Confidence = Field(description="Confidence in the source-platform analysis.")


class MarketRange(_Contract):
    """Shared shape of commercial_market and fleet_auction_market."""

    value_range_low: float = Field(description="Estimated lower bound of the value range in USD.")
    value_range_high: float = Field(description="Estimated upper bound of the value range in USD.")
    rationale: str = Field(description="Evidence and reasoning behind the estimated range.")
    confidence: Confidence = Field(description="Confidence in the market conclusion.")


class MileagePattern(_Contract):
    """A mileage-band value or market pattern materially supported by the research."""

    mileage_range: str = Field(
        description="Approximate mileage band associated with the observed pattern."
    )
    observed_pattern: str = Field(description="Value or market pattern observed for this mileage band.")
    rationale: str = Field(description="Why the research supports this mileage pattern.")


class ModelYearPattern(_Contract):
    """A model-year value or market pattern materially supported by the research."""

    model_year_or_range: str = Field(
        description="Model year or model-year range associated with the observed pattern."
    )
    observed_pattern: str = Field(
        description="Value or market pattern observed for the model year or range."
    )
    rationale: str = Field(description="Why the research supports this model-year pattern.")


class Modifier(_Contract):
    """A configuration, regional, source-platform, or market modifier materially
    supported by the research."""

    modifier: str = Field(description="Factor associated with a meaningful market or value difference.")
    observed_effect: str = Field(description="Observed direction or nature of the effect.")
    rationale: str = Field(description="Research basis for treating this as a meaningful modifier.")


class RepresentativeComparable(_Contract):
    """One comparable vehicle that materially contributed to the market conclusions."""

    vehicle: str = Field(description="Vehicle make, model, series, and configuration as available.")
    year: int | None = Field(description="Model year when available.")
    mileage: int | None = Field(description="Vehicle mileage when available.")
    price: float = Field(description="Observed price in USD.")
    evidence_type: EvidenceType = Field(
        description="Type of price evidence represented by this comparable."
    )
    source_platform: str = Field(
        description="Dealer, marketplace, auction, or fleet-disposal platform associated with the comparable."
    )
    location: str | None = Field(description="Vehicle location when available.")
    source_url: str | None = Field(
        description="Source URL when available. Preserve Tavily's top-level returned sources separately as well; no elaborate URL-reconciliation layer is required in v0.2."
    )
    condition_context: ConditionContext = Field(
        description="Broad comparable-condition context based only on listing descriptions, stated disclosures, and clearly available listing evidence."
    )
    condition_notes: str = Field(
        description="Brief condition context. Do not perform deep photo analysis or invent defects."
    )
    relevance: Confidence = Field(description="How directly comparable the vehicle is to the supplied cohort.")
    relevance_notes: str = Field(description="Why this vehicle is useful as a comparable.")
    limitations: str = Field(
        description="Important limitations such as asking price rather than transaction price or broader geography."
    )


class ResearchContent(_Contract):
    """The Tavily `output_schema` contract — verbatim v0.2 field set."""

    cohort_summary: str = Field(
        description="A concise description of the vehicle cohort researched and the effective scope of the research."
    )
    source_platform_analysis: SourcePlatformAnalysis
    commercial_market: MarketRange
    fleet_auction_market: MarketRange
    mileage_patterns: list[MileagePattern] = Field(
        description="Mileage-related value patterns materially supported by the research. Return an empty array when no meaningful pattern is supported."
    )
    model_year_patterns: list[ModelYearPattern] = Field(
        description="Model-year value patterns materially supported by the research. Return an empty array when no meaningful pattern is supported."
    )
    important_modifiers: list[Modifier] = Field(
        description="Other configuration, regional, source-platform, or market modifiers materially supported by the research. Do not invent modifiers to populate this field."
    )
    representative_comparables: list[RepresentativeComparable] = Field(
        description="A useful representative set of comparable vehicles that materially contributed to the market conclusions."
    )
    major_caveats: list[str] = Field(
        description="Major limitations, evidence gaps, or cautions that materially affect interpretation of the research."
    )
    overall_confidence: Confidence = Field(
        description="Overall confidence in the market picture produced by the research."
    )
    research_summary: str = Field(
        description="Concise synthesis of the overall market picture and most important reasoning for downstream Claude CoWork."
    )


# Keys Tavily's live output_schema validator rejects wherever they appear,
# not just at the top level — confirmed against the real API on 2026-07-12
# ("Output schema contains unexpected keys: additionalProperties, title" on
# a fully nested schema). Pydantic emits both on every object schema because
# _Contract sets `extra="forbid"`.
_DISALLOWED_KEYS = {"additionalProperties", "title"}


def _inline_refs(node, defs: dict):
    """Recursively resolve pydantic's `$ref`/`$defs` indirection into a
    fully self-contained schema, and drop keys Tavily's output_schema
    validator rejects. Not documented in Tavily's published API reference."""
    if isinstance(node, dict):
        if "$ref" in node:
            ref_name = node["$ref"].rsplit("/", 1)[-1]
            resolved = _inline_refs(defs[ref_name], defs)
            merged = dict(resolved)
            merged.update({k: v for k, v in node.items() if k != "$ref"})
            return {k: v for k, v in merged.items() if k not in _DISALLOWED_KEYS}
        if "allOf" in node and len(node["allOf"]) == 1 and "$ref" in node["allOf"][0]:
            resolved = _inline_refs(node["allOf"][0], defs)
            merged = dict(resolved)
            merged.update({k: v for k, v in node.items() if k != "allOf"})
            return {k: v for k, v in merged.items() if k not in _DISALLOWED_KEYS}
        if "anyOf" in node:
            # CONTRACT CONFLICT (confirmed live 2026-07-12, documented per the
            # implementation instructions rather than silently redesigned):
            # the approved v0.2 output_schema on the Valuation Research Scout
            # AI-OS record types nullable fields (year, mileage, location,
            # source_url) as `"type": ["integer", "null"]` — standard JSON
            # Schema nullable-type-list form. Tavily's live API rejects BOTH
            # pydantic's `anyOf` rendering ("Property 'year' missing required
            # 'type' field") AND the approved list-type form itself
            # ("'type' must be a string, got list. Union types ... are not
            # supported — use a single type."). Tavily's structured-output
            # feature currently has no way to express "this field is
            # optional/nullable" at all. We collapse to the single non-null
            # type for the WIRE request only — Tavily's own model will always
            # return some value of that type, never JSON null, so the
            # "when available" language in each field's description is what
            # actually signals optionality to the research model now. The
            # ResearchContent pydantic contract (the validation source of
            # truth) is untouched and still declares these fields `T | None`.
            options = [_inline_refs(opt, defs) for opt in node["anyOf"]]
            if all(set(opt.keys()) == {"type"} for opt in options):
                types = [opt["type"] for opt in options if opt["type"] != "null"]
                if len(types) != 1:
                    raise ValueError(
                        f"cannot collapse anyOf to a single Tavily-compatible type: {node}"
                    )
                merged = {k: v for k, v in node.items() if k != "anyOf"}
                merged["type"] = types[0]
                return {k: v for k, v in merged.items() if k not in _DISALLOWED_KEYS}
            # complex anyOf (e.g. a nullable nested object) - not needed by
            # the v0.2 contract; fall through unresolved rather than guess.
        return {
            k: _inline_refs(v, defs)
            for k, v in node.items()
            if k not in _DISALLOWED_KEYS
        }
    if isinstance(node, list):
        return [_inline_refs(v, defs) for v in node]
    return node


def tavily_output_schema() -> dict:
    """The `output_schema` request payload actually accepted by Tavily's
    live API: only `properties` and `required` at the top level, no
    `$ref`/`$defs`, every property (including nested objects) carrying a
    `description`. `ResearchContent.model_json_schema()` remains the
    canonical contract for validation; this is a request-shape adapter
    over it, not a second source of truth."""
    full = ResearchContent.model_json_schema()
    defs = full.get("$defs", {})
    return {
        "properties": _inline_refs(full["properties"], defs),
        "required": full["required"],
    }


class TavilySource(_Contract):
    """One entry of Tavily's top-level returned `sources[]`."""

    title: str
    url: str
    favicon: str | None = None


class CohortResearch(_Contract):
    """cohort_research.json — assembled in code from the cohort manifest
    entry and the completed Tavily response. This is the CoWork-facing
    contract; tavily_raw_response.json alongside it preserves the raw API
    response for commissioning/debugging."""

    cohort_id: str
    source: str  # "Tavily Research"
    analyzed_at: str
    model: str  # mini | pro | auto — whichever was actually used
    schema_version: str = SCHEMA_VERSION
    prompt_version: str
    request_id: str
    content: ResearchContent
    sources: list[TavilySource]


class CohortFailure(_Contract):
    cohort_id: str
    stage: str  # validate | request | poll | write
    reason: str


class RunSummary(_Contract):
    """run_summary.json — run-level outcome CoWork reads first."""

    run_id: str
    started_at: str
    finished_at: str
    schema_version: str = SCHEMA_VERSION
    cohorts_total: int
    processed: list[str]
    failed: list[CohortFailure]
    api_calls_used: int
