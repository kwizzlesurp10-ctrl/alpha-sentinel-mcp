"""Short TTL cache for free /sample tool responses."""

from __future__ import annotations

import time
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}
TTL_SECONDS = 120.0


def get(key: str) -> Any | None:
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None
    return value


def set(key: str, value: Any, ttl: float = TTL_SECONDS) -> None:
    _cache[key] = (time.time() + ttl, value)


def clear() -> None:
    _cache.clear()
