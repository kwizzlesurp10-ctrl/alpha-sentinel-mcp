"""FastMCP server for Alpha Sentinel tool access."""

from fastmcp import FastMCP
import logging

from app.config import settings
from app.tools_registry import TOOL_SPECS, get_tool_spec, list_all_tools
from app.intelligence.price_feed import fetch_price_endpoint
from app.intelligence.volatility import analyze_volatility_endpoint
from app.intelligence.sentiment import aggregate_sentiment_endpoint
from app.intelligence.risk import calculate_risk_score_endpoint
from app.intelligence.reports import generate_market_report_endpoint

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp_app = FastMCP(
    "Alpha Sentinel",
    instructions="""You are Alpha Sentinel, a market intelligence agent that provides real-time cryptocurrency data through paid MCP tools.

## Available Tools

### Free Tier (500 calls/month)
- **fetch_price**: Real-time price lookups ($0.005 value)

### Pro Tier / Tool Credits Required
- **analyze_volatility**: Z-score anomaly detection ($0.02)
- **aggregate_sentiment**: Social sentiment aggregation ($0.01)  
- **calculate_risk_score**: Multi-factor risk assessment ($0.03)
- **generate_market_report**: Comprehensive intelligence reports ($0.15)

## Pricing Strategy
Based on x402 market research - priced below median ($0.014) to encourage adoption.
Free tier included to build trust and demonstrate value.""",
)


# ============================================================================
# Tool Implementations
# ============================================================================

@mcp_app.tool()
async def fetch_price(symbol: str) -> str:
    """Fetch real-time cryptocurrency price from CoinGecko API.
    
    FREE TIER TOOL - No payment required!
    
    Args:
        symbol: Cryptocurrency symbol (e.g., 'btc', 'eth', 'sol')
        
    Returns:
        JSON string with current price, 24h change, volume
        
    Example:
        >>> fetch_price("btc")
        '{"success": true, "data": {"symbol": "btc", "price_usd": 67842.50, ...}}'
    """
    try:
        result = await fetch_price_endpoint(symbol)
        import json
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"fetch_price error: {e}")
        return f'{{"error": "Failed to fetch price: {str(e)}"}}'


@mcp_app.tool()
async def analyze_volatility(
    symbol: str,
    window_minutes: int = 60,
    z_threshold: float = 2.0
) -> str:
    """Analyze price volatility using statistical Z-score detection.
    
    PRO/CREDS REQUIRED - $0.02 per call
    
    Args:
        symbol: Cryptocurrency symbol
        window_minutes: Analysis window (1-1440 min, default: 60)
        z_threshold: Std dev threshold (0.1-5.0σ, default: 2.0)
        
    Returns:
        JSON string with volatility metrics, anomaly scores, alert level
        
    Alert Levels: NORMAL → MODERATE → HIGH → CRITICAL
    """
    try:
        result = await analyze_volatility_endpoint(symbol, window_minutes, z_threshold)
        import json
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"analyze_volatility error: {e}")
        return f'{{"error": "Analysis failed: {str(e)}"}}'


@mcp_app.tool()
async def aggregate_sentiment(
    symbols: list[str],
    sources: list[str] | None = None,
    window_minutes: int = 60
) -> str:
    """Aggregate social media sentiment across multiple sources.
    
    PRO/CREDS REQUIRED - $0.01 per call
    
    Args:
        symbols: List of crypto symbols to analyze
        sources: Data sources (default: ["twitter", "reddit"])
        window_minutes: Time window (5-1440 min, default: 60)
        
    Returns:
        JSON string with overall sentiment, breakdown by source, momentum indicators
        
    Categories: BULLISH | NEUTRAL | BEARISH
    """
    try:
        result = await aggregate_sentiment_endpoint(symbols, sources, window_minutes)
        import json
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"aggregate_sentiment error: {e}")
        return f'{{"error": "Sentiment analysis failed: {str(e)}"}}'


@mcp_app.tool()
async def calculate_risk_score(
    symbols: list[str],
    include_factors: list[str] | None = None
) -> str:
    """Calculate multi-factor risk assessment for cryptocurrencies.
    
    PRO/CREDS REQUIRED - $0.03 per call
    
    Args:
        symbols: List of crypto symbols to assess
        include_factors: Risk factors to analyze (default: all)
        
    Returns:
        JSON string with risk level, factor breakdown, actionable recommendations
        
    Risk Levels: LOW | MEDIUM | HIGH | CRITICAL
    """
    try:
        result = await calculate_risk_score_endpoint(symbols, include_factors)
        import json
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"calculate_risk_score error: {e}")
        return f'{{"error": "Risk calculation failed: {str(e)}"}}'


@mcp_app.tool()
async def generate_market_report(
    report_type: str = "daily",
    symbols: list[str] | None = None,
    format: str = "json"
) -> str:
    """Generate comprehensive market intelligence report.
    
    PRO/CREDS REQUIRED - $0.15 per report
    
    Args:
        report_type: Type of report (daily/weekly/monthly)
        symbols: Coins to include (default: bitcoin, ethereum)
        format: Output format (json/pdf)
        
    Returns:
        JSON string with executive summary, key signals, recommendations
        
    Perfect for daily briefings or pre-trade due diligence!
    """
    try:
        result = await generate_market_report_endpoint(report_type, symbols, format)
        import json
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"generate_market_report error: {e}")
        return f'{{"error": "Report generation failed: {str(e)}"}}'


# ============================================================================
# Server Metadata
# ============================================================================

def get_server_info():
    """Get server information and tool counts."""
    return {
        "name": "Alpha Sentinel",
        "version": "0.1.0",
        "total_tools": len(TOOL_SPECS),
        "free_tools": len([t for t in TOOL_SPECS if t["tier_access"]["free"]]),
        "paid_tools": len([t for t in TOOL_SPECS if not t["tier_access"]["free"]]),
        "tools": [spec["name"] for spec in TOOL_SPECS],
        "pricing_tier": {
            "free_monthly_quota": settings.free_tier_monthly_quota,
            "pro_tier_price": settings.pro_tier_price,
        },
    }


if __name__ == "__main__":
    # Run MCP server via stdio transport
    mcp_app.run()
