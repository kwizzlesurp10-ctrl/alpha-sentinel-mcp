"""Persistent payment idempotency + settlement replay guards (Upstash SET NX + TTL)."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.kv_store import get_store

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 86_400  # 24h — covers validBefore / challenge windows


class IdempotencyStoreRequired(Exception):
    """Production/mainnet paid path without durable KV."""


@dataclass(frozen=True)
class IdempotencyBeginResult:
    allowed: bool
    fingerprint: str
    reason: str | None = None


def payment_fingerprint(payment_signature: str) -> str:
    raw = payment_signature.strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def must_persist_idempotency() -> bool:
    if (os.environ.get("VERCEL_ENV") or "").lower() == "production":
        return True
    from app import x402_services

    net = x402_services.resolve_revenue_network()
    if net == "eip155:8453":
        return True
    return settings.x402_default_network == "eip155:8453"


def allow_memory_fallback() -> bool:
    return not must_persist_idempotency()


def _payment_key(scope: str, resource_id: str, fingerprint: str) -> str:
    return f"x402:idem:{scope}:{resource_id}:{fingerprint}"


def _tx_key(tx_hash: str) -> str:
    return f"x402:settled_tx:{tx_hash.strip().lower()}"


async def ensure_idempotency_backend() -> None:
    store = get_store()
    from app.kv_store import InMemoryKvStore, UpstashKvStore

    if isinstance(store, UpstashKvStore) and store.available():
        return
    if isinstance(store, InMemoryKvStore) and allow_memory_fallback():
        return
    if must_persist_idempotency():
        raise IdempotencyStoreRequired(
            "KV_REST_API_URL and KV_REST_API_TOKEN (or UPSTASH_REDIS_REST_URL/TOKEN) "
            "required for paid x402 on Base mainnet / Vercel production"
        )


async def begin_payment_attempt(
    scope: str,
    resource_id: str,
    payment_signature: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> IdempotencyBeginResult:
    """Mark-before-settle: atomic NX claim on payment fingerprint."""
    await ensure_idempotency_backend()
    fp = payment_fingerprint(payment_signature)
    key = _payment_key(scope, resource_id, fp)
    store = get_store()
    acquired = await store.set_nx(key, "inflight", ttl_seconds)
    if acquired:
        return IdempotencyBeginResult(allowed=True, fingerprint=fp)
    existing = await store.get(key)
    if existing == "inflight":
        return IdempotencyBeginResult(
            allowed=False, fingerprint=fp, reason="duplicate_inflight"
        )
    return IdempotencyBeginResult(
        allowed=False, fingerprint=fp, reason="payment_already_consumed"
    )


async def release_payment_attempt(
    scope: str,
    resource_id: str,
    fingerprint: str,
) -> None:
    store = get_store()
    await store.delete(_payment_key(scope, resource_id, fingerprint))


async def complete_payment_attempt(
    scope: str,
    resource_id: str,
    fingerprint: str,
    settlement: dict[str, Any] | None,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """Record successful settlement; NX-guard tx hash replay."""
    tx = _extract_tx_hash(settlement)
    if tx:
        store = get_store()
        if not await store.set_nx(_tx_key(tx), "1", ttl_seconds):
            return False
        await store.set(
            _payment_key(scope, resource_id, fingerprint),
            tx,
            ttl_seconds,
        )
    else:
        store = get_store()
        await store.set(
            _payment_key(scope, resource_id, fingerprint),
            "settled",
            ttl_seconds,
        )
    return True


def _extract_tx_hash(settlement: dict[str, Any] | None) -> str | None:
    if not settlement:
        return None
    tx = (
        settlement.get("transaction")
        or settlement.get("tx_hash")
        or settlement.get("txHash")
    )
    if not tx:
        return None
    return str(tx).strip()


async def verify_settle_with_idempotency(
    scope: str,
    resource_id: str,
    payment_signature: str,
    payment_required_header: str,
) -> dict[str, Any]:
    """Verify + settle with NX idempotency (HTTP + MCP shared)."""
    from app import x402_services

    begin = await begin_payment_attempt(scope, resource_id, payment_signature)
    if not begin.allowed:
        return {
            "idempotency_blocked": True,
            "reason": begin.reason or "replay_rejected",
            "is_valid": False,
            "payment_settled": False,
        }

    try:
        result = await x402_services.verify_and_settle_from_headers(
            payment_signature, payment_required_header
        )
    except Exception:
        await release_payment_attempt(scope, resource_id, begin.fingerprint)
        raise

    if not result.get("is_valid") or not result.get("payment_settled"):
        await release_payment_attempt(scope, resource_id, begin.fingerprint)
        return result

    settlement = result.get("settlement") or {}
    if not await complete_payment_attempt(
        scope, resource_id, begin.fingerprint, settlement
    ):
        await release_payment_attempt(scope, resource_id, begin.fingerprint)
        return {
            "idempotency_blocked": True,
            "reason": "settlement_tx_replay",
            "is_valid": False,
            "payment_settled": False,
            "settlement": settlement,
        }

    return result


def idempotency_unavailable_response() -> dict[str, Any]:
    return {
        "error": "idempotency_store_unavailable",
        "detail": (
            "Paid x402 requires Upstash Redis (KV_REST_API_URL + KV_REST_API_TOKEN or "
            "UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN) on Base mainnet / production."
        ),
    }


def clear_memory_state() -> None:
    """Test helper."""
    from app.kv_store import InMemoryKvStore

    store = get_store()
    if isinstance(store, InMemoryKvStore):
        store.clear()


def clear() -> None:
    from app.kv_store import reset_memory_singleton

    clear_memory_state()
    reset_memory_singleton()
    from app import payment_replay as legacy

    legacy.clear()
