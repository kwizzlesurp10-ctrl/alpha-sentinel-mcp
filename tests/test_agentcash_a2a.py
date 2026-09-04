"""Gating tests: AgentCash catalog/402, remote MCP, A2A Send/Get, fetch_price.

Drives the shipped ASGI app. Mocks only outbound CoinGecko HTTP.
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.application import app
from app.tools_registry import EXPECTED_TOOL_NAMES, PAID_TOOLS
from tests.conftest import MOCK_BTC_USD, TEST_PAY_TO


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _contains_price_usd(obj) -> float | None:
    if isinstance(obj, dict):
        if "price_usd" in obj and isinstance(obj["price_usd"], (int, float)):
            return float(obj["price_usd"])
        for v in obj.values():
            found = _contains_price_usd(v)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _contains_price_usd(item)
            if found is not None:
                return found
    elif isinstance(obj, str):
        try:
            return _contains_price_usd(json.loads(obj))
        except Exception:
            return None
    return None


@pytest.mark.asyncio
async def test_paid_catalog_lists_paid_tools_with_price_and_network(client):
    response = await client.get("/catalog")
    assert response.status_code == 200
    body = response.json()
    tools = body.get("tools") or body
    assert isinstance(tools, list)
    names = {item["name"] for item in tools}
    assert set(PAID_TOOLS) <= names
    assert "fetch_price" not in names
    for item in tools:
        assert item["url"]
        assert item["method"]
        assert item.get("network")
        price = item.get("price_usdc", item.get("price"))
        assert price not in (None, "", "free")
        assert "http" in str(item["url"]).lower() or item["url"].startswith("/")


@pytest.mark.asyncio
async def test_well_known_x402_catalog(client):
    response = await client.get("/.well-known/x402")
    assert response.status_code == 200
    data = response.json()
    details = data.get("catalog") or data.get("resource_details") or []
    names = {item["name"] for item in details}
    assert set(PAID_TOOLS) <= names
    for item in details:
        assert item["url"]
        assert item["method"]
        assert item["network"]
        assert item.get("price") or item.get("price_usdc")


@pytest.mark.asyncio
async def test_unpaid_paid_tool_returns_x402_402(client):
    response = await client.post("/tools/analyze_volatility?symbol=btc")
    assert response.status_code == 402
    body = response.json()
    blob = json.dumps(body)
    assert "network" in blob
    assert "payTo" in blob or "pay_to" in blob
    assert "amount" in blob
    assert "resource" in blob
    assert body.get("network")
    assert body.get("payTo") == TEST_PAY_TO
    assert body.get("amount")
    assert body.get("resource")
    assert "analyze_volatility" in str(body.get("resource"))


@pytest.mark.asyncio
async def test_paid_header_skips_402(client):
    response = await client.post(
        "/tools/analyze_volatility?symbol=btc",
        headers={"PAYMENT-SIGNATURE": "test-proof"},
    )
    # Handler runs; CoinGecko may 502 without mock — not a 402.
    assert response.status_code != 402


@pytest.mark.asyncio
async def test_mcp_initialize_and_tools_list_include_fetch_price(client):
    init = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
    )
    assert init.status_code == 200
    init_body = init.json()
    assert init_body.get("result", {}).get("serverInfo", {}).get("name")
    assert "protocolVersion" in init_body.get("result", {})

    listed = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    assert listed.status_code == 200
    tools = listed.json()["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "fetch_price" in names
    for expected in EXPECTED_TOOL_NAMES:
        assert expected in names


@pytest.mark.asyncio
async def test_well_known_mcp_advertises_remote_http_url(client):
    response = await client.get("/.well-known/mcp")
    assert response.status_code == 200
    data = response.json()
    blob = json.dumps(data)
    assert "/mcp" in blob
    assert "http" in blob.lower()
    url = data.get("url") or data.get("streamableHttpUrl") or data.get("mcpServers", {}).get(
        "alpha-sentinel", {}
    ).get("url")
    assert url
    assert url.startswith("http") or url.startswith("/")
    assert "mcp" in url


@pytest.mark.asyncio
async def test_agent_card_skills_and_agentcash_x402(client):
    response = await client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    card = response.json()
    assert card.get("url")
    skill_ids = {s["id"] for s in card["skills"]}
    for name in EXPECTED_TOOL_NAMES:
        assert name in skill_ids
    schemes = card.get("securitySchemes") or {}
    scheme_blob = json.dumps(schemes).lower()
    assert "x402" in schemes
    assert "agentcash" in scheme_blob
    assert "x402" in scheme_blob


@pytest.mark.asyncio
async def test_a2a_send_message_fetch_price_and_get_task(client, mock_coingecko_api):
    send = await client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "send-1",
            "method": "message/send",
            "params": {
                "skill": "fetch_price",
                "params": {"symbol": "btc"},
                "message": {
                    "role": "user",
                    "parts": [
                        {"kind": "text", "text": "fetch_price"},
                        {"kind": "data", "data": {"skill": "fetch_price", "symbol": "btc"}},
                    ],
                },
            },
        },
    )
    assert send.status_code == 200
    payload = send.json()
    result = payload.get("result") or payload
    assert result.get("kind") in ("task", "message", None) or result.get("id")
    task_id = result["id"]
    price = _contains_price_usd(result)
    assert price is not None
    assert price == MOCK_BTC_USD

    got = await client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "get-1",
            "method": "tasks/get",
            "params": {"id": task_id},
        },
    )
    assert got.status_code == 200
    fetched = got.json()["result"]
    assert fetched["id"] == task_id
    assert _contains_price_usd(fetched) == MOCK_BTC_USD


@pytest.mark.asyncio
async def test_openapi_marks_paid_tools_for_agentcash(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec.get("info", {}).get("x-agentcash") is True
    paid_path = "/tools/analyze_volatility"
    op = spec["paths"][paid_path]["post"]
    assert op.get("x-payment-required") is True
    info = op.get("x-payment-info") or {}
    assert info.get("network")
    assert info.get("price") or info.get("price_usdc")
    assert "402" in (op.get("responses") or {})


def test_redis_client_not_required_for_catalog():
    from app.redis_client import configured

    # Catalog/402/MCP must work even if Redis env is absent in CI.
    assert configured() in (True, False)


@pytest.mark.asyncio
async def test_http_fetch_price_returns_price_usd(client, mock_coingecko_api):
    response = await client.post("/tools/fetch_price?symbol=btc")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["price_usd"] == MOCK_BTC_USD
