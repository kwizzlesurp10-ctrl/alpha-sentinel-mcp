"""x402 production gates: 402 shape, tamper/replay, MCP unpaid, discovery, no-mock guard."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.application import app
from app.commerce_payment import clear_tool_challenges
from app.config import settings
from app.payment_replay import clear as clear_replay
from app.tools_registry import PAID_TOOLS


@pytest.fixture(autouse=True)
def _reset_payment_state():
    clear_tool_challenges()
    clear_replay()
    from app import challenge_cache

    challenge_cache.clear()
    yield
    clear_tool_challenges()
    clear_replay()
    challenge_cache.clear()


@pytest.mark.asyncio
async def test_paid_tool_unpaid_returns_402_with_payment_required():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tools/analyze_volatility", json={"symbol": "btc"})
    assert response.status_code == 402
    assert response.headers.get("PAYMENT-REQUIRED")
    body = response.json()
    assert body.get("x402Version") == 2 or body.get("accepts")


@pytest.mark.asyncio
async def test_tampered_payment_required_rejected(monkeypatch):
    from app.tool_payment_gate import build_tool_challenge

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await build_tool_challenge(
            "analyze_volatility",
            "http://test/tools/analyze_volatility",
        )
        evil = "dGVzdA=="
        response = await client.post(
            "/tools/analyze_volatility",
            json={"symbol": "btc"},
            headers={
                "PAYMENT-SIGNATURE": "dGVzdA==",
                "PAYMENT-REQUIRED": evil,
            },
        )
    assert response.status_code == 402
    assert "tampered" in response.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_replay_settlement_rejected():
    from app.payment_replay import claim_settlement_tx

    assert claim_settlement_tx("0xabc") is True
    assert claim_settlement_tx("0xabc") is False


@pytest.mark.asyncio
async def test_well_known_x402_lists_paid_resources():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/.well-known/x402")
    assert response.status_code == 200
    data = response.json()
    assert data.get("x402_version") == 2
    assert data.get("resources")
    assert data.get("catalog")


@pytest.mark.asyncio
async def test_llms_txt_present():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/llms.txt")
    assert response.status_code == 200
    assert "Alpha Sentinel" in response.text


@pytest.mark.asyncio
async def test_mcp_unpaid_paid_tool_returns_structured_payment():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "analyze_volatility", "arguments": {"symbol": "btc"}},
            },
        )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result.get("isError") is True
    sc = result.get("structuredContent") or {}
    assert sc.get("x402Version") == 2
    assert sc.get("accepts")


@pytest.mark.asyncio
async def test_openapi_marks_paid_tools():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/openapi.json")
    schema = response.json()
    paths = schema.get("paths", {})
    paid_path = "/tools/analyze_volatility"
    assert paid_path in paths
    post = paths[paid_path].get("post") or paths[paid_path].get("get")
    assert post.get("x-payment-required") is True


FORBIDDEN_RUNTIME_TOKENS = ("random.randint", "simulate_sentiment", "Simulated verification")


def test_runtime_modules_do_not_import_mock_patterns():
    root = Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_RUNTIME_TOKENS:
            if token in text:
                offenders.append(f"{path.relative_to(root)}: {token}")
    assert not offenders, "runtime mock patterns found:\n" + "\n".join(offenders)


def test_sentiment_module_has_no_random_import():
    path = Path(__file__).resolve().parents[1] / "app" / "intelligence" / "sentiment.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.names[0].name
        for node in tree.body
        if isinstance(node, ast.Import) and node.names
    }
    assert "random" not in imports
