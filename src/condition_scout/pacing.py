"""Polite pacing for CDN downloads and free-tier RPM limits.

Injectable clock/sleep so tests never actually wait.
"""

from __future__ import annotations

import time
from typing import Callable


class RatePacer:
    """Enforces a minimum interval between successive `wait()` returns."""

    def __init__(
        self,
        min_interval_s: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.min_interval_s = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    @classmethod
    def per_minute(cls, rpm: int, **kwargs) -> "RatePacer":
        return cls(60.0 / rpm, **kwargs)

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            remaining = self.min_interval_s - (now - self._last)
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()
        self._last = now
