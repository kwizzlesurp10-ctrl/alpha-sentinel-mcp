"""Alpha Sentinel MCP Server - Main FastAPI application."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.commerce import CommerceLayer
from app.x402_services import X402Services
from app.mcp_server import mcp_app
from app.intelligence.price_feed import fetch_price_endpoint
from app.intelligence.volatility import analyze_volatility_endpoint
from app.intelligence.sentiment import aggregate_sentiment_endpoint
from app.intelligence.risk import calculate_risk_score_endpoint
from app.intelligence.reports import generate_market_report_endpoint
from app.tools_registry import TOOL_SPECS, TOOL_COUNT
from app.agent_surface import agent_card, paid_resources

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Alpha Sentinel MCP Server",
    description="""
## Market Intelligence x402 Marketplace 🚀

Real-time crypto market monitoring, volatility alerts, and sentiment analysis 
as paid MCP tools for AI agents.

### Quick Start

**Free Tier:** 500 calls/month, 10/min  
**Pro Tier:** $29/mo, unlimited quota, 120/min  
**Tool Credits:** $1.00 per 100 flexible calls

### Core Tools

- **`fetch_price()`** - Real-time price lookup ($0.005)
- **`analyze_volatility()`** - Anomaly detection ($0.02)  
- **`aggregate_sentiment()`** - Social sentiment aggregation ($0.01)
- **`calculate_risk_score()`** - Multi-factor risk scoring ($0.03)
- **`generate_market_report()`** - Comprehensive reports ($0.15)

### Settlement

