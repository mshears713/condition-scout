"""JJ Kane: GET www.jjkane.com/api/items/{id} -> imageUrls[] on a public CDN
(prod.cdn.jjkane.com/{id}-{n}). No auth, plain requests. Undocumented
endpoint discovered by the 2026-07-09 probe — could change."""

from __future__ import annotations

import json

from condition_scout.manifest import ManifestListing

API_URL = "https://www.jjkane.com/api/items/{listing_id}"


def resolve(listing: ManifestListing, http) -> list[str]:
    from condition_scout.resolvers import ResolveError

    resp = http.get(API_URL.format(listing_id=listing.listing_id))
    if not resp.ok:
        raise ResolveError(f"JJ Kane item API returned HTTP {resp.status_code}")
    try:
        data = json.loads(resp.text)
    except json.JSONDecodeError as exc:
        raise ResolveError(f"JJ Kane item API returned non-JSON: {exc}") from exc
    urls = data.get("imageUrls")
    if urls is None or not isinstance(urls, list):
        raise ResolveError("JJ Kane item API response has no imageUrls array")
    return [str(u) for u in urls]
