"""Paid catalog and x402 402-challenge builders over the live tool registry.

Pure functions so tests (and AgentCash discover/check) can assert catalog and
payment-required bodies without a chain. Buyer private keys never live here.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.config import parse_price, settings
from app.tools_registry import (
    PAID_TOOLS,
    TOOL_HTTP_ALIASES,
    TOOL_HTTP_PATHS,
    TOOL_PRICES,
    TOOL_SPECS,
    http_path_to_tool,
)

# Base mainnet USDC (native token for x402 exact scheme on eip155:8453).
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Used only when X402_PAY_TO_ADDRESS is unset so AgentCash can still parse a
# payTo field. Operator should replace this with a real seller address.
FALLBACK_PAY_TO = "0x0000000000000000000000000000000000000A02"


def public_base_url() -> str:
    return settings.public_base_url.rstrip("/")


def seller_pay_to() -> str:
    return (settings.x402_pay_to_address or "").strip() or FALLBACK_PAY_TO


def settlement_network() -> str:
    return settings.x402_default_network


def tool_price_usd(tool_name: str) -> float:
    return parse_price(TOOL_PRICES.get(tool_name, settings.x402_default_price))


def usdc_atomic(price_usd: float) -> str:
    """USDC has 6 decimals; x402 amounts are integer atomic units as strings."""
    return str(int(round(float(price_usd) * 1_000_000)))


def tool_resource_url(tool_name: str, base: str | None = None) -> str:
    path = TOOL_HTTP_PATHS.get(tool_name, f"/tools/{tool_name}")
    return f"{(base or public_base_url())}{path}"


def paid_catalog(base_url: str | None = None, network: str | None = None) -> list[dict[str, Any]]:
    """Every paid intelligence tool with URL, method, USDC price, and network."""
    base = (base_url or public_base_url()).rstrip("/")
    net = network or settlement_network()
    catalog: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        name = spec["name"]
        if name not in PAID_TOOLS:
            continue
        price_usd = tool_price_usd(name)
        catalog.append(
            {
                "name": name,
                "url": tool_resource_url(name, base),
                "method": "POST",
                "price": TOOL_PRICES.get(name, "$0.01"),
                "price_usdc": price_usd,
                "amount": usdc_atomic(price_usd),
                "network": net,
                "description": spec["description"].strip().split("\n", 1)[0].strip(),
            }
        )
    return catalog


def all_tool_resources(base_url: str | None = None) -> list[dict[str, Any]]:
    """Paid + free HTTP resources (llms.txt / storefront). Derived from registry."""
    base = (base_url or public_base_url()).rstrip("/")
    net = settlement_network()
    out: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        name = spec["name"]
        free = bool(spec["tier_access"].get("free"))
        price_usd = tool_price_usd(name)
        out.append(
            {
                "name": name,
                "url": tool_resource_url(name, base),
                "method": "POST",
                "price": "free" if free else TOOL_PRICES.get(name, "$0.01"),
                "price_usdc": 0.0 if free else price_usd,
                "amount": "0" if free else usdc_atomic(price_usd),
                "network": None if free else net,
                "what": spec["description"].strip().split("\n", 1)[0].strip(),
                "params": {
                    k: (v.get("description") or k)
                    for k, v in (spec.get("inputSchema") or {}).get("properties", {}).items()
                },
            }
        )
    return out


def payment_required_body(
    tool_name: str,
    *,
    resource_url: str | None = None,
    network: str | None = None,
    pay_to: str | None = None,
    price_usd: float | None = None,
) -> dict[str, Any]:
    """x402 payment-required payload (HTTP 402 body).

    Top-level network/payTo/amount/resource are required for AgentCash check;
    `accepts[]` follows the x402 exact-scheme challenge shape.
    """
    net = network or settlement_network()
    pay = pay_to or seller_pay_to()
    usd = tool_price_usd(tool_name) if price_usd is None else float(price_usd)
    amount = usdc_atomic(usd)
    resource = resource_url or tool_resource_url(tool_name)
    accept = {
        "scheme": "exact",
        "network": net,
        "maxAmountRequired": amount,
        "amount": amount,
        "resource": resource,
        "description": f"Alpha Sentinel {tool_name}",
        "mimeType": "application/json",
        "payTo": pay,
        "maxTimeoutSeconds": 300,
        "asset": USDC_BASE,
        "extra": {"name": "USDC", "version": "2"},
    }
    return {
        "x402Version": 1,
        "error": "Payment required",
        "network": net,
        "payTo": pay,
        "amount": amount,
        "resource": resource,
        "accepts": [accept],
    }


def payment_header_present(headers: Any) -> bool:
    if headers is None:
        return False
    getter = headers.get if hasattr(headers, "get") else lambda *_: None
    for key in ("PAYMENT-SIGNATURE", "X-PAYMENT", "payment-signature", "x-payment"):
        val = getter(key)
        if val:
            return True
    return False


def paid_tool_for_request_path(path: str) -> str | None:
    """Return the paid tool name for this HTTP path, or None if not gated."""
    name = http_path_to_tool(path)
    if name and name in PAID_TOOLS:
        return name
    # Alias table is already consulted by http_path_to_tool; keep a direct check.
    bare = path.split("?")[0]
    if bare.startswith("/api/"):
        bare = bare[4:]
    alias = TOOL_HTTP_ALIASES.get(bare)
    if alias and alias in PAID_TOOLS:
        return alias
    return None


def resource_url_from_path(path: str) -> str:
    parsed = urlparse(path)
    bare = parsed.path or path
    if bare.startswith("/api/"):
        bare = bare[4:] or "/"
    return f"{public_base_url()}{bare}"
