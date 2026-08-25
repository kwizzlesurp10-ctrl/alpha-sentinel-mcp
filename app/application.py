"""Alpha Sentinel MCP Server - Main FastAPI application (Vercel + local)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from app.agent_surface import agent_card, paid_resources
from app.commerce import CommerceLayer
from app.config import settings
from app.intelligence.price_feed import fetch_price_endpoint
from app.intelligence.reports import generate_market_report_endpoint
from app.intelligence.risk import calculate_risk_score_endpoint
from app.intelligence.sentiment import aggregate_sentiment_endpoint
from app.intelligence.volatility import analyze_volatility_endpoint
from app.tools_registry import (
    EXPECTED_TOOL_NAMES,
    FREE_TOOLS,
    PAID_TOOLS,
    TOOL_COUNT,
    TOOL_PRICES,
    TOOL_SPECS,
)
from app.x402_services import X402Services

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Alpha Sentinel MCP Server",
    description="Market Intelligence x402 Marketplace — predictive crypto intel for AI agents.",
    version="0.2.0",
    contact={"name": "Keith Severson", "email": settings.contact_email},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

commerce_layer = CommerceLayer(settings)
x402_services = X402Services(settings)

# FastMCP is optional — never block HTTP boot on serverless cold start.
try:
    from app.mcp_server import mcp_app  # type: ignore

    if hasattr(mcp_app, "http_app"):
        app.mount("/mcp", mcp_app.http_app())
        logger.info("FastMCP mounted at /mcp via http_app()")
    elif hasattr(mcp_app, "sse_app"):
        app.mount("/mcp", mcp_app.sse_app())
        logger.info("FastMCP mounted at /mcp via sse_app()")
    elif hasattr(mcp_app, "mount"):
        mcp_app.mount(app)
        logger.info("FastMCP mounted via .mount(app)")
    else:
        logger.warning("FastMCP present but no mount/http_app/sse_app — HTTP tools only")
except Exception as exc:  # noqa: BLE001
    logger.warning("FastMCP unavailable (%s) — HTTP tool endpoints still active", exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.middleware("http")
async def normalize_vercel_api_path(request: Request, call_next):
    """Map Vercel function paths so routes resolve under /api/* and bare /*.

    Vercel may present:
      - /api
      - /api/health
      - /health (via rewrite)
      - /index / /index.py quirks
    """
    path = request.scope.get("path", "") or "/"

    # Strip accidental script suffixes
    for junk in ("/index.py", "/index"):
        if path.endswith(junk):
            path = path[: -len(junk)] or "/"

    # If path is exactly the function root, treat as /
    if path in ("/api", "/api/"):
        path = "/"
    elif path.startswith("/api/"):
        # Keep /api/* as-is (routes are registered with /api prefix too)
        # Also expose bare path twin via duplicate router — no strip needed.
        pass

    if path != request.scope.get("path"):
        request.scope["path"] = path
        request.scope["raw_path"] = path.encode("utf-8")

    return await call_next(request)


api = APIRouter(tags=["alpha-sentinel"])


# Root "/" is reserved for Mission Control SPA (see api/index.py).
# API discovery lives at /health and /docs.


@api.get("/health")
async def health_check():
    x402_status = await x402_services.status() if x402_services else {"enabled": False}
    return {
        "status": "healthy",
        "service": "alpha-sentinel-api",
        "version": "0.2.0",
        "timestamp": _now_iso(),
        "components": {
            "api": "running",
            "commerce": commerce_layer.status(),
            "x402": x402_status,
        },
    }


@api.get("/doctor")
async def doctor():
    """Ops readiness checks for Mission Control."""
    checks = []

    pay_to = settings.x402_pay_to_address
    checks.append(
        {
            "id": "pay_to",
            "name": "Seller receive address",
            "status": "pass" if pay_to else "fail",
            "message": f"Configured ({pay_to[:10]}…)" if pay_to else "X402_PAY_TO_ADDRESS missing",
            "fix": "Set X402_PAY_TO_ADDRESS in Vercel env (seller cold wallet only)",
        }
    )

    checks.append(
        {
            "id": "buyer_key",
            "name": "Buyer private key (must stay local)",
            "status": "pass" if not settings.evm_private_key else "warn",
            "message": "Not set on server (correct)"
            if not settings.evm_private_key
            else "EVM_PRIVATE_KEY is set on server — move to local-only",
            "fix": "Unset EVM_PRIVATE_KEY on Vercel; keep buyer key in ~/secrets only",
        }
    )

    checks.append(
        {
            "id": "network",
            "name": "Default settlement network",
            "status": "pass",
            "message": settings.x402_default_network,
        }
    )

    checks.append(
        {
            "id": "tools",
            "name": "Tool registry",
            "status": "pass" if TOOL_COUNT >= 5 else "fail",
            "message": f"{TOOL_COUNT} tools registered ({len(FREE_TOOLS)} free)",
        }
    )

    cg_ok = False
    cg_msg = "not probed"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{settings.coingecko_base_url}/ping")
            cg_ok = r.status_code == 200
            cg_msg = f"HTTP {r.status_code}"
    except Exception as exc:  # noqa: BLE001
        cg_msg = str(exc)[:120]

    checks.append(
        {
            "id": "coingecko",
            "name": "CoinGecko reachability",
            "status": "pass" if cg_ok else "warn",
            "message": cg_msg,
            "fix": "Optional COINGECKO_API_KEY for higher rate limits",
        }
    )

    worst = "pass"
    for c in checks:
        if c["status"] == "fail":
            worst = "fail"
            break
        if c["status"] == "warn" and worst == "pass":
            worst = "warn"

    return {"status": worst, "timestamp": _now_iso(), "checks": checks}


@api.api_route("/tools/fetch_price", methods=["GET", "POST"])
async def http_fetch_price(
    symbol: str = Query(..., description="Crypto symbol (e.g., btc, eth)"),
):
    """Free-tier friendly price feed (GET or POST)."""
    try:
        result = await fetch_price_endpoint(symbol)
        commerce_layer.consume_call("anonymous", cost_usd=0.0)
        return result
    except Exception as e:
        logger.error("Price fetch failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@api.api_route("/tools/analyze_volatility", methods=["GET", "POST"])
async def http_analyze_volatility(
    symbol: str = Query(...),
    window_minutes: int = Query(default=60, ge=1, le=1440),
    z_threshold: float = Query(default=2.0, ge=0.1, le=5.0),
):
    try:
        return await analyze_volatility_endpoint(symbol, window_minutes, z_threshold)
    except Exception as e:
        logger.error("Volatility analysis failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@api.api_route("/tools/aggregate_sentiment", methods=["GET", "POST"])
async def http_aggregate_sentiment(
    symbols: list[str] = Query(default=["btc", "eth"]),
    sources: list[str] = Query(default=["twitter", "reddit"]),
    window_minutes: int = Query(default=60, ge=5, le=1440),
):
    try:
        return await aggregate_sentiment_endpoint(symbols, sources, window_minutes)
    except Exception as e:
        logger.error("Sentiment analysis failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@api.api_route("/tools/calculate_risk", methods=["GET", "POST"])
async def http_calculate_risk(
    symbols: list[str] = Query(default=["btc", "eth"]),
    include_factors: list[str] = Query(default=["volatility", "liquidity", "correlation"]),
):
    try:
        return await calculate_risk_score_endpoint(symbols, include_factors)
    except Exception as e:
        logger.error("Risk calculation failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@api.api_route("/tools/generate_report", methods=["GET", "POST"])
async def http_generate_report(
    report_type: Literal["daily", "weekly", "monthly"] = Query(default="daily"),
    symbols: list[str] = Query(default=["btc", "eth"]),
    format: Literal["json", "pdf"] = Query(default="json"),
):
    try:
        return await generate_market_report_endpoint(report_type, symbols, format)
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@api.get("/.well-known/agent-card.json")
async def agent_card_endpoint():
    return agent_card()


@api.get("/.well-known/mcp")
async def mcp_manifest():
    manifest = {
        "mcpServers": {
            "alpha-sentinel": {
                "command": "python",
                "args": ["run_stdio.py"],
                "description": "Alpha Sentinel Market Intelligence",
                "tools": TOOL_SPECS,
            }
        },
        "tools": [
            {
                "name": t["name"],
                "description": t["description"][:280],
                "price": TOOL_PRICES.get(t["name"], "$0.01"),
                "free_tier": t["tier_access"]["free"],
            }
            for t in TOOL_SPECS
        ],
        "count": TOOL_COUNT,
        "http_base": "/api/tools",
    }
    return JSONResponse(content=manifest)


@api.get("/.well-known/paid-resources")
async def paid_resources_endpoint():
    return paid_resources()


@api.get("/quota/{agent_id}")
async def get_quota(agent_id: str):
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


@api.get("/stats")
async def get_stats():
    stats = commerce_layer.get_stats()
    commerce_status = commerce_layer.status()
    return {
        "total_agents": stats.get("total_agents", 0),
        "free_tier_active": max(
            stats.get("free_active", 0), commerce_status.get("free_tier_count", 0)
        ),
        "pro_tier_active": max(
            stats.get("pro_active", 0), commerce_status.get("pro_tier_count", 0)
        ),
        "tool_credits_sold": stats.get("tool_credits_sold", 0),
        "revenue_today_usd": stats.get("revenue_today_usd", 0.0),
        "calls_today": stats.get("calls_today", 0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0.0),
        "active_tools": EXPECTED_TOOL_NAMES,
        "free_tools": FREE_TOOLS,
        "paid_tools": PAID_TOOLS,
        "tool_count": TOOL_COUNT,
        "pricing": TOOL_PRICES,
        "network": settings.x402_default_network,
        "pay_to_configured": bool(settings.x402_pay_to_address),
        "timestamp": _now_iso(),
    }


@api.get("/pulse")
async def get_pulse_report(block_depth: int = Query(default=12, ge=1, le=100)):
    try:
        from app.pulse import generate_pulse_report  # optional module

        return await generate_pulse_report(block_depth)
    except ImportError:
        return {
            "status": "stub",
            "message": "Pulse module not bundled in this build",
            "block_depth": block_depth,
            "timestamp": _now_iso(),
        }
    except Exception as e:
        logger.error("Pulse generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@api.get("/ledger/{name}")
async def get_ledger(name: str):
    if name not in ["spend", "revenue"]:
        raise HTTPException(status_code=400, detail="name must be 'spend' or 'revenue'")
    try:
        with open(f"ledger/{name}.jsonl", encoding="utf-8") as f:
            entries = [line.strip() for line in f if line.strip()]
        return {"name": name, "count": len(entries), "entries": entries[-100:]}
    except FileNotFoundError:
        return {"name": name, "count": 0, "entries": []}


@api.get("/wallet")
async def get_wallet_info():
    addr = settings.x402_pay_to_address
    return {
        "seller_receive_address": (addr[:10] + "…") if addr and len(addr) > 10 else addr,
        "seller_receive_address_full": addr,
        "buyer_address": "configured" if settings.evm_private_key else "not configured",
        "network": settings.x402_default_network,
        "pay_to_configured": bool(addr),
    }


@api.get("/swarm/stats")
async def get_swarm_stats():
    if not settings.swarm_enabled:
        return {"enabled": False, "message": "Swarm agency disabled"}
    return {"enabled": True, "message": "Swarm module not loaded in serverless build"}


# Register routes at root (local + bare rewrites) AND under /api (Vercel function paths)
app.include_router(api)
app.include_router(api, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
