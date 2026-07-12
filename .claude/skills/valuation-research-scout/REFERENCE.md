# Valuation Research Scout — field reference

Full contract detail for `cohort_research.json` and `run_summary.json`.
Read this only when you need field-level detail beyond what SKILL.md
covers.

## `cohort_research.json`

```
cohort_id, source ("Tavily Research"), analyzed_at, model (mini|pro|auto),
schema_version, prompt_version, request_id
content: {
  cohort_summary,
  source_platform_analysis: { platform, same_platform_evidence_found,
    evidence_summary, observed_value_pattern, influence_on_auction_range,
    confidence },
  commercial_market: { value_range_low, value_range_high, rationale, confidence },
  fleet_auction_market: { value_range_low, value_range_high, rationale, confidence },
  mileage_patterns: [{ mileage_range, observed_pattern, rationale }],
  model_year_patterns: [{ model_year_or_range, observed_pattern, rationale }],
  important_modifiers: [{ modifier, observed_effect, rationale }],
  representative_comparables: [{ vehicle, year, mileage, price,
    evidence_type: asking|sold|auction_clearing|wholesale|live_auction_context|other,
    source_platform, location, source_url,
    condition_context: clean|typical_used_fleet|rough|major_stated_issues|unknown,
    condition_notes, relevance: low|medium|high, relevance_notes, limitations }],
  major_caveats: [],
  overall_confidence: low|medium|high,
  research_summary
}
sources: [{ title, url, favicon? }]   # Tavily's own top-level returned sources,
                                      # separate from representative_comparables[].source_url
```

**Two markets, always distinguish:** `commercial_market` (ordinary
used-commercial-vehicle channels — dealers, marketplaces) vs
`fleet_auction_market` (fleet-disposal, commercial/government/institutional
auction, wholesale). Auction clearing values typically run well below
commercial asking prices — don't average them together.

**`source_platform_analysis`** exists because same-platform completed-sale
evidence (e.g. other JJ Kane lots) is weighted more heavily than generic
market data — it reflects the same buyer population and auction mechanics
as the subject batch. `same_platform_evidence_found: false` means treat
`fleet_auction_market` with more caution.

**`condition_context`** on comparables is a *broad* label from listing
descriptions only — never deep photo analysis, never invented defects. It
exists to keep comparables honest about what condition tier they represent,
not to interpret the subject van's condition (that's Condition Scout's job,
joined separately by you).

**`evidence_type`** distinguishes `sold`/`auction_clearing` (real
transactions) from `asking` (unsold) and `live_auction_context` (an
in-progress bid, not a completed sale) — never treat a live bid as a
clearing price.

**`model`** will read `"mini"` in practice — that's the standing production
choice as of the 2026-07-12 commissioning run (SKILL.md Step 2 and
`docs/validation/stage5/wpb-mini-vs-pro-commissioning.md` have the full
rationale). Don't treat a `"pro"` or `"auto"` value here as normal; it
means someone deliberately overrode `--model`.

## `run_summary.json` (run-folder root)

```
run_id, started_at, finished_at, schema_version, cohorts_total,
processed[], failed: [{ cohort_id, stage: validate|request|poll|write, reason }],
api_calls_used
```

A `failed` cohort has no `cohort_research.*` — the folder still exists
(from the manifest snapshot) but the research artifact is absent.
