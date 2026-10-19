"""x402 payment transport for Streamable HTTP MCP (mirrors x402-mcp PR #658)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from app.config import settings
from app.payments import TOOL_PRICES
from app.tool_payment_gate import (
    _tool_discovery_example,
    _tool_discovery_output_example,
)
from app.tools_registry import FREE_TOOLS, PAID_TOOLS, get_tool_spec

logger = logging.getLogger(__name__)

MCP_STREAMABLE_HTTP_PATH = "/mcp"
MCP_PAYMENT_META_KEY = "x402/payment"
MCP_PAYMENT_RESPONSE_META_KEY = "x402/payment-response"


def mcp_resource_url(tool_name: str | None = None) -> str:
    """Absolute resource URL for challenges.

    When *tool_name* is set, use ``/tools/{tool_name}`` so each MCP tool gets its
    own CDP Bazaar catalog entry instead of collapsing onto ``/mcp``.
    """
    from app.bazaar_indexing import mcp_tool_resource_url

    if tool_name:
        return mcp_tool_resource_url(settings.public_base_url, tool_name)
    return f"{settings.public_base_url.rstrip('/')}{MCP_STREAMABLE_HTTP_PATH}"


@lru_cache(maxsize=1)
def get_mcp_resource_server() -> Any:
    from x402.extensions.bazaar import bazaar_resource_server_extension

    from app import x402_services

    server = x402_services._resource_server(settings.x402_default_network)
    try:
        server.register_extension(bazaar_resource_server_extension)
    except Exception:
        pass
    return server


def _bazaar_extensions(tool_name: str) -> dict[str, Any]:
    from x402.extensions.bazaar import (
        DeclareMcpDiscoveryConfig,
        OutputConfig,
        declare_mcp_discovery_extension,
    )

    spec = get_tool_spec(tool_name) or {}
    return declare_mcp_discovery_extension(
        DeclareMcpDiscoveryConfig(
            tool_name=tool_name,
            description=(spec.get("description") or tool_name).strip()[:480],
            transport="streamable-http",
            input_schema=spec.get("inputSchema") or {"type": "object"},
            example=_tool_discovery_example(tool_name),
            output=OutputConfig(example=_tool_discovery_output_example(tool_name)),
        )
    )


def build_tool_payment_bundle(tool_name: str) -> tuple[list[Any], Any, dict[str, Any]]:
    from x402.schemas import PaymentRequirements, ResourceInfo

    from app import x402_services
    from app.models import BuildSellerRequirementsInput

    if tool_name in FREE_TOOLS:
        raise ValueError(f"{tool_name} is free — no payment bundle")

    pay_to = settings.x402_pay_to_address
    if not pay_to:
        raise ValueError("X402_PAY_TO_ADDRESS required for MCP paid tools")

    network = x402_services.resolve_revenue_network()
    price = TOOL_PRICES.get(tool_name, settings.x402_default_price)
    spec = get_tool_spec(tool_name) or {}
    description = x402_services._clamp_description(
        (spec.get("description") or tool_name).strip().split("\n", 1)[0]
    )

    built = x402_services.build_seller_requirements(
        BuildSellerRequirementsInput(
            network=network,
            pay_to=pay_to,
            price=price,
            scheme="exact",
            description=description,
            resource_url=mcp_resource_url(tool_name),
            mime_type="application/json",
            discoverable=settings.bazaar_discoverable,
            discovery_method="POST",
            discovery_input_example=_tool_discovery_example(tool_name),
            discovery_output_example=_tool_discovery_output_example(tool_name),
            service_name=(settings.bazaar_service_name or "Alpha Sentinel")[:32],
            service_tags=[
                t.strip()
                for t in settings.bazaar_service_tags.split(",")
                if t.strip()
            ],
        )
    )
    raw_reqs = built.get("requirements") or []
    accepts = [PaymentRequirements.model_validate(r) for r in raw_reqs]
    if not accepts:
        raise ValueError(f"could not build payment requirements for {tool_name}")

    resource_payload = built.get("resource") or {}
    resource = ResourceInfo.model_validate(resource_payload) if resource_payload else ResourceInfo(
        url=mcp_resource_url(tool_name),
        description=description,
        mime_type="application/json",
    )
    extensions = _bazaar_extensions(tool_name)
    return accepts, resource, extensions


def payment_required_structured_content(
    tool_name: str,
) -> dict[str, Any]:
    accepts, resource, extensions = build_tool_payment_bundle(tool_name)
    req = accepts[0]
    accept_dump = req.model_dump(by_alias=True, exclude_none=True) if hasattr(req, "model_dump") else dict(req)
    return {
        "x402Version": 2,
        "error": f"Payment required for {tool_name}",
        "accepts": [accept_dump],
        "resource": resource.model_dump(by_alias=True, exclude_none=True)
        if hasattr(resource, "model_dump")
        else dict(resource),
        "extensions": extensions,
        "upsell": f"POST {settings.public_base_url.rstrip('/')}/tools/{tool_name}/sample for a free preview",
    }


def extract_mcp_payment_meta(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if not params:
        return None
    meta = params.get("_meta") or params.get("meta") or {}
    if isinstance(meta, dict):
        body = meta.get(MCP_PAYMENT_META_KEY) or meta.get("x402/payment")
        if isinstance(body, dict):
            return body
    return None


async def execute_paid_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    payment_body: dict[str, Any] | None,
    handler: Any,
) -> dict[str, Any]:
    """Run handler after verify+settle when payment_body present; else payment required."""
    if tool_name not in PAID_TOOLS:
        return await handler(arguments)

    if not payment_body:
        sc = payment_required_structured_content(tool_name)
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps(sc)}],
            "structuredContent": sc,
        }

    from x402.http import encode_payment_signature_header


    try:
        sig = encode_payment_signature_header(payment_body)
    except Exception:
        sig = json.dumps(payment_body)

    accepts, resource, extensions = build_tool_payment_bundle(tool_name)
    from x402.http import encode_payment_required_header
    from x402.schemas import PaymentRequired

    pr = PaymentRequired(
        x402_version=2,
        accepts=list(accepts),
        error=f"Alpha Sentinel {tool_name}",
        resource=resource,
        extensions=extensions,
    )
    required_header = encode_payment_required_header(pr)

    from app.payment_idempotency import (
        IdempotencyStoreRequired,
        idempotency_unavailable_response,
        verify_settle_with_idempotency,
    )

    try:
        result = await verify_settle_with_idempotency(
            "mcp", tool_name, sig, required_header
        )
    except IdempotencyStoreRequired:
        err = idempotency_unavailable_response()
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps(err)}],
            "structuredContent": err,
        }

    if result.get("idempotency_blocked") or not result.get("is_valid") or not result.get(
        "payment_settled"
    ):
        sc = payment_required_structured_content(tool_name)
        sc["invalid_reason"] = result.get("invalid_reason") or result.get("reason")
        sc["settlement_error"] = result.get("settlement_error")
        if result.get("idempotency_blocked"):
            sc["error"] = "replay_rejected"
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps(sc)}],
            "structuredContent": sc,
        }

    try:
        tool_result = await handler(arguments)
    except Exception as exc:
        tool_result = {
            "isError": True,
            "content": [{"type": "text", "text": str(exc)}],
        }

    settlement = result.get("settlement") or {}
    meta = {MCP_PAYMENT_RESPONSE_META_KEY: settlement}
    if isinstance(tool_result, dict):
        tool_result["_meta"] = {**(tool_result.get("_meta") or {}), **meta}
    return tool_result
