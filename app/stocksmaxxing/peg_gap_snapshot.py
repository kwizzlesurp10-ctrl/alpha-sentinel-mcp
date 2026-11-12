"""Full peg-gap API response snapshot (KV + memory) for fast dashboard loads."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_memory: dict[str, tuple[float, dict[str, Any]]] = {}


def _snapshot_key(alert_threshold_pct: float, page_size: int) -> str:
    return f"peg-gap:v1:{page_size}:{alert_threshold_pct:.2f}"


async def load_peg_gap_snapshot(
    *,
    alert_threshold_pct: float,
    page_size: int,
) -> dict[str, Any] | None:
    key = _snapshot_key(alert_threshold_pct, page_size)
    entry = _memory.get(key)
    if entry and time.monotonic() <= entry[0]:
        payload = dict(entry[1])
        payload["meta"] = {**(payload.get("meta") or {}), "cache_status": "memory_hit"}
        return payload

    try:
        from app.kv_store import get_store

        store = get_store()
        if not store.available():
            return None
        raw = await store.get(f"snapshot:{key}")
        if not raw:
            return None
        data = json.loads(raw)
        expires_at = float(data.get("expires_at", 0))
        if expires_at <= time.time():
            return None
        payload = data["payload"]
        _memory[key] = (time.monotonic() + max(0.0, expires_at - time.time()), payload)
        out = dict(payload)
        out["meta"] = {**(out.get("meta") or {}), "cache_status": "kv_hit"}
        return out
    except Exception as exc:
        logger.debug("peg-gap snapshot load failed: %s", exc)
        return None


async def save_peg_gap_snapshot(
    *,
    alert_threshold_pct: float,
    page_size: int,
    payload: dict[str, Any],
) -> None:
    key = _snapshot_key(alert_threshold_pct, page_size)
    ttl = int(settings.peg_gap_snapshot_cache_ttl_seconds)
    body = {
        "expires_at": time.time() + ttl,
        "payload": payload,
    }
    _memory[key] = (time.monotonic() + ttl, payload)
    try:
        from app.kv_store import get_store

        store = get_store()
        if store.available():
            await store.set(f"snapshot:{key}", json.dumps(body), ttl)
    except Exception as exc:
        logger.debug("peg-gap snapshot save failed: %s", exc)


def clear_snapshot_cache() -> None:
    _memory.clear()
