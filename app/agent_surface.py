"""The machine-readable storefront surface: /llms.txt, /.well-known/x402, A2A agent card."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.tools_registry import TOOL_COUNT, TOOL_SPECS


def _base() -> str:
    return settings.public_base_url.rstrip("/")


def ownership_proofs() -> list[str]:
    """Signatures proving the operator controls this origin, if any exist."""
    return [p.strip() for p in settings.ownership_proofs.split(",") if p.strip()]


def paid_resources() -> list[dict[str, Any]]:
    """Every paid HTTP resource this deployment serves, priced from live config."""
    base = _base()
    return [
        {
            "url": f"{base}/tools/fetch_price",
            "method": "POST",
            "price": "free",
            "network": None,
            "name": "fetch_price",
            "what": "Real-time cryptocurrency price lookup from CoinGecko / Coinbase APIs.",
            "params": {"symbol": "Crypto symbol or ticker (e.g. btc, eth, sol)"},
        },
        {
            "url": f"{base}/tools/analyze_volatility",
            "method": "POST",
            "price": settings.volatility_alerts_price,
            "network": settings.x402_default_network,
            "name": "analyze_volatility",
            "what": "Z-score statistical anomaly detection on historical cryptocurrency price movements.",
            "params": {
                "symbol": "Crypto symbol (required)",
                "window_minutes": "Time window in minutes (1-1440, default: 60)",
                "z_threshold": "Z-score threshold in standard deviations (0.1-5.0, default: 2.0)",
            },
        },
        {
            "url": f"{base}/tools/aggregate_sentiment",
            "method": "POST",
            "price": settings.sentiment_analysis_price,
            "network": settings.x402_default_network,
            "name": "aggregate_sentiment",
            "what": "Social sentiment aggregation across Twitter/X and Reddit for crypto symbols.",
            "params": {
                "symbols": "List of crypto symbols to analyze (required)",
                "sources": "Data sources to include (default: ['twitter', 'reddit'])",
                "window_minutes": "Time window in minutes (5-1440, default: 60)",
            },
        },
        {
            "url": f"{base}/tools/calculate_risk",
            "method": "POST",
            "price": settings.risk_assessment_price,
            "network": settings.x402_default_network,
            "name": "calculate_risk",
            "what": "Multi-factor risk assessment (volatility, liquidity, correlation) for cryptocurrencies.",
            "params": {
                "symbols": "List of crypto symbols to assess (required)",
                "include_factors": "Risk factors to analyze (default: ['volatility', 'liquidity', 'correlation'])",
            },
        },
        {
            "url": f"{base}/tools/generate_report",
            "method": "POST",
            "price": settings.market_report_price,
            "network": settings.x402_default_network,
            "name": "generate_report",
            "what": "Comprehensive daily/weekly/monthly market intelligence reports.",
            "params": {
                "report_type": "Report frequency (daily, weekly, monthly, default: daily)",
                "symbols": "List of crypto symbols (default: ['btc', 'eth'])",
                "format": "Output format (json, pdf, default: json)",
            },
        },
    ]


def well_known_x402() -> dict[str, Any]:
    """Machine manifest of the paid surface, content from live config."""
    return {
        "version": 1,
        "x402_version": 2,
        "service": "alpha-sentinel-mcp",
        "base_url": _base(),
        "networks": [settings.x402_default_network],
        "payment_header": "PAYMENT-SIGNATURE",
        "challenge_header": "PAYMENT-REQUIRED",
        "receipt_header": "PAYMENT-RESPONSE",
        "resources": [r["url"] for r in paid_resources() if r["price"] != "free"],
        "resource_details": paid_resources(),
        **({"ownershipProofs": ownership_proofs()} if ownership_proofs() else {}),
        "mcp": {
            "manifest": f"{_base()}/.well-known/mcp",
            "streamable_http": f"{_base()}/mcp/mcp",
        },
        "docs": f"{_base()}/llms.txt",
    }


def llms_txt() -> str:
    base = _base()
    lines = [
        "# Alpha Sentinel Market Intelligence MCP Server",
        "",
        "> Pay-per-call HTTP APIs and MCP tools over x402: USDC on Base, no API key, no signup.",
        "",
        "## Available Paid and Free Resources",
        "",
    ]
    for r in paid_resources():
        price = r["price"] if r["price"] == "free" else f"{r['price']} USDC per call"
        lines.append(f"### {r['name']} — {price}")
        lines.append(f"`{r['method']} {r['url']}`")
        lines.append("")
        lines.append(r["what"])
        for k, v in r["params"].items():
            lines.append(f"- `{k}`: {v}")
        lines.append("")
    return "\n".join(lines)


def agent_card() -> dict[str, Any]:
    """A2A Protocol v1.0 Agent Card for ecosystem discovery."""
    base = _base()
    network = settings.x402_default_network
    skills = [
        {
            "id": spec["name"],
            "name": spec["name"],
            "description": spec["description"],
            "tags": ["crypto", "market-intelligence", "x402", "base"],
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        }
        for spec in TOOL_SPECS
    ]

    return {
        "name": "Alpha Sentinel Market Intelligence (x402)",
        "description": "Real-time crypto market monitoring, statistical volatility alerts, and sentiment analysis via x402 MCP.",
        "version": "0.1.0",
        "protocolVersion": "1.0",
        "provider": {
            "organization": "SEVTECH",
            "url": "https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp",
        },
        "documentationUrl": f"{base}/llms.txt",
        "supportedInterfaces": [
            {
                "url": f"{base}/tools/fetch_price",
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            },
            {
                "url": f"{base}/.well-known/x402",
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            },
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "skills": skills,
        "securitySchemes": {
            "x402": {
                "type": "apiKey",
                "in": "header",
                "name": "PAYMENT-SIGNATURE",
                "description": f"x402 micropayments on {network}.",
            }
        },
        "security": [
            {},
            {"x402": []},
        ],
    }
