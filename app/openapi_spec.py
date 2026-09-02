"""Public OpenAPI document AgentCash/x402scan actually read first.

Paid operations get x-payment-info + a documented 402 so discover/check
do not classify the storefront as a free API.
"""

from __future__ import annotations

from typing import Any

from app.payments import paid_catalog, public_base_url, settlement_network, seller_pay_to
from app.tools_registry import FREE_TOOLS, PAID_TOOLS, TOOL_HTTP_ALIASES, TOOL_HTTP_PATHS, http_path_to_tool

PUBLIC_FREE_PATHS = {
    "/health",
    "/llms.txt",
    "/catalog",
    "/.well-known/x402",
    "/.well-known/mcp",
    "/.well-known/agent-card.json",
    "/.well-known/agent.json",
    "/.well-known/paid-resources",
    "/.well-known/paid-catalog",
    "/tools/fetch_price",
    "/mcp",
    "/mcp/mcp",
    "/a2a",
}


def _payment_info(tool_name: str) -> dict[str, Any]:
    item = next((c for c in paid_catalog() if c["name"] == tool_name), None)
    price = item["price"] if item else "$0.01"
    amount = item["amount"] if item else "10000"
    return {
        "protocol": "x402",
        "agentcash": True,
        "network": settlement_network(),
        "price": price,
        "price_usdc": item["price_usdc"] if item else 0.01,
        "amount": amount,
        "payTo": seller_pay_to(),
        "asset": "USDC",
    }


def decorate_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Mark paid routes for AgentCash; keep the rest (tests hit /health etc.)."""
    info = schema.setdefault("info", {})
    info["x-guidance"] = (
        "Paid intelligence tools return HTTP 402 with network, payTo, amount, "
        "and resource. Retry with PAYMENT-SIGNATURE / X-PAYMENT (AgentCash fetch). "
        f"Catalog: {public_base_url()}/catalog  MCP: {public_base_url()}/mcp  "
        f"A2A: {public_base_url()}/a2a"
    )
    info["x-payment-protocol"] = "x402"
    info["x-agentcash"] = True

    paths = schema.get("paths") or {}
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        tool = http_path_to_tool(path)
        paid = tool in PAID_TOOLS if tool else False
        for method, op in list(methods.items()):
            if method.startswith("x-") or not isinstance(op, dict):
                continue
            if paid and tool:
                pay = _payment_info(tool)
                op["x-payment-info"] = pay
                op["x-payment-required"] = True
                op["x-x402"] = True
                op.setdefault("responses", {})["402"] = {
                    "description": "Payment required (x402 / AgentCash)",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "network": {"type": "string"},
                                    "payTo": {"type": "string"},
                                    "amount": {"type": "string"},
                                    "resource": {"type": "string"},
                                },
                                "required": ["network", "payTo", "amount", "resource"],
                            }
                        }
                    },
                }
            elif tool in FREE_TOOLS or path in PUBLIC_FREE_PATHS or path.replace("/api", "") in PUBLIC_FREE_PATHS:
                op["security"] = []
    return schema
