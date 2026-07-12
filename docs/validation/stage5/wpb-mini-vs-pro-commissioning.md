# West Palm Beach Cohort — Tavily Mini vs Pro Commissioning

2026-07-12. Same cohort definition, source-platform context, standing
prompt (v0.2), and structured output schema run through Tavily Mini and
Pro side by side, per the commissioning instructions. No automatic
Mini-to-Pro escalation or research-sufficiency judging was implemented —
this is a one-time comparison for Mike to pick the production model from.

**Cohort:** Chevrolet Express / GMC Savana 2500 cargo van, 2017-2018,
Florida/Southeast, 51,689-163,753 miles, 8 JJ Kane listings.

Artifacts: `valuation_research_run_wpb_mini/` and
`valuation_research_run_wpb_pro/` (both committed).

## Result summary

| | Mini | Pro |
|---|---|---|
| Response time | 30.75s | 340.01s (~11x slower) |
| Contract validation | **Passed** on first try | **Failed** — 14 validation errors |
| Sources returned | 5 | 1 |
| Representative comparables | 5, all fully populated | 8, but 4 with `price: null` and all 8 using free-text `evidence_type` instead of the declared enum |
| Commercial market range | $12,950-$14,999 (medium confidence) | $13,192-$16,204 (medium confidence) |
| Fleet/auction market range | $4,750-$9,000 (low confidence) | $1,050-$1,700 (low confidence) |
| Same-platform (JJ Kane) evidence | Not found; noted as a caveat | Not found (specific JJ Kane *listings* found — real, current item IDs like 1614587, 1616081, 1604992 — but no completed hammer prices); noted as a caveat |

## Content quality (qualitative)

**Pro's research is genuinely deeper.** It found and cited 5 *real, current*
JJ Kane/Proxibid item listings by ID (1597636, 1604992, 1607624, 1614587,
1616081) with correct mileage and upfit details, cross-referenced JJ Kane's
own inconsistent buyer-fee terms pages (12% vs 12-17% vs flat 17% across
different pages — a genuinely useful, specific caveat), and pulled in
IAA/Copart/CarGurus/repo.com evidence with a materially lower and more
conservative fleet/auction range ($1,050-$1,700) than Mini's ($4,750-$9,000).
Mini's research is shallower but internally cleaner.

**Pro's structured-output adherence was unreliable in this run.** Despite
`output_schema` declaring `evidence_type` as a closed enum (`asking | sold
| auction_clearing | wholesale | live_auction_context | other`) and `price`
as a required, non-nullable number, Pro's response used free-text phrases
instead of enum values (`"same-platform listing without final sale price"`,
`"retail asking-listing"`, `"completed other-auction wholesale sale"`,
`"retail/other listing (repo.com)"`) for every one of its 8 comparables,
and left `price` as JSON `null` for 4 of them (contract-conflict #6 in
`tavily-api-findings.md` — Tavily's structured-output feature has no way to
express "field genuinely unknown" once a field is required and typed
non-nullable, so Pro appears to fall back to a close-but-non-conforming
value rather than omit the field or pick an enum value). Mini's response
had none of these issues — every comparable had a real enum value and a
real number.

The raw Pro response is fully preserved at
`valuation_research_run_wpb_pro/cohorts/wpb-express-savana-2500-2017-2018/tavily_raw_response.json`
for inspection; no `cohort_research.json`/`.md` exists for it because it
never passed contract validation (by design — an invalid artifact is not
written, matching Condition Scout's failure-isolation pattern).

## Recommendation

**Mini for production**, at least for v0.2. It reliably honors the
structured contract (the entire point of using `output_schema` at all),
completes in ~30s vs. ~5.5 minutes, and its content — while shallower —
was accurate and appropriately low-confidence where evidence was thin. Pro's
extra research depth is real and valuable, but not reliable enough to trust
unattended in a batch pipeline without a repair/retry mechanism the
approved v0.2 contract explicitly says not to build yet ("Do not implement
automatic Mini-to-Pro escalation... do not build a research-quality
bureaucracy in v0.2").

If Pro's depth is wanted later, the more promising path is loosening
`evidence_type` to a free-text field with the enum values as *suggested*
values in its description (or accepting the enum-mismatch and re-mapping it
in code) rather than a strict closed enum — but that's a v0.3+ design
decision for Mike, not something implemented here.

This is a single run of each model on one cohort — a reasonable first
commissioning signal, not a statistically robust sample.
