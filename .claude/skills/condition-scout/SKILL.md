---
name: condition-scout
description: Turn Van Deal Radar auction listing photos into structured, image-cited vehicle condition evidence (JSON + Markdown) for Stage 5 Valuation Review. Use when a batch of listings reaches Needs Valuation Review status and condition evidence is needed before building the HTML Valuation Review Report.
---

# Condition Scout

Local Python CLI. Photos in, evidence out: downloads each queued listing's
auction photos, analyzes them with the Gemini vision API, and writes
structured, image-cited condition evidence that you (CoWork) consume when
building the Valuation Review Report.

**Governing rule — do not violate this:** photo AI *describes* condition;
valuation logic *interprets* condition. Never use this tool's output to make
or imply a buy/bid/pass decision. Its output contains zero dollar figures
and zero decision language by design — if you ever see either, something is
wrong, not intentional. Condition Scout has zero financial role: there is
no `adjustment_categories` field or any other field that maps condition to
a dollar effect, and there never will be in this tool.

## Stage 5 — run this in parallel with Valuation Research Scout

Per the approved Stage 5 fan-out/fan-in architecture: after you derive the
valuation cohort(s), launch this tool and Valuation Research Scout **in
parallel** — this tool can take several minutes to process listing photos,
and Tavily cohort research should run during that same window rather than
afterward. The two branches are independent — this tool never inspects
Valuation Research Scout's output, and Valuation Research Scout never
inspects this tool's findings. Only you (CoWork) join both evidence
streams afterward into the Stage 5 valuation package.

## When to use this

The Van Deal Radar Listings database has rows at `Status = Needs Valuation
Review`. Before building the condition-evidence sections of the Valuation
Review Report for those rows, run this tool to get real, per-photo,
image-cited findings — never write condition evidence yourself from
imagined or inferred detail.

## Step 1 — Write `run_manifest.json`

Create (or reuse) a run folder, e.g. `valuation_run_2026-07-10/`, containing
`run_manifest.json`:

```json
{
  "run_id": "valuation_run_2026-07-10",
  "created_at": "2026-07-10T12:00:00Z",
  "vehicle_context": "This is a used commercial fleet cargo van (Chevrolet Express/GMC Savana) being evaluated for a flip-to-camper-conversion project, not a retail or consumer vehicle purchase.",
  "buyer_calibration": "This buyer converts cheap work vans to campers. Cosmetic ugliness (paint, adhesive/decal residue, light rust) and cargo-area wear matter little for grade -- they don't add real recon labor. Body/structural condition, tires, glass, and cab condition matter more, since they add real recon labor.",
  "listings": [
    {
      "listing_id": "1604992",
      "source": "JJ Kane",
      "listing_url": "https://www.jjkane.com/?s=1604992",
      "year": 2017,
      "platform": "Chevrolet Express",
      "mileage": 104572
    }
  ]
}
```

Field notes:
- `run_id` (top-level) is required; `created_at` is optional (informational
  only).
- `listing_id` / `source` / `listing_url` are required per listing.
  `source` must be one of `JJ Kane`, `PublicSurplus`, `Purple Wave` to get an
  automatic resolver, or anything else (e.g. `GovDeals`) with a manifest
  `photo_urls` override.
- `year` / `platform` / `mileage` are optional but should always be supplied
  when known — they go straight into the vision prompt as listing context.
- `auction_id` (optional) — only needed for Purple Wave lots when the
  8-digit auction id isn't parseable from the URL.
- `photo_urls` (optional array of plain URL strings, in display order) —
  pre-resolved photo URLs. **Required for GovDeals** (its gallery is
  Akamai-guarded and not auto-resolved) and for any source name the tool
  doesn't recognize.
- `vehicle_context` / `buyer_calibration` (optional, run-level, not
  per-listing, both plain strings) — added 2026-07-10. Genuinely optional:
  omitting them falls back to the work-van/camper-flip framing shown above,
  which is correct for that exact deal type and requires no action from you.
  Only set them explicitly when the deal thesis or vehicle type is
  *different* from that fallback (a different platform, a different buyer
  intent, a different flip strategy) — that's the whole point of these
  fields: change data here, not prompt files, when the judgment context
  changes.

## Step 2 — Run it

```powershell
uv sync   # only needed once per checkout
uv run condition-scout run --run-dir valuation_run_2026-07-10/
```

Requires `GEMINI_API_KEY` available to the process (repo-root `.env` file,
already gitignored, or an environment variable). **Never print, log, ask
the user to paste, or write this key anywhere else.** If you can't execute
this command directly in your current environment, tell Mike the manifest
is ready and ask him to run it (Claude Code or a local shell both work).

Exit codes: `0` = every listing processed or skipped-by-design · `1` = at
least one listing failed (check `run_summary.json`, this is common and not
alarming — the batch still completed for everything else) · `2` =
manifest/setup error (fix the manifest or environment, then re-run).

Safe to re-run the same folder any time — already-downloaded photos and
already-analyzed listings are skipped (resume), at zero extra API cost.

## Step 3 — Read the results

Check in this order:
1. **`run_summary.json`** (run-folder root) — `processed` / `failed` /
   `skipped` / `api_calls_used` for the most recent invocation. Start here.
2. **`run_history.jsonl`** (run-folder root, one JSON line per invocation)
   — only needed if the batch spanned more than one invocation (iterative
   work, or a resume after quota ran out); `run_summary.json` alone only
   reflects the latest invocation and can be misleading about *when* things
   actually finished.
3. **`listings/<listing_id>/condition_analysis.md`** — the human-readable
   evidence to build the report section from. Do not re-open the photos
   yourself; this file plus its JSON twin are the complete, citation-backed
   condition evidence.
4. **`listings/<listing_id>/condition_analysis.json`** — same content,
   structured, if you need to compute anything (e.g. count zones with
   moderate-or-worse findings) rather than just quote it. Field reference in
   `REFERENCE.md` next to this file.

A listing in `failed` OR `skipped` has no `condition_analysis.*` — do not
fabricate evidence for either. A `failed` listing is a real error (report it
and move on, or ask Mike whether to retry). A `skipped` listing is by
design (e.g. an unrecognized source with no `photo_urls` override) — report
it as skipped, not as a failure.

## Known constraints

- Free-tier Gemini quota: pessimistically ~250 calls/day. A real 8-listing
  batch (~32 photos/listing average) used 259 calls with zero 429s in
  practice — comfortably workable, but don't run multiple large batches the
  same day without checking.
- No dollar amounts or buy/bid/pass language anywhere in output, ever — this
  is enforced by tests, not just prompt instruction.
- `red_flag_hint` on findings is a *hint* toward the Listings database's Red
  Flags vocabulary — this tool never sets Red Flags itself; that's yours to
  do.
