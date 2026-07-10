"""Condition Scout — Van Radar photo evidence tool.

Downloads listing photos for the Stage 5 valuation queue, analyzes them with
the Gemini vision API, and writes structured, image-cited condition evidence
(JSON + Markdown) that Claude CoWork consumes when building the HTML
Valuation Review Report.

Governing rule: photo AI describes condition; valuation logic interprets it.
"""

__version__ = "0.1.0"

SCHEMA_VERSION = "0.2"
PROMPT_VERSION = "0.2"