All payments settled via x402 on Base network (Sepolia dev / Mainnet prod).
Fiat rail available via Stripe fallback.
    """,
    version="0.1.0",
    contact={
        "name": "Keith Severson",
        "email": settings.contact_email,
    },
)

# CORS middleware (allow dashboard origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize layers
commerce_layer = CommerceLayer(settings)
x402_services = X402Services(settings)

# Mount FastMCP server
mcp_app.mount(app)


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "service": "Alpha Sentinel MCP Server",
        "version": "0.1.0",
        "status": "operational",
        "tools_count": TOOL_COUNT,
        "documentation": "/docs",
        "agent_card": "/.well-known/agent-card.json",
        "mcp_manifest": "/.well-known/mcp",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": "now",
        "components": {
            "api": "running",
            "commerce": commerce_layer.status(),
            "x402": await x402_services.status() if x402_services else "disabled",
        }
    }


# ============================================================================
# MCP Tool Endpoints (direct HTTP access as x402-gated resources)
# ============================================================================

@app.post("/tools/fetch_price")
async def http_fetch_price(
    symbol: str = Query(..., description="Crypto symbol (e.g., btc, eth)")
):
    """HTTP endpoint for price feed (x402-gated).
    
    This is the paid resource path - requires settlement before execution.
    MCP tool calls go through /mcp instead.
    """
    try:
        result = await fetch_price_endpoint(symbol)
        return result
    except Exception as e:
        logger.error(f"Price fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/analyze_volatility")
async def http_analyze_volatility(
    symbol: str = Query(...),
    window_minutes: int = Query(default=60, ge=1, le=1440),
    z_threshold: float = Query(default=2.0, ge=0.1, le=5.0)
):
    """HTTP endpoint for volatility analysis (x402-gated)."""
    try:
        result = await analyze_volatility_endpoint(symbol, window_minutes, z_threshold)
        return result
    except Exception as e:
        logger.error(f"Volatility analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/aggregate_sentiment")
async def http_aggregate_sentiment(
    symbols: list[str] = Query(..., description="List of crypto symbols"),
    sources: list[str] = Query(default=["twitter", "reddit"], description="Data sources"),
    window_minutes: int = Query(default=60, ge=5, le=1440)
):
    """HTTP endpoint for sentiment aggregation (x402-gated)."""
    try:
        result = await aggregate_sentiment_endpoint(symbols, sources, window_minutes)
        return result
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/calculate_risk")
async def http_calculate_risk(
    symbols: list[str] = Query(...),
    include_factors: list[str] = Query(default=["volatility", "liquidity", "correlation"])
):
    """HTTP endpoint for risk assessment (x402-gated)."""
    try:
        result = await calculate_risk_score_endpoint(symbols, include_factors)
        return result
    except Exception as e:
        logger.error(f"Risk calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/generate_report")
async def http_generate_report(
    report_type: str = Query(default="daily", enum=["daily", "weekly", "monthly"]),
    symbols: list[str] = Query(default=["btc", "eth"]),
    format: str = Query(default="json", enum=["json", "pdf"])
):
    """HTTP endpoint for market report generation (x402-gated)."""
    try:
        result = await generate_market_report_endpoint(report_type, symbols, format)
        return result
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Agent Card & Discovery (/.well-known/)
# ============================================================================

@app.get("/.well-known/agent-card.json")
async def agent_card_endpoint():
    """Agent card for discoverability (A2A protocol)."""
    return agent_card()


@app.get("/.well-known/mcp")
async def mcp_manifest():
    """MCP tool registry manifest."""
    from fastapi.responses import JSONResponse
    manifest = {
        "mcpServers": {
            "alpha-sentinel": {
                "command": "python",
                "args": ["run_stdio.py"],
                "description": "Alpha Sentinel Market Intelligence",
                "tools": TOOL_SPECS,
            }
        }
    }
    return JSONResponse(content=manifest)


@app.get("/.well-known/paid-resources")
async def paid_resources_endpoint():
    """Paid resources catalog for Bazaar discovery."""
    return paid_resources()


# ============================================================================
# Commerce & Quota Endpoints
# ============================================================================

@app.get("/quota/{agent_id}")
async def get_quota(agent_id: str):
    """Get remaining quota for an agent."""
    quota = commerce_layer.get_quota(agent_id)
    return {
        "agent_id": agent_id,
        "tier": quota.tier,
        "remaining": quota.remaining,
        "remaining_calls": quota.remaining,
        "limit": quota.limit,
        "rate_limit_per_min": quota.rate_limit_per_min,
        "reset_at": quota.reset_at.isoformat() if quota.reset_at else None,
    }


@app.get("/stats")
async def get_stats():
    """Live usage statistics."""
    stats = commerce_layer.get_stats()
    return {
        "total_agents": stats.get("total_agents", 0),
        "free_tier_active": stats.get("free_active", 0),
        "pro_tier_active": stats.get("pro_active", 0),
        "tool_credits_sold": stats.get("tool_credits_sold", 0),
        "revenue_today_usd": stats.get("revenue_today_usd", 0.0),
        "calls_today": stats.get("calls_today", 0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0.0),
    }


# ============================================================================
# Pulse & Diligence Products
# ============================================================================

@app.get("/pulse")
async def get_pulse_report(block_depth: int = Query(default=12, ge=1, le=100)):
    """Base network Pulse synthesis report (paid resource)."""
    try:
        from app.pulse import generate_pulse_report
        return await generate_pulse_report(block_depth)
    except Exception as e:
        logger.error(f"Pulse generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/us-rental-diligence")
async def us_rental_diligence(
    property_addresses: list[str] = Query(..., max_items=5),
    cities: list[str] = Query(...)  # e.g., ["minneapolis", "mn"]
):
    """US Rental Diligence Pack - multi-property compliance check.
    
    Combines municipal open-data sources to check:
    - Rental license status
    - Violation history
    - Tenant rights compliance
    - Property condemnation records
    
    Price: $1.50 (clamped to [0.75, 2.50] USD)
    """
    try:
        from app.city_compliance import rental_diligence_composite
        return await rental_diligence_composite(property_addresses, cities)
    except Exception as e:
        logger.error(f"Diligence pack failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Ledger & Settlement
# ============================================================================

@app.get("/ledger/{name}")
async def get_ledger(name: str):
    """Get ledger entries (git-ignored jsonl files)."""
    if name not in ["spend", "revenue"]:
        raise HTTPException(status_code=400, detail="name must be 'spend' or 'revenue'")
    
    try:
        with open(f"ledger/{name}.jsonl", "r") as f:
            entries = [line.strip() for line in f if line.strip()]
        return {"name": name, "count": len(entries), "entries": entries[-100:]}
    except FileNotFoundError:
        return {"name": name, "count": 0, "entries": []}


@app.get("/wallet")
async def get_wallet_info():
    """Get wallet addresses (public info only)."""
    wallet_info = {
        "seller_receive_address": settings.x402_pay_to_address[:10] + "..." 
                                   if settings.x402_pay_to_address else None,
        "buyer_address": "configured" if settings.evm_private_key else "not configured",
        "network": settings.x402_default_network,
    }
    return wallet_info


# ============================================================================
# Swarm Agency Stats (if enabled)
# ============================================================================

@app.get("/swarm/stats")
async def get_swarm_stats():
    """Swarm agency operational metrics."""
    if not settings.swarm_enabled:
        return {"enabled": False, "message": "Swarm agency disabled"}
    
    try:
        from app.swarm.assessor import Assessor
        assessor = Assessor()
        score = assessor.score_profit_routes()
        
        return {
            "enabled": True,
            "ltv_cac_ratio": score.ltv_cac,
            "target_ltv_cac": settings.swarm_target_ltv_cac,
            "margin_ratio": score.margin_ratio,
            "profit_routes_found": len(score.routes),
            "top_route": score.top_route.dict() if score.top_route else None,
        }
    except Exception as e:
        logger.error(f"Swarm stats failed: {e}")
        return {"error": str(e)}


# ============================================================================
# Operator Actions (dashboard POST endpoints)
# ============================================================================

@app.post("/operator/settle-composite-sale")
async def operator_settle_composite_sale(
    composite_id: str,
    buyer_address: str,
    amount_usd: float,
):
    """Operator action: settle a swarm composite sale.
    
    Only enabled when DASHBOARD_ACTIONS=true in environment.
    """
    if not settings.dashboard_actions:
        raise HTTPException(status_code=403, detail="Dashboard actions disabled")
    
    try:
        from app.swarm.merchant import settle_composite_sale
        await settle_composite_sale(composite_id, buyer_address, amount_usd)
        return {"status": "settled", "composite_id": composite_id}
    except Exception as e:
        logger.error(f"Composite settlement failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/operator/update-tool-price")
async def operator_update_tool_price(
    tool_name: str,
    new_price: str,
):
    """Operator action: update MCP tool pricing dynamically."""
    if not settings.dashboard_actions:
        raise HTTPException(status_code=403, detail="Dashboard actions disabled")
    
    try:
        from app.tools_registry import update_tool_price
        update_tool_price(tool_name, new_price)
        return {"status": "updated", "tool": tool_name, "new_price": new_price}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Price update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Application Lifecycle
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("🚀 Alpha Sentinel MCP Server starting up...")
    logger.info(f"📊 Tools registered: {TOOL_COUNT}")
    logger.info(f"💰 Seller address: {settings.x402_pay_to_address[:10] + '...' if settings.x402_pay_to_address else 'NOT CONFIGURED'}")
    
    if settings.cdp_api_key_id and settings.cdp_api_key_secret:
        logger.info("✅ CDP facilitator configured for mainnet selling")
    else:
        logger.warning("⚠️  CDP credentials not set - will only sell on Sepolia testnet")
    
    if settings.redis_url:
        logger.info("✅ Redis configured for state persistence")
    else:
        logger.info("ℹ️  Using in-memory stores (consider Redis for production)")
    
    if settings.swarm_enabled:
        logger.info("🦋 Swarm agency enabled - buy-compose-resell active!")
    else:
        logger.info("ℹ️  Swarm agency disabled")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("👋 Alpha Sentinel shutting down...")


# ============================================================================
# OpenAPI Customization
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
