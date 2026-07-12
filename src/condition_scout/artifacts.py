"""Artifact writers: condition_analysis.json / .md and run_summary.json.

The JSON is the CoWork contract; the Markdown is the human-readable twin.
Every artifact is schema-validated (it is built from validated models) and
stamped with schema_version + prompt_version.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from condition_scout.manifest import ManifestListing
from condition_scout.schema import (
    ConditionAnalysis,
    PhotoRecord,
    RunHistoryEntry,
    RunSummary,
    SynthesisResult,
    compute_coverage,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_condition_analysis(
    listing: ManifestListing,
    records: list[PhotoRecord],
    synthesis: SynthesisResult,
    *,
    model: str,
    prompt_version: str,
    analyzed_at: str | None = None,
) -> ConditionAnalysis:
    """Assemble the artifact: per-photo audit trail + code-computed coverage
    + synthesis-pass findings."""
    return ConditionAnalysis(
        listing_id=listing.listing_id,
        source=listing.source,
        analyzed_at=analyzed_at or utc_now_iso(),
        model=model,
        prompt_version=prompt_version,
        photo_observations=records,
        photo_coverage=compute_coverage(records),
        findings=synthesis.findings,
        positives=synthesis.positives,
        dash_evidence=synthesis.dash_evidence,
        mismatch_flags=synthesis.mismatch_flags,
        overall=synthesis.overall,
    )


def _refs(image_refs: list[str]) -> str:
    return ", ".join(f"`{r}`" for r in image_refs)


def render_markdown(analysis: ConditionAnalysis) -> str:
    """Human-readable condition_analysis.md. Descriptive evidence only —
    findings always cite their image files."""
    a = analysis
    lines: list[str] = []
    lines.append(f"# Condition Analysis — {a.source} listing {a.listing_id}")
    lines.append("")
    lines.append(
        f"**Visual grade:** {a.overall.visual_grade.value} "
        f"(confidence: {a.overall.confidence.value})"
    )
    lines.append("")
    lines.append(a.overall.summary)
    lines.append("")
    lines.append("## Photo coverage")
    lines.append("")
    cov = a.photo_coverage
    lines.append(
        f"{cov.photos_analyzed} photos analyzed — coverage "
        f"{cov.coverage_quality.value}."
    )
    lines.append(f"- Zones covered: {', '.join(z.value for z in cov.zones_covered) or 'none'}")
    lines.append(f"- Zones missing: {', '.join(z.value for z in cov.zones_missing) or 'none'}")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    if a.findings:
        for f in a.findings:
            hint = f" · red-flag hint: {f.red_flag_hint}" if f.red_flag_hint else ""
            lines.append(
                f"- **{f.zone.value} — {f.severity.value}** "
                f"({f.confidence.value} confidence): {f.description} "
                f"[{_refs(f.image_refs)}]{hint}"
            )
    else:
        lines.append("- No negative findings reported.")
    lines.append("")
    lines.append("## Positives")
    lines.append("")
    if a.positives:
        for p in a.positives:
            lines.append(
                f"- {p.description} ({p.confidence.value} confidence) "
                f"[{_refs(p.image_refs)}]"
            )
    else:
        lines.append("- None recorded.")
    lines.append("")
    lines.append("## Dash evidence")
    lines.append("")
    d = a.dash_evidence
    lines.append(f"- Warning lights: {', '.join(d.warning_lights) or 'no dash photo analyzed'}")
    lines.append(f"- Odometer visible: {'yes' if d.odometer_visible else 'no'}")
    if d.odometer_reading is not None:
        lines.append(f"- Odometer reading (contradiction flagged): {d.odometer_reading}")
    if d.image_refs:
        lines.append(f"- Evidence: {_refs(d.image_refs)}")
    lines.append("")
    if a.mismatch_flags:
        lines.append("## Mismatch flags")
        lines.append("")
        for flag in a.mismatch_flags:
            lines.append(f"- {flag}")
        lines.append("")
    lines.append("## Per-photo observations")
    lines.append("")
    for rec in a.photo_observations:
        lines.append(f"### `{rec.photo}` — {rec.view} ({rec.photo_quality.value})")
        lines.append("")
        for obs in rec.observations:
            sev = f", severity {obs.severity.value}" if obs.severity.value != "none" else ""
            lines.append(
                f"- [{obs.polarity.value}{sev}, {obs.confidence.value} confidence] "
                f"{obs.noticed}"
            )
        if rec.dash_warning_lights:
            lines.append(f"- Dash warning lights: {', '.join(rec.dash_warning_lights)}")
        if rec.odometer_contradiction:
            lines.append(f"- Odometer contradiction: {rec.odometer_contradiction}")
        if rec.mismatch_note:
            lines.append(f"- Mismatch note: {rec.mismatch_note}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Analyzed {a.analyzed_at} · model {a.model} · schema v{a.schema_version} "
        f"· prompt v{a.prompt_version}. Descriptive condition evidence only — "
        "this file never contains value estimates or purchase advice.*"
    )
    lines.append("")
    return "\n".join(lines)


def write_condition_analysis(
    listing_folder: Path, analysis: ConditionAnalysis
) -> None:
    (listing_folder / "condition_analysis.json").write_text(
        analysis.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (listing_folder / "condition_analysis.md").write_text(
        render_markdown(analysis), encoding="utf-8"
    )


def write_run_summary(run_dir: Path, summary: RunSummary) -> Path:
    path = run_dir / "run_summary.json"
    path.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def append_run_history(run_dir: Path, entry: RunHistoryEntry) -> Path:
    """Append one line to run_history.jsonl — run_summary.json reflects only
    the latest invocation, so this is the only place the full multi-
    invocation timeline survives."""
    path = run_dir / "run_history.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
    return path
