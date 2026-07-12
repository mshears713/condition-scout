"""Stage 5 fan-out/fan-in: Condition Scout and Valuation Research Scout must
be safely launchable in parallel, with neither branch inspecting or
blocking on the other (per the approved Valuation Review architecture).

In real Stage 5 usage, Claude CoWork launches these as two separate OS
processes (two CLI invocations), so there is no shared-interpreter-state
concern at all. This test instead proves two properties that DO matter for
correctness even then: (1) running both orchestrators concurrently in one
process produces the same correct, isolated output as running them
sequentially — no accidental shared global state or cross-talk between the
two packages — and (2) a slow branch (photo analysis / Tavily research
genuinely takes real wall-clock time) does not force the other branch to
wait, which is the entire point of running them in parallel rather than
in sequence.
"""

from __future__ import annotations

import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from condition_scout.analyzer import AnalyzerConfig
from condition_scout.fakenet import FakeNetworkGemini, FakeNetworkHttp
from condition_scout.orchestrator import run_batch as run_condition_scout_batch
from condition_scout.schema import RunSummary as ConditionScoutRunSummary

from tests.fake_tavily import sample_research_content_dict
from valuation_research_scout.fakenet import FakeNetworkTavily
from valuation_research_scout.orchestrator import RunConfig, run_batch as run_valuation_scout_batch
from valuation_research_scout.schema import RunSummary as ValuationScoutRunSummary
from valuation_research_scout.tavily import TavilyResult

CONDITION_SCOUT_MANIFEST = Path(__file__).parent / "e2e_run" / "run_manifest.json"
CALL_DELAY_S = 0.08  # stands in for real per-call vision/research latency
VALUATION_COHORT_COUNT = 5  # gives the valuation branch comparable weight to condition scout's ~14 calls


class DelayedFakeGemini:
    """Wraps FakeNetworkGemini with a fixed per-call delay so the timing
    assertion below is meaningful (the real fakes are near-instant)."""

    def __init__(self, inner, delay_s: float):
        self._inner = inner
        self._delay_s = delay_s

    def generate(self, **kwargs):
        time.sleep(self._delay_s)
        return self._inner.generate(**kwargs)


class DelayedFakeTavily:
    def __init__(self, delay_s: float):
        self._delay_s = delay_s
        self.calls = 0

    def run(self, **kwargs):
        time.sleep(self._delay_s)
        self.calls += 1
        return TavilyResult(
            request_id=f"delayed-fake-{self.calls:03d}",
            content=sample_research_content_dict(),
            sources=[{"title": "Fake Source", "url": "https://example.com/fake"}],
            raw={"status": "completed"},
        )


def _run_condition_scout(run_dir: Path, delay_s: float) -> ConditionScoutRunSummary:
    shutil.copyfile(CONDITION_SCOUT_MANIFEST, run_dir / "run_manifest.json")
    return run_condition_scout_batch(
        run_dir,
        http=FakeNetworkHttp(),
        gemini=DelayedFakeGemini(FakeNetworkGemini(), delay_s),
        config=AnalyzerConfig(rpm=100000),
        download_interval_s=0.0,
    )


def _run_valuation_scout(run_dir: Path, delay_s: float, cohort_count: int) -> ValuationScoutRunSummary:
    (run_dir / "run_manifest.json").write_text(
        json.dumps({
            "run_id": "parallel-test-valuation-run",
            "cohorts": [
                {
                    "cohort_id": f"wpb-express-savana-2500-2017-2018-{i}",
                    "vehicle_family": "Chevrolet Express / GMC Savana 2500 cargo van",
                    "source_platform": "JJ Kane",
                    "listing_ids": ["1604992"],
                }
                for i in range(cohort_count)
            ],
        }),
        encoding="utf-8",
    )
    return run_valuation_scout_batch(
        run_dir,
        tavily=DelayedFakeTavily(delay_s),
        config=RunConfig(model="mini"),
    )


def test_branches_run_concurrently_without_interference(tmp_path):
    concurrent_condition_dir = tmp_path / "concurrent_condition_run"
    concurrent_valuation_dir = tmp_path / "concurrent_valuation_run"
    concurrent_condition_dir.mkdir()
    concurrent_valuation_dir.mkdir()

    concurrent_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        condition_future = pool.submit(_run_condition_scout, concurrent_condition_dir, CALL_DELAY_S)
        valuation_future = pool.submit(
            _run_valuation_scout, concurrent_valuation_dir, CALL_DELAY_S, VALUATION_COHORT_COUNT
        )
        condition_summary = condition_future.result()
        valuation_summary = valuation_future.result()
    concurrent_elapsed = time.perf_counter() - concurrent_start

    # both branches completed correctly and independently
    assert set(condition_summary.processed) == {"1619602", "4043486", "ED5334", "gd-7781"}
    assert len(valuation_summary.processed) == VALUATION_COHORT_COUNT
    assert valuation_summary.failed == []

    # artifacts landed in their own run folders only — no cross-talk
    assert (concurrent_condition_dir / "listings" / "1619602" / "condition_analysis.json").is_file()
    assert (concurrent_valuation_dir / "cohorts" / "wpb-express-savana-2500-2017-2018-0" / "cohort_research.json").is_file()
    assert not (concurrent_condition_dir / "cohorts").exists()
    assert not (concurrent_valuation_dir / "listings").exists()

    # the actual point of Stage 5 parallelism: neither branch waits on the
    # other. Measure the same two branches run sequentially (fresh dirs, same
    # delay) and assert the concurrent run is meaningfully faster than their
    # sum — i.e. genuinely overlapping wall-clock time, not just "both
    # eventually finish without crashing."
    sequential_condition_dir = tmp_path / "sequential_condition_run"
    sequential_valuation_dir = tmp_path / "sequential_valuation_run"
    sequential_condition_dir.mkdir()
    sequential_valuation_dir.mkdir()

    sequential_start = time.perf_counter()
    _run_condition_scout(sequential_condition_dir, CALL_DELAY_S)
    _run_valuation_scout(sequential_valuation_dir, CALL_DELAY_S, VALUATION_COHORT_COUNT)
    sequential_elapsed = time.perf_counter() - sequential_start

    assert concurrent_elapsed < sequential_elapsed * 0.85, (
        f"concurrent run ({concurrent_elapsed:.2f}s) was not meaningfully faster than "
        f"the same two branches run sequentially ({sequential_elapsed:.2f}s) - "
        "branches may be serializing on shared state instead of overlapping"
    )
