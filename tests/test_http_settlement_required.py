"""HTTP paid gate must require payment_settled, not just is_valid."""

from __future__ import annotations

import base64
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.application import app
from app.commerce_payment import store_tool_challenge
from app.config import settings


def _challenge_header(pay_to: str) -> str:
    body = {
        "x402Version": 2,
        "error": "Payment required",
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "amount": "20000",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "payTo": pay_to,
                "maxTimeoutSeconds": 300,
                "extra": {"name": "USD Coin", "version": "2"},
            }
        ],
    }
    return base64.b64encode(json.dumps(body).encode()).decode()


@pytest.mark.asyncio
async def test_http_gate_402_when_settle_fails_after_verify(monkeypatch):
    header = _challenge_header(settings.x402_pay_to_address or "0x1111111111111111111111111111111111111111")
    fake = {
        "payment_required_header": header,
        "payment_required": {"x402Version": 2, "error": "Payment required"},
        "requirements": [],
    }

    async def _fake_build(tool_name, resource_url):
        return fake

    monkeypatch.setattr("app.tool_payment_gate.build_tool_challenge", _fake_build)
    store_tool_challenge("analyze_volatility", "http://test/tools/analyze_volatility", fake)

    async def _verify_settle(scope, resource_id, sig, req_header):
        return {
            "is_valid": True,
            "payment_settled": False,
            "settlement_error": "facilitator_timeout",
            "settlement": {"success": False},
        }

    monkeypatch.setattr(
        "app.tool_payment_gate.verify_settle_with_idempotency",
        _verify_settle,
    )
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setattr(settings, "cdp_api_key_id", "id")
    monkeypatch.setattr(settings, "cdp_api_key_secret", "secret")
    # Seller-ready check uses _use_cdp; force ready.
    monkeypatch.setattr(
        "app.tool_payment_gate._seller_ready_for_settlement",
        lambda: (True, ""),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tools/analyze_volatility",
            json={"symbol": "btc", "window_minutes": 60},
            headers={"PAYMENT-SIGNATURE": "sig-after-verify-settle-fail"},
        )
    assert response.status_code == 402
    body = response.json()
    assert body.get("error") == "Payment settlement failed"
    assert "facilitator_timeout" in (body.get("invalid_reason") or "")
    # Must not have returned paid intelligence data.
    assert "data" not in body or body.get("success") is not True


@pytest.mark.asyncio
async def test_http_gate_passes_when_payment_settled(monkeypatch, mock_coingecko_api):
    header = _challenge_header(settings.x402_pay_to_address or "0x1111111111111111111111111111111111111111")
    fake = {
        "payment_required_header": header,
        "payment_required": {"x402Version": 2, "error": "Payment required"},
        "requirements": [],
    }

    async def _fake_build(tool_name, resource_url):
        return fake

    monkeypatch.setattr("app.tool_payment_gate.build_tool_challenge", _fake_build)
    store_tool_challenge("fetch_price", "http://test/tools/fetch_price", fake)

    async def _verify_settle(scope, resource_id, sig, req_header):
        return {
            "is_valid": True,
            "payment_settled": True,
            "settlement": {
                "success": True,
                "transaction": "0xsettled",
                "network": "eip155:8453",
                "payer": "0xabc",
            },
        }

    monkeypatch.setattr(
        "app.tool_payment_gate.verify_settle_with_idempotency",
        _verify_settle,
    )
    monkeypatch.setattr(
        "app.tool_payment_gate._seller_ready_for_settlement",
        lambda: (True, ""),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tools/fetch_price",
            json={"symbol": "btc"},
            headers={"PAYMENT-SIGNATURE": "sig-settled-ok"},
        )
    assert response.status_code == 200
    assert response.json().get("data", {}).get("price_usd") or response.json().get("price_usd")
