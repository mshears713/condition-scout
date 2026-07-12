"""FakeGemini: a scripted Gemini client for the M3 behavior matrix.

Script entries are either a response string (returned as the model output)
or an exception instance (raised). Every call is recorded with its model,
parts, and response schema so tests can assert on call assembly."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class RecordedCall:
    model: str
    parts: list
    response_schema: dict


@dataclass
class FakeGemini:
    script: list = field(default_factory=list)
    calls: list = field(default_factory=list)

    def generate(self, *, model: str, parts: list, response_schema: dict) -> str:
        self.calls.append(RecordedCall(model, parts, response_schema))
        if not self.script:
            raise AssertionError("FakeGemini script exhausted")
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def photo_record_dict(
    view: str = "exterior_front",
    noticed: str = "Front bumper straight, no visible damage",
    polarity: str = "positive",
    severity: str = "none",
    **extra,
):
    return {
        "view": view,
        "photo_quality": "clear",
        "observations": [
            {
                "noticed": noticed,
                "zone": view.split()[0].rstrip("—-: "),
                "polarity": polarity,
                "severity": severity,
                "confidence": "high",
            }
        ],
        "dash_warning_lights": None,
        "odometer_contradiction": None,
        "mismatch_note": None,
        **extra,
    }


def photo_record_json(**kwargs) -> str:
    return json.dumps(photo_record_dict(**kwargs))


def synthesis_result_dict():
    return {
        "findings": [
            {
                "zone": "cab_interior",
                "polarity": "negative",
                "description": "Driver seat bottom heavily torn with exposed foam",
                "severity": "heavy",
                "confidence": "high",
                "image_refs": ["photo_001.jpg"],
                "red_flag_hint": "Interior / Cargo Roughness",
            }
        ],
        "positives": [
            {
                "description": "Straight body panels",
                "confidence": "medium",
                "image_refs": ["photo_001.jpg"],
            }
        ],
        "dash_evidence": {
            "warning_lights": ["none visible"],
            "odometer_visible": False,
            "odometer_reading": None,
            "image_refs": [],
        },
        "mismatch_flags": [],
        "overall": {
            "visual_grade": "serviceable",
            "summary": "Work van with a torn driver seat and typical fleet wear.",
            "confidence": "medium",
        },
    }


def synthesis_result_json() -> str:
    return json.dumps(synthesis_result_dict())
