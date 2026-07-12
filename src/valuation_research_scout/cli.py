"""Command-line interface: a single verb, ``run``.

Usage:
    valuation-research-scout run --run-dir <folder> [--model mini|pro|auto]
                                 [--poll-interval N] [--timeout N]
                                 [--fake-network]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="valuation-research-scout",
        description=(
            "Cohort in, market research out: call Tavily Research for each "
            "cohort in a run folder's run_manifest.json and write an "
            "inspectable cohort-research artifact per cohort."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Process every cohort in a run folder's run_manifest.json.",
    )
    run_parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Run folder containing run_manifest.json (e.g. valuation_research_run_2026-07-12/).",
    )
    run_parser.add_argument(
        "--model",
        default=None,
        choices=("mini", "pro", "auto"),
        help="Tavily research model (default: auto).",
    )
    run_parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Seconds between Tavily task-status polls (default 5.0).",
    )
    run_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Max seconds to wait for a single research task (default 900).",
    )
    run_parser.add_argument(
        "--fake-network",
        action="store_true",
        help="Use a fake Tavily backend (acceptance testing only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        from valuation_research_scout.orchestrator import run_from_cli

        return run_from_cli(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
