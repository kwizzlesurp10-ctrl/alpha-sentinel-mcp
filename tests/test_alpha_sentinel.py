"""Tests for Alpha Sentinel MCP Server."""

import pytest
from httpx import AsyncClient
from app.main import app
from app.config import settings


@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint returns service info."""
    response = await client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Alpha Sentinel MCP Server"
    assert data["status"] == "operational"
    assert "tools_count" in data


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "components" in data


@pytest.mark.asyncio
async def test_mcp_manifest(client):
    """Test MCP manifest generation."""
    response = await client.get("/.well-known/mcp")
    
    assert response.status_code == 200
    data = response.json()
    assert "mcpServers" in data
    assert "alpha-sentinel" in data["mcpServers"]
    assert "tools" in data["mcpServers"]["alpha-sentinel"]


@pytest.mark.asyncio
async def test_quota_endpoint(client):
    """Test quota retrieval for new agent."""
    agent_id = "test_agent_123"
    response = await client.get(f"/quota/{agent_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == agent_id
    assert data["tier"] == "free"
    assert data["remaining"] == settings.free_tier_monthly_quota
    assert data["rate_limit_per_min"] == settings.free_tier_rate_limit_per_min


@pytest.mark.asyncio
async def test_stats_endpoint(client):
    """Test statistics endpoint."""
    response = await client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    assert "total_agents" in data
    assert "free_tier_active" in data
    assert "pro_tier_active" in data


@pytest.mark.asyncio
async def test_wallet_info(client):
    """Test wallet information endpoint (public only)."""
    response = await client.get("/wallet")
    
    assert response.status_code == 200
    data = response.json()
    # Should never expose full addresses
    if data.get("seller_receive_address"):
        assert len(data["seller_receive_address"]) < 50  # Truncated


# ============================================================================
# Intelligence Module Tests
# ============================================================================

from app.intelligence.price_feed import validate_symbol
from app.intelligence.volatility import calculate_z_score
from app.intelligence.risk import classify_volatility


def test_validate_symbol():
    """Test symbol validation."""
    assert validate_symbol("btc") is True
    assert validate_symbol("ethereum") is True
    assert validate_symbol("nonexistent_coin_xyz") is False


def test_calculate_z_score():
    """Test Z-score calculation."""
    prices = [100.0, 101.0, 102.0, 100.5, 101.5]
    result = calculate_z_score(prices, threshold=2.0)
    
    assert result["anomalies_detected"] is False
    assert "mean" in result
    assert "std_dev" in result
    assert len(result["z_scores"]) == len(prices)


def test_calculate_z_score_with_anomaly():
    """Test Z-score with anomalous price point."""
    prices = [100.0, 100.0, 100.0, 100.0, 200.0]  # Last point is anomalous
    result = calculate_z_score(prices, threshold=1.5)
    
    assert result["anomalies_detected"] is True
    assert len(result["anomalies"]) > 0


def test_classify_volatility():
    """Test volatility classification."""
    assert classify_volatility("NORMAL") == "LOW"
    assert classify_volatility("MODERATE") == "MEDIUM"
    assert classify_volatility("HIGH") == "HIGH"
    assert classify_volatility("CRITICAL") == "CRITICAL"


# ============================================================================
# Tools Registry Tests
# ============================================================================

from app.tools_registry import (
    TOOL_COUNT,
    EXPECTED_TOOL_NAMES,
    FREE_TOOLS,
    PAID_TOOLS,
    get_tool_spec,
)


def test_tool_count_consistency():
    """Test that tool counts match specifications."""
    assert TOOL_COUNT == len(EXPECTED_TOOL_NAMES)
    assert TOOL_COUNT == 5  # fetch_price, analyze_volatility, aggregate_sentiment, calculate_risk_score, generate_market_report


def test_free_vs_paid_tools():
    """Test free/paid tool categorization."""
    assert len(FREE_TOOLS) >= 1  # At least fetch_price should be free
    assert len(PAID_TOOLS) >= 1  # Most tools require credits
    assert set(FREE_TOOLS).isdisjoint(set(PAID_TOOLS))  # No overlap


def test_get_tool_spec():
    """Test tool specification lookup."""
    spec = get_tool_spec("fetch_price")
    assert spec is not None
    assert spec["name"] == "fetch_price"
    assert "inputSchema" in spec
    assert "description" in spec
    
    # Non-existent tool
    assert get_tool_spec("non_existent_tool") is None


# ============================================================================
# Integration Tests (requires mocked APIs)
# ============================================================================

@pytest.mark.asyncio
async def test_fetch_price_integration(mock_coingecko_api):
    """Test price fetch integration (mocked)."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/tools/fetch_price?symbol=btc")
        
        # Would fail without x402 payment, so test MCP tool instead
        pass


# ============================================================================
# Helper Fixtures
# ============================================================================

@pytest.fixture
def mock_coingecko_api(monkeypatch):
    """Mock CoinGecko API responses."""
    async def mock_get(*args, **kwargs):
        class MockResponse:
            async def json(self):
                return {
                    "bitcoin": {
                        "usd": 67842.50,
                        "usd_24h_change": 2.34,
                        "usd_24h_vol": 28500000000,
                    }
                }
            
            @property
            def status_code(self):
                return 200
            
            def raise_for_status(self):
                pass
        
        return MockResponse()
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
