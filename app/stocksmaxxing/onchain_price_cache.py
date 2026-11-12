"""Short TTL cache for onchain price lookups (peg-gap dashboard)."""

from __future__ import annotations

import time
from typing import Any, TypeVar

T = TypeVar("T")

_store: dict[str, tuple[float, Any]] = {}


def get_cached(key: str, ttl_seconds: int) -> Any | None:
    entry = _store.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.monotonic() > expires_at:
        _store.pop(key, None)
        return None
    return value


def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    _store[key] = (time.monotonic() + max(1, ttl_seconds), value)


def clear_cache() -> None:
    _store.clear()
