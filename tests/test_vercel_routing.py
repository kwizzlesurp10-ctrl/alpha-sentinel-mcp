"""Vercel routing contract: API paths must rewrite before SPA fallback."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.application import app


def _vercel_config() -> dict:
    return json.loads(Path("vercel.json").read_text(encoding="utf-8"))


def test_vercel_has_no_rewrites_shadowing_fastapi():
    """Project uses Vercel's FastAPI framework preset (entrypoint api.index:app).

    Every request that is not a static file in dashboard/dist is routed to the
    FastAPI app at its original path. Rewrites are applied *before* the app and
    now forward the rewritten destination path, so a catch-all SPA rewrite
    (``/(.*) -> /index.html``) or ``-> /api/index`` rewrites hide the whole API
    (prod served index.html for /health, /mcp, /tools/*). Keep rewrites empty.
    """
    cfg = _vercel_config()
    rewrites = cfg.get("rewrites") or []
    assert not any(r.get("destination") == "/index.html" for r in rewrites)
    assert not any(r.get("destination") == "/api/index" for r in rewrites)
    assert "routes" not in cfg


def test_pyproject_declares_fastapi_entrypoint():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'entrypoint = "api.index:app"' in text


@pytest.mark.asyncio
async def test_fetch_price_unpaid_returns_402_with_payment_required():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in (
            "/tools/fetch_price?symbol=BTC",
            "/api/tools/fetch_price?symbol=BTC",
        ):
            response = await client.get(path)
            assert response.status_code == 402
            assert response.headers.get("PAYMENT-REQUIRED")
            body = response.json()
            assert body.get("network")
            assert "fetch_price" in str(body.get("resource") or "")


@pytest.mark.asyncio
async def test_health_is_json_not_spa():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert "application/json" in (response.headers.get("content-type") or "")
    assert response.json().get("service") == "alpha-sentinel-api"


@pytest.mark.asyncio
async def test_mcp_post_initialize():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            },
        )
    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"]


@pytest.mark.asyncio
async def test_fetch_price_sample_route(monkeypatch):
    from tests.conftest import MOCK_BTC_USD

    async def _fake_fetch(symbol: str):
        return {
            "success": True,
            "data": {"symbol": symbol, "price_usd": MOCK_BTC_USD},
        }

    monkeypatch.setattr(
        "app.intelligence.price_feed.fetch_price_endpoint",
        _fake_fetch,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/tools/fetch_price/sample")
    assert response.status_code == 200
    assert response.json().get("sample") is True
