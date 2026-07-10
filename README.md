# Condition Scout — Van Radar Photo Evidence Tool

Photos in, evidence out. A local Python CLI for Van Deal Radar Stage 5:
downloads each queued listing's auction photos, analyzes them with the Gemini
vision API, and writes structured, image-cited condition evidence
(`condition_analysis.json` + `.md`) that Claude CoWork consumes when building
the HTML Valuation Review Report.

**Governing rule:** photo AI *describes* condition; valuation logic
*interprets* condition. No dollar amounts, no buy/bid/pass language, ever.

## Usage

```powershell
uv sync
uv run condition-scout run --run-dir valuation_run_2026-07-10/
```

The run folder must contain a `run_manifest.json` written by CoWork. The tool
fills each `listings/<listing_id>/` folder with `photos/`,
`photo_manifest.json`, `condition_analysis.json`, and `condition_analysis.md`,
then writes a run-level `run_summary.json`. Per-listing failures are recorded
and skipped — one bad listing never aborts the batch. Re-running resumes:
downloaded photos and already-analyzed listings are skipped.

`GEMINI_API_KEY` must be set in the environment for real runs (locally via
env var; in CI it is an Actions repository secret).

## Development

```powershell
uv run pytest -q            # fully-faked suite: no network, no secrets
uv run pytest -q -m live -o addopts=""   # live smoke, CI only (<10 requests)
```

See `AGENTS.md` for the agent context and architecture, and the Notion Tool
page for intent (Project Brief / Engineering Plan / Build Log).
