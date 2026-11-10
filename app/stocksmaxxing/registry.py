"""Stocks Maxxing paid tool specs (merged into app.tools_registry at import time)."""

from __future__ import annotations

from typing import Any

_STOCKS_DISCLAIMER = (
    "RESEARCH ONLY — not investment advice. No trading, execution, custody, or swaps. "
    "Coinbase tokenized stocks are not offered to U.S. persons."
)

STOCKSMAXXING_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "tokenized_stock_list",
        "description": f"""List Coinbase tokenized stocks on Base (read-only catalog).

{_STOCKS_DISCLAIMER}

**Cost:** $0.01 USD per call""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional name/symbol/ISIN filter"},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25},
                "page_token": {"type": "string"},
            },
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},
        "stocksmaxxing": True,
    },
    {
        "name": "tokenized_stock_lookup",
        "description": f"""Lookup metadata for one tokenized stock (contract, ISIN, multiplier, prospectus).

{_STOCKS_DISCLAIMER}

**Cost:** $0.01 USD per call""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "minLength": 1, "description": "Token ticker e.g. CRCLc"},
            },
            "required": ["symbol"],
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},
        "stocksmaxxing": True,
    },
    {
        "name": "tokenized_stock_nav_deviation",
        "description": f"""Compare Chainlink NAV/reference to underlying equity spot (research spread).

{_STOCKS_DISCLAIMER}

**Cost:** $0.02 USD per call""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "minLength": 1},
            },
            "required": ["symbol"],
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},
        "stocksmaxxing": True,
    },
    {
        "name": "tokenized_stock_corporate_action",
        "description": f"""Fetch one announced/applied corporate action by UUID (from onchain Announcement URI).

{_STOCKS_DISCLAIMER}

**Cost:** $0.02 USD per call""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "corporate_action_id": {
                    "type": "string",
                    "description": "UUID from Announcement event URI",
                },
            },
            "required": ["corporate_action_id"],
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},
        "stocksmaxxing": True,
    },
    {
        "name": "tokenized_stock_research_brief",
        "description": f"""Multi-symbol research brief: metadata, NAV staleness, deviation notes.

{_STOCKS_DISCLAIMER}

**Cost:** $0.05 USD per call""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 10,
                },
            },
            "required": ["symbols"],
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},
        "stocksmaxxing": True,
    },
    {
        "name": "tokenized_stock_model_portfolio",
        "description": f"""Model portfolio / rebalance suggestions (weights only — no orders).

{_STOCKS_DISCLAIMER}

**Cost:** $0.08 USD per call""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 12,
                },
                "current_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
                "objective": {
                    "type": "string",
                    "enum": ["balanced", "low_staleness_nav", "diversified"],
                    "default": "balanced",
                },
            },
            "required": ["symbols"],
        },
        "requires_env": False,
        "tier_access": {"free": False, "pro": True},
        "stocksmaxxing": True,
    },
]

STOCKSMAXXING_TOOL_PRICES: dict[str, str] = {
    "tokenized_stock_list": "$0.01",
    "tokenized_stock_lookup": "$0.01",
    "tokenized_stock_nav_deviation": "$0.02",
    "tokenized_stock_corporate_action": "$0.02",
    "tokenized_stock_research_brief": "$0.05",
    "tokenized_stock_model_portfolio": "$0.08",
}

STOCKSMAXXING_TOOL_HTTP_PATHS: dict[str, str] = {
    name: f"/tools/{name}" for name in STOCKSMAXXING_TOOL_PRICES
}

STOCKSMAXXING_TOOL_NAMES: list[str] = list(STOCKSMAXXING_TOOL_PRICES.keys())
