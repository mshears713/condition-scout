"""PublicSurplus: GET /sms/auction/ajaxpicloader?auctionId={id} returns a
JS array of full-size CloudFront image URLs. No auth. Undocumented endpoint
discovered by the 2026-07-09 probe — could change.

The payload is JavaScript, not JSON, so URLs are extracted by pattern rather
than parsed structurally."""

from __future__ import annotations

import re

from condition_scout.manifest import ManifestListing

API_URL = (
    "https://www.publicsurplus.com/sms/auction/ajaxpicloader?auctionId={listing_id}"
)

_URL_RE = re.compile(r"https?://[^\s'\"\\,\]]+")


def resolve(listing: ManifestListing, http) -> list[str]:
    from condition_scout.resolvers import ResolveError

    resp = http.get(API_URL.format(listing_id=listing.listing_id))
    if not resp.ok:
        raise ResolveError(f"PublicSurplus picloader returned HTTP {resp.status_code}")
    # keep image URLs only, preserving payload order, de-duplicated
    seen: set[str] = set()
    urls: list[str] = []
    for url in _URL_RE.findall(resp.text):
        if url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls
