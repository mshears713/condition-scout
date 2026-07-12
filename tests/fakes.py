"""Shared test doubles: fixture-backed FakeHttp and a fake clock."""

from __future__ import annotations

from pathlib import Path

from condition_scout.http import HttpError, HttpResponse

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_bytes(relative: str) -> bytes:
    return (FIXTURES / relative).read_bytes()


class FakeHttp:
    """Maps exact URLs to canned responses (or exceptions to raise).

    Unmapped URLs return 404 — convenient for Purple Wave enumeration tests.
    Every request is recorded as (method, url)."""

    def __init__(self, routes: dict[str, HttpResponse | Exception] | None = None):
        self.routes: dict[str, HttpResponse | Exception] = routes or {}
        self.requests: list[tuple[str, str]] = []

    def add(self, url: str, body: bytes | str = b"", status: int = 200) -> None:
        content = body.encode() if isinstance(body, str) else body
        self.routes[url] = HttpResponse(status_code=status, content=content)

    def add_error(self, url: str, message: str = "simulated timeout") -> None:
        self.routes[url] = HttpError(message)

    def _respond(self, method: str, url: str) -> HttpResponse:
        self.requests.append((method, url))
        outcome = self.routes.get(url)
        if outcome is None:
            return HttpResponse(status_code=404)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def get(self, url: str) -> HttpResponse:
        return self._respond("GET", url)

    def head(self, url: str) -> HttpResponse:
        resp = self._respond("HEAD", url)
        return HttpResponse(status_code=resp.status_code)  # HEAD: no body


class FakeClock:
    """Deterministic clock + sleep recorder for pacing tests."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds
