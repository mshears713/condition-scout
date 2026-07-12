"""Gemini client seam.

The analyzer talks to this tiny interface; tests substitute FakeGemini and
the real client wraps the google-genai SDK. Per the Analysis Prompt Spec:
temperature 0, thinking off, JSON output enforced via responseJsonSchema.

Client contract: `generate(model=..., parts=..., response_schema=...)`
returns the response text, raising RateLimitError on 429 and GeminiError on
any other API failure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class GeminiError(Exception):
    """Non-retryable API failure."""


class RateLimitError(GeminiError):
    """HTTP 429 — retried with exponential backoff by the analyzer."""


@dataclass
class ImagePart:
    data: bytes
    mime_type: str = "image/jpeg"


# Parts of a call: prompt text (str) or an image.
Part = "str | ImagePart"


def mime_type_for(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


class RealGeminiClient:
    """google-genai SDK wrapper. Requires GEMINI_API_KEY in the environment
    or in a local .env file at the repo root (never logged, never
    committed — see .gitignore)."""

    def __init__(self, api_key: str | None = None):
        from google import genai

        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiError(
                "GEMINI_API_KEY is not set; real Gemini calls are impossible"
            )
        self._client = genai.Client(api_key=key)

    def generate(self, *, model: str, parts: list, response_schema: dict) -> str:
        from google.genai import errors, types

        contents = [
            types.Part.from_bytes(data=p.data, mime_type=p.mime_type)
            if isinstance(p, ImagePart)
            else p
            for p in parts
        ]
        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=response_schema,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        try:
            response = self._client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except errors.APIError as exc:
            if getattr(exc, "code", None) == 429:
                raise RateLimitError(f"Gemini rate limit: {exc}") from exc
            raise GeminiError(f"Gemini API error: {exc}") from exc
        if response.text is None:
            raise GeminiError("Gemini returned an empty response")
        return response.text
