"""Orchestrator/CLI acceptance tests: batch loop, per-cohort error isolation,
and the fake-network CLI mode."""

from __future__ import annotations

import json

import pytest

from tests.fake_tavily import FakeTavily, completed_status, failed_status, sample_research_content_dict
from valuation_research_scout.cli import build_parser, main
from valuation_research_scout.manifest import ManifestError
from valuation_research_scout.orchestrator import RunConfig, run_batch


def write_manifest(run_dir, cohorts, source_platform_context=None):
    data = {"run_id": "test-run", "cohorts": cohorts}
    if source_platform_context:
        data["source_platform_context"] = source_platform_context
    (run_dir / "run_manifest.json").write_text(json.dumps(data), encoding="utf-8")


def one_cohort(cohort_id="c1"):
    return {
        "cohort_id": cohort_id,
        "vehicle_family": "Chevrolet Express / GMC Savana 2500 cargo van",
        "model_year_min": 2017,
        "model_year_max": 2018,
        "source_platform": "JJ Kane",
        "listing_ids": ["1604992"],
    }


def test_run_batch_processes_cohort_successfully(tmp_path):
    write_manifest(tmp_path, [one_cohort()], source_platform_context="JJ Kane is a no-reserve absolute auction.")
    tavily = FakeTavily(poll_script=[completed_status(sample_research_content_dict())])
    summary = run_batch(tmp_path, tavily=tavily, config=RunConfig(model="mini"))
    assert summary.processed == ["c1"]
    assert summary.failed == []
    assert summary.api_calls_used == 1
    research = json.loads((tmp_path / "cohorts" / "c1" / "cohort_research.json").read_text(encoding="utf-8"))
    assert research["model"] == "mini"
    assert (tmp_path / "cohorts" / "c1" / "tavily_raw_response.json").is_file()
    assert (tmp_path / "cohorts" / "c1" / "cohort_research.md").is_file()
    # the rendered prompt actually carried the supplied source-platform context
    assert "no-reserve absolute auction" in tavily.creates[0].input


def test_run_batch_isolates_failed_cohort(tmp_path):
    write_manifest(tmp_path, [one_cohort("c1"), one_cohort("c2")])
    tavily = FakeTavily(poll_script=[failed_status(), completed_status(sample_research_content_dict())])
    summary = run_batch(tmp_path, tavily=tavily, config=RunConfig(model="mini"))
    assert summary.processed == ["c2"]
    assert len(summary.failed) == 1
    assert summary.failed[0].cohort_id == "c1"
    assert summary.failed[0].stage == "request"
    # a failed cohort has no artifact
    assert not (tmp_path / "cohorts" / "c1" / "cohort_research.json").exists()


def test_run_batch_preserves_raw_response_when_content_fails_validation(tmp_path):
    # Real finding from the West Palm Beach Pro commissioning run: Tavily
    # can return a "completed" response whose content violates our own
    # required-field contract (e.g. a representative comparable missing
    # 'price'). The raw response must still be preserved for debugging -
    # that's exactly when it's needed most.
    write_manifest(tmp_path, [one_cohort("c1")])
    bad_content = sample_research_content_dict()
    del bad_content["representative_comparables"][0]["price"]
    tavily = FakeTavily(poll_script=[completed_status(bad_content)])
    summary = run_batch(tmp_path, tavily=tavily, config=RunConfig(model="pro"))
    assert summary.failed[0].stage == "write"
    assert not (tmp_path / "cohorts" / "c1" / "cohort_research.json").exists()
    raw = json.loads((tmp_path / "cohorts" / "c1" / "tavily_raw_response.json").read_text(encoding="utf-8"))
    assert raw["content"] == bad_content


def test_run_batch_rejects_invalid_model(tmp_path):
    write_manifest(tmp_path, [one_cohort()])
    tavily = FakeTavily(poll_script=[completed_status(sample_research_content_dict())])

    with pytest.raises(ManifestError, match="invalid model"):
        run_batch(tmp_path, tavily=tavily, config=RunConfig(model="ultra"))


def test_cli_fake_network_end_to_end(tmp_path):
    write_manifest(tmp_path, [one_cohort("c1"), one_cohort("c2")])
    exit_code = main(["run", "--run-dir", str(tmp_path), "--fake-network"])
    assert exit_code == 0
    summary = json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["processed"] == ["c1", "c2"]
    assert summary["failed"] == []


def test_cli_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["--help"])
    assert excinfo.value.code == 0
    assert "run" in capsys.readouterr().out
