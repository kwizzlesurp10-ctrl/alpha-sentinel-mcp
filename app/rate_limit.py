"""Simple per-IP rate limit for free/sample routes."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from app.config import settings

_windows: dict[str, deque[float]] = defaultdict(deque)


def allow_free_request(client_key: str, limit_per_min: int | None = None) -> bool:
    limit = limit_per_min or settings.free_tier_rate_limit_per_min
    now = time.time()
    window = _windows[client_key]
    while window and now - window[0] > 60.0:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def clear() -> None:
    _windows.clear()
