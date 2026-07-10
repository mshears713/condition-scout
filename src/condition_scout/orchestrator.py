"""Batch orchestrator: manifest in, condition artifacts out.

Per-listing errors are recorded and skipped, never fatal to the batch.
Implemented across milestones M1-M5; M0 ships the entry point only.
"""

from __future__ import annotations

import argparse


def run_from_cli(args: argparse.Namespace) -> int:
    raise SystemExit(
        "condition-scout run is not implemented yet (build milestone M0); "
        "see AGENTS.md for the milestone plan."
    )
