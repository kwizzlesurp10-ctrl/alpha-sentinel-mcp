"""TTL cache for onchain price lookups (memory + optional KV)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_store: dict[str, tuple[float, Any]] = {}
_neg_store: dict[str, tuple[float, dict[str, str]]] = {}


def _kv_key(kind: str, key: str) -> str:
    return f"onchain-price:{kind}:{key}"


def get_cached(key: str, ttl_seconds: int) -> Any | None:
    entry = _store.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.monotonic() > expires_at:
        _store.pop(key, None)
        return None
    return value


def get_negative_cached(key: str, ttl_seconds: int) -> dict[str, str] | None:
    entry = _neg_store.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.monotonic() > expires_at:
        _neg_store.pop(key, None)
        return None
    return value


def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    _store[key] = (time.monotonic() + max(1, ttl_seconds), value)
    _neg_store.pop(key, None)


def set_negative_cached(key: str, code: str, message: str, ttl_seconds: int) -> None:
    payload = {"code": code, "message": message}
    _neg_store[key] = (time.monotonic() + max(1, ttl_seconds), payload)
    _store.pop(key, None)


async def hydrate_cached_from_kv(key: str) -> bool:
    """Load memory cache from KV if present (cross-invocation warm)."""
    try:
        from app.kv_store import get_store

        store = get_store()
        if not store.available():
            return False
        for kind, target in (("pos", _store), ("neg", _neg_store)):
            raw = await store.get(_kv_key(kind, key))
            if not raw:
                continue
            data = json.loads(raw)
            expires_at = float(data.get("expires_at", 0))
            if expires_at <= time.time():
                continue
            mono_expires = time.monotonic() + max(0.0, expires_at - time.time())
            if kind == "pos":
                target[key] = (mono_expires, data["value"])
            else:
                target[key] = (mono_expires, {"code": data["code"], "message": data["message"]})
            return True
    except Exception as exc:
        logger.debug("KV hydrate miss for %s: %s", key, exc)
    return False


async def persist_cached_to_kv(key: str, *, positive: dict[str, Any] | None, negative: dict[str, str] | None) -> None:
    try:
        from app.kv_store import get_store

        store = get_store()
        if not store.available():
            return
        now = time.time()
        if positive is not None:
            ttl = int(settings.peg_gap_onchain_cache_ttl_seconds)
            blob = json.dumps({"expires_at": now + ttl, "value": positive})
            await store.set(_kv_key("pos", key), blob, ttl)
        elif negative is not None:
            ttl = int(settings.peg_gap_onchain_negative_cache_ttl_seconds)
            blob = json.dumps(
                {
                    "expires_at": now + ttl,
                    "code": negative["code"],
                    "message": negative["message"],
                }
            )
            await store.set(_kv_key("neg", key), blob, ttl)
    except Exception as exc:
        logger.debug("KV persist skip for %s: %s", key, exc)


def clear_cache() -> None:
    _store.clear()
    _neg_store.clear()
