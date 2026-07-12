---
name: valuation-research-scout
description: Call Tavily Research for a Van Deal Radar valuation cohort and get back structured, source-cited market research (commercial-market range, fleet/auction clearing range, representative comparables) for Stage 5 Valuation Review. Use when a batch of listings reaches Needs Valuation Review status and cohort-level market research is needed alongside Condition Scout, before building the HTML Valuation Review Report.
---

# Valuation Research Scout

Local Python CLI. Cohort in, market research out: calls Tavily Research
with the approved standing prompt and structured output schema for each
cohort in a run folder, polls to completion, and writes an inspectable
cohort-research artifact that you (CoWork) consume when building the
Valuation Review Report.

**Governing rule — do not violate this:** this tool researches cohort-level
market value only. It never values an individual subject listing, never
inspects Condition Scout's findings or photos, and never recommends buying,
bidding, or a maximum bid. It is a simple Tavily API wrapper, not a second
reasoning or orchestration agent — it does not judge whether research is
"good enough" or auto-escalate Mini to Pro.

## Stage 5 — run this in parallel with Condition Scout

Per the approved Stage 5 fan-out/fan-in architecture: after you derive the
valuation cohort(s) and supply source-platform context, launch this tool
and Condition Scout **in parallel** — Condition Scout can take several
minutes to process listing photos, and Tavily research should run during
that same window rather than afterward. The two branches are independent;
neither tool inspects the other's output. Only you (CoWork) join both
evidence streams afterward into the Stage 5 valuation package.

In practice, with the standing Mini model (see Step 2), this branch
finishes in well under a minute (~30s observed in commissioning) while
Condition Scout's photo analysis takes several minutes — expect this
branch to complete first and simply hold its artifact until Condition
Scout finishes. That's the parallelism working as intended, not a problem.

## When to use this

The Van Deal Radar Listings database has rows at `Status = Needs Valuation
Review`. Before building the market-research sections of the Valuation
Review Report, derive the valuation cohort(s) (which listings belong
together — same vehicle family, comparable years/mileage/geography) and run
this tool to get real, source-cited market research — never write market
research yourself from imagined or inferred detail.

## Step 1 — Write `run_manifest.json`

Create (or reuse) a run folder, e.g. `valuation_research_run_2026-07-12/`,
containing `run_manifest.json`:

```json
{
  "run_id": "valuation_research_run_2026-07-12",
  "created_at": "2026-07-12T12:00:00Z",
  "source_platform_context": "JJ Kane is a true no-reserve absolute Proxibid auction. Archived catalogs show real hammer prices publicly. Buyer fee ~12%, admin fee $125 flat on titled items.",
  "cohorts": [
    {
      "cohort_id": "wpb-express-savana-2500-2017-2018",
      "vehicle_family": "Chevrolet Express / GMC Savana 2500 cargo van",
      "series_or_weight_class": "2500 full-size cargo van",
      "body_configuration": "cargo van, no side windows",
      "model_year_min": 2017,
      "model_year_max": 2018,
      "mileage_min": 51689,
      "mileage_max": 163753,
      "use_context": "commercial/fleet cargo van",
      "primary_geography": "Florida",
      "secondary_geography": "Southeast US",
      "source_platform": "JJ Kane",
      "listing_count": 8,
      "listing_ids": ["1604992", "1615297", "1608490", "1601998", "1614587", "1614586", "1615299", "1608489"]
    }
  ]
}
```

Field notes:
- `run_id` (top-level) and each cohort's `cohort_id`, `vehicle_family`,
  `source_platform`, and `listing_ids` (non-empty) are required. Everything
  else is optional but should be supplied when known — it goes straight
  into the research prompt as cohort context.
- `source_platform_context` (optional, run-level, plain string) — you
  (CoWork) own this. It's prose about the source platform / disposal
  ecosystem (auction structure, fee schedule, reserve type, how results
  are published) that helps Tavily weight same-platform evidence
  correctly. Omitting it falls back to a generic default.
- You own cohort formation — which listings belong together. This tool
  never derives cohorts itself; it only researches the cohort you supply.

## Step 2 — Run it

```powershell
uv sync   # only needed once per checkout
uv run valuation-research-scout run --run-dir valuation_research_run_2026-07-12/ --model mini
```

**Always pass `--model mini` explicitly.** This is the standing production
choice as of the 2026-07-12 West Palm Beach commissioning run (full
writeup: `docs/validation/stage5/wpb-mini-vs-pro-commissioning.md`) —
Pro's research was genuinely deeper (it found real, current JJ Kane item
listings and cross-referenced fee inconsistencies Mini missed) but its
structured output didn't reliably honor the schema's `evidence_type` enum
or the required `price` field, so it failed contract validation. Pro also
costs roughly 2-5x more in Tavily credits per call (15-250 vs Mini's
4-110, against a 1,000-credit/month free-tier budget — see Known
constraints). The CLI still accepts `--model pro` or `--model auto`, but
don't use them for a normal Stage 5 run: if Pro is ever worth revisiting
(e.g. after a schema change to accept free-text evidence types), that's a
deliberate re-commissioning decision for Mike, not a default.

Requires `TAVILY_API_KEY` available to the process (repo-root `.env` file,
already gitignored, or an environment variable). **Never print, log, ask
the user to paste, or write this key anywhere else.**

Exit codes: `0` = every cohort processed · `1` = at least one cohort failed
(check `run_summary.json`) · `2` = manifest/setup error.

## Step 3 — Read the results

1. **`run_summary.json`** (run-folder root) — `processed` / `failed` /
   `api_calls_used`. Start here.
2. **`cohorts/<cohort_id>/cohort_research.md`** — the human-readable
   market research to build the report section from.
3. **`cohorts/<cohort_id>/cohort_research.json`** — same content,
   structured. Field reference in `REFERENCE.md` next to this file.
4. **`cohorts/<cohort_id>/tavily_raw_response.json`** — the full raw
   Tavily response, preserved for commissioning/debugging only; you don't
   normally need this.

A cohort in `failed` has no `cohort_research.*` — do not fabricate
research for it, and **do not just re-run it to see if it works.** Every
attempt spends real Tavily credits whether it succeeds or fails (see Known
constraints). Read the failure reason in `run_summary.json` and the
console output first; report it to Mike and ask before retrying — this
tool has no resume/skip for cohorts the way Condition Scout resumes
already-analyzed listings, so a re-run always re-spends credits, even for
a cohort that already has a valid `cohort_research.json`.

## Known constraints

- **Cost.** Each cohort research call spends real Tavily credits — Mini
  costs roughly 4-110 credits per call, against a 1,000-credit/month
  free-tier budget (Pro costs 15-250 and isn't currently used — see Step
  2). Be deliberate: one run per cohort per valuation batch, never a
  retry loop, and don't re-run a cohort that already has a valid
  `cohort_research.json` without a real reason.
- No buy/bid/pass recommendations, no maximum-bid calculation, no
  individual-subject-van valuation, no defect-specific dollar deductions —
  anywhere in output, by prompt design. This tool cannot strip words like
  "bid" from Tavily's own prose (the approved prompt itself uses "current
  live bid" descriptively) — the prohibition is on recommendation
  language, not auction vocabulary.
- Tavily task completion: ~30s observed for Mini in commissioning (Pro
  observed ~340s, not currently used). This tool polls until complete or
  failed rather than returning early.
