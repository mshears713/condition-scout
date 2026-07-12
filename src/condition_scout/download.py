"""Photo downloader: polite pacing, resumable, writes photo_manifest.json.

Individual photo failures are logged and skipped; a listing only fails at
this stage when zero photos could be downloaded."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from condition_scout.http import HttpError
from condition_scout.manifest import ManifestListing
from condition_scout.pacing import RatePacer
from condition_scout.schema import PhotoManifest, PhotoManifestEntry

logger = logging.getLogger(__name__)

DEFAULT_DOWNLOAD_INTERVAL_S = 0.5


class DownloadError(Exception):
    """No photos could be downloaded for a listing."""


def filename_for(order: int, url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        suffix = ".jpg"  # JJ Kane CDN serves extensionless JPEG URLs
    return f"photo_{order:03d}{suffix}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def download_photos(
    listing: ManifestListing,
    urls: list[str],
    listing_folder: Path,
    http,
    pacer: RatePacer | None = None,
) -> PhotoManifest:
    """Download photos into listing_folder/photos/ and write
    photo_manifest.json. Already-present files are skipped (resume)."""
    pacer = pacer or RatePacer(DEFAULT_DOWNLOAD_INTERVAL_S)
    photos_dir = listing_folder / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    entries: list[PhotoManifestEntry] = []
    for order, url in enumerate(urls, start=1):
        name = filename_for(order, url)
        target = photos_dir / name
        if target.exists() and target.stat().st_size > 0:
            entries.append(PhotoManifestEntry(order=order, filename=name, url=url))
            continue
        pacer.wait()
        try:
            resp = http.get(url)
        except HttpError as exc:
            logger.warning("photo %s of %s failed: %s", order, listing.listing_id, exc)
            continue
        if not resp.ok or not resp.content:
            logger.warning(
                "photo %s of %s: HTTP %s%s",
                order,
                listing.listing_id,
                resp.status_code,
                "" if resp.content else " (empty body)",
            )
            continue
        target.write_bytes(resp.content)
        entries.append(PhotoManifestEntry(order=order, filename=name, url=url))

    if not entries:
        raise DownloadError(
            f"none of {len(urls)} photos could be downloaded for "
            f"listing {listing.listing_id}"
        )

    manifest = PhotoManifest(
        listing_id=listing.listing_id,
        source=listing.source,
        downloaded_at=utc_now_iso(),
        photos=entries,
    )
    (listing_folder / "photo_manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return manifest
