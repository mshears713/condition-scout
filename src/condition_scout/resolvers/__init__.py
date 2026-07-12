"""Per-source photo-URL resolvers.

Each resolver returns an ordered list of photo URLs for one listing.
A manifest-supplied `photo_urls` override always wins (the GovDeals path,
and the escape hatch for any resolver breakage). Unknown source without
override URLs => SkipListing; the batch continues.
"""

from __future__ import annotations

from condition_scout.manifest import ManifestListing, normalize_source
from condition_scout.resolvers import jjkane, override, publicsurplus, purplewave


class ResolveError(Exception):
    """Photo URL resolution failed for one listing (recorded, not fatal)."""


class SkipListing(Exception):
    """Listing cannot be processed by design (e.g. unknown source, no
    override URLs, empty gallery) — recorded as skipped, not failed."""


_RESOLVERS = {
    "jjkane": jjkane.resolve,
    "publicsurplus": publicsurplus.resolve,
    "purplewave": purplewave.resolve,
}


def resolve_photo_urls(listing: ManifestListing, http) -> list[str]:
    if listing.photo_urls:
        return override.resolve(listing)

    resolver = _RESOLVERS.get(normalize_source(listing.source))
    if resolver is None:
        raise SkipListing(
            f"source {listing.source!r} has no resolver and the manifest "
            "supplied no photo_urls override"
        )
    urls = resolver(listing, http)
    if not urls:
        raise SkipListing(f"no photos found for {listing.source} listing")
    return urls
