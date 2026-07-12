# Condition Scout — field reference

Full contract detail for `condition_analysis.json`, `run_summary.json`, and
`run_history.jsonl`. Read this only when you need field-level detail beyond
what SKILL.md covers — e.g. computing something from the JSON rather than
just reading the Markdown twin.

## `condition_analysis.json`

Two layers: `photo_observations` is the per-photo audit trail (drill-down /
spot-check use); `findings`/`overall` is what you actually consume.

```
listing_id, source, analyzed_at, model, schema_version, prompt_version
photo_observations: [{
  photo, view, photo_quality: clear|blurry|dark|partial,
  observations: [{ noticed, zone, polarity: positive|negative,
                    severity, confidence }],
  dash_warning_lights?, odometer_contradiction?, mismatch_note?
}]
photo_coverage: { photos_analyzed, zones_covered[], zones_missing[],
                  coverage_quality: good|partial|poor }
findings: [{ zone, polarity, description, severity, confidence,
             image_refs[] (never empty — every finding cites real files),
             red_flag_hint? }]
positives: [{ description, confidence, image_refs[] }]
adjustment_categories: [{ zone, band: severity }]   # one per zone at
                                                     # moderate-or-worse
dash_evidence: { warning_lights[], odometer_visible, odometer_reading?,
                 image_refs[] }
mismatch_flags: []   # photo/listing contradictions (e.g. wrong vehicle,
                     # blatant odometer mismatch)
overall: { visual_grade, summary, confidence }
```

**Zones (10):** exterior_front, exterior_sides, exterior_rear, roof,
tires_wheels, engine_bay, cab_interior, dash_instruments, cargo_area,
underbody.

**Severity:** `none | minor | moderate | heavy | severe` — words, not
numbers (a future condition-adjustment matrix maps these to dollar bands;
this tool never does that math itself).

**Confidence:** `low | medium | high`.

**Visual grade** (`overall.visual_grade`) — **Mike-process-relative, not
retail, and deliberately not the same vocabulary as the Listings database's
Vehicle Quality field (Great/Good/Fair/Poor/Very Poor) — never conflate the
two:**
- `excellent` — like-new, no real wear items at all
- `good` — any amount of cosmetic wear (paint, decal residue, light rust)
  and any number of moderate findings, as long as there's no heavy-or-worse
  finding anywhere. This is the default grade for a normal used work van.
- `serviceable` — exactly one heavy finding, confined to one
  process-irrelevant zone (cab_interior or cargo_area)
- `rough` — heavy-or-worse damage in two or more separate zones, or any
  heavy damage in a process-relevant zone (body/structural, tires, glass)
- `poor` — severe abuse across zones

A dash warning light never by itself moves the grade — it's a "worth
checking before bidding" flag, not a recon-labor signal (you can't confirm
from a photo whether it's real).

**`red_flag_hint`** maps toward the Listings database's Red Flags vocabulary
(Body Damage, Rust/Corrosion, Severe Rust/Structural Corrosion,
Interior/Cargo Roughness, Door/Glass/Tire Issue, CEL/Dash Warning, Flood
Risk/Flood Damage, Suspicious/Contradictory Info) — it's a hint only, you
still decide whether to actually set a Red Flag.

## `run_summary.json` (run-folder root)

```
run_id, started_at, finished_at, schema_version, listings_total,
processed[], failed: [{ listing_id, stage: resolve|download|analyze|
                        synthesize|write, reason }],
skipped: [{ listing_id, reason }], api_calls_used
```

`started_at`/`finished_at` are for the **most recent invocation only** — if
the run folder was invoked more than once (e.g. tuning iterations, or a
resume the next day after quota ran out), this does not reflect the full
history. Use `run_history.jsonl` for that.

## `run_history.jsonl` (run-folder root, appended, one JSON object per line)

```
invocation_started_at, invocation_finished_at,
newly_processed[]   # listings actually analyzed THIS invocation
resumed[]           # listings that already had valid analysis, skipped at 0 cost
failed[], skipped[], api_calls_used   # this invocation only
```

Sum `newly_processed` counts across all lines (or just check the last
line's `resumed` + `newly_processed` union) to reconstruct the true
timeline of a multi-invocation batch.
