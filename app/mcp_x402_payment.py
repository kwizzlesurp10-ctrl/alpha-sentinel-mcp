"""x402 payment transport for Streamable HTTP MCP (mirrors x402-mcp PR #658)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from app import x402_services
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

    from x402.http import (
        encode_payment_required_header,
        encode_payment_signature_header,
    )
    from x402.schemas import PaymentPayload, PaymentRequired

    from app.payment_idempotency import (
        IdempotencyStoreRequired,
        begin_payment_attempt,
        cache_paid_response,
        complete_payment_attempt,
        idempotency_unavailable_response,
        load_cached_paid_response,
        release_payment_attempt,
    )

    def _payment_error(reason: str, error: str | None = None, **extra: Any) -> dict[str, Any]:
        sc = payment_required_structured_content(tool_name)
        sc["invalid_reason"] = reason
        if error:
            sc["error"] = error
        sc.update({k: v for k, v in extra.items() if v is not None})
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps(sc)}],
            "structuredContent": sc,
        }

    # The MCP payment is a PaymentPayload object; the facilitator path expects
    # the base64 PAYMENT-SIGNATURE encoding of it.
    try:
        payload_model = PaymentPayload.model_validate(payment_body)
        sig = encode_payment_signature_header(payload_model)
    except Exception as exc:
        return _payment_error(f"malformed_payment: {str(exc).splitlines()[0][:160]}")

    accepts, resource, extensions = build_tool_payment_bundle(tool_name)
    pr = PaymentRequired(
        x402_version=2,
        accepts=list(accepts),
        error=f"Alpha Sentinel {tool_name}",
        resource=resource,
        extensions=extensions,
    )
    required_header = encode_payment_required_header(pr)

    try:
        begin = await begin_payment_attempt("mcp", tool_name, sig)
    except IdempotencyStoreRequired:
        err = idempotency_unavailable_response()
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps(err)}],
            "structuredContent": err,
        }

    if not begin.allowed:
        cached = await load_cached_paid_response("mcp", tool_name, begin.fingerprint)
        if cached:
            try:
                replay = json.loads(cached["body"])
            except (json.JSONDecodeError, TypeError):
                replay = None
            if isinstance(replay, dict):
                replay["_meta"] = {**(replay.get("_meta") or {}), "x402/idempotent-replay": True}
                return replay
        return _payment_error(begin.reason or "payment_already_consumed", error="replay_rejected")

    # Verify only; settle after the tool succeeds so a failed call never
    # burns the buyer's authorization (same contract as the HTTP gate).
    try:
        verified = await x402_services.verify_from_headers(sig, required_header)
    except Exception:
        await release_payment_attempt("mcp", tool_name, begin.fingerprint)
        raise
    if not verified.get("is_valid"):
        await release_payment_attempt("mcp", tool_name, begin.fingerprint)
        return _payment_error(verified.get("invalid_reason") or "verification_failed")
    verified["_payment_required"] = required_header

    try:
        tool_result = await handler(arguments)
    except Exception as exc:
        tool_result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
    if not isinstance(tool_result, dict) or tool_result.get("isError"):
        await release_payment_attempt("mcp", tool_name, begin.fingerprint)
        return tool_result if isinstance(tool_result, dict) else {
            "isError": True,
            "content": [{"type": "text", "text": "tool returned no result"}],
        }

    settled = await x402_services.settle_verified_payment(verified)
    if not settled.get("payment_settled"):
        await release_payment_attempt("mcp", tool_name, begin.fingerprint)
        return _payment_error(
            settled.get("settlement_error") or settled.get("invalid_reason") or "settlement_failed",
            error="Payment settlement failed",
            settlement_error=settled.get("settlement_error"),
        )

    settlement = settled.get("settlement") or {}
    if not await complete_payment_attempt("mcp", tool_name, begin.fingerprint, settlement):
        await release_payment_attempt("mcp", tool_name, begin.fingerprint)
        return _payment_error("settlement_tx_replay", error="replay_rejected")

    tool_result["_meta"] = {
        **(tool_result.get("_meta") or {}),
        MCP_PAYMENT_RESPONSE_META_KEY: settlement,
    }
    try:
        await cache_paid_response(
            "mcp", tool_name, begin.fingerprint, status_code=200, body=json.dumps(tool_result)
        )
    except Exception as exc:
        logger.warning("failed to cache MCP paid response: %s", exc)
    return tool_result
