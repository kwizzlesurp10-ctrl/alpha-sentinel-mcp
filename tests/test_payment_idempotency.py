"""Persistent payment idempotency (Upstash NX + fail-closed production)."""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.application import app
from app.config import settings
from app.kv_store import InMemoryKvStore, set_store_override
from app.payment_idempotency import (
    IdempotencyStoreRequired,
    begin_payment_attempt,
    clear,
    complete_payment_attempt,
    ensure_idempotency_backend,
)
from tests.conftest import make_payment_signature


@pytest.fixture
def shared_kv():
    store = InMemoryKvStore()
    set_store_override(store)
    clear()
    yield store
    set_store_override(None)
    store.clear()


@pytest.mark.asyncio
async def test_concurrent_duplicate_payment_blocked(shared_kv, monkeypatch):
    monkeypatch.setattr(
        "app.payment_idempotency.must_persist_idempotency", lambda: False
    )
    sig = "same-payment-signature-body"

    async def attempt():
        return await begin_payment_attempt("http", "analyze_volatility", sig)

    results = await asyncio.gather(attempt(), attempt())
    allowed = [r.allowed for r in results]
    assert allowed.count(True) == 1
    assert allowed.count(False) == 1


@pytest.mark.asyncio
async def test_cross_instance_shared_kv_blocks_replay(shared_kv, monkeypatch):
    """Two logical instances share one Upstash-shaped store."""
    monkeypatch.setattr(
        "app.payment_idempotency.must_persist_idempotency", lambda: False
    )
    sig = "cross-instance-sig"
    first = await begin_payment_attempt("mcp", "fetch_price_tool", sig)
    assert first.allowed
    ok = await complete_payment_attempt(
        "mcp",
        "fetch_price_tool",
        first.fingerprint,
        {"transaction": "0xabc123"},
    )
    assert ok

    # Second instance: same store, same payment
    second = await begin_payment_attempt("mcp", "fetch_price_tool", sig)
    assert not second.allowed
    assert second.reason == "payment_already_consumed"


@pytest.mark.asyncio
async def test_fail_closed_without_kv(monkeypatch):
    monkeypatch.setattr(
        "app.payment_idempotency.must_persist_idempotency", lambda: True
    )
    set_store_override(None)
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.delenv("KV_REST_API_TOKEN", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    monkeypatch.setattr("app.redis_client.kv_configured", lambda: False)

    with pytest.raises(IdempotencyStoreRequired):
        await ensure_idempotency_backend()


@pytest.mark.asyncio
async def test_http_paid_fail_closed_503_without_kv(monkeypatch):
    """With a payment signature present, missing KV must 503 (not settle)."""
    import base64
    import json

    monkeypatch.setattr(
        "app.payment_idempotency.must_persist_idempotency", lambda: True
    )
    set_store_override(None)
    monkeypatch.setattr("app.redis_client.kv_configured", lambda: False)
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setattr(settings, "cdp_api_key_id", "test-cdp-id")
    monkeypatch.setattr(settings, "cdp_api_key_secret", "test-cdp-secret")

    # Don't rely on the (removed) offline facilitator fallback — seed a
    # server-authored challenge the gate can reuse.
    header = base64.b64encode(
        json.dumps(
            {
                "x402Version": 2,
                "error": "Payment required",
                "accepts": [
                    {
                        "scheme": "exact",
                        "network": "eip155:8453",
                        "amount": "20000",
                        "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                        "payTo": settings.x402_pay_to_address,
                        "maxTimeoutSeconds": 300,
                        "extra": {"name": "USD Coin", "version": "2"},
                    }
                ],
            }
        ).encode()
    ).decode()
    fake = {
        "payment_required_header": header,
        "payment_required": {"x402Version": 2, "error": "Payment required"},
        "requirements": [],
    }

    async def _fake_build(tool_name, resource_url):
        return fake

    monkeypatch.setattr(
        "app.tool_payment_gate.build_tool_challenge", _fake_build
    )
    from app.commerce_payment import store_tool_challenge

    store_tool_challenge("analyze_volatility", "http://test/tools/analyze_volatility", fake)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tools/analyze_volatility",
            json={"symbol": "btc"},
            headers={"PAYMENT-SIGNATURE": make_payment_signature("fake-but-present-signature")},
        )
    assert response.status_code == 503
    assert response.json().get("error") == "idempotency_store_unavailable"


@pytest.mark.asyncio
async def test_settlement_tx_replay_after_complete(shared_kv, monkeypatch):
    monkeypatch.setattr(
        "app.payment_idempotency.must_persist_idempotency", lambda: False
    )
    fp = "abc123fingerprint0000000000000001"
    scope, resource = "http", "tool_a"
    await shared_kv.set(_payment_key(scope, resource, fp), "inflight", 3600)
    ok = await complete_payment_attempt(
        scope, resource, fp, {"transaction": "0xdeadbeef"}
    )
    assert ok
    begin2 = await begin_payment_attempt(scope, resource, "another-sig-same-tx")
    assert begin2.allowed
    ok2 = await complete_payment_attempt(
        scope, resource, begin2.fingerprint, {"transaction": "0xdeadbeef"}
    )
    assert not ok2


def _payment_key(scope: str, resource_id: str, fingerprint: str) -> str:
    return f"x402:idem:{scope}:{resource_id}:{fingerprint}"
