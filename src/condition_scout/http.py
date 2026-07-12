"""Thin HTTP seam so resolvers and the downloader are fake-first testable.

The real client wraps requests with a browser-like User-Agent (the probe
showed all three automated sources serve plain requests). Tests substitute a
fixture-backed fake; nothing above this module imports requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
DEFAULT_TIMEOUT_S = 30


class HttpError(Exception):
    """Network-level failure (timeout, connection refused, TLS...)."""


@dataclass
class HttpResponse:
    status_code: int
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class RequestsHttpClient:
    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._timeout_s = timeout_s

    def _request(self, method: str, url: str) -> HttpResponse:
        try:
            resp = self._session.request(method, url, timeout=self._timeout_s)
        except requests.RequestException as exc:
            raise HttpError(f"{method} {url} failed: {exc}") from exc
        return HttpResponse(
            status_code=resp.status_code,
            content=resp.content,
            headers=dict(resp.headers),
        )

    def get(self, url: str) -> HttpResponse:
        return self._request("GET", url)

    def head(self, url: str) -> HttpResponse:
        return self._request("HEAD", url)
