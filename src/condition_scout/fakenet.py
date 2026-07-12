"""Deterministic fake backends for `--fake-network` acceptance runs.

This mode exists so the full pipeline (manifest -> resolve -> download ->
analyze -> synthesize -> artifacts) can be exercised end-to-end with zero
network and zero secrets: resolvers see plausible endpoint responses, every
image URL serves a tiny valid JPEG, and the fake Gemini returns
deterministic, schema-valid records. Never used in real runs.
"""

from __future__ import annotations

import base64
import json
import re

from condition_scout.http import HttpResponse
from condition_scout.schema import ZONES

# A minimal valid 1x1 JPEG (same bytes as tests/fixtures/photos/sample_van.jpg).
_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oADAMB"
    "AAIRAxEAPwD3+iiigD//2Q=="
)
JPEG_BYTES = base64.b64decode(_JPEG_B64)

_JJKANE_RE = re.compile(r"jjkane\.com/api/items/(?P<id>[^/?]+)$")
_PS_RE = re.compile(r"publicsurplus\.com/sms/auction/ajaxpicloader\?auctionId=(?P<id>.+)$")
_PW_RE = re.compile(r"cloudfront\.net/i/a/\d{4}/\d{8}ve/[A-Za-z0-9]+(?P<letter>[A-Z])\.JPG$")

# The acceptance manifest uses this id to exercise the failure path.
FAILING_LISTING_ID = "404404"
FAKE_PW_PHOTO_COUNT = 3  # letters A..C exist


class FakeNetworkHttp:
    """Serves plausible resolver responses and JPEG bytes for any image URL."""

    def get(self, url: str) -> HttpResponse:
        match = _JJKANE_RE.search(url)
        if match:
            if match.group("id") == FAILING_LISTING_ID:
                return HttpResponse(status_code=404)
            body = json.dumps(
                {
                    "id": match.group("id"),
                    "imageCount": 3,
                    "imageUrls": [
                        f"https://prod.cdn.jjkane.com/{match.group('id')}-{n}"
                        for n in (1, 2, 3)
                    ],
                }
            )
            return HttpResponse(status_code=200, content=body.encode())
        match = _PS_RE.search(url)
        if match:
            urls = ",".join(
                f'"https://fake.cloudfront.net/auction/{match.group("id")}/IMG_{n:04d}.JPG"'
                for n in (1, 2)
            )
            return HttpResponse(
                status_code=200, content=f"var picArray = [{urls}];".encode()
            )
        # anything else is treated as an image URL
        return HttpResponse(status_code=200, content=JPEG_BYTES)

    def head(self, url: str) -> HttpResponse:
        match = _PW_RE.search(url)
        if match:
            exists = match.group("letter") in "ABC"[:FAKE_PW_PHOTO_COUNT]
            return HttpResponse(status_code=200 if exists else 404)
        return HttpResponse(status_code=200)


_FILENAME_RE = re.compile(r"(?:This photo's filename|Photo filename): (\S+)")


class FakeNetworkGemini:
    """Deterministic, schema-valid responses; no key, no quota, no network."""

    def __init__(self):
        self.calls_made = 0

    def generate(self, *, model: str, parts: list, response_schema: dict) -> str:
        self.calls_made += 1
        text = "\n".join(p for p in parts if isinstance(p, str))
        filenames = _FILENAME_RE.findall(text)
        if response_schema.get("type") == "array":
            return json.dumps(
                [self._record(name, i) for i, name in enumerate(filenames)]
            )
        if filenames:  # single-photo vision call
            record = self._record(filenames[0], self.calls_made)
            record.pop("photo", None)  # single mode omits photo; tool stamps it
            return json.dumps(record)
        return json.dumps(self._synthesis(text))

    @staticmethod
    def _record(filename: str, index: int) -> dict:
        zone = ZONES[index % len(ZONES)]
        return {
            "photo": filename,
            "view": zone,
            "photo_quality": "clear",
            "observations": [
                {
                    "noticed": f"{zone.replace('_', ' ')} appears intact with typical fleet wear",
                    "zone": zone,
                    "polarity": "positive",
                    "severity": "none",
                    "confidence": "medium",
                }
            ],
            "dash_warning_lights": ["none visible"] if zone == "dash_instruments" else None,
            "odometer_contradiction": None,
            "mismatch_note": None,
        }

    @staticmethod
    def _synthesis(text: str) -> dict:
        refs = re.findall(r'"photo":\s*"([^"]+)"', text) or ["photo_001.jpg"]
        return {
            "findings": [
                {
                    "zone": "cab_interior",
                    "polarity": "negative",
                    "description": "Typical fleet wear on the driver seat edge",
                    "severity": "minor",
                    "confidence": "medium",
                    "image_refs": [refs[0]],
                    "red_flag_hint": None,
                }
            ],
            "positives": [
                {
                    "description": "Body panels straight in all exterior views",
                    "confidence": "medium",
                    "image_refs": [refs[0]],
                }
            ],
            "adjustment_categories": [],
            "dash_evidence": {
                "warning_lights": ["none visible"],
                "odometer_visible": False,
                "odometer_reading": None,
                "image_refs": [],
            },
            "mismatch_flags": [],
            "overall": {
                "visual_grade": "good",
                "summary": (
                    "Work van showing typical fleet wear across the photographed "
                    "zones with no damage requiring repair visible."
                ),
                "confidence": "medium",
            },
        }
