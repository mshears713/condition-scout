# M5 AI-readability test — 2026-07-10

Per the Validation Strategy: a fresh subagent (no build context) was given
ONLY the two artifacts from the faked e2e run
(`docs/validation/m5-e2e/condition_analysis.{json,md}`) and asked to write
the "Condition Evidence" section of a Valuation Review Report.

## Verdict: PASS

The subagent, without access to photos, the Tool page, or the codebase:

- stated grade + confidence correctly (good / medium);
- summarized coverage exactly (3 photos, zones covered vs missing);
- cited specific photo filenames for every claim;
- carried the dash/warning-light evidence including the empty-image_refs
  caveat;
- included zero dollar figures and zero buy/bid/pass language;
- flagged genuine gaps (no odometer evidence, poor coverage) — exactly the
  drill-down behavior the two-layer schema exists for.

Notably, it also caught an internal inconsistency in the artifact: the
finding cites `photo_001.jpg` (an exterior_sides view) for a cab_interior
issue. That inconsistency is an artifact of the deterministic
`--fake-network` Gemini stand-in (fakenet.py returns a canned synthesis
regardless of observations), not of the pipeline logic — the real synthesis
prompt forbids findings that don't trace to observations. Logged in the
Build Log as a known fake-fidelity limit.

## Subagent output (verbatim)

## Condition Evidence

*Source: photo condition analysis for JJ Kane listing 1619602, analyzed 2026-07-10T04:32:36Z (model gemini-2.5-flash-lite, schema/prompt v0.2).*

### Overall visual condition

**Grade: Good** (confidence: **medium**). The analysis summary describes a work van showing typical fleet wear across the photographed zones, with no damage requiring repair visible.

### Photo coverage

**3 photos analyzed — coverage rated "poor."**

| Status | Zones |
|---|---|
| Covered | exterior_sides (`photo_001.jpg`), exterior_rear (`photo_002.jpg`), roof (`photo_003.jpg`) |
| Missing | exterior_front, tires_wheels, engine_bay, cab_interior, dash_instruments, cargo_area, underbody |

All three photos were rated "clear" quality.

### Condition findings (negatives)

- **Cab interior — minor severity** (medium confidence): Typical fleet wear on the driver seat edge. Evidence cited: `photo_001.jpg`. *Note: the artifacts label `photo_001.jpg` as an exterior-sides view and list cab_interior among the missing zones — see Gaps noticed.*

No zones reached moderate severity or worse (adjustment categories: none). No mismatch flags or odometer contradictions were reported.

### Positives

- **Body panels straight in all exterior views** (medium confidence). Evidence cited: `photo_001.jpg`.
- Per-photo observations, all positive at medium confidence:
  - `photo_001.jpg` (exterior_sides, clear): exterior sides appear intact with typical fleet wear.
  - `photo_002.jpg` (exterior_rear, clear): exterior rear appears intact with typical fleet wear.
  - `photo_003.jpg` (roof, clear): roof appears intact with typical fleet wear.

### Dash / warning-light evidence

- Warning lights: **none visible** — however, no photo is cited for this claim (image_refs empty) and the dash_instruments zone is listed as missing from coverage, so this is effectively unverified.
- Odometer: **not visible in any photo**; no odometer reading captured. No odometer contradiction was flagged on any photo.

### Gaps noticed

- **Poor photo coverage (3 photos):** no images of the exterior front, tires/wheels, engine bay, cab interior, dash/instruments, cargo area, or underbody — most of the zones a valuation review would want are undocumented.
- **No odometer evidence:** mileage cannot be visually corroborated from the photos.
- **Unsupported dash claim:** "warning lights: none visible" cites no photo and the dash zone was never photographed.
- **Internal inconsistency:** the sole negative finding (driver seat edge wear, cab_interior) cites `photo_001.jpg`, which is labeled an exterior_sides photo, and cab_interior is simultaneously listed as a missing zone. Likewise, the positive "body panels straight in all exterior views" cites only `photo_001.jpg` rather than all three exterior photos.
- **No cargo-area or tire condition evidence** — both typically material for a cargo van's condition assessment.
