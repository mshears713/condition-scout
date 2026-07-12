"""Prompt loading and versioning.

The repo's prompts/ folder carries a copy synced from the "Valuation
Research Scout" Notion record (the page wins on disagreement).
prompt_version is parsed from the filename (research_prompt_v0.2.md) and
stamped into every cohort_research.json.
"""

from __future__ import annotations

import re
from pathlib import Path

_VERSION_RE = re.compile(r"research_prompt_v(\d+\.\d+)\.md$")
_HEADER_RE = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)


class PromptError(Exception):
    """Prompt file missing, unreadable, or version-unparseable."""


def find_prompts_dir(explicit: Path | None = None) -> Path:
    """Locate prompts/: explicit argument, else walk up from this file (repo
    src layout), else the current working directory."""
    if explicit is not None:
        return explicit
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "prompts"
        if list(candidate.glob("research_prompt_v*.md")):
            return candidate
    return Path.cwd() / "prompts"


def _strip_header(text: str) -> str:
    """Drop the leading HTML sync-provenance comment — Tavily never sees it."""
    return _HEADER_RE.sub("", text).strip()


def load_research_prompt(prompts_dir: Path | None = None) -> tuple[str, str]:
    """Returns (template, version). Highest version wins if several present."""
    folder = find_prompts_dir(prompts_dir)
    files = sorted(folder.glob("research_prompt_v*.md"))
    if not files:
        raise PromptError(f"no research_prompt_v*.md in {folder}")
    path = files[-1]
    version = _VERSION_RE.search(path.name).group(1)
    return _strip_header(path.read_text(encoding="utf-8")), version


def fill_template(template: str, *, cohort_summary: str, source_platform_context: str) -> str:
    return template.replace("{COHORT_SUMMARY}", cohort_summary).replace(
        "{SOURCE_PLATFORM_CONTEXT}", source_platform_context
    )
