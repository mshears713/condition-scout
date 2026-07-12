"""Artifact writers: cohort_research.json / .md, tavily_raw_response.json,
and run_summary.json.

cohort_research.json is the CoWork contract; tavily_raw_response.json
alongside it preserves the full raw Tavily response for commissioning and
debugging (Tool Behavior step 6). The Markdown is the human-readable twin.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from valuation_research_scout.manifest import Cohort
from valuation_research_scout.schema import CohortResearch, ResearchContent, RunSummary
from valuation_research_scout.tavily import TavilyResult


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_cohort_research(
    cohort: Cohort,
    result: TavilyResult,
    *,
    model: str,
    prompt_version: str,
    analyzed_at: str | None = None,
) -> CohortResearch:
    content = result.content
    if isinstance(content, str):
        content = json.loads(content)
    return CohortResearch(
        cohort_id=cohort.cohort_id,
        source="Tavily Research",
        analyzed_at=analyzed_at or utc_now_iso(),
        model=model,
        prompt_version=prompt_version,
        request_id=result.request_id,
        content=ResearchContent.model_validate(content),
        sources=result.sources,
    )


def _range(low: float, high: float) -> str:
    return f"${low:,.0f}-${high:,.0f}"


def render_markdown(research: CohortResearch) -> str:
    r = research
    c = r.content
    lines: list[str] = []
    lines.append(f"# Cohort Research — {r.cohort_id}")
    lines.append("")
    lines.append(c.cohort_summary)
    lines.append("")
    lines.append("## Source platform analysis")
    lines.append("")
    spa = c.source_platform_analysis
    lines.append(f"- Platform: {spa.platform}")
    lines.append(f"- Same-platform evidence found: {'yes' if spa.same_platform_evidence_found else 'no'}")
    lines.append(f"- Evidence summary: {spa.evidence_summary}")
    lines.append(f"- Observed value pattern: {spa.observed_value_pattern}")
    lines.append(f"- Influence on auction range: {spa.influence_on_auction_range}")
    lines.append(f"- Confidence: {spa.confidence.value}")
    lines.append("")
    lines.append("## Commercial market")
    lines.append("")
    lines.append(f"{_range(c.commercial_market.value_range_low, c.commercial_market.value_range_high)} "
                 f"(confidence: {c.commercial_market.confidence.value})")
    lines.append("")
    lines.append(c.commercial_market.rationale)
    lines.append("")
    lines.append("## Fleet / auction market")
    lines.append("")
    lines.append(f"{_range(c.fleet_auction_market.value_range_low, c.fleet_auction_market.value_range_high)} "
                 f"(confidence: {c.fleet_auction_market.confidence.value})")
    lines.append("")
    lines.append(c.fleet_auction_market.rationale)
    lines.append("")
    lines.append("## Mileage patterns")
    lines.append("")
    if c.mileage_patterns:
        for p in c.mileage_patterns:
            lines.append(f"- **{p.mileage_range}**: {p.observed_pattern} — {p.rationale}")
    else:
        lines.append("- None materially supported.")
    lines.append("")
    lines.append("## Model-year patterns")
    lines.append("")
    if c.model_year_patterns:
        for p in c.model_year_patterns:
            lines.append(f"- **{p.model_year_or_range}**: {p.observed_pattern} — {p.rationale}")
    else:
        lines.append("- None materially supported.")
    lines.append("")
    lines.append("## Other modifiers")
    lines.append("")
    if c.important_modifiers:
        for m in c.important_modifiers:
            lines.append(f"- **{m.modifier}**: {m.observed_effect} — {m.rationale}")
    else:
        lines.append("- None materially supported.")
    lines.append("")
    lines.append("## Representative comparables")
    lines.append("")
    if c.representative_comparables:
        for comp in c.representative_comparables:
            year = f"year {comp.year}" if comp.year is not None else "year unknown"
            mileage = f"{comp.mileage:,} mi" if comp.mileage is not None else "mileage unknown"
            loc = f", {comp.location}" if comp.location else ""
            url = f" — {comp.source_url}" if comp.source_url else ""
            lines.append(
                f"- **{comp.vehicle}** ({year}, {mileage}) — ${comp.price:,.0f} "
                f"({comp.evidence_type.value}) via {comp.source_platform}{loc} "
                f"[condition: {comp.condition_context.value}, relevance: {comp.relevance.value}]{url}"
            )
            lines.append(f"  - {comp.condition_notes}")
            lines.append(f"  - Relevance: {comp.relevance_notes}")
            lines.append(f"  - Limitations: {comp.limitations}")
    else:
        lines.append("- None returned.")
    lines.append("")
    lines.append("## Major caveats")
    lines.append("")
    if c.major_caveats:
        for caveat in c.major_caveats:
            lines.append(f"- {caveat}")
    else:
        lines.append("- None recorded.")
    lines.append("")
    lines.append(f"**Overall confidence:** {c.overall_confidence.value}")
    lines.append("")
    lines.append("## Research summary")
    lines.append("")
    lines.append(c.research_summary)
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    if r.sources:
        for s in r.sources:
            lines.append(f"- [{s.title}]({s.url})")
    else:
        lines.append("- None returned.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Analyzed {r.analyzed_at} · model {r.model} · schema v{r.schema_version} "
        f"· prompt v{r.prompt_version} · request {r.request_id}. Cohort-level market "
        "research only — never a subject-van valuation, never buy/bid/pass guidance.*"
    )
    lines.append("")
    return "\n".join(lines)


def write_cohort_research(
    cohort_folder: Path, research: CohortResearch, raw_response: dict
) -> None:
    (cohort_folder / "cohort_research.json").write_text(
        research.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (cohort_folder / "cohort_research.md").write_text(
        render_markdown(research), encoding="utf-8"
    )
    write_raw_response(cohort_folder, raw_response)


def write_raw_response(cohort_folder: Path, raw_response: dict) -> None:
    """Preserve Tavily's raw response for commissioning/debugging — written
    as soon as Tavily itself succeeds, independent of whether the response
    later passes ResearchContent contract validation. A validation failure
    is exactly when this evidence is most needed."""
    (cohort_folder / "tavily_raw_response.json").write_text(
        json.dumps(raw_response, indent=2) + "\n", encoding="utf-8"
    )


def write_run_summary(run_dir: Path, summary: RunSummary) -> Path:
    path = run_dir / "run_summary.json"
    path.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
