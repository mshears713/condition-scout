"""Prompt loading and versioning.

The repo's prompts/ folder carries copies synced from the "Condition Scout —
Analysis Prompt Spec" Knowledge page (the page wins on disagreement).
prompt_version is parsed from the filenames (photo_prompt_v0.2.md) and
stamped into every condition_analysis.json.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_VERSION_RE = re.compile(r"photo_prompt_v(\d+\.\d+)\.md$")
_HEADER_RE = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)


class PromptError(Exception):
    """Prompt files missing, unreadable, or version-mismatched."""


@dataclass
class PromptPack:
    photo_template: str
    synthesis_template: str
    version: str


def find_prompts_dir(explicit: Path | None = None) -> Path:
    """Locate prompts/: explicit argument, else walk up from this file (repo
    src layout), else the current working directory."""
    if explicit is not None:
        return explicit
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "prompts"
        if list(candidate.glob("photo_prompt_v*.md")):
            return candidate
    return Path.cwd() / "prompts"


def _strip_header(text: str) -> str:
    """Drop the leading HTML sync-provenance comment — the model never sees it."""
    return _HEADER_RE.sub("", text).strip()


def load_prompts(prompts_dir: Path | None = None) -> PromptPack:
    folder = find_prompts_dir(prompts_dir)
    photo_files = sorted(folder.glob("photo_prompt_v*.md"))
    if not photo_files:
        raise PromptError(f"no photo_prompt_v*.md in {folder}")
    photo_path = photo_files[-1]  # highest version wins if several present
    version = _VERSION_RE.search(photo_path.name).group(1)
    synthesis_path = folder / f"synthesis_prompt_v{version}.md"
    if not synthesis_path.is_file():
        raise PromptError(
            f"prompt version mismatch: {photo_path.name} has no matching "
            f"{synthesis_path.name}"
        )
    return PromptPack(
        photo_template=_strip_header(photo_path.read_text(encoding="utf-8")),
        synthesis_template=_strip_header(synthesis_path.read_text(encoding="utf-8")),
        version=version,
    )


def fill_template(template: str, *, year, platform, mileage) -> str:
    """Substitute the listing context tokens ({YEAR}, {PLATFORM}, {MILEAGE})."""
    return (
        template.replace("{YEAR}", str(year) if year is not None else "unknown-year")
        .replace("{PLATFORM}", platform or "unknown-platform")
        .replace(
            "{MILEAGE}",
            f"{mileage:,}" if mileage is not None else "unknown",
        )
    )
