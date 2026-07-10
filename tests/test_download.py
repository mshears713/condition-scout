"""M2 downloader tests: pacing, resume, per-photo failure tolerance."""

from __future__ import annotations

import json

import pytest

from condition_scout.download import DownloadError, download_photos, filename_for
from condition_scout.manifest import ManifestListing
from condition_scout.pacing import RatePacer
from tests.fakes import FakeClock, FakeHttp

JPEG = b"\xff\xd8\xff\xdb fake jpeg bytes \xff\xd9"


def listing() -> ManifestListing:
    return ManifestListing(
        listing_id="1619602",
        source="JJ Kane",
        listing_url="https://www.jjkane.com/item/1619602",
    )


def urls(n: int) -> list[str]:
    return [f"https://prod.cdn.jjkane.com/1619602-{i}" for i in range(1, n + 1)]


def make_pacer(clock: FakeClock, interval: float = 0.5) -> RatePacer:
    return RatePacer(interval, clock=clock.clock, sleep=clock.sleep)


def test_download_writes_photos_and_manifest(tmp_path):
    http = FakeHttp()
    for u in urls(3):
        http.add(u, JPEG)
    manifest = download_photos(listing(), urls(3), tmp_path, http, make_pacer(FakeClock()))

    assert [p.filename for p in manifest.photos] == [
        "photo_001.jpg", "photo_002.jpg", "photo_003.jpg",
    ]
    for entry in manifest.photos:
        assert (tmp_path / "photos" / entry.filename).read_bytes() == JPEG
    on_disk = json.loads((tmp_path / "photo_manifest.json").read_text())
    assert on_disk["listing_id"] == "1619602"
    assert [p["url"] for p in on_disk["photos"]] == urls(3)


def test_filename_extension_handling():
    assert filename_for(1, "https://cdn.example/a/IMG_1.JPG") == "photo_001.jpg"
    assert filename_for(12, "https://cdn.example/a/x.png") == "photo_012.png"
    # JJ Kane CDN URLs are extensionless -> default .jpg
    assert filename_for(3, "https://prod.cdn.jjkane.com/1619602-3") == "photo_003.jpg"


def test_download_paces_between_requests():
    clock = FakeClock()
    http = FakeHttp()
    for u in urls(3):
        http.add(u, JPEG)
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        download_photos(listing(), urls(3), Path(tmp), http, make_pacer(clock, 0.5))
    # first request immediate, then one pace per subsequent request
    assert clock.sleeps == [0.5, 0.5]


def test_download_resume_skips_existing_files(tmp_path):
    http = FakeHttp()
    for u in urls(3):
        http.add(u, JPEG)
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "photo_001.jpg").write_bytes(JPEG)

    manifest = download_photos(listing(), urls(3), tmp_path, http, make_pacer(FakeClock()))
    assert len(manifest.photos) == 3
    fetched = [u for _, u in http.requests]
    assert urls(1)[0] not in fetched  # photo_001 not re-fetched
    assert len(fetched) == 2


def test_download_tolerates_partial_failures(tmp_path):
    http = FakeHttp()
    good = urls(3)
    http.add(good[0], JPEG)
    http.add_error(good[1], "simulated timeout")
    # good[2] unmapped -> 404
    manifest = download_photos(listing(), good, tmp_path, http, make_pacer(FakeClock()))
    assert [p.filename for p in manifest.photos] == ["photo_001.jpg"]
    assert (tmp_path / "photo_manifest.json").exists()


def test_download_all_failed_raises(tmp_path):
    http = FakeHttp()  # everything 404s
    with pytest.raises(DownloadError, match="none of 2 photos"):
        download_photos(listing(), urls(2), tmp_path, http, make_pacer(FakeClock()))


def test_pacer_no_sleep_when_calls_are_slow():
    clock = FakeClock()
    pacer = RatePacer(0.5, clock=clock.clock, sleep=clock.sleep)
    pacer.wait()
    clock.advance(1.0)  # more than the interval elapsed on its own
    pacer.wait()
    assert clock.sleeps == []
