"""M0 smoke tests: the environment executes code and the CLI stands up."""

from __future__ import annotations

import pytest

from condition_scout import PROMPT_VERSION, SCHEMA_VERSION
from condition_scout.cli import build_parser


def test_versions_are_pinned():
    assert SCHEMA_VERSION == "0.2"
    assert PROMPT_VERSION == "0.2"


def test_cli_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["--help"])
    assert excinfo.value.code == 0
    assert "run" in capsys.readouterr().out


def test_cli_run_requires_run_dir():
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["run"])
    assert excinfo.value.code == 2
