"""A2A x402: verify → run skill → settle on success; tasks survive instance hops via KV."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.a2a import META_PAYLOAD, META_STATUS, TASKS, clear_task_store

PAYMENT = {
    "x402Version": 2,
    "accepted": {
        "scheme": "exact",
        "network": "eip155:8453",
        "amount": "5000",
        "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "payTo": "0x0d25A44f74868eCE53B305C97139CF4B62963410",
        "maxTimeoutSeconds": 300,
        "extra": {"name": "USD Coin", "version": "2"},
    },
    "payload": {
        "signature": "0x" + "11" * 65,
        "authorization": {
            "from": "0x" + "22" * 20,
            "to": "0x0d25A44f74868eCE53B305C97139CF4B62963410",
            "value": "5000",
            "validAfter": "0",
            "validBefore": "9999999999",
            "nonce": "0x" + "44" * 32,
        },
    },
}


@pytest.fixture
async def client():
    from app.application import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def facilitator(monkeypatch):
    calls = {"verify": 0, "settle": 0}

    async def _verify(sig, required):
        calls["verify"] += 1
        return {"is_valid": True, "_payload": object(), "_requirements": object(), "_network": "eip155:8453"}

    async def _settle(ctx):
        calls["settle"] += 1
        return {
            "payment_settled": True,
            "settlement": {"success": True, "transaction": "0x" + "cd" * 32, "network": "eip155:8453", "payer": "0x1"},
        }

    monkeypatch.setattr("app.x402_services.verify_from_headers", _verify)
    monkeypatch.setattr("app.x402_services.settle_verified_payment", _settle)
    return calls


async def _send(client, message):
    r = await client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {"message": message}},
    )
    assert r.status_code == 200
    return r.json()


async def _challenge(client):
    body = await _send(
        client,
        {"role": "user", "kind": "message", "messageId": "m1",
         "parts": [{"kind": "data", "data": {"skillId": "fetch_price", "symbol": "btc"}}]},
    )
    task = body["result"]
    assert task["status"]["state"] == "input-required"
    return task["id"]


def _pay(task_id):
    return {"role": "user", "kind": "message", "messageId": "m2", "taskId": task_id,
            "parts": [{"kind": "text", "text": "paid"}],
            "metadata": {META_STATUS: "payment-submitted", META_PAYLOAD: PAYMENT}}


@pytest.mark.asyncio
async def test_settles_after_skill_success_and_task_survives_instance_hop(
    client, facilitator, mock_coingecko_api
):
    clear_task_store()
    task_id = await _challenge(client)
    TASKS.clear()  # simulate the payment landing on a different serverless instance
    result = (await _send(client, _pay(task_id)))["result"]
    assert result["status"]["state"] == "completed"
    assert result.get("artifacts")
    assert facilitator == {"verify": 1, "settle": 1}


@pytest.mark.asyncio
async def test_skill_failure_does_not_settle(client, facilitator, monkeypatch):
    clear_task_store()
    task_id = await _challenge(client)

    async def _boom(skill, args):
        raise RuntimeError("upstream down")

    monkeypatch.setattr("app.a2a.invoke_skill", _boom)
    result = (await _send(client, _pay(task_id)))["result"]
    assert result["status"]["state"] == "failed"
    assert not result.get("artifacts")
    assert facilitator == {"verify": 1, "settle": 0}
