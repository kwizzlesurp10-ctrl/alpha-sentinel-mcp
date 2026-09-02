"""The machine-readable storefront surface: /llms.txt, /.well-known/x402, A2A agent card."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.payments import all_tool_resources, paid_catalog, public_base_url, settlement_network
from app.tools_registry import TOOL_COUNT, TOOL_SPECS


def _base() -> str:
    return public_base_url()


def ownership_proofs() -> list[str]:
    """Signatures proving the operator controls this origin, if any exist."""
    return [p.strip() for p in settings.ownership_proofs.split(",") if p.strip()]


def paid_resources() -> list[dict[str, Any]]:
    """HTTP resources derived from the live tool registry (free + paid)."""
    return all_tool_resources()


def well_known_x402() -> dict[str, Any]:
    """Machine manifest of the paid surface, content from live config."""
    catalog = paid_catalog()
    return {
        "version": 1,
        "x402_version": 2,
        "service": "alpha-sentinel-mcp",
        "base_url": _base(),
        "networks": [settlement_network()],
        "payment_header": "PAYMENT-SIGNATURE",
        "challenge_header": "PAYMENT-REQUIRED",
        "receipt_header": "PAYMENT-RESPONSE",
        "resources": [item["url"] for item in catalog],
        "resource_details": catalog,
        "catalog": catalog,
        **({"ownershipProofs": ownership_proofs()} if ownership_proofs() else {}),
        "mcp": {
            "manifest": f"{_base()}/.well-known/mcp",
            "streamable_http": f"{_base()}/mcp",
            "url": f"{_base()}/mcp",
        },
        "a2a": {
            "agent_card": f"{_base()}/.well-known/agent-card.json",
            "jsonrpc": f"{_base()}/a2a",
        },
        "docs": f"{_base()}/llms.txt",
        "agentcash": {
            "discover": f"{_base()}/.well-known/x402",
            "payment": "x402",
            "asset": "USDC",
        },
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
    """A2A Protocol v1.0 Agent Card for ecosystem discovery.

    Skills are 1:1 with TOOL_SPECS. `url` is the JSON-RPC Send Message / Get Task
    endpoint. Payment is advertised as x402 + AgentCash (USDC).
    """
    base = _base()
    network = settlement_network()
    skills = [
        {
            "id": spec["name"],
            "name": spec["name"],
            "description": spec["description"].strip(),
            "tags": ["crypto", "market-intelligence", "x402", "agentcash", "base", "a2a"],
            "inputModes": ["application/json", "text/plain"],
            "outputModes": ["application/json"],
        }
        for spec in TOOL_SPECS
    ]

    return {
        "name": "Alpha Sentinel Market Intelligence (x402)",
        "description": (
            "Real-time crypto market monitoring, statistical volatility alerts, "
            "and sentiment analysis via x402 MCP / AgentCash pay-per-call."
        ),
        "url": f"{base}/a2a",
        "version": "0.2.0",
        "protocolVersion": "1.0",
        "provider": {
            "organization": "SEVTECH",
            "url": "https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp",
        },
        "documentationUrl": f"{base}/llms.txt",
        "defaultInputModes": ["application/json", "text/plain"],
        "defaultOutputModes": ["application/json"],
        "supportedInterfaces": [
            {
                "url": f"{base}/a2a",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            },
            {
                "url": f"{base}/mcp",
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            },
            {
                "url": f"{base}/.well-known/x402",
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            },
        ],
        "additionalInterfaces": [
            {"url": f"{base}/a2a", "transport": "JSONRPC"},
            {"url": f"{base}/mcp", "transport": "HTTP"},
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
                "description": (
                    f"x402 micropayments (USDC) on {network}. "
                    "AgentCash discover/check/fetch compatible."
                ),
            },
            "agentcash": {
                "type": "apiKey",
                "in": "header",
                "name": "X-PAYMENT",
                "description": (
                    f"AgentCash x402 pay-per-call. USDC on {network}. "
                    "npx agentcash@latest discover this origin, then fetch."
                ),
            },
        },
        "security": [
            {},
            {"x402": []},
            {"agentcash": []},
        ],
    }


def mcp_well_known() -> dict[str, Any]:
    """Remote MCP registration document (Streamable HTTP, not stdio-only)."""
    from app.tools_registry import TOOL_PRICES, TOOL_SPECS as specs

    base = _base()
    http_url = f"{base}/mcp"
    return {
        "mcpServers": {
            "alpha-sentinel": {
                "url": http_url,
                "type": "streamable-http",
                "transport": "streamable-http",
                "command": "python",
                "args": ["run_stdio.py"],
                "description": "Alpha Sentinel Market Intelligence",
                "tools": specs,
            }
        },
        "url": http_url,
        "streamableHttpUrl": http_url,
        "transport": "streamable-http",
        "tools": [
            {
                "name": t["name"],
                "description": t["description"][:280],
                "price": TOOL_PRICES.get(t["name"], "$0.01"),
                "free_tier": t["tier_access"]["free"],
            }
            for t in specs
        ],
        "count": TOOL_COUNT,
        "http_base": f"{base}/tools",
    }
