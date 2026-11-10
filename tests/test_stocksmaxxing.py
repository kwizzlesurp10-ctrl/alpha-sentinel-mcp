"""Stocks Maxxing tokenized-stock tools — fixture-backed, no live price fabrication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.application import app
from app.stocksmaxxing.disclaimer import DISCLAIMER_SHORT
from app.stocksmaxxing.executor import execute_stocksmaxxing_tool

FIXTURES = Path(__file__).parent / "fixtures" / "tokenized_stocks_crcl.json"
FIXTURE_DATA = json.loads(FIXTURES.read_text(encoding="utf-8"))


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def mock_stocksmaxxing_upstream(monkeypatch):
    """Patch outbound HTTP for Coinbase tokenized stocks + Yahoo underlying quotes."""
    import httpx

    original_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_s = str(url)
        if not url_s.startswith("http") or url_s.startswith("http://test"):
            return await original_get(self, url, *args, **kwargs)

        class MockResponse:
            def __init__(self, payload, status=200):
                self._payload = payload
                self.status_code = status

            def json(self):
                return self._payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

        if "tokenized-stocks" in url_s:
            if url_s.endswith("/tokenized-stocks") or "/tokenized-stocks?" in url_s:
                return MockResponse(FIXTURE_DATA["list_page"])
            if "/metadata/" in url_s:
                return MockResponse(FIXTURE_DATA["metadata"])
            if "/chains" in url_s:
                return MockResponse(FIXTURE_DATA["chains"])
            if "/corporate-actions/" in url_s:
                return MockResponse(FIXTURE_DATA["corporate_action"])
            return MockResponse({"code": 5, "message": "not found"}, status=404)
        if "finance/chart" in url_s:
            return MockResponse(FIXTURE_DATA["yahoo_chart"])
        if "geckoterminal.com" in url_s:
            return MockResponse(
                {
                    "data": {
                        "attributes": {
                            "price_usd": "67.04",
                            "volume_usd": {"h24": "1000.0"},
                        }
                    }
                }
            )
        if "coingecko" in url_s or "ping" in url_s:
            return MockResponse({})
        return MockResponse({})

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)


def test_disclaimer_present_on_tool_output():
    payload = {"success": True, "data": {}}
    from app.stocksmaxxing.disclaimer import with_disclaimer

    out = with_disclaimer(payload)
    assert out["research_only"] is True
    assert out["no_trading_or_execution"] is True
    assert DISCLAIMER_SHORT in out["disclaimer"]


@pytest.mark.asyncio
async def test_tokenized_stock_list_sample(client):
    response = await client.get("/tools/tokenized_stock_list/sample")
    assert response.status_code == 200
    body = response.json()
    assert body.get("sample") is True
    preview = body.get("preview") or {}
    structured = preview.get("structuredContent") or preview
    assert structured.get("success") is True
    tokens = (structured.get("data") or {}).get("tokens") or []
    assert any(t.get("symbol") == "CRCLc" for t in tokens)


@pytest.mark.asyncio
async def test_research_brief_includes_proof_of_research_receipt():
    from app.stocksmaxxing.executor import execute_stocksmaxxing_tool

    result = await execute_stocksmaxxing_tool(
        "tokenized_stock_research_brief", {"symbols": ["CRCLc"]}
    )
    assert result["success"] is True
    receipt = result["data"]["proof_of_research_receipt"]
    assert receipt["content_hash"].startswith("0x")
    assert len(receipt["content_hash"]) == 66
    assert receipt["canonical_attestation"]["symbols"] == ["CRCLc"]


@pytest.mark.asyncio
async def test_canonical_hash_stable():
    from app.stocksmaxxing.research_receipt import build_attestation_payload, sha256_hex

    body = build_attestation_payload(
        symbols=["CRCLc"],
        sections=[{"symbol": "CRCLc", "summary": "test"}],
        data_sources=["a", "b"],
        generated_at="2026-11-10T10:00:00+00:00",
    )
    h1 = sha256_hex(body)
    h2 = sha256_hex(body)
    assert h1 == h2


@pytest.mark.asyncio
async def test_seal_receipt_prepared_without_registry():
    from app.stocksmaxxing.services import tokenized_stock_seal_receipt_endpoint

    out = await tokenized_stock_seal_receipt_endpoint(
        content_hash="0x" + "ab" * 32,
        brief_id="cafebabe",
    )
    assert out["success"] is True
    assert out["data"]["seal"]["status"] == "registry_not_configured"


@pytest.mark.asyncio
async def test_verify_receipt_public(client):
    from app.stocksmaxxing.research_receipt import build_attestation_payload, sha256_hex

    body = build_attestation_payload(
        symbols=["CRCLc"],
        sections=[{"symbol": "CRCLc"}],
        data_sources=["https://api.coinbase.com/v1/tokenized-stocks", "yahoo"],
        generated_at="2026-11-10T10:00:00+00:00",
    )
    ch = sha256_hex(body)
    response = await client.post(
        "/stocksmaxxing/verify-receipt",
        json={"canonical_attestation": body, "content_hash": ch},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["hash_matches_payload"] is True
    assert payload["computed_hash"] == ch


@pytest.mark.asyncio
async def test_peg_gap_radar_executor():
    from app.stocksmaxxing.executor import execute_stocksmaxxing_tool

    result = await execute_stocksmaxxing_tool(
        "tokenized_stock_peg_gap_radar",
        {"alert_threshold_pct": 0.01, "symbols": ["CRCLc"]},
    )
    assert result["success"] is True
    rows = result["data"]["rows"]
    assert len(rows) == 1
    assert rows[0].get("gap_pct") is not None


@pytest.mark.asyncio
async def test_tokenized_stock_lookup_sample(client):
    response = await client.get("/tools/tokenized_stock_lookup/sample")
    assert response.status_code == 200
    body = response.json()
    structured = (body.get("preview") or {}).get("structuredContent") or body.get("preview") or {}
    assert structured.get("success") is True
    catalog = (structured.get("data") or {}).get("catalog_record") or {}
    assert catalog.get("symbol") == "CRCLc"


@pytest.mark.asyncio
async def test_unpaid_stocks_tool_returns_402(client):
    response = await client.post("/tools/tokenized_stock_nav_deviation", json={"symbol": "CRCLc"})
    assert response.status_code == 402
    assert response.headers.get("PAYMENT-REQUIRED")


@pytest.mark.asyncio
async def test_nav_deviation_executor():
    result = await execute_stocksmaxxing_tool(
        "tokenized_stock_nav_deviation", {"symbol": "CRCLc"}
    )
    assert result["success"] is True
    data = result["data"]
    assert data["nav_price_usd"] == 67.1
    assert data["underlying_price_usd"] == 67.56
    assert data["deviation_pct"] is not None
    assert result["disclaimer"]


@pytest.mark.asyncio
async def test_model_portfolio_executor():
    result = await execute_stocksmaxxing_tool(
        "tokenized_stock_model_portfolio",
        {"symbols": ["CRCLc"], "objective": "diversified"},
    )
    assert result["success"] is True
    weights = result["data"]["suggested_weights"]
    assert weights.get("CRCLc") == 1.0
    assert result["no_trading_or_execution"] is True


@pytest.mark.asyncio
async def test_nav_missing_returns_error(monkeypatch):
    async def mock_get(self, url, *args, **kwargs):
        class MockResponse:
            status_code = 200

            def json(self):
                return {
                    "tokens": [
                        {
                            "symbol": "NAVLESSc",
                            "name": "No Nav Inc",
                            "multiplier": 1,
                        }
                    ]
                }

            def raise_for_status(self):
                return None

        return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    from app.stocksmaxxing.services import tokenized_stock_nav_deviation_endpoint

    out = await tokenized_stock_nav_deviation_endpoint("NAVLESSc")
    assert out["success"] is False
    assert out["code"] == "nav_unavailable"
