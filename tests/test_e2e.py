"""M5 acceptance tests: the full faked batch through the real CLI entry
point — mixed success/failure/skip manifest, exit codes, artifacts, resume."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from condition_scout.cli import main
from condition_scout.schema import ConditionAnalysis, RunSummary

E2E_MANIFEST = Path(__file__).parent / "e2e_run" / "run_manifest.json"

EXPECTED_PROCESSED = {"1619602", "4043486", "ED5334", "gd-7781"}
EXPECTED_PHOTO_COUNTS = {"1619602": 3, "4043486": 2, "ED5334": 3, "gd-7781": 2}


@pytest.fixture()
def run_dir(tmp_path) -> Path:
    shutil.copyfile(E2E_MANIFEST, tmp_path / "run_manifest.json")
    return tmp_path


def run_cli(run_dir: Path) -> int:
    return main(["run", "--run-dir", str(run_dir), "--fake-network"])


def load_summary(run_dir: Path) -> RunSummary:
    return RunSummary.model_validate(
        json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    )


def test_e2e_mixed_batch(run_dir, capsys):
    exit_code = run_cli(run_dir)
    assert exit_code == 1  # the deliberate 404404 failure surfaces in the code

    summary = load_summary(run_dir)
    assert summary.run_id == "e2e_fake_run"
    assert set(summary.processed) == EXPECTED_PROCESSED
    assert [f.listing_id for f in summary.failed] == ["404404"]
    assert summary.failed[0].stage == "resolve"
    assert [s.listing_id for s in summary.skipped] == ["gsa-001"]
    # 10 photos + 4 synthesis calls, no retries in fake mode
    assert summary.api_calls_used == 14

    out = capsys.readouterr().out
    assert "4 processed, 1 failed, 1 skipped" in out
    assert "FAILED 404404" in out
    assert "SKIPPED gsa-001" in out


def test_e2e_artifacts_complete_and_valid(run_dir):
    run_cli(run_dir)
    for lid in EXPECTED_PROCESSED:
        folder = run_dir / "listings" / lid
        assert (folder / "listing_snapshot.json").is_file()
        photos = sorted((folder / "photos").glob("photo_*"))
        assert len(photos) == EXPECTED_PHOTO_COUNTS[lid]
        photo_manifest = json.loads((folder / "photo_manifest.json").read_text(encoding="utf-8"))
        assert len(photo_manifest["photos"]) == EXPECTED_PHOTO_COUNTS[lid]

        analysis = ConditionAnalysis.model_validate(
            json.loads((folder / "condition_analysis.json").read_text(encoding="utf-8"))
        )
        assert analysis.listing_id == lid
        assert analysis.schema_version == "0.6"
        assert analysis.prompt_version == "0.6"
        assert analysis.photo_coverage.photos_analyzed == EXPECTED_PHOTO_COUNTS[lid]
        # evidence citation rule: every finding cites downloaded files
        filenames = {p.name for p in photos}
        for finding in analysis.findings:
            assert set(finding.image_refs) <= filenames
        md = (folder / "condition_analysis.md").read_text(encoding="utf-8")
        assert "$" not in md
    # the failed and skipped listings must not have analysis artifacts
    for lid in ("404404", "gsa-001"):
        assert not (run_dir / "listings" / lid / "condition_analysis.json").exists()


def test_e2e_resume_skips_analyzed_listings(run_dir):
    run_cli(run_dir)
    first = load_summary(run_dir)
    run_cli(run_dir)
    second = load_summary(run_dir)
    assert set(second.processed) == EXPECTED_PROCESSED
    # nothing re-analyzed: the resumed run only re-attempts the failure
    assert second.api_calls_used == 0
    assert first.api_calls_used == 14


def test_e2e_run_history_tracks_each_invocation(run_dir):
    run_cli(run_dir)
    run_cli(run_dir)
    lines = (run_dir / "run_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first_entry = json.loads(lines[0])
    second_entry = json.loads(lines[1])
    assert set(first_entry["newly_processed"]) == EXPECTED_PROCESSED
    assert first_entry["resumed"] == []
    assert first_entry["api_calls_used"] == 14
    # second invocation resumed everything from the first, analyzed nothing new
    assert second_entry["newly_processed"] == []
    assert set(second_entry["resumed"]) == EXPECTED_PROCESSED
    assert second_entry["api_calls_used"] == 0


def test_e2e_missing_manifest_is_exit_2(tmp_path, capsys):
    assert main(["run", "--run-dir", str(tmp_path), "--fake-network"]) == 2
    assert "no run_manifest.json" in capsys.readouterr().out


def test_e2e_clean_manifest_exits_zero(tmp_path):
    data = json.loads(E2E_MANIFEST.read_text(encoding="utf-8"))
    data["listings"] = [l for l in data["listings"] if l["listing_id"] == "1619602"]
    (tmp_path / "run_manifest.json").write_text(json.dumps(data), encoding="utf-8")
    assert run_cli(tmp_path) == 0
