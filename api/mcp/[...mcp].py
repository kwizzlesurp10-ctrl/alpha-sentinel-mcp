"""
Vercel Serverless Function - Alpha Sentinel MCP API Handler
This file handles all incoming API requests at /api/mcp/*
"""
import json
from typing import Any, Dict
import os
from datetime import datetime

# FastAPI-compatible handlers (we'll use these functions)
# In production, you'd import from app.core modules
try:
    # Try to import your existing modules
    from app.intelligence.price_feed import PriceFetcher
    from app.intelligence.volatility import VolatilityAnalyzer
    from app.intelligence.sentiment import SentimentAggregator
    from app.intelligence.risk import RiskScorer
    from app.intelligence.reports import ReportGenerator
    from app.commerce import QuotaManager
    from app.x402_services import X402Service
except ImportError:
    # Fallback for initial deployment - define stubs
    print("⚠️ Using stub implementations - import modules need fixing")

async def handler(request):
    """
    Main Vercel serverless function entry point
    Handles all /api/mcp/* requests
    """
    
    # Parse request
    method = request.method
    path = request.path
    
    # Health check endpoints
    if path == '/health' or path == '/status':
        return await handle_health()
    
    elif path == '/stats':
        return await handle_stats()
    
    elif path == '/.well-known/mcp':
        return await handle_mcp_manifest()
    
    # Tool-specific endpoints (route by query param)
    elif 'fetch_price' in path or 'symbol=' in request.query_string:
        symbol = extract_param('symbol', request)
        return await handle_price_fetch(symbol)
    
    elif 'volatility' in path:
        symbol = extract_param('symbol', request)
        window = int(extract_param('window', request, 14))
        return await handle_volatility(symbol, window)
    
    elif 'sentiment' in path:
        symbols = extract_param('symbols', request)
        days = int(extract_param('days', request, 7))
        return await handle_sentiment(symbols.split(','), days)
    
    elif 'risk' in path:
        symbol = extract_param('symbol', request)
        return await handle_risk_score(symbol)
    
    elif 'report' in path:
        symbols = extract_param('symbols', request)
        type = extract_param('type', request, 'daily')
        return await handle_market_report(symbols.split(','), type)
    
    else:
        # Return error for unknown paths
        return {
            "error": "Unknown endpoint",
            "message": f"Path not found: {path}",
            "available_endpoints": [
                "/health",
                "/stats",
                "/.well-known/mcp",
                "/tools/fetch_price?symbol=btc",
                "/tools/analyze_volatility?symbol=eth&window=30",
                "/tools/aggregate_sentiment?symbols=btc,eth,sol&days=7",
                "/tools/calculate_risk_score?symbol=ada",
                "/tools/generate_market_report?symbols=btc,eth&type=daily"
            ]
        }


def extract_param(param_name: str, request, default=None):
    """Extract query parameter from request"""
    query_string = request.query_string
    
    if '=' not in query_string:
        return default
    
    params = {}
    for pair in query_string.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[key] = value
    
    return params.get(param_name, default)


async def handle_health():
    """Return health status"""
    return {
        "status": "healthy",
        "service": "alpha-sentinel-api",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


async def handle_stats():
    """Return service statistics"""
    # You'd populate this with real metrics from your QuotaManager
    return {
        "total_requests_24h": 0,
        "active_users_free": 12,
        "active_users_pro": 5,
        "quota_consumed_today": 1500,
        "uptime_hours": 72
    }


async def handle_mcp_manifest():
    """Return MCP manifest for discovery"""
    return {
        "name": "alpha-sentinel-mcp",
        "description": "Market intelligence and analytics tools with x402 micropayments",
        "version": "1.0.0",
        "endpoints": {
            "base_url": "https://alpha-sentinel-api.vercel.app/api",
            "mcp_tools_endpoint": "/api/mcp/"
        },
        "tools": [
            {
                "name": "fetch_price",
                "description": "Get current cryptocurrency price with x402 payment",
                "cost_usd": 0.005,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "example": "btc"}
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "analyze_volatility",
                "description": "Calculate z-score volatility anomaly detection",
                "cost_usd": 0.02,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "example": "eth"},
                        "window_days": {"type": "integer", "default": 14}
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "aggregate_sentiment",
                "description": "Aggregate social sentiment across multiple cryptocurrencies",
                "cost_usd": 0.01,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbols": {"type": "array", "items": {"type": "string"}},
                        "days": {"type": "integer", "default": 7}
                    },
                    "required": ["symbols"]
                }
            },
            {
                "name": "calculate_risk_score",
                "description": "Multi-factor risk scoring for assets",
                "cost_usd": 0.03,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"}
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "generate_market_report",
                "description": "Comprehensive market analysis report",
                "cost_usd": 0.15,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbols": {"type": "array", "items": {"type": "string"}},
                        "type": {"type": "string", "enum": ["daily", "weekly", "monthly"]}
                    },
                    "required": ["symbols"]
                }
            }
        ],
        "pricing_tiers": {
            "free": {"monthly_quota": 500, "rate_limit_per_min": 10, "price": "$0"},
            "pro": {"monthly_quota": 50000, "rate_limit_per_min": 120, "price": "$29/month"},
            "pay_per_use": {"credits_starting_at": "$1.00/100 calls"}
        }
    }


