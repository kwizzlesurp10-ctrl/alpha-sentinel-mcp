"""HTTP paid gate must require payment_settled (covered via deferred settle)."""

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


@pytest.fixture
def seed(monkeypatch):
    header = _challenge_header(settings.x402_pay_to_address or "0x1111111111111111111111111111111111111111")
    fake = {
        "payment_required_header": header,
        "payment_required": {"x402Version": 2, "error": "Payment required"},
        "requirements": [],
    }

    async def _fake_build(tool_name, resource_url):
        return fake

    monkeypatch.setattr("app.tool_payment_gate.build_tool_challenge", _fake_build)
    monkeypatch.setattr("app.tool_payment_gate._seller_ready_for_settlement", lambda: (True, ""))
    store_tool_challenge("analyze_volatility", "http://test/tools/analyze_volatility", fake)
    store_tool_challenge("fetch_price", "http://test/tools/fetch_price", fake)
    return fake


@pytest.mark.asyncio
async def test_http_gate_402_when_settle_fails_after_verify(monkeypatch, seed, mock_coingecko_api):
    async def _verify(sig, req):
        return {"is_valid": True, "_payload": object(), "_requirements": object(), "_network": "eip155:8453"}

    async def _settle(ctx):
        return {"payment_settled": False, "settlement_error": "facilitator_timeout", "settlement": {"success": False}}

    monkeypatch.setattr("app.tool_payment_gate.x402_services.verify_from_headers", _verify)
    monkeypatch.setattr("app.tool_payment_gate.x402_services.settle_verified_payment", _settle)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tools/fetch_price",
            json={"symbol": "btc"},
            headers={"PAYMENT-SIGNATURE": "sig-settle-fail-gate"},
        )
    assert response.status_code == 402
    assert response.json().get("error") == "Payment settlement failed"


@pytest.mark.asyncio
async def test_http_gate_passes_when_payment_settled(monkeypatch, seed, mock_coingecko_api):
    async def _verify(sig, req):
        return {"is_valid": True, "_payload": object(), "_requirements": object(), "_network": "eip155:8453"}

    async def _settle(ctx):
        return {
            "payment_settled": True,
            "settlement": {"success": True, "transaction": "0xsettled", "network": "eip155:8453", "payer": "0xabc"},
        }

    monkeypatch.setattr("app.tool_payment_gate.x402_services.verify_from_headers", _verify)
    monkeypatch.setattr("app.tool_payment_gate.x402_services.settle_verified_payment", _settle)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/tools/fetch_price",
            json={"symbol": "btc"},
            headers={"PAYMENT-SIGNATURE": "sig-settled-ok-gate"},
        )
    assert response.status_code == 200
