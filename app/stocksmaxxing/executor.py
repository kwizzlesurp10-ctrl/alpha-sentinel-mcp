"""Dispatch stocksmaxxing tools for MCP / A2A / samples."""

from __future__ import annotations

from typing import Any

from app.stocksmaxxing import services
from app.stocksmaxxing.registry import STOCKSMAXXING_TOOL_NAMES


async def execute_stocksmaxxing_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in STOCKSMAXXING_TOOL_NAMES:
        raise ValueError(f"Unknown stocksmaxxing tool: {name}")

    if name == "tokenized_stock_list":
        return await services.tokenized_stock_list_endpoint(
            query=arguments.get("query"),
            page_size=int(arguments.get("page_size") or 25),
            page_token=arguments.get("page_token"),
        )
    if name == "tokenized_stock_lookup":
        return await services.tokenized_stock_lookup_endpoint(str(arguments.get("symbol") or ""))
    if name == "tokenized_stock_nav_deviation":
        return await services.tokenized_stock_nav_deviation_endpoint(str(arguments.get("symbol") or ""))
    if name == "tokenized_stock_corporate_action":
        return await services.tokenized_stock_corporate_action_endpoint(
            str(arguments.get("corporate_action_id") or "")
        )
    if name == "tokenized_stock_research_brief":
        symbols = arguments.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [symbols]
        return await services.tokenized_stock_research_brief_endpoint(list(symbols))
    if name == "tokenized_stock_model_portfolio":
        symbols = arguments.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [symbols]
        weights = arguments.get("current_weights")
        return await services.tokenized_stock_model_portfolio_endpoint(
            list(symbols),
            current_weights=weights if isinstance(weights, dict) else None,
            objective=str(arguments.get("objective") or "balanced"),
        )
    raise ValueError(f"Unhandled stocksmaxxing tool: {name}")
