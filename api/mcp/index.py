import json
from datetime import datetime

# This is the actual Vercel handler - must use Python 3.9+ syntax
async def handler(request):
    """Vercel serverless function handler for Alpha Sentinel MCP"""
    
    # Parse request
    method = request.method
    path = request.path
    
    print(f"🔍 Request: {method} {path}")
    
    # Health check endpoints
    if path == '/health' or path == '/status':
        return {
            "status": "healthy",
            "service": "alpha-sentinel-api", 
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }
    
    elif path == '/stats':
        return {
            "total_requests_24h": 0,
            "active_users_free": 12,
            "active_users_pro": 5,
            "quota_consumed_today": 1500,
            "uptime_hours": 72
        }
    
    elif path == '/.well-known/mcp':
        return await handle_mcp_manifest()
    
    # Route to tools based on path
    elif 'fetch_price' in path and 'symbol=' in str(request.query_string):
        symbol = extract_param('symbol', request)
        if symbol:
            return await handle_price_fetch(symbol)
    
    elif 'volatility' in path:
        symbol = extract_param('symbol', request)
        window = int(extract_param('window', request) or 14)
        return await handle_volatility(symbol or 'btc', window)
    
    elif 'sentiment' in path:
        symbols = extract_param('symbols', request)
        days = int(extract_param('days', request) or 7)
        return await handle_sentiment(symbols.split(','), days)
    
    elif 'risk' in path:
        symbol = extract_param('symbol', request)
        return await handle_risk_score(symbol or 'ada')
    
    elif 'report' in path:
        symbols = extract_param('symbols', request)
        type = extract_param('type', request) or 'daily'
        return await handle_market_report(symbols.split(','), type)
    
    else:
        return {"error": "Unknown endpoint", "message": f"Not found: {path}"}


def extract_param(param_name, request):
    """Extract query parameter from request"""
    query_string = getattr(request, 'query_string', '') or ''
    
    if '=' not in query_string:
        return None
    
    params = {}
    for pair in query_string.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[key] = value
    
    return params.get(param_name)


async def handle_mcp_manifest():
    """Return MCP tool manifest"""
    return {
        "name": "alpha-sentinel-mcp",
        "description": "Market intelligence and analytics tools with x402 micropayments",
        "version": "1.0.0",
        "tools": [
            {
                "name": "fetch_price",
                "description": "Get current cryptocurrency price",
                "cost_usd": 0.005,
                "inputSchema": {
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
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "window_days": {"type": "integer", "default": 14}
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "aggregate_sentiment",
                "description": "Aggregate social sentiment across cryptocurrencies",
                "cost_usd": 0.01,
                "inputSchema": {
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
                "description": "Multi-factor risk scoring",
                "cost_usd": 0.03,
                "inputSchema": {
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
                "inputSchema": {
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


async def handle_price_fetch(symbol):
    """Fetch cryptocurrency price (stub implementation)"""
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
        "payment_required": False  # Free tier includes this
    }


async def handle_volatility(symbol, window):
    """Calculate volatility/z-score (stub)"""
    return {
        "success": True,
        "tool": "analyze_volatility",
        "symbol": symbol.upper(),
        "z_score": 1.5,
        "interpretation": get_volatility_interpretation(1.5),
        "window_days": window,
        "x402_cost": 0.02
    }


async def handle_sentiment(symbols, days):
    """Aggregate sentiment (stub)"""
    sentiments = {}
    for symbol in symbols:
        sentiments[symbol.upper()] = {
            "score": 0.65,
            "sentiment": "positive",
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


async def handle_risk_score(symbol):
    """Calculate risk score (stub)"""
    return {
        "success": True,
        "tool": "calculate_risk_score",
        "symbol": symbol.upper(),
        "risk_score": 3.2,
        "risk_level": classify_risk(3.2),
        "factors": {
            "volatility": "medium",
            "liquidity": "high",
            "market_correlation": "moderate"
        },
        "x402_cost": 0.03
    }


async def handle_market_report(symbols, type):
    """Generate market report (stub)"""
    return {
        "success": True,
        "tool": "generate_market_report",
        "report_type": type,
        "symbols": symbols,
        "summary": {
            "market_overview": "Mixed signals across major assets...",
            "key_drivers": ["ETF flows", "Macro economics"],
            "top_gainers": ["BTC", "ETH"],
            "top_losers": ["SOL", "ADA"]
        },
        "full_report_url": "/reports/daily-2026-08-24.pdf",
        "x402_cost": 0.15
    }


def get_volatility_interpretation(z_score):
    """Interpret z-score"""
    if abs(z_score) > 3:
        return "Extreme anomaly detected"
    elif abs(z_score) > 2:
        return "Significant volatility"
    elif abs(z_score) > 1:
        return "Moderate deviation"
    else:
        return "Normal trading range"


def classify_risk(score):
    """Classify risk level"""
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
