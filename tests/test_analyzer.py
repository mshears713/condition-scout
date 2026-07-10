"""M3 analyzer tests: prompt loading, call assembly (both modes), pacing,
429 backoff, malformed-JSON repair, truncation, failure, resume-skip."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from condition_scout.analyzer import (
    REPAIR_INSTRUCTION,
    AnalysisFailure,
    AnalyzerConfig,
    CallStats,
    analyze_photos,
    has_valid_analysis,
    synthesize,
)
from condition_scout.gemini import ImagePart, RateLimitError
from condition_scout.manifest import ManifestListing
from condition_scout.pacing import RatePacer
from condition_scout.prompts import PromptError, fill_template, load_prompts
from condition_scout.schema import PhotoManifest, PhotoManifestEntry
from tests.fake_gemini import (
    FakeGemini,
    photo_record_json,
    synthesis_result_json,
)
from tests.fakes import FakeClock, FIXTURES

SAMPLE_JPG = FIXTURES / "photos" / "sample_van.jpg"


@pytest.fixture(scope="module")
def prompts():
    return load_prompts()


def listing() -> ManifestListing:
    return ManifestListing(
        listing_id="1619602",
        source="JJ Kane",
        listing_url="https://www.jjkane.com/item/1619602",
        year=2016,
        platform="Ford Transit 250",
        mileage=128000,
    )


def make_run(tmp_path: Path, n_photos: int) -> tuple[Path, PhotoManifest]:
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for i in range(1, n_photos + 1):
        name = f"photo_{i:03d}.jpg"
        shutil.copyfile(SAMPLE_JPG, photos_dir / name)
        entries.append(
            PhotoManifestEntry(
                order=i, filename=name, url=f"https://cdn.example/{i}"
            )
        )
    manifest = PhotoManifest(
        listing_id="1619602",
        source="JJ Kane",
        downloaded_at="2026-07-10T15:00:00Z",
        photos=entries,
    )
    return tmp_path, manifest


def fast_pacer() -> RatePacer:
    clock = FakeClock()
    return RatePacer(0, clock=clock.clock, sleep=clock.sleep)


def no_sleep(_: float) -> None:
    pass


# --- prompt loading ----------------------------------------------------------

def test_load_prompts_version_and_header_stripping(prompts):
    assert prompts.version == "0.2"
    for template in (prompts.photo_template, prompts.synthesis_template):
        assert "Synced copy" not in template  # provenance header stripped
    assert "[PHOTO]" in prompts.photo_template
    assert "[PHOTO_OBSERVATIONS]" in prompts.synthesis_template
    assert "warning lights" in prompts.photo_template


def test_load_prompts_missing_dir_raises(tmp_path):
    with pytest.raises(PromptError, match="no photo_prompt"):
        load_prompts(tmp_path)


def test_fill_template_substitutes_context():
    filled = fill_template(
        "Vehicle: {YEAR} {PLATFORM} cargo van, listed at {MILEAGE} miles.",
        year=2016, platform="Ford Transit 250", mileage=128000,
    )
    assert filled == "Vehicle: 2016 Ford Transit 250 cargo van, listed at 128,000 miles."
    unknown = fill_template("{YEAR} {PLATFORM} {MILEAGE}", year=None, platform=None, mileage=None)
    assert unknown == "unknown-year unknown-platform unknown"


# --- call assembly: per-photo default mode ----------------------------------

def test_single_mode_one_call_per_photo_with_context(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 3)
    fake = FakeGemini(script=[photo_record_json() for _ in range(3)])
    records = analyze_photos(
        listing(), manifest, folder, fake, prompts,
        AnalyzerConfig(photos_per_call=1), pacer=fast_pacer(), sleep=no_sleep,
    )
    assert len(fake.calls) == 3
    call = fake.calls[0]
    assert call.model == "gemini-2.5-flash-lite"
    text_parts = [p for p in call.parts if isinstance(p, str)]
    images = [p for p in call.parts if isinstance(p, ImagePart)]
    assert len(images) == 1
    assert images[0].data == SAMPLE_JPG.read_bytes()
    assert images[0].mime_type == "image/jpeg"
    joined = "\n".join(text_parts)
    assert "2016 Ford Transit 250 cargo van, listed at 128,000 miles" in joined
    assert "photo_001.jpg" in joined
    assert "photo" not in call.response_schema.get("required", [])
    # filenames stamped from the manifest, not trusted from the model
    assert [r.photo for r in records] == ["photo_001.jpg", "photo_002.jpg", "photo_003.jpg"]


def test_single_mode_prompt_version_survives(prompts):
    # the loaded pack version is what gets stamped into artifacts (M4 wires it)
    assert prompts.version == "0.2"


# --- call assembly: grouped fallback mode ------------------------------------

def test_grouped_mode_batches_photos(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 5)
    batch = json.dumps(
        [json.loads(photo_record_json(photo=f"photo_{i:03d}.jpg")) for i in range(1, 6)]
    )
    fake = FakeGemini(script=[batch])
    records = analyze_photos(
        listing(), manifest, folder, fake, prompts,
        AnalyzerConfig(photos_per_call=5), pacer=fast_pacer(), sleep=no_sleep,
    )
    assert len(fake.calls) == 1
    call = fake.calls[0]
    images = [p for p in call.parts if isinstance(p, ImagePart)]
    assert len(images) == 5
    assert call.response_schema["type"] == "array"
    assert [r.photo for r in records] == [f"photo_{i:03d}.jpg" for i in range(1, 6)]


def test_grouped_mode_wrong_record_count_triggers_repair_then_fails(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 3)
    short = json.dumps(
        [json.loads(photo_record_json(photo=f"photo_{i:03d}.jpg")) for i in range(1, 3)]
    )
    fake = FakeGemini(script=[short, short])
    with pytest.raises(AnalysisFailure, match="twice"):
        analyze_photos(
            listing(), manifest, folder, fake, prompts,
            AnalyzerConfig(photos_per_call=3), pacer=fast_pacer(), sleep=no_sleep,
        )
    assert len(fake.calls) == 2


def test_grouped_mode_batches_split_correctly(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 7)  # 5 + 2 with photos_per_call=5
    def batch_json(filenames):
        return json.dumps(
            [json.loads(photo_record_json(photo=f)) for f in filenames]
        )
    fake = FakeGemini(script=[
        batch_json([f"photo_{i:03d}.jpg" for i in range(1, 6)]),
        batch_json([f"photo_{i:03d}.jpg" for i in range(6, 8)]),
    ])
    records = analyze_photos(
        listing(), manifest, folder, fake, prompts,
        AnalyzerConfig(photos_per_call=5), pacer=fast_pacer(), sleep=no_sleep,
    )
    assert len(fake.calls) == 2
    assert len(records) == 7


# --- 429 backoff --------------------------------------------------------------

def test_rate_limit_backoff_then_success(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 1)
    fake = FakeGemini(
        script=[RateLimitError("429"), RateLimitError("429"), photo_record_json()]
    )
    stats = CallStats()
    sleeps: list[float] = []
    records = analyze_photos(
        listing(), manifest, folder, fake, prompts,
        AnalyzerConfig(), pacer=fast_pacer(), stats=stats, sleep=sleeps.append,
    )
    assert len(records) == 1
    assert stats.calls == 3  # retries burn quota and are counted
    assert sleeps == [2.0, 4.0]  # exponential backoff


def test_rate_limit_exhaustion_fails_listing(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 1)
    fake = FakeGemini(script=[RateLimitError("429")] * 5)
    with pytest.raises(AnalysisFailure, match="rate-limited after 5 attempts"):
        analyze_photos(
            listing(), manifest, folder, fake, prompts,
            AnalyzerConfig(max_rate_limit_retries=4),
            pacer=fast_pacer(), sleep=no_sleep,
        )


# --- malformed / truncated output ---------------------------------------------

def test_malformed_json_repaired_once(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 1)
    fake = FakeGemini(script=["I looked at the photo and", photo_record_json()])
    records = analyze_photos(
        listing(), manifest, folder, fake, prompts,
        AnalyzerConfig(), pacer=fast_pacer(), sleep=no_sleep,
    )
    assert len(records) == 1
    assert len(fake.calls) == 2
    assert REPAIR_INSTRUCTION in fake.calls[1].parts  # repair note appended


def test_truncated_json_repaired_once(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 1)
    truncated = photo_record_json()[:40]
    fake = FakeGemini(script=[truncated, photo_record_json()])
    records = analyze_photos(
        listing(), manifest, folder, fake, prompts,
        AnalyzerConfig(), pacer=fast_pacer(), sleep=no_sleep,
    )
    assert len(records) == 1


def test_malformed_twice_fails_listing(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 1)
    fake = FakeGemini(script=["garbage", "still garbage"])
    with pytest.raises(AnalysisFailure) as excinfo:
        analyze_photos(
            listing(), manifest, folder, fake, prompts,
            AnalyzerConfig(), pacer=fast_pacer(), sleep=no_sleep,
        )
    assert excinfo.value.stage == "analyze"


def test_schema_violation_counts_as_malformed(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 1)
    bad = json.dumps({"view": "exterior_front"})  # missing required fields
    fake = FakeGemini(script=[bad, photo_record_json()])
    records = analyze_photos(
        listing(), manifest, folder, fake, prompts,
        AnalyzerConfig(), pacer=fast_pacer(), sleep=no_sleep,
    )
    assert len(records) == 1


# --- RPM pacing -----------------------------------------------------------------

def test_rpm_pacing_between_calls(tmp_path, prompts):
    folder, manifest = make_run(tmp_path, 3)
    clock = FakeClock()
    pacer = RatePacer.per_minute(10, clock=clock.clock, sleep=clock.sleep)
    fake = FakeGemini(script=[photo_record_json() for _ in range(3)])
    analyze_photos(
        listing(), manifest, folder, fake, prompts,
        AnalyzerConfig(rpm=10), pacer=pacer, sleep=no_sleep,
    )
    assert clock.sleeps == [6.0, 6.0]  # 10 rpm -> 6s between calls


# --- synthesis -------------------------------------------------------------------

def test_synthesize_happy_path(prompts):
    fake = FakeGemini(script=[synthesis_result_json()])
    records = [
        json.loads(photo_record_json())
    ]
    from condition_scout.schema import PhotoRecord

    recs = [PhotoRecord.model_validate({**records[0], "photo": "photo_001.jpg"})]
    result = synthesize(
        listing(), recs, fake, prompts, AnalyzerConfig(),
        pacer=fast_pacer(), sleep=no_sleep,
    )
    assert result.overall.visual_grade == "serviceable"
    call = fake.calls[0]
    assert all(isinstance(p, str) for p in call.parts)  # text-only, no photos
    assert "photo_001.jpg" in call.parts[0]  # observations embedded
    assert "[PHOTO_OBSERVATIONS]" not in call.parts[0]


def test_synthesize_failure_stage_is_synthesize(prompts):
    from condition_scout.schema import PhotoRecord

    rec = PhotoRecord.model_validate(
        {**json.loads(photo_record_json()), "photo": "photo_001.jpg"}
    )
    fake = FakeGemini(script=["junk", "junk"])
    with pytest.raises(AnalysisFailure) as excinfo:
        synthesize(
            listing(), [rec], fake, prompts, AnalyzerConfig(),
            pacer=fast_pacer(), sleep=no_sleep,
        )
    assert excinfo.value.stage == "synthesize"


# --- resume-skip ------------------------------------------------------------------

def test_has_valid_analysis(tmp_path):
    golden = Path(__file__).parent / "golden" / "condition_analysis.json"
    assert not has_valid_analysis(tmp_path)  # missing
    target = tmp_path / "condition_analysis.json"
    target.write_text('{"broken": true}')
    assert not has_valid_analysis(tmp_path)  # invalid
    target.write_text(golden.read_text())
    assert has_valid_analysis(tmp_path)  # valid
