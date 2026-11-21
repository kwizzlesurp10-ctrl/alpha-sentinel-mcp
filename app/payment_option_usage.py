"""Lightweight counters for which x402 payment options buyers use."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.kv_store import get_store, key_prefix
from app.payment_options import BASE_MAINNET_CAIP2

logger = logging.getLogger(__name__)

USAGE_KEY = f"{key_prefix()}payment-option-usage"

_lock = asyncio.Lock()
_memory_counts: dict[str, int] = {}


def option_key(network: str, asset: str) -> str:
    return f"{network}|{asset}"


def usage_count_snapshot() -> dict[str, int]:
    return dict(_memory_counts)


def reset_counts_for_tests() -> None:
    global _memory_counts
    _memory_counts = {}


def usage_rank_fingerprint() -> str:
    """Short hash input for challenge cache fingerprints when ranking changes."""
    if not _memory_counts:
        return "0"
    return str(sum(_memory_counts.values()))


_STATS_TTL = 86_400 * 365


async def _persist_counts_blob() -> None:
    store = get_store()
    if not store.available():
        return
    await store.set(USAGE_KEY, json.dumps(_memory_counts), ttl_seconds=_STATS_TTL)


async def load_usage_counts() -> dict[str, int]:
    """Hydrate in-process counters from KV when present."""
    global _memory_counts
    store = get_store()
    if not store.available():
        return dict(_memory_counts)
    raw = await store.get(USAGE_KEY)
    if not raw:
        return dict(_memory_counts)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            async with _lock:
                _memory_counts = {str(k): int(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("payment option usage blob corrupt: %s", exc)
    return dict(_memory_counts)


async def record_payment_option_usage(network: str | None, asset: str | None) -> None:
    if not network or not asset:
        return
    key = option_key(network, asset)
    async with _lock:
        _memory_counts[key] = int(_memory_counts.get(key, 0)) + 1
    await _persist_counts_blob()


async def record_payment_option_usage_from_verify_ctx(verify_ctx: dict[str, Any]) -> None:
    requirements = verify_ctx.get("_requirements")
    network = verify_ctx.get("_network")
    asset = None
    if requirements is not None:
        asset = getattr(requirements, "asset", None)
        if asset is None and isinstance(requirements, dict):
            asset = requirements.get("asset")
        if not network:
            network = getattr(requirements, "network", None) or (
                requirements.get("network") if isinstance(requirements, dict) else None
            )
    await record_payment_option_usage(str(network) if network else None, str(asset) if asset else None)


async def get_usage_report() -> dict[str, Any]:
    await load_usage_counts()
    rows = []
    for key, count in sorted(_memory_counts.items(), key=lambda item: (-item[1], item[0])):
        net, _, asset = key.partition("|")
        rows.append(
            {
                "network": net,
                "asset": asset,
                "count": count,
                "default_tie_break": net == BASE_MAINNET_CAIP2,
            }
        )
    return {
        "options": rows,
        "ranking": "most_used_first",
        "tie_break_network": BASE_MAINNET_CAIP2,
        "total_payments": sum(_memory_counts.values()),
    }
