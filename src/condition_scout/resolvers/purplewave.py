"""Purple Wave: predictable CloudFront pattern
    https://d323w7klwy72q3.cloudfront.net/i/a/{year}/{auction_id}ve/{lot_id}{L}.JPG
with photo letters A, B, C... — enumerate with HEAD until the first miss
(probe example: ED5334[A-I].JPG). The auction id (e.g. 20260715) comes from
the manifest's optional auction_id field, else is parsed from the listing URL;
year is its first four digits."""

from __future__ import annotations

import re
import string

from condition_scout.manifest import ManifestListing

CDN_BASE = "https://d323w7klwy72q3.cloudfront.net/i/a"
MAX_PHOTOS = 26  # one alphabet's worth

_AUCTION_ID_RE = re.compile(r"/(\d{8})(?:ve)?(?:/|$)")


def auction_id_for(listing: ManifestListing) -> str:
    from condition_scout.resolvers import ResolveError

    if listing.auction_id:
        return listing.auction_id
    match = _AUCTION_ID_RE.search(listing.listing_url)
    if match:
        return match.group(1)
    raise ResolveError(
        "Purple Wave listing needs an 8-digit auction id (manifest auction_id "
        f"field or in the listing URL); got {listing.listing_url!r}"
    )


def resolve(listing: ManifestListing, http) -> list[str]:
    auction_id = auction_id_for(listing)
    year = auction_id[:4]
    urls: list[str] = []
    for letter in string.ascii_uppercase[:MAX_PHOTOS]:
        url = f"{CDN_BASE}/{year}/{auction_id}ve/{listing.listing_id}{letter}.JPG"
        if not http.head(url).ok:
            break
        urls.append(url)
    return urls
