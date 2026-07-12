"""Valuation Research Scout — Van Radar cohort market research tool.

A simple Python Tavily Research API wrapper, not a second reasoning or
orchestration agent. Accepts a cohort definition and source-platform context
prepared by Claude CoWork, calls Tavily Research with the approved standing
prompt and structured output schema, polls to completion, and writes an
inspectable cohort-research artifact for CoWork to consume.

Governing rule: this tool researches cohort-level market value only. It
never values an individual subject listing, never inspects Condition Scout
findings, and never recommends buying, bidding, or a maximum bid.
"""

__version__ = "0.1.0"

SCHEMA_VERSION = "0.2"
PROMPT_VERSION = "0.2"
