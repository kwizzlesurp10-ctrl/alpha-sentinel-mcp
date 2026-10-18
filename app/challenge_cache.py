"""Cache PAYMENT-REQUIRED headers so selling does not hit the facilitator every request."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable

log = logging.getLogger("x402")

_mem: dict[str, dict[str, str]] = {}


def fingerprint(**parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def clear() -> None:
    _mem.clear()


def get_or_build(name: str, fp: str, builder: Callable[[], str]) -> str:
    fp = str(fp)
    cached = _mem.get(name)
    if cached and cached.get("fp") == fp:
        return cached["header"]

    try:
        header = builder()
    except Exception as exc:  # noqa: BLE001
        if cached and cached.get("header"):
            log.warning(
                "challenge_cache: build failed for %s (%s); serving last-known-good",
                name,
                exc,
            )
            return cached["header"]
        raise

    _mem[name] = {"fp": fp, "header": header}
    return header


def load(name: str) -> dict[str, str] | None:
    return _mem.get(name)
