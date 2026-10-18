"""HTTP x402 gate for paid intelligence tools (server-authored challenges)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app import challenge_cache, x402_services
from app.commerce_payment import (
    reject_tampered_client_header,
    resolve_tool_authoritative_header,
    store_tool_challenge,
)
from app.config import settings
from app.models import BuildSellerRequirementsInput
from app.payment_replay import claim_settlement_tx
from app.payments import TOOL_PRICES, tool_resource_url
from app.tools_registry import PAID_TOOLS, TOOL_HTTP_PATHS, get_tool_spec

logger = logging.getLogger(__name__)

_built_by_fp: dict[str, dict[str, Any]] = {}


def _tool_discovery_example(tool_name: str) -> dict[str, Any]:
    if tool_name == "analyze_volatility":
        return {"symbol": "btc", "window_minutes": 60, "z_threshold": 2.0}
    if tool_name == "aggregate_sentiment":
        return {"symbols": ["btc", "eth"], "sources": ["news"], "window_minutes": 60}
    if tool_name == "calculate_risk_score":
        return {"symbols": ["btc", "eth"], "include_factors": ["volatility", "liquidity"]}
    if tool_name == "generate_market_report":
        return {"report_type": "daily", "symbols": ["btc", "eth"], "format": "json"}
    return {}


def _tool_discovery_output_example(tool_name: str) -> dict[str, Any]:
    return {"success": True, "tool": tool_name, "data": {}}


async def build_tool_challenge(tool_name: str, resource_url: str) -> dict[str, Any]:
    if tool_name not in PAID_TOOLS:
        raise ValueError(f"not a paid tool: {tool_name}")

    pay_to = settings.x402_pay_to_address
    if not pay_to:
        raise ValueError("X402_PAY_TO_ADDRESS unset")

    spec = get_tool_spec(tool_name)
    desc = (spec or {}).get("description", tool_name).strip().split("\n", 1)[0].strip()
    price = TOOL_PRICES.get(tool_name, settings.x402_default_price)
    network = x402_services.resolve_revenue_network()

    fp = challenge_cache.fingerprint(
        tool=tool_name,
        resource_url=resource_url,
        description=desc,
        price=price,
        network=network,
        pay_to=pay_to,
    )
    cached = _built_by_fp.get(fp)
    if cached:
        return cached

    built = x402_services.build_seller_requirements(
        BuildSellerRequirementsInput(
            network=network,
            pay_to=pay_to,
            price=price,
            scheme="exact",
            description=desc[:480],
            resource_url=resource_url,
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

    payment_required_body: dict[str, Any]
    try:
        from x402.http import decode_payment_required_header

        pr = decode_payment_required_header(built["payment_required_header"])
        payment_required_body = (
            pr.model_dump(by_alias=True, exclude_none=True)
            if hasattr(pr, "model_dump")
            else dict(pr)
        )
    except Exception:
        payment_required_body = {"error": "Payment required", "x402Version": 2}

    payload = {
        **built,
        "payment_required": payment_required_body,
        "tool_name": tool_name,
        "resource_url": resource_url,
    }

    def _header() -> str:
        return built["payment_required_header"]

    challenge_cache.get_or_build(f"tool:{tool_name}", fp, _header)
    store_tool_challenge(tool_name, resource_url, built)
    _built_by_fp[fp] = payload
    return payload


def payment_signature_from_request(request: Request) -> str | None:
    for key in ("PAYMENT-SIGNATURE", "X-PAYMENT", "payment-signature", "x-payment"):
        val = request.headers.get(key)
        if val:
            return val
    return None


def payment_required_from_request(request: Request) -> str | None:
    for key in ("PAYMENT-REQUIRED", "payment-required"):
        val = request.headers.get(key)
        if val:
            return val
    return None


def settlement_receipt_header(settlement: dict[str, Any] | None) -> str | None:
    if not settlement:
        return None
    return base64.b64encode(json.dumps(settlement).encode()).decode()


async def handle_paid_tool_request(
    request: Request,
    tool_name: str,
    resource_url: str,
) -> JSONResponse | None:
    """Return a JSONResponse to short-circuit the request, or None to proceed."""
    if tool_name not in PAID_TOOLS:
        return None

    try:
        built = await build_tool_challenge(tool_name, resource_url)
    except Exception as exc:
        logger.warning("challenge build failed for %s: %s", tool_name, exc)
        stale = challenge_cache.load(f"tool:{tool_name}")
        if stale and stale.get("header"):
            built = {
                "payment_required": {"error": "Payment required", "x402Version": 2},
                "payment_required_header": stale["header"],
            }
        else:
            return JSONResponse(
                status_code=503,
                headers={"Retry-After": "30"},
                content={"error": "challenge_unavailable", "detail": str(exc)[:200]},
            )

    auth_header = built["payment_required_header"]
    sig = payment_signature_from_request(request)
    if not sig:
        body = built.get("payment_required") or {}
        legacy = {
            "x402Version": body.get("x402Version", 2),
            "error": body.get("error") or "Payment required",
            "network": x402_services.resolve_revenue_network(),
            "payTo": settings.x402_pay_to_address,
            "amount": built.get("requirements", [{}])[0].get("amount")
            if built.get("requirements")
            else None,
            "resource": resource_url,
            "accepts": built.get("requirements") or [],
        }
        return JSONResponse(
            status_code=402,
            content={**body, **{k: v for k, v in legacy.items() if v is not None}},
            headers={
                "PAYMENT-REQUIRED": auth_header,
                "Access-Control-Expose-Headers": "PAYMENT-REQUIRED,PAYMENT-RESPONSE",
            },
        )

    try:
        challenge = resolve_tool_authoritative_header(tool_name, rebuild=lambda: None)
        reject_tampered_client_header(
            tool_name,
            payment_required_from_request(request),
            challenge,
        )
        auth_header = challenge.payment_required_header
    except ValueError as exc:
        return JSONResponse(
            status_code=402,
            content={
                "error": "payment_invalid",
                "detail": str(exc),
            },
            headers={"PAYMENT-REQUIRED": auth_header},
        )

    result = await x402_services.verify_and_settle_from_headers(sig, auth_header)
    if not result.get("is_valid"):
        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment verification failed",
                "invalid_reason": result.get("invalid_reason"),
            },
            headers={"PAYMENT-REQUIRED": auth_header},
        )

    settlement = result.get("settlement") or {}
    if result.get("payment_settled"):
        tx = (
            settlement.get("transaction")
            or settlement.get("tx_hash")
            or settlement.get("txHash")
        )
        if not claim_settlement_tx(str(tx) if tx else None):
            return JSONResponse(
                status_code=402,
                content={"error": "replay_rejected", "detail": "settlement tx already used"},
                headers={"PAYMENT-REQUIRED": auth_header},
            )

    request.state.x402_settlement = settlement
    request.state.x402_payment_settled = bool(result.get("payment_settled"))
    request.state.x402_receipt_header = settlement_receipt_header(settlement)
    return None


def attach_payment_response(response: JSONResponse, request: Request) -> JSONResponse:
    receipt = getattr(request.state, "x402_receipt_header", None)
    if receipt:
        response.headers["PAYMENT-RESPONSE"] = receipt
        response.headers.setdefault(
            "Access-Control-Expose-Headers",
            "PAYMENT-REQUIRED,PAYMENT-RESPONSE",
        )
    return response
