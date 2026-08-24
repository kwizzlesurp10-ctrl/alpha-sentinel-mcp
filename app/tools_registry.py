"""Tools Registry - Single Source of Truth for MCP tools.

This module defines all available MCP tools and their specifications.
The registry drives:
- /mcp manifest generation
- Tool execution routing
- README documentation
- Test assertions

Remember to touch ALL related files when adding a new tool!
"""

from typing import Callable, Any

# ============================================================================
# Tool Specifications (SSOT)
# ============================================================================

TOOL_SPECS = [
    {
        "name": "fetch_price",
        "description": """Fetch real-time cryptocurrency price from CoinGecko API.
        
Returns current price, 24h change, and trading volume for any supported cryptocurrency.

**Use Case:** Get instant price data before executing trades or analyzing positions.

**Cost:** $0.005 USD per call (cheapest tier - high frequency allowed)

**Example Response:**
{
  "symbol": "bitcoin",
  "price_usd": 67842.50,
  "change_24h": 2.34,
  "volume_24h": 28500000000,
  "timestamp": "2026-08-24T15:30:00Z"
}""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Cryptocurrency symbol (e.g., 'btc', 'eth', 'sol')",
                    "minLength": 1,
                }
            },
            "required": ["symbol"],
        },
        "requires_env": False,  # No special credentials needed
        "tier_access": {"free": True, "pro": True},
    },
    {
        "name": "analyze_volatility",
        "description": """Analyze price volatility using statistical Z-score anomaly detection.
        
Calculates standard deviations from mean price to detect anomalous movements.
Configurable thresholds and time windows for customized analysis.

**Use Case:** Identify unusual price movements before they become obvious trends.

**Cost:** $0.02 USD per call

**Parameters:**
- `symbol`: Crypto symbol to analyze
- `window_minutes`: Historical window (1-1440 min, default: 60)
- `z_threshold`: Std dev threshold for anomalies (0.1-5.0σ, default: 2.0)

**Alert Levels:** NORMAL → MODERATE → HIGH → CRITICAL""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Cryptocurrency symbol",
                },
                "window_minutes": {
                    "type": "integer",
                    "default": 60,
                    "minimum": 1,
                    "maximum": 1440,
                    "description": "Analysis window in minutes",
                },
                "z_threshold": {
                    "type": "number",
                    "default": 2.0,
                    "minimum": 0.1,
                    "maximum": 5.0,
                    "description": "Z-score threshold for anomalies",
                }
            },
            "required": ["symbol"],
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},  # Pro/credits only
    },
    {
        "name": "aggregate_sentiment",
        "description": """Aggregate social media sentiment across multiple sources.
        
Combines Twitter/X, Reddit, and other platforms into unified sentiment scores (-1.0 to +1.0).
Detects momentum shifts and trend changes in community opinion.

**Use Case:** Gauge market psychology before major moves.

**Cost:** $0.01 USD per call

**Sources:** twitter, reddit, telegram, news

**Output:** Overall sentiment category (bullish/neutral/bearish) with breakdown by source.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of crypto symbols to analyze",
                    "minItems": 1,
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["twitter", "reddit", "telegram", "news"]},
                    "default": ["twitter", "reddit"],
                    "description": "Data sources to query",
                },
                "window_minutes": {
                    "type": "integer",
                    "default": 60,
                    "minimum": 5,
                    "maximum": 1440,
                    "description": "Time window for sentiment history",
                }
            },
            "required": ["symbols"],
        },
        "requires_env": True,  # Needs API keys
        "tier_access": {"free": False, "pro": True},
    },
    {
        "name": "calculate_risk_score",
        "description": """Calculate multi-factor risk assessment for cryptocurrencies.
        
Combines volatility, liquidity, market cap tier, and Bitcoin correlation into
a comprehensive risk score (0-1 scale) with actionable recommendations.

**Use Case:** Assess position sizing and stop-loss levels.

**Cost:** $0.03 USD per call

**Risk Levels:** LOW | MEDIUM | HIGH | CRITICAL

**Factors Analyzed:**
- Volatility risk (40% weight)
- Liquidity risk (25% weight)
- Market cap tier (20% weight)
- BTC correlation (15% weight)""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of crypto symbols to assess",
                    "minItems": 1,
                },
                "include_factors": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["volatility", "liquidity", "correlation"]},
                    "default": ["volatility", "liquidity", "correlation"],
                    "description": "Risk factors to analyze",
                }
            },
            "required": ["symbols"],
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},
    },
    {
        "name": "generate_market_report",
        "description": """Generate comprehensive market intelligence report.
        
Synthesizes price, volatility, sentiment, and risk data into actionable insights.
Perfect for daily briefings or strategic planning.

**Use Case:** End-of-day summary or pre-trade due diligence.

**Cost:** $0.15 USD per report

**Report Types:**
- daily: 24-hour overview
- weekly: 7-day trends  
- monthly: 30-day strategic analysis

**Includes:** Executive summary, key signals, actionable recommendations""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "default": "daily",
                    "description": "Type of report to generate",
                },
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["bitcoin", "ethereum"],
                    "description": "Cryptocurrencies to include",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "pdf"],
                    "default": "json",
                    "description": "Output format",
                }
            },
            "required": [],
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},
    },
]

# ============================================================================
# Derived Constants (computed from TOOL_SPECS)
# ============================================================================

TOOL_COUNT = len(TOOL_SPECS)

EXPECTED_TOOL_NAMES = [spec["name"] for spec in TOOL_SPECS]

FREE_TOOLS = [spec["name"] for spec in TOOL_SPECS if spec["tier_access"]["free"]]

PAID_TOOLS = [spec["name"] for spec in TOOL_SPECS if not spec["tier_access"]["free"]]

NEEDS_ENV_TOOLS = [spec["name"] for spec in TOOL_SPECS if spec["requires_env"]]

# ============================================================================
# Pricing Configuration
# ============================================================================

TOOL_PRICES = {
    "fetch_price": "$0.005",
    "analyze_volatility": "$0.02",
    "aggregate_sentiment": "$0.01",
    "calculate_risk_score": "$0.03",
    "generate_market_report": "$0.15",
}


def get_tool_price(tool_name: str) -> str:
    """Get price for a specific tool."""
    return TOOL_PRICES.get(tool_name, "$0.01")


def update_tool_price(tool_name: str, new_price: str):
    """Update tool pricing dynamically.
    
    Only called via operator dashboard action endpoint.
    
    Args:
        tool_name: Name of tool to update
        new_price: New price string (e.g., "$0.02")
        
    Raises:
        ValueError if tool not found
    """
    for spec in TOOL_SPECS:
        if spec["name"] == tool_name:
            old_price = spec.get("price", "")
            spec["price"] = new_price
            TOOL_PRICES[tool_name] = new_price
            return
    
    raise ValueError(f"Tool '{tool_name}' not found in registry")


# ============================================================================
# Tool Lookup Functions
# ============================================================================

def get_tool_spec(tool_name: str) -> dict | None:
    """Get specification for a tool by name."""
    for spec in TOOL_SPECS:
        if spec["name"] == tool_name:
            return spec
    return None


def list_all_tools() -> list[str]:
    """List all available tool names."""
    return EXPECTED_TOOL_NAMES.copy()


def list_free_tools() -> list[str]:
    """List tools available in free tier."""
    return FREE_TOOLS.copy()


def list_paid_tools() -> list[str]:
    """List pro/credit-required tools."""
    return PAID_TOOLS.copy()


def validate_tool_call(tool_name: str) -> tuple[bool, str]:
    """Validate if tool can be executed.
    
    Returns:
        (can_execute, message)
    """
    spec = get_tool_spec(tool_name)
    
    if not spec:
        return False, f"Unknown tool: {tool_name}"
    
    if spec["requires_env"]:
        # Would check for required env vars here
        pass
    
    return True, f"Tool '{tool_name}' is available"
