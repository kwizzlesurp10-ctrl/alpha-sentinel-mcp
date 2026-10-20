"""MCP x402: payment in params._meta, verify → run → settle-on-success, idempotent replay."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.application import app

CANON = "0x0d25A44f74868eCE53B305C97139CF4B62963410"


def _payment() -> dict:
    return {
        "x402Version": 2,
        "accepted": {
            "scheme": "exact",
            "network": "eip155:8453",
            "amount": "5000",
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "payTo": CANON,
            "maxTimeoutSeconds": 300,
            "extra": {"name": "USD Coin", "version": "2"},
        },
        "payload": {
            "signature": "0x" + "11" * 65,
            "authorization": {
                "from": "0x" + "22" * 20,
                "to": CANON,
                "value": "5000",
                "validAfter": "0",
                "validBefore": "9999999999",
                "nonce": "0x" + "33" * 32,
            },
        },
    }


def _call(meta: dict | None, arguments: dict | None = None, rid: int = 1) -> dict:
    params: dict = {"name": "fetch_price", "arguments": arguments or {"symbol": "btc"}}
    if meta is not None:
        params["_meta"] = meta
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": params}


@pytest.fixture
def facilitator(monkeypatch):
    calls = {"verify": [], "settle": 0}

    async def _verify(sig, required):
        import base64
        import json

        calls["verify"].append(json.loads(base64.b64decode(sig)))
        return {"is_valid": True, "_payload": object(), "_requirements": object(), "_network": "eip155:8453"}

    async def _settle(ctx):
        calls["settle"] += 1
        return {
            "payment_settled": True,
            "settlement": {"success": True, "transaction": "0x" + "ab" * 32, "network": "eip155:8453", "payer": "0x1"},
        }

    monkeypatch.setattr("app.mcp_x402_payment.x402_services.verify_from_headers", _verify)
    monkeypatch.setattr("app.mcp_x402_payment.x402_services.settle_verified_payment", _settle)
    return calls


async def _post(body):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/mcp", json=body, headers={"accept": "application/json"})
    assert r.status_code == 200
    return r.json()["result"]


@pytest.mark.asyncio
async def test_params_meta_payment_is_base64_encoded_and_settled(facilitator, mock_coingecko_api):
    res = await _post(_call({"x402/payment": _payment()}))
    assert not res.get("isError"), res
    assert facilitator["verify"] and facilitator["verify"][0]["payload"]["authorization"]["to"] == CANON
    assert facilitator["settle"] == 1
    assert res["_meta"]["x402/payment-response"]["success"] is True

    # Idempotent retry: same payment returns cached result, no second settle.
    again = await _post(_call({"x402/payment": _payment()}, rid=2))
    assert facilitator["settle"] == 1
    assert again["_meta"].get("x402/idempotent-replay") is True
    assert again["structuredContent"] == res["structuredContent"]


@pytest.mark.asyncio
async def test_tool_failure_never_settles(facilitator, monkeypatch):
    async def _boom(name, args):
        raise ValueError("bad symbol")

    monkeypatch.setattr("app.mcp_http._execute_tool", _boom)
    res = await _post(_call({"x402/payment": _payment()}, {"symbol": "???"}))
    assert res["isError"] is True
    assert facilitator["verify"] and facilitator["settle"] == 0


@pytest.mark.asyncio
async def test_malformed_payment_rejected_without_facilitator(facilitator):
    res = await _post(_call({"x402/payment": {"x402Version": 2}}))
    assert res["isError"] is True
    assert res["structuredContent"]["invalid_reason"].startswith("malformed_payment")
    assert facilitator["verify"] == [] and facilitator["settle"] == 0


@pytest.mark.asyncio
async def test_unpaid_call_still_returns_challenge():
    res = await _post(_call(None))
    assert res["isError"] is True
    a = res["structuredContent"]["accepts"][0]
    from app.config import settings

    assert a["payTo"] == settings.x402_pay_to_address and a["maxTimeoutSeconds"] == 300


@pytest.mark.asyncio
async def test_success_false_result_never_settles(facilitator, monkeypatch):
    async def _soft_fail(name, args):
        return {"success": False, "error": "Unknown symbol"}

    monkeypatch.setattr("app.mcp_http._execute_tool", _soft_fail)
    res = await _post(_call({"x402/payment": _payment()}, {"symbol": "zzz"}))
    assert res["isError"] is True
    assert facilitator["settle"] == 0
