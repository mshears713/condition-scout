# Condition Scout — Agent Context (canonical)

Derived from the Notion Tool page "Condition Scout — Van Radar Photo Evidence
Tool" (https://app.notion.com/p/399850a911d381199117e6963c3df82e). This file
is disposable: if it disagrees with the Tool page, the Tool page wins.

## Purpose

Turn auction listing photos into structured, image-cited condition evidence
for Van Deal Radar Stage 5 Valuation Review. Manifest in → photos downloaded →
Gemini vision analysis → `condition_analysis.json` + `.md` per listing, plus a
run-level summary. Claude CoWork consumes the artifacts; it never re-opens the
photos.

**Governing rule: photo AI describes condition; valuation logic interprets
condition.** No dollar amounts, no value opinions, no buy/bid/pass language,
no mechanical diagnosis beyond visible evidence — anywhere in output.

## v0 Boundary

One command, batch-driven:

```
condition-scout run --run-dir valuation_run_YYYY-MM-DD/
```

- Sources: JJ Kane, PublicSurplus, Purple Wave (plain-`requests` resolvers);
  GovDeals via manifest-supplied pre-resolved photo URLs (override path).
- No GUI, no daemon, no database, **no Notion access**, no browser automation.
- Per-listing failures are recorded and skipped, never fatal. Resumable.
- `run_summary.json` reflects only the most recent invocation of a run
  folder. `run_history.jsonl` (one appended line per invocation) has the
  full timeline across multi-invocation batches (iterative tuning,
  resume-next-day after quota exhaustion) — check it, not just
  `run_summary.json`, when reconstructing when a batch actually completed.
- Designed to the Gemini free tier: default `photos_per_call=1`, RPM pacing,
  429 exponential backoff, `photos_per_call>1` grouping as a quota fallback.
- Out of scope for v0: GovDeals scraping, GSA, dollar math, valuation/report
  building, setting Red Flags, edge-case hardening.

## Architecture (approved — do not re-architect; flag deltas)

```
src/condition_scout/
  cli.py           # single verb: run --run-dir <folder> [flags]
  manifest.py      # load + pydantic-validate run_manifest.json
  resolvers/       # jjkane.py, publicsurplus.py, purplewave.py, override.py
  download.py      # requests, pacing, photo_manifest.json, resume
  analyzer.py      # google-genai client seam, per-photo calls, synthesis
  schema.py        # condition_analysis v0.6 pydantic models (zero financial
                   # role — no adjustment_categories or dollar-mapping field)
  artifacts.py     # json + md writers, run_summary.json
  orchestrator.py  # batch loop, per-listing error isolation, resume
prompts/           # photo_prompt_v0.6.md, synthesis_prompt_v0.6.md
                   # synced from the "Condition Scout — Analysis Prompt Spec"
                   # Knowledge page; the page wins on disagreement
```

- pydantic v2 for all contracts; `responseJsonSchema` on Gemini calls plus
  local validation (belt and suspenders); one malformed-JSON repair retry,
  then fail the listing only.
- Model name is config (Flash-Lite class; default is the rolling
  `gemini-flash-lite-latest` alias after the pinned 2.5 name 404'd for new
  API projects at the 2026-07-10 live smoke), never hardcoded logic.
- Every `condition_analysis.json` records `schema_version` and
  `prompt_version`.

## Milestones

- **M0** — harness bring-up: scaffold, uv, pytest, CLI skeleton, CI stub,
  prompts synced, `docs/kickoff.md`.
- **M1** — contracts: manifest + condition_analysis v0.2 + run_summary models,
  run-folder skeleton, golden files, malformed-manifest rejection.
- **M2** — resolvers + downloader against recorded fixtures; pacing + resume;
  404/timeout/empty-gallery paths.
- **M3** — analyzer: client seam + FakeGemini matrix (valid, malformed JSON,
  429s, truncation), both call modes, backoff, repair retry, failure
  isolation, resume-skip.
- **M4** — synthesis + artifact writers with golden files.
- **M5** — e2e faked batch, AI-readability test, live-smoke CI trigger,
  Validation Ledger finalized, AVB Report, `docs/kickoff-stage4.md`, draft
  handoff PR.

## Testing & Validation

- Default suite is **fully faked** — no network, no secrets:
  `uv run pytest -q`.
- Live smoke (CI only, Actions-injected `GEMINI_API_KEY`, <10 requests):
  `uv run pytest -q -m live`. Skips cleanly when the secret is absent.
- Fixtures: `tests/fixtures/{http,gemini,photos}/`; golden files in
  `tests/golden/`. Synthetic fixtures are acceptable; note fidelity limits.
- Evidence: raw output in `docs/validation/`; verdicts + AVB Report in the
  Tool page Build Log.
- Ledger honesty: **Verified only with executed evidence; otherwise Deferred
  with a written Stage 4 step. Never bluff a Verified.**

## Secret Hygiene (absolute)

`GEMINI_API_KEY` exists only as a GitHub Actions repository secret. Never
request, print, log, or commit it. Live tests must not print response
fragments containing the key. A missing secret is a finding to log and defer,
never a stop.

## Stop-and-Flag Rules

Stop only for: product-scope ambiguity, missing credentials/access (other
than the by-design absent local Gemini key), repo/tool failure, architecture
conflict, plan contradiction, intent-changing decisions. Provisional deltas
that preserve architecture and intent: adopt least-invasive fix, flag in the
Build Log and AVB Report, continue. Never silently re-architect.
