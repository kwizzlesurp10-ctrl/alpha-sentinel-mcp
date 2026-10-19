"""Verify first, settle only after a successful handler; cache for idempotent retry."""

from __future__ import annotations

import base64
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.application import app
from app.commerce_payment import store_tool_challenge
from app.config import settings


def _header(pay_to: str) -> str:
    body = {
        "x402Version": 2,
        "error": "Payment required",
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "amount": "5000",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "payTo": pay_to,
                "maxTimeoutSeconds": 300,
                "extra": {"name": "USD Coin", "version": "2"},
            }
        ],
    }
    return base64.b64encode(json.dumps(body).encode()).decode()


@pytest.fixture
def seed_challenge(monkeypatch):
    pay_to = settings.x402_pay_to_address or "0x1111111111111111111111111111111111111111"
    header = _header(pay_to)
    fake = {
        "payment_required_header": header,
        "payment_required": {"x402Version": 2, "error": "Payment required"},
        "requirements": [],
    }

    async def _fake_build(tool_name, resource_url):
        return fake

    monkeypatch.setattr("app.tool_payment_gate.build_tool_challenge", _fake_build)
    monkeypatch.setattr(
        "app.tool_payment_gate._seller_ready_for_settlement",
        lambda: (True, ""),
    )
    store_tool_challenge("fetch_price", "http://test/tools/fetch_price", fake)
    return fake


@pytest.mark.asyncio
async def test_bad_input_with_payment_returns_400_without_settle(
    monkeypatch, seed_challenge
):
    settles: list[int] = []

    async def _verify(sig, req):
        return {
            "is_valid": True,
            "payment_settled": False,
            "_payload": object(),
            "_requirements": object(),
            "_network": "eip155:8453",
        }

    async def _settle(ctx):
        settles.append(1)
        return {"payment_settled": True, "settlement": {"success": True, "transaction": "0x1"}}

    monkeypatch.setattr("app.tool_payment_gate.x402_services.verify_from_headers", _verify)
    monkeypatch.setattr("app.tool_payment_gate.x402_services.settle_verified_payment", _settle)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # missing symbol → 400 from handler; settle must NOT run
        response = await client.post(
            "/tools/fetch_price",
            json={},
            headers={"PAYMENT-SIGNATURE": "sig-bad-input-no-settle"},
        )
    assert response.status_code == 400
    assert settles == []


@pytest.mark.asyncio
async def test_success_settles_and_idempotent_retry_replays_cache(
    monkeypatch, seed_challenge, mock_coingecko_api
):
    settles: list[int] = []

    async def _verify(sig, req):
        return {
            "is_valid": True,
            "payment_settled": False,
            "_payload": object(),
            "_requirements": object(),
            "_network": "eip155:8453",
        }

    async def _settle(ctx):
        settles.append(1)
        return {
            "is_valid": True,
            "payment_settled": True,
            "settlement": {
                "success": True,
                "transaction": "0xdead",
                "network": "eip155:8453",
                "payer": "0xabc",
            },
        }

    monkeypatch.setattr("app.tool_payment_gate.x402_services.verify_from_headers", _verify)
    monkeypatch.setattr("app.tool_payment_gate.x402_services.settle_verified_payment", _settle)

    sig = "sig-success-then-replay-unique"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/tools/fetch_price",
            json={"symbol": "btc"},
            headers={"PAYMENT-SIGNATURE": sig},
        )
        assert first.status_code == 200
        assert first.headers.get("payment-response") or first.headers.get("PAYMENT-RESPONSE")
        body1 = first.json()
        assert settles == [1]

        # Same signature → cached replay, no second settle
        second = await client.post(
            "/tools/fetch_price",
            json={"symbol": "btc"},
            headers={"PAYMENT-SIGNATURE": sig},
        )
    assert second.status_code == 200
    assert second.headers.get("x-payment-idempotent-replay") == "1"
    assert second.json() == body1
    assert settles == [1]


@pytest.mark.asyncio
async def test_settle_failure_after_success_handler_returns_402(
    monkeypatch, seed_challenge, mock_coingecko_api
):
    async def _verify(sig, req):
        return {
            "is_valid": True,
            "_payload": object(),
            "_requirements": object(),
            "_network": "eip155:8453",
        }

    async def _settle(ctx):
        return {
            "is_valid": True,
            "payment_settled": False,
            "settlement_error": "facilitator_timeout",
            "settlement": {"success": False},
        }

    monkeypatch.setattr("app.tool_payment_gate.x402_services.verify_from_headers", _verify)
    monkeypatch.setattr("app.tool_payment_gate.x402_services.settle_verified_payment", _settle)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tools/fetch_price",
            json={"symbol": "btc"},
            headers={"PAYMENT-SIGNATURE": "sig-settle-fail-after-ok"},
        )
    assert response.status_code == 402
    assert response.json().get("error") == "Payment settlement failed"
