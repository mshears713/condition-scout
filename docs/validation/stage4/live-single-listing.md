# Stage 4 — Worklist Item 2: Real quota/429 behavior + single-listing live run

**Date:** 2026-07-10
**Listing:** 1604992 — 2017 Chevrolet Express G2500 Cargo Van, West Palm Beach FL,
104,572 mi, Vehicle Quality "Good", no Red Flags noted, 28 photos. Real
`Needs Valuation Review` row from the Van Deal Radar Listings database
(part of an 8-listing West Palm Beach JJ Kane batch closing 2026-07-28).

## Setup

- `GEMINI_API_KEY` loaded via `.env` at repo root (gitignored; not in shell
  env, not printed/logged/committed — see condition_scout/gemini.py's
  `load_dotenv()`).
- Real JJ Kane item API confirmed live and matching Notion data before the
  run: `GET https://www.jjkane.com/api/items/1604992` → 28 images, VIN/desc
  matches the Listings database row exactly.
- `run_manifest.json` written per `src/condition_scout/manifest.py` contract
  (listing_id/source/listing_url required; year/platform/mileage optional).

## Command

    uv run condition-scout run --run-dir valuation_run_stage4/

## Result

    INFO 1604992: analyzed 28 photos
    run valuation_run_stage4_2026-07-10: 1 processed, 0 failed, 0 skipped (29 API calls) - see run_summary.json
    EXIT CODE: 0

- Wall time: ~4m7s for 28 photo calls + 1 synthesis call (29 total), no 429s
  encountered, no backoff triggered.
- `run_summary.json`: `api_calls_used: 29` (28 photos + 1 synthesis, matches
  `photos_per_call=1` default exactly).
- `photos/`: 28 files downloaded, matches `imageCount` from the live API.
- `condition_analysis.json`: pydantic-validates cleanly against the v0.2
  schema (schema_version 0.2, prompt_version 0.2, model
  gemini-flash-lite-latest).
- `condition_analysis.md`: zero `$`, zero buy/bid/pass/worth/value-estimate
  language outside the fixed disclaimer sentence itself (checked by grep).
- Overall grade: **serviceable** (confidence: high). Coverage: **good**
  (28/28 photos; zones covered: exterior_front/sides/rear, tires_wheels,
  engine_bay, cab_interior, dash_instruments, cargo_area; missing: roof,
  underbody — expected, auction photo sets don't shoot underneath).
- 9 merged findings (minor exterior paint, engine bay dust/oxidation, one
  heavy cab_interior tear + one moderate console damage, dash cluster
  crack), 3 positive findings (ladder rack, Adrian Steel shelving, tire
  tread), dash_evidence: seatbelt warning light noted, odometer not read,
  no mismatch_flags.

## Quota check

AI Studio quota page before/after was **not checked** — no browser access to
the authenticated quota UI from this session. Mike: worth a manual glance
before the full 8-listing batch (item 3) to confirm remaining daily
allowance, since this single listing already used 29 of a pessimistic
~250/day budget.

## Verdict

**VERIFIED** — real quota/429 behavior observed (no 429s at this volume),
single-listing live run against a real Needs Valuation Review row completed
cleanly end to end: photos resolved, downloaded, analyzed, synthesized,
written, schema-valid, zero prohibited language. Ready for Mike's quality
spot-check (worklist item 5) before proceeding to the remaining 7 listings
in the West Palm Beach batch (worklist item 3).
