"""First-party Streamable HTTP MCP JSON-RPC (initialize + tools/list + tools/call).

Does not require FastMCP at request time. Tool names come from the live registry
so MCP, HTTP, and the A2A Agent Card cannot drift.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools_registry import EXPECTED_TOOL_NAMES, TOOL_SPECS, get_tool_spec

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "alpha-sentinel"
SERVER_VERSION = "0.2.0"


def mcp_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": spec["name"],
            "description": spec["description"].strip(),
            "inputSchema": spec["inputSchema"],
        }
        for spec in TOOL_SPECS
    ]


def initialize_result(client_version: str | None = None) -> dict[str, Any]:
    version = client_version or PROTOCOL_VERSION
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": (
            "Alpha Sentinel market intelligence over x402/AgentCash. "
            "fetch_price is free; other tools require USDC payment on Base."
        ),
    }


def tools_list_result() -> dict[str, Any]:
    tools = mcp_tools()
    names = [t["name"] for t in tools]
    if "fetch_price" not in names:
        raise RuntimeError("registry missing fetch_price")
    return {"tools": tools}


async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments = arguments or {}
    spec = get_tool_spec(name)
    if spec is None:
        return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

    from app.intelligence.price_feed import fetch_price_endpoint
    from app.intelligence.reports import generate_market_report_endpoint
    from app.intelligence.risk import calculate_risk_score_endpoint
    from app.intelligence.sentiment import aggregate_sentiment_endpoint
    from app.intelligence.volatility import analyze_volatility_endpoint

    try:
        if name == "fetch_price":
            result = await fetch_price_endpoint(str(arguments.get("symbol") or "btc"))
        elif name == "analyze_volatility":
            result = await analyze_volatility_endpoint(
                str(arguments.get("symbol") or "btc"),
                int(arguments.get("window_minutes") or 60),
                float(arguments.get("z_threshold") or 2.0),
            )
        elif name == "aggregate_sentiment":
            symbols = arguments.get("symbols") or ["btc"]
            if isinstance(symbols, str):
                symbols = [symbols]
            result = await aggregate_sentiment_endpoint(
                list(symbols),
                arguments.get("sources"),
                int(arguments.get("window_minutes") or 60),
            )
        elif name == "calculate_risk_score":
            symbols = arguments.get("symbols") or ["btc"]
            if isinstance(symbols, str):
                symbols = [symbols]
            result = await calculate_risk_score_endpoint(list(symbols), arguments.get("include_factors"))
        elif name == "generate_market_report":
            symbols = arguments.get("symbols")
            if isinstance(symbols, str):
                symbols = [symbols]
            result = await generate_market_report_endpoint(
                str(arguments.get("report_type") or "daily"),
                symbols,
                str(arguments.get("format") or "json"),
            )
        else:
            return {"isError": True, "content": [{"type": "text", "text": f"Unhandled tool: {name}"}]}
    except Exception as exc:  # noqa: BLE001
        logger.exception("MCP tool %s failed", name)
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}

    return {
        "content": [{"type": "text", "text": json.dumps(result)}],
        "structuredContent": result,
    }


def jsonrpc_response(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def handle_jsonrpc(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one MCP JSON-RPC request. Notifications return None."""
    method = payload.get("method")
    req_id = payload.get("id")
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "initialize":
        return jsonrpc_response(req_id, initialize_result(params.get("protocolVersion")))
    if method == "tools/list":
        return jsonrpc_response(req_id, tools_list_result())
    if method == "tools/call":
        name = params.get("name") or params.get("tool")
        args = params.get("arguments") or params.get("args") or {}
        if not name:
            return jsonrpc_error(req_id, -32602, "tools/call requires name")
        result = await call_tool(str(name), args if isinstance(args, dict) else {})
        return jsonrpc_response(req_id, result)
    if method == "ping":
        return jsonrpc_response(req_id, {})

    if req_id is None:
        return None
    return jsonrpc_error(req_id, -32601, f"Method not found: {method}")


def registered_tool_names() -> list[str]:
    return list(EXPECTED_TOOL_NAMES)
