"""Live-smoke tests (CI live-smoke job only): `pytest -m live`.

Quota-tiny by design — at most 5 requests per run (3 resolver probes, 1-2
Gemini calls including a possible repair retry), well under the <10 budget.

Skip rules:
- The Gemini test skips cleanly when GEMINI_API_KEY is absent (the affected
  Ledger item reverts to Deferred — a finding, not a failure).
- Resolver tests skip (not fail) when the endpoint answers but the probe
  listing is gone — auction listings are mortal; endpoint shape is what we
  are verifying. A dead/blocked endpoint fails the test: that is a finding.

Secret hygiene: nothing here prints response bodies or the key.
"""

from __future__ import annotations

import json
import os

import pytest

pytestmark = pytest.mark.live

# Probe subjects recorded 2026-07-09 (Engineering Plan §7).
JJKANE_ITEM = "1619602"
PS_AUCTION = "4043486"
PW_URL = "https://d323w7klwy72q3.cloudfront.net/i/a/2026/20260715ve/ED5334A.JPG"


@pytest.fixture(scope="module")
def http():
    from condition_scout.http import RequestsHttpClient

    return RequestsHttpClient(timeout_s=30)


def test_live_jjkane_item_api_shape(http):
    resp = http.get(f"https://www.jjkane.com/api/items/{JJKANE_ITEM}")
    if resp.status_code == 404:
        pytest.skip(f"JJ Kane item {JJKANE_ITEM} no longer exists (endpoint reachable)")
    assert resp.ok, f"JJ Kane item API returned HTTP {resp.status_code}"
    data = json.loads(resp.text)
    assert isinstance(data.get("imageUrls"), list)


def test_live_publicsurplus_picloader_shape(http):
    resp = http.get(
        "https://www.publicsurplus.com/sms/auction/ajaxpicloader"
        f"?auctionId={PS_AUCTION}"
    )
    if resp.status_code == 404:
        pytest.skip(f"PublicSurplus auction {PS_AUCTION} gone (endpoint reachable)")
    assert resp.ok, f"picloader returned HTTP {resp.status_code}"
    assert "http" in resp.text, "picloader payload contains no URLs"


def test_live_purplewave_cdn_pattern(http):
    resp = http.head(PW_URL)
    if resp.status_code in (403, 404):
        pytest.skip("Purple Wave probe lot photos no longer served (CDN reachable)")
    assert resp.ok, f"Purple Wave CDN returned HTTP {resp.status_code}"


@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY absent — live Gemini smoke reverts to Deferred",
)
def test_live_gemini_structured_output_single_photo(tmp_path):
    """One real Gemini call on a fixture photo, validated against the
    PhotoRecord contract — proves responseJsonSchema adherence end to end."""
    import shutil
    from pathlib import Path

    from condition_scout.analyzer import AnalyzerConfig, CallStats, analyze_photos
    from condition_scout.gemini import RealGeminiClient
    from condition_scout.manifest import ManifestListing
    from condition_scout.prompts import load_prompts
    from condition_scout.schema import PhotoManifest, PhotoManifestEntry

    fixture = Path(__file__).parent / "fixtures" / "photos" / "sample_van.jpg"
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    shutil.copyfile(fixture, photos_dir / "photo_001.jpg")

    listing = ManifestListing(
        listing_id="live-smoke",
        source="JJ Kane",
        listing_url="https://example.com/live-smoke",
        year=2016,
        platform="Ford Transit 250",
        mileage=128000,
    )
    manifest = PhotoManifest(
        listing_id="live-smoke",
        source="JJ Kane",
        downloaded_at="2026-07-10T00:00:00Z",
        photos=[
            PhotoManifestEntry(
                order=1, filename="photo_001.jpg", url="https://example.com/1.jpg"
            )
        ],
    )
    stats = CallStats()
    records = analyze_photos(
        listing, manifest, tmp_path,
        RealGeminiClient(), load_prompts(),
        AnalyzerConfig(),  # default model, per-photo mode
        stats=stats,
    )
    # pydantic validation inside analyze_photos IS the structured-output proof
    assert len(records) == 1
    assert records[0].photo == "photo_001.jpg"
    assert stats.calls <= 2  # one call, at most one repair retry
