"""Tests for Human SEO landing page, LLM SEO JSON-LD, Protocol SEO manifests, and Long-Tail SEO Playbooks."""

from __future__ import annotations

import json
import re

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.application import app
from app.stocksmaxxing.registry import STOCKSMAXXING_TOOL_NAMES
from app.tools_registry import EXPECTED_TOOL_NAMES

LANDING_PAGE_TOOL_NAMES = [t for t in EXPECTED_TOOL_NAMES if t not in STOCKSMAXXING_TOOL_NAMES]


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_semantic_landing_page_human_seo(client):
    """Verify `/` serves high-text-density semantic HTML with required H1, keyword clusters, and tool directory."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in (resp.headers.get("content-type") or "").lower()
    html = resp.text

    # 1. Exact H1 Header
    assert "<h1>Predictive Crypto Intelligence Hub for AI Agents.</h1>" in html

    # 2. Keyword Clusters
    for kw in (
        "Predictive Alpha",
        "On-chain Market Intelligence",
        "x402 Monetized API",
        "Autonomous Trading Data",
    ):
        assert kw in html, f"Missing keyword cluster '{kw}' on landing page"

    # 3. Tool directory lists legacy crypto intel tools (stocksmaxxing tools live under /tools/* + docs/stocksmaxxing.md)
    for tool in LANDING_PAGE_TOOL_NAMES:
        assert tool in html, f"Missing tool '{tool}' in landing page directory"
        assert f"/tools/{tool}" in html, f"Missing internal link to /tools/{tool}"
    assert "stocksmaxxing" in html.lower() or "/docs/stocksmaxxing" in html

    # 4. Internal links to Playbooks and Protocol Manifests
    for link in (
        "/docs",
        "/docs/automate-volatility-alerts",
        "/docs/integrate-predictive-alpha",
        "/docs/reduce-slippage-sentiment",
        "/.well-known/mcp.json",
    ):
        assert link in html, f"Missing internal link '{link}' on landing page"


@pytest.mark.asyncio
async def test_structured_data_llm_seo_json_ld(client):
    """Verify JSON-LD schema on landing page declares SoftwareApplication / Service, API Service, and Financial Market Analysis."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text

    matches = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert matches, "Expected at least one <script type='application/ld+json'> block"

    blob = "\n".join(matches)
    parsed = [json.loads(m.strip()) for m in matches]
    assert parsed

    assert "SoftwareApplication" in blob or "Service" in blob
    assert "API Service" in blob
    assert "Financial Market Analysis" in blob


@pytest.mark.asyncio
async def test_protocol_seo_mcp_json_and_robots_txt(client):
    """Verify /.well-known/mcp.json and /robots.txt explicitly allow x402 and Google bots."""
    mcp_resp = await client.get("/.well-known/mcp.json")
    assert mcp_resp.status_code == 200
    mcp_data = mcp_resp.json()
    assert "mcpServers" in mcp_data
    assert "alpha-sentinel" in mcp_data["mcpServers"]
    assert mcp_data["count"] == len(EXPECTED_TOOL_NAMES)

    robots_resp = await client.get("/robots.txt")
    assert robots_resp.status_code == 200
    robots_txt = robots_resp.text
    assert "x402" in robots_txt
    assert "Googlebot" in robots_txt
    assert "Allow: /" in robots_txt
    assert "/.well-known/mcp.json" in robots_txt

    sitemap_resp = await client.get("/sitemap.xml")
    assert sitemap_resp.status_code == 200
    assert "/docs/automate-volatility-alerts" in sitemap_resp.text
    assert "/docs/integrate-predictive-alpha" in sitemap_resp.text
    assert "/docs/reduce-slippage-sentiment" in sitemap_resp.text


@pytest.mark.asyncio
async def test_long_tail_seo_playbooks_docs(client):
    """Verify /docs and all three specific Playbooks render with exact H1 headers."""
    hub = await client.get("/docs")
    assert hub.status_code == 200
    assert "text/html" in (hub.headers.get("content-type") or "").lower()
    assert "How to automate volatility alerts using Alpha Sentinel" in hub.text
    assert "Integrating predictive alpha into an autonomous trading agent" in hub.text
    assert "Reducing slippage with real-time sentiment analysis" in hub.text

    playbooks = {
        "/docs/automate-volatility-alerts": "How to automate volatility alerts using Alpha Sentinel",
        "/docs/integrate-predictive-alpha": "Integrating predictive alpha into an autonomous trading agent",
        "/docs/reduce-slippage-sentiment": "Reducing slippage with real-time sentiment analysis",
    }
    for path, expected_h1 in playbooks.items():
        r = await client.get(path)
        assert r.status_code == 200, f"Playbook {path} returned {r.status_code}"
        assert "text/html" in (r.headers.get("content-type") or "").lower()
        assert f"<h1>{expected_h1}</h1>" in r.text
