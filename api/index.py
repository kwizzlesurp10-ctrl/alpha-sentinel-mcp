"""Minimal Vercel FastAPI entry — diagnose boot, then expand."""
from fastapi import FastAPI

app = FastAPI(title="Alpha Sentinel", version="0.2.0-min")


@app.get("/")
@app.get("/api")
@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "alpha-sentinel-api", "version": "0.2.0-min"}


@app.get("/stats")
@app.get("/api/stats")
async def stats():
    return {
        "total_agents": 0,
        "free_tier_active": 0,
        "pro_tier_active": 0,
        "tool_credits_sold": 0,
        "revenue_today_usd": 0.0,
        "calls_today": 0,
        "avg_latency_ms": 0.0,
        "active_tools": ["fetch_price"],
        "free_tools": ["fetch_price"],
        "paid_tools": [],
        "tool_count": 1,
        "pricing": {"fetch_price": "$0.00"},
        "network": "eip155:8453",
        "pay_to_configured": True,
        "timestamp": "now",
        "note": "minimal bootstrap handler",
    }