async def handle_price_fetch(symbol: str):
    """Fetch price for a cryptocurrency symbol"""
    try:
        # TODO: Implement actual integration
        # For now, return mock data structure
        return {
            "success": True,
            "tool": "fetch_price",
            "symbol": symbol.upper(),
            "data": {
                "price_usd": 42000.00,
                "change_24h_percent": 2.3,
                "market_cap": 820000000000,
                "volume_24h": 35000000000,
                "timestamp": datetime.now().isoformat()
            },
            "x402_cost": 0.005,
            "payment_required": False  # Free tier includes this tool
        }
    except Exception as e:
        return {"error": str(e), "success": False}


async def handle_volatility(symbol: str, window: int = 14):
    """Calculate volatility/z-score for a symbol"""
    try:
        # TODO: Implement actual volatility calculation
        return {
            "success": True,
            "tool": "analyze_volatility",
            "symbol": symbol.upper(),
            "z_score": 1.5,
            "interpretation": get_volatility_interpretation(1.5),
            "window_days": window,
            "x402_cost": 0.02
        }
    except Exception as e:
        return {"error": str(e), "success": False}


async def handle_sentiment(symbols: list, days: int = 7):
    """Aggregate sentiment across symbols"""
    try:
        # TODO: Implement actual sentiment aggregation
        sentiments = {}
        for symbol in symbols:
            sentiments[symbol.upper()] = {
                "score": 0.65,  # -1 to 1 scale
                "sentiment": "positive" if 0.65 > 0 else "negative",
                "reddit_mentions": 1500,
                "twitter_mentions": 3200,
                "news_articles": 45
            }
        
        return {
            "success": True,
            "tool": "aggregate_sentiment",
            "period_days": days,
            "sentiments": sentiments,
            "x402_cost": 0.01 * len(symbols)
        }
    except Exception as e:
        return {"error": str(e), "success": False}


async def handle_risk_score(symbol: str):
    """Calculate risk score"""
    try:
        # TODO: Implement actual risk calculation
        risk_score = 3.2  # Example score
        
        return {
            "success": True,
            "tool": "calculate_risk_score",
            "symbol": symbol.upper(),
            "risk_score": round(risk_score, 2),
            "risk_level": classify_risk(risk_score),
            "factors": {
                "volatility": "medium",
                "liquidity": "high",
                "market_correlation": "moderate"
            },
            "x402_cost": 0.03
        }
    except Exception as e:
        return {"error": str(e), "success": False}


async def handle_market_report(symbols: list, type: str = "daily"):
    """Generate market report"""
    try:
        # TODO: Implement actual report generation
        return {
            "success": True,
            "tool": "generate_market_report",
            "report_type": type,
            "symbols": symbols,
            "summary": {
                "market_overview": "Mixed signals across major assets...",
                "key_drivers": ["ETF flows", "Macro economics", "Regulatory news"],
                "top_gainers": ["BTC", "ETH"],
                "top_losers": ["SOL", "ADA"]
            },
            "full_report_url": "/reports/daily-2026-08-24.pdf",
            "x402_cost": 0.15
        }
    except Exception as e:
        return {"error": str(e), "success": False}


def get_volatility_interpretation(z_score: float) -> str:
    """Interpret z-score value"""
    if abs(z_score) > 3:
        return "Extreme anomaly detected"
    elif abs(z_score) > 2:
        return "Significant volatility"
    elif abs(z_score) > 1:
        return "Moderate deviation"
    else:
        return "Normal trading range"


def classify_risk(score: float) -> str:
    """Classify risk level based on score (0-10 scale)"""
    if score < 2:
        return "LOW"
    elif score < 4:
        return "MEDIUM"
    elif score < 6:
        return "MODERATE"
    elif score < 8:
        return "HIGH"
    else:
        return "EXTREME"
