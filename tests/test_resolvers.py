"""M2 resolver tests against recorded-shape fixtures, incl. error paths."""

from __future__ import annotations

import pytest

from condition_scout.manifest import ManifestListing
from condition_scout.resolvers import ResolveError, SkipListing, resolve_photo_urls
from tests.fakes import FakeHttp, fixture_bytes

JJKANE_API = "https://www.jjkane.com/api/items/1619602"
PS_API = "https://www.publicsurplus.com/sms/auction/ajaxpicloader?auctionId=4043486"
PW_BASE = "https://d323w7klwy72q3.cloudfront.net/i/a/2026/20260715ve"


def listing(source: str, listing_id: str, **kwargs) -> ManifestListing:
    return ManifestListing(
        listing_id=listing_id,
        source=source,
        listing_url=kwargs.pop("listing_url", f"https://example.com/{listing_id}"),
        **kwargs,
    )


# --- JJ Kane -----------------------------------------------------------------

def test_jjkane_resolves_image_urls_in_order():
    http = FakeHttp()
    http.add(JJKANE_API, fixture_bytes("http/jjkane_item_1619602.json"))
    urls = resolve_photo_urls(listing("JJ Kane", "1619602"), http)
    assert urls == [
        "https://prod.cdn.jjkane.com/1619602-1",
        "https://prod.cdn.jjkane.com/1619602-2",
        "https://prod.cdn.jjkane.com/1619602-3",
    ]


def test_jjkane_404_is_resolve_error():
    with pytest.raises(ResolveError, match="HTTP 404"):
        resolve_photo_urls(listing("JJ Kane", "1619602"), FakeHttp())


def test_jjkane_non_json_is_resolve_error():
    http = FakeHttp()
    http.add(JJKANE_API, "<html>maintenance</html>")
    with pytest.raises(ResolveError, match="non-JSON"):
        resolve_photo_urls(listing("JJ Kane", "1619602"), http)


def test_jjkane_missing_image_urls_is_resolve_error():
    http = FakeHttp()
    http.add(JJKANE_API, '{"id": 1619602}')
    with pytest.raises(ResolveError, match="no imageUrls"):
        resolve_photo_urls(listing("JJ Kane", "1619602"), http)


def test_jjkane_empty_gallery_is_skip():
    http = FakeHttp()
    http.add(JJKANE_API, '{"id": 1619602, "imageUrls": []}')
    with pytest.raises(SkipListing, match="no photos"):
        resolve_photo_urls(listing("JJ Kane", "1619602"), http)


# --- PublicSurplus -----------------------------------------------------------

def test_publicsurplus_extracts_cloudfront_urls_from_js_payload():
    http = FakeHttp()
    http.add(PS_API, fixture_bytes("http/publicsurplus_picloader_4043486.txt"))
    urls = resolve_photo_urls(listing("PublicSurplus", "4043486"), http)
    assert len(urls) == 4
    assert urls[0].endswith("IMG_0001.JPG")
    assert all(u.startswith("https://") for u in urls)


def test_publicsurplus_error_status_is_resolve_error():
    http = FakeHttp()
    http.add(PS_API, "server error", status=500)
    with pytest.raises(ResolveError, match="HTTP 500"):
        resolve_photo_urls(listing("PublicSurplus", "4043486"), http)


def test_publicsurplus_payload_without_urls_is_skip():
    http = FakeHttp()
    http.add(PS_API, "var picArray = [];")
    with pytest.raises(SkipListing):
        resolve_photo_urls(listing("PublicSurplus", "4043486"), http)


# --- Purple Wave -------------------------------------------------------------

def purple_listing(**kwargs) -> ManifestListing:
    return listing(
        "Purple Wave",
        "ED5334",
        listing_url="https://www.purplewave.com/auction/20260715/item/ED5334",
        **kwargs,
    )


def test_purplewave_enumerates_until_first_miss():
    http = FakeHttp()
    for letter in "ABCDEFGHI":  # probe example: ED5334[A-I].JPG
        http.add(f"{PW_BASE}/ED5334{letter}.JPG")
    urls = resolve_photo_urls(purple_listing(), http)
    assert len(urls) == 9
    assert urls[0] == f"{PW_BASE}/ED5334A.JPG"
    assert urls[-1] == f"{PW_BASE}/ED5334I.JPG"
    # enumeration used HEAD, stopped at the first 404 (A..I hits + J miss)
    assert all(m == "HEAD" for m, _ in http.requests)
    assert len(http.requests) == 10


def test_purplewave_uses_manifest_auction_id_over_url():
    http = FakeHttp()
    http.add("https://d323w7klwy72q3.cloudfront.net/i/a/2025/20251101ve/ED5334A.JPG")
    urls = resolve_photo_urls(
        purple_listing(auction_id="20251101"), http
    )
    assert len(urls) == 1


def test_purplewave_no_photos_is_skip():
    with pytest.raises(SkipListing, match="no photos"):
        resolve_photo_urls(purple_listing(), FakeHttp())


def test_purplewave_unparseable_auction_id_is_resolve_error():
    bad = listing("Purple Wave", "ED5334", listing_url="https://www.purplewave.com/item/ED5334")
    with pytest.raises(ResolveError, match="auction id"):
        resolve_photo_urls(bad, FakeHttp())


# --- override path (GovDeals) ------------------------------------------------

def test_override_urls_win_without_any_http():
    http = FakeHttp()
    urls = resolve_photo_urls(
        listing(
            "GovDeals",
            "gd-7781",
            photo_urls=[
                "https://webassets.lqdt1.com/images/aaaa1111-1.jpg",
                "https://webassets.lqdt1.com/images/aaaa1111-2.jpg",
            ],
        ),
        http,
    )
    assert len(urls) == 2
    assert http.requests == []  # override never touches the network


def test_override_beats_known_source_resolver():
    http = FakeHttp()
    urls = resolve_photo_urls(
        listing("JJ Kane", "1619602", photo_urls=["https://x.example/1.jpg"]),
        http,
    )
    assert urls == ["https://x.example/1.jpg"]
    assert http.requests == []


def test_unknown_source_without_override_is_skip():
    with pytest.raises(SkipListing, match="no resolver"):
        resolve_photo_urls(listing("GSA Auctions", "z1"), FakeHttp())
