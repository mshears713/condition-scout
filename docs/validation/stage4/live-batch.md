# Stage 4 — Worklist Items 3 & 4: Full real batch + CDN behavior at volume

**Date:** 2026-07-10
**Batch:** West Palm Beach JJ Kane, all 8 listings, auction closing 2026-07-28.
Run incrementally over the course of one session (prompt tuning happened
between sub-batches — see below), never across multiple days, so
resume-next-day behavior was not exercised; resume-within-a-batch was,
repeatedly and successfully (see below).

## Final result — all 8 listings

    run valuation_run_stage4_2026-07-10: 8 processed, 0 failed, 0 skipped (93 API calls) - see run_summary.json
    (this was the final incremental run; cumulative run_summary.json shows
    listings_total: 8, processed: all 8, failed: [], skipped: [])

| Listing | Mileage | Grade | Heavy findings |
|---|---|---|---|
| 1604992 | 104,572 | serviceable (v0.2 baseline, not re-run under v0.5) | 1 (cab_interior) |
| 1615297 | 96,267 | rough (v0.3, not re-run under v0.5) | 1 (cab_interior) |
| 1608490 | 163,753 | serviceable (v0.4, not re-run under v0.5) | 1 (cab_interior) |
| 1601998 | 91,039 | serviceable (v0.4, not re-run under v0.5) | 0 |
| 1614587 | 51,689 | serviceable (v0.4, not re-run under v0.5) | 0 |
| 1614586 | 159,982 | **serviceable (v0.5)** | 1 (cab_interior, both seats torn) |
| 1615299 | 75,689 | **serviceable (v0.5)** | 1 (cab_interior, driver seat torn) |
| 1608489 | 145,475 | **good (v0.5)** | 0 |

The last 3 (analyzed under the final v0.5 prompt) are the clean signal for
the current tuning: the two listings with a genuine heavy finding graded
serviceable; the one with several moderates but zero heavy findings graded
good — confirming the v0.5 grade-anchor fix (Mike: "good, borderline
great... not by a long shot serviceable" for the earlier zero-heavy cases).
The first 5 listings were analyzed under earlier prompt versions (v0.2-v0.4)
during iterative tuning and were not re-run under v0.5 once the grade
anchor was fixed, to avoid burning quota re-confirming rather than making
forward progress — their grades reflect the prompt version active when
each was analyzed, not v0.5's calibration. Mike may want 1604992/1615297/
1608490 re-graded under v0.5 at some point since those were the exact
listings that drove the v0.3/v0.4 corrections but not the v0.5 one.

## Total real quota used today (single-listing test + 3 incremental batches)

29 (item 2, single listing) + 68 + 69 + 93 (three incremental batch runs,
each adding new listings while resuming previously-analyzed ones at 0
cost) = **259 real Gemini API calls**, close to the Engineering Plan's
pessimistic ~250-call/8-listing estimate (259 vs ~250, the small overage
consistent with photo counts running slightly above the ~30/listing
planning assumption: 28/35/31/33/34/26/32/32 photos, average ~32.6).
**Zero 429s encountered all day** across all four run invocations.

## Resume behavior (exercised repeatedly, not just once)

Every incremental run in this session resumed correctly: previously
completed listings logged `valid condition_analysis.json exists -
resume-skip` and cost 0 additional API calls, confirmed via
`run_summary.json`'s `api_calls_used` matching exactly the new listings'
photo+synthesis count each time (68, 69, 93 — never inflated by
re-analyzing earlier listings). This is same-session resume, not
resume-across-days; a genuine next-day resume test would need a real
mid-batch quota exhaustion, which never happened (quota was never hit).

## CDN behavior at volume (worklist item 4)

Photos downloaded across the full day: 28+35+31+33+34+26+32+32 = 251 real
photos from the JJ Kane CDN (`prod.cdn.jjkane.com`), across 4 separate
run invocations. Checked all run logs for HTTP 403/429/timeout warnings
during download: **none found**. No throttling observed at this volume.
(Total real HTTP traffic today also included ~8 JJ Kane `/api/items/{id}`
resolver calls and a handful of manual reachability-check requests.)

## Verdict

**Worklist item 3 (full real batch within one day's quota): VERIFIED.**
All 8 listings processed, 0 failures, comfortably within free-tier quota
(259 calls, no 429s). Resume-within-batch behavior repeatedly confirmed
correct and cost-free. Resume-*next-day* behavior specifically was not
exercised (quota was never actually exhausted) — noting this as a real
gap rather than claiming it Verified by proxy.

**Worklist item 4 (CDN behavior at volume): VERIFIED.** No throttling,
403s, or timeouts across 251 real photo downloads + 8 resolver calls in
one session.
