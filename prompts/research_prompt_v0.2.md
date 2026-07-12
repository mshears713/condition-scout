<!--
Synced copy of the standing Tavily Research prompt from the Notion
"Valuation Research Scout" record (v0.2, 2026-07-12). Source of truth is
the Notion page; if they disagree, the page wins.
prompt_version: 0.2

The tool substitutes {COHORT_SUMMARY} (code-rendered from the cohort
manifest fields) and {SOURCE_PLATFORM_CONTEXT} (from run_manifest.json,
CoWork-supplied prose about the source platform / disposal ecosystem —
falls back to a generic default if the manifest doesn't supply one), then
sends this text as `input` to Tavily Research along with the structured
`output_schema` (schema.py) and the selected model (mini/pro/auto).
-->

You are researching current used-commercial-vehicle values for the Van Deal Radar valuation system.

Your task is to establish an evidence-based market baseline for the vehicle cohort provided below.

## VEHICLE COHORT

{COHORT_SUMMARY}

## CURRENT SOURCE / PLATFORM CONTEXT

The subject listings in this valuation batch come from:

{SOURCE_PLATFORM_CONTEXT}

Treat the source platform as an important research dimension.

When useful evidence is available, specifically research comparable vehicles sold, completed, cleared, or listed through the same platform or disposal ecosystem.

Same-platform completed sale or clearing evidence is especially valuable because it may reflect the same buyer population, auction mechanics, seller type, and fleet-disposal environment as the subject batch.

Clearly distinguish:
- completed or historical same-platform results
- current live bids
- active listings
- same-platform evidence where final sale price is unavailable

Do not treat a current live bid as a clearing value unless the sale has completed.

## RESEARCH GOAL

Determine what comparable vehicles in this cohort appear to be worth in two distinct markets:

1. COMMERCIAL MARKET
Ordinary used-commercial-vehicle channels such as commercial vehicle dealers, used work-vehicle sellers, and relevant vehicle marketplaces.

2. FLEET / AUCTION MARKET
Fleet-disposal, commercial auction, government or institutional auction, and comparable wholesale channels.

This is cohort-level market research.

Do not value any individual subject listing. Individual vans will be compared with this research later using separate listing metadata and photo-condition evidence.

## COMPARABLE SELECTION

Prefer comparable vehicles that are close to the supplied cohort in:
- vehicle family, make, and model
- series or weight class
- cargo/body configuration
- model year
- mileage
- commercial or fleet-use context
- primary or secondary geography
- source platform or a comparable fleet-disposal channel when relevant

You may broaden model year or geography when direct evidence is limited, but clearly explain when broader evidence is being used and why it remains relevant.

Do not rely on obviously different vehicle categories simply because they share a model name.

The cohort has already passed Van Deal Radar's candidate-quality screening. Research ordinary running vehicles comparable to the supplied cohort. Do not focus on non-running vehicles, salvage or rebuilt vehicles, or examples with known major mechanical failures.

## COMMERCIAL MARKET RESEARCH

Estimate the current commercial-market value range for the cohort.

Clearly distinguish between:
- asking-price evidence
- sold or transaction evidence, when available

Explain the evidence and reasoning behind the estimated range.

Identify meaningful mileage patterns and model-year patterns when the available evidence supports them.

## FLEET / AUCTION MARKET RESEARCH

Estimate the fleet / auction clearing-value range for the cohort.

Prioritize relevant evidence in roughly this order when available:
1. completed comparable sales or clearing results from the subject source platform
2. completed comparable fleet-disposal or commercial-auction results
3. other relevant wholesale or auction clearing evidence
4. active auction or fleet listings used only as supporting market context

Research the subject platform directly when practical.

Explain how much same-platform evidence was found and how strongly it influenced the estimated fleet / auction range.

Do not treat current live bids as completed sale prices.

## MODIFIERS AND PATTERNS

Identify only value modifiers or market patterns materially supported by the research.

Pay particular attention to:
- mileage bands
- model-year effects

These should be analyzed separately because each may materially affect value.

Other supported patterns may include:
- relevant configuration differences
- geographic effects
- source-platform effects
- commercial-market versus fleet-auction pricing differences

Do not invent a modifier merely to fill the output.

## REPRESENTATIVE COMPARABLES

Return representative comparable vehicles that materially helped establish the market picture.

For each comparable, preserve enough information to understand:
- what the vehicle was
- year
- mileage when available
- observed price
- whether the price represents asking, sold, auction clearing, wholesale, live auction context, or another evidence type
- source platform
- location when available
- source URL when available
- why the comparable is relevant
- important limitations of the comparison

Also provide a rough condition assessment based only on the listing description, stated disclosures, and clearly available listing evidence.

Use:
- clean
- typical_used_fleet
- rough
- major_stated_issues
- unknown

This condition assessment is only a broad comparable-context label.

Do not perform deep photo-condition analysis. Do not invent defects. When condition is unclear, use unknown.

Prefer a useful, representative evidence set over a large list of weak examples.

## RESEARCH RULES

Do not:
- recommend buying a vehicle
- recommend bidding
- calculate a maximum bid
- value a specific subject van
- perform deep listing-photo analysis
- create defect-specific dollar deductions
- convert cosmetic condition into a price adjustment
- model camper conversion profit or resale profit

Prefer ranges and uncertainty over false precision.

Use a confidence level of low, medium, or high for the major value conclusions.

The output should contain enough reasoning and representative evidence for another AI analyst to understand the market picture and later compare individual subject vans against it without rerunning this research.
