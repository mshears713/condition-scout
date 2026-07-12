"""Tavily Research API client seam.

The orchestrator talks to this tiny interface; tests substitute FakeTavily
and the real client wraps `requests` directly (per the AI-OS record: call
Tavily directly from Python, no SDK). Plain REST, verified live against the
real API on 2026-07-12 (several details differ from Tavily's published
docs — noted below):

  POST /research   -> live: HTTP 200 (docs say 201) {request_id, status:
                      "pending", ...}. This client accepts both 200 and 201.
  GET  /research/{request_id}
       -> 202 {status: "pending" | "in_progress"} while running
       -> 200 {status: "completed", content, sources[]} on success
       -> 200 {status: "failed"} on failure

  output_schema must contain ONLY "properties" and "required" at the top
  level (not just "type" — "$defs"/"title"/"additionalProperties" are also
  rejected, at any nesting depth) with HTTP 400 ("Output schema contains
  unexpected keys"), which is stricter than the docs state. Every property,
  including nested objects, must carry its own "description" or the request
  400s. Nullable fields cannot use JSON Schema's "type": [T, "null"] list
  form at all ("Union types ... are not supported - use a single type") —
  this is a genuine conflict with the approved v0.2 contract, which
  specifies exactly that form; see the long comment in schema._inline_refs
  for how it's resolved (collapsed to a single type on the wire request
  only). See schema.tavily_output_schema() and schema._inline_refs() for how
  ResearchContent's pydantic schema (which naturally uses $ref/$defs) is
  adapted to Tavily's actual accepted shape.

GET polling does not count against Tavily's rate limits (per Tavily's own
guidance), so a short fixed poll interval is safe. No poll-interval or
timeout guidance is documented by Tavily; the defaults below are this
implementation's choice, not a pinned API behavior.

Client contract: `run(input=..., model=..., output_schema=...)` returns the
completed response dict (with `content` and `sources`), raising
TavilyTaskFailed if Tavily reports status "failed" and TavilyTimeout if the
task never completes within `timeout_s`.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://api.tavily.com"
DEFAULT_POLL_INTERVAL_S = 5.0
DEFAULT_TIMEOUT_S = 900.0  # 15 minutes


class TavilyError(Exception):
    """Non-retryable API failure (auth, bad request, rate limit, server error)."""


class TavilyTaskFailed(TavilyError):
    """Tavily reported status "failed" for a research task."""


class TavilyTimeout(TavilyError):
    """Polling exceeded timeout_s without the task reaching a terminal state."""


@dataclass
class TavilyResult:
    request_id: str
    content: dict | str
    sources: list[dict]
    raw: dict


class RealTavilyClient:
    """Thin `requests` wrapper. Requires TAVILY_API_KEY in the environment
    or in a local .env file at the repo root (never logged, never
    committed — see .gitignore)."""

    def __init__(self, api_key: str | None = None, base_url: str = DEFAULT_BASE_URL):
        key = api_key or os.environ.get("TAVILY_API_KEY")
        if not key:
            raise TavilyError(
                "TAVILY_API_KEY is not set; real Tavily calls are impossible"
            )
        self._api_key = key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def create_task(
        self,
        *,
        input: str,
        model: str,
        output_schema: dict,
        output_length: str = "long",
    ) -> str:
        import requests

        body = {
            "input": input,
            "model": model,
            "output_schema": output_schema,
            "output_length": output_length,
        }
        try:
            resp = requests.post(
                f"{self._base_url}/research",
                headers=self._headers(),
                json=body,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise TavilyError(f"POST /research failed: {exc}") from exc
        # Tavily's docs say 201; the live API actually returns 200 with a
        # {"status": "pending", ...} body (confirmed 2026-07-12). Accept both.
        if resp.status_code not in (200, 201):
            raise TavilyError(
                f"POST /research returned HTTP {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()
        request_id = data.get("request_id")
        if not request_id:
            raise TavilyError(f"POST /research response missing request_id: {data}")
        return request_id

    def get_status(self, request_id: str) -> dict:
        import requests

        try:
            resp = requests.get(
                f"{self._base_url}/research/{request_id}",
                headers=self._headers(),
                timeout=30,
            )
        except requests.RequestException as exc:
            raise TavilyError(f"GET /research/{request_id} failed: {exc}") from exc
        if resp.status_code not in (200, 202):
            raise TavilyError(
                f"GET /research/{request_id} returned HTTP {resp.status_code}: "
                f"{resp.text[:500]}"
            )
        return resp.json()

    def run(
        self,
        *,
        input: str,
        model: str,
        output_schema: dict,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> TavilyResult:
        request_id = self.create_task(
            input=input, model=model, output_schema=output_schema
        )
        deadline = clock() + timeout_s
        while True:
            data = self.get_status(request_id)
            status = data.get("status")
            if status == "completed":
                return TavilyResult(
                    request_id=request_id,
                    content=data.get("content"),
                    sources=data.get("sources", []),
                    raw=data,
                )
            if status == "failed":
                raise TavilyTaskFailed(
                    f"Tavily research task {request_id} failed: {data}"
                )
            if clock() >= deadline:
                raise TavilyTimeout(
                    f"Tavily research task {request_id} did not complete within "
                    f"{timeout_s}s (last status: {status})"
                )
            sleep(poll_interval_s)
