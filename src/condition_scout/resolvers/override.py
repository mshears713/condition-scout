"""Manifest override: pre-resolved photo URLs supplied by CoWork (or Mike).

This is the GovDeals path — full gallery URLs exist only in the
Akamai-guarded rendered DOM, so v0 never scrapes them — and the universal
escape hatch when a resolver breaks or a source is unknown."""

from __future__ import annotations

from condition_scout.manifest import ManifestListing


def resolve(listing: ManifestListing) -> list[str]:
    return list(listing.photo_urls or [])
