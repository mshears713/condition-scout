"""Command-line interface: a single verb, ``run``.

Usage:
    condition-scout run --run-dir <folder> [--fake-network] [--model NAME]
                        [--photos-per-call N] [--rpm N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="condition-scout",
        description=(
            "Photos in, evidence out: download listing photos for a valuation "
            "run and write image-cited condition artifacts per listing."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Process every listing in a run folder's run_manifest.json.",
    )
    run_parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Run folder containing run_manifest.json (e.g. valuation_run_2026-07-10/).",
    )
    run_parser.add_argument(
        "--model",
        default=None,
        help="Gemini model name (default: gemini-2.5-flash-lite; also via config).",
    )
    run_parser.add_argument(
        "--photos-per-call",
        type=int,
        default=None,
        help="Photos per vision call (default 1; group >1 as a quota fallback).",
    )
    run_parser.add_argument(
        "--rpm",
        type=int,
        default=None,
        help="Max vision-API requests per minute (default 10).",
    )
    run_parser.add_argument(
        "--fake-network",
        action="store_true",
        help="Use fake HTTP + fake Gemini backends (acceptance testing only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        from condition_scout.orchestrator import run_from_cli

        return run_from_cli(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
