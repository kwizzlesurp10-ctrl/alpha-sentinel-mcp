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
from app.deploy_env import is_vercel_production
from app.models import BuildSellerRequirementsInput
from app.payment_idempotency import (
    IdempotencyStoreRequired,
    begin_payment_attempt,
    cache_paid_response,
    complete_payment_attempt,
    idempotency_unavailable_response,
    load_cached_paid_response,
    release_payment_attempt,
)
from app.payments import TOOL_PRICES
from app.tools_registry import PAID_TOOLS, get_tool_spec

logger = logging.getLogger(__name__)

_built_by_fp: dict[str, dict[str, Any]] = {}


def clear_built_challenge_cache() -> None:
    _built_by_fp.clear()


def _tool_discovery_example(tool_name: str) -> dict[str, Any]:
    if tool_name == "fetch_price":
        return {"symbol": "btc"}
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
        store_tool_challenge(tool_name, resource_url, cached)
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


def _seller_ready_for_settlement() -> tuple[bool, str]:
    if not (settings.x402_pay_to_address or "").strip():
        return False, "X402_PAY_TO_ADDRESS is not configured"
    net = x402_services.resolve_revenue_network()
    if net == "eip155:8453" and not x402_services._use_cdp(net):
        return (
            False,
            "CDP_API_KEY_ID and CDP_API_KEY_SECRET are required for Base mainnet settlement",
        )
    return True, ""


async def handle_paid_tool_request(
    request: Request,
    tool_name: str,
    resource_url: str,
) -> JSONResponse | None:
    """Return a JSONResponse to short-circuit the request, or None to proceed."""
    if tool_name not in PAID_TOOLS:
        return None

    if is_vercel_production():
        ready, reason = _seller_ready_for_settlement()
        if not ready:
            return JSONResponse(
                status_code=503,
                headers={"Retry-After": "120"},
                content={
                    "error": "x402_seller_misconfigured",
                    "detail": reason,
                },
            )

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

    # Idempotency: claim before verify. A prior successful payment returns the
    # cached response so the buyer is not charged twice and still gets data.
    # Reject undecodable signatures locally: no KV claim, no facilitator call.
    try:
        x402_services.decode_payment_signature(sig)
    except Exception as exc:
        return JSONResponse(
            status_code=402,
            content={
                "error": "payment_invalid",
                "invalid_reason": f"malformed_payment: {str(exc).splitlines()[0][:160]}",
            },
            headers={"PAYMENT-REQUIRED": auth_header},
        )

    try:
        begin = await begin_payment_attempt("http", tool_name, sig)
    except IdempotencyStoreRequired:
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "120"},
            content=idempotency_unavailable_response(),
        )

    if not begin.allowed:
        cached = await load_cached_paid_response("http", tool_name, begin.fingerprint)
        if cached:
            headers = {
                "Access-Control-Expose-Headers": "PAYMENT-REQUIRED,PAYMENT-RESPONSE",
                "X-Payment-Idempotent-Replay": "1",
            }
            if cached.get("payment_response_header"):
                headers["PAYMENT-RESPONSE"] = cached["payment_response_header"]
            try:
                body = json.loads(cached["body"])
            except json.JSONDecodeError:
                body = {"raw": cached["body"]}
            return JSONResponse(
                status_code=int(cached["status_code"]),
                content=body,
                headers=headers,
            )
        return JSONResponse(
            status_code=402,
            content={
                "error": "replay_rejected",
                "detail": begin.reason or "payment_already_consumed",
            },
            headers={"PAYMENT-REQUIRED": auth_header},
        )

    # Verify only — settlement waits until the handler succeeds (so a 400 on
    # bad input never burns the USDC authorization).
    try:
        verified = await x402_services.verify_from_headers(sig, auth_header)
    except Exception:
        await release_payment_attempt("http", tool_name, begin.fingerprint)
        raise

    if not verified.get("is_valid"):
        await release_payment_attempt("http", tool_name, begin.fingerprint)
        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment verification failed",
                "invalid_reason": verified.get("invalid_reason"),
            },
            headers={"PAYMENT-REQUIRED": auth_header},
        )

    verified["_payment_required"] = auth_header
    request.state.x402_pending = {
        "scope": "http",
        "tool_name": tool_name,
        "fingerprint": begin.fingerprint,
        "signature": sig,
        "auth_header": auth_header,
        "verify_ctx": verified,
    }
    return None


def _soft_failure(response: JSONResponse) -> str | None:
    try:
        body = json.loads(bytes(response.body).decode() or "null")
    except Exception:
        return None
    if isinstance(body, dict) and body.get("success") is False:
        return str(body.get("error") or "tool returned success=false")[:300]
    return None


async def finalize_pending_payment(request: Request, response: JSONResponse) -> JSONResponse:
    """Settle (on 2xx) or release (on error) a payment deferred by the gate."""
    pending = getattr(request.state, "x402_pending", None)
    if not pending:
        return response

    scope = pending["scope"]
    tool_name = pending["tool_name"]
    fingerprint = pending["fingerprint"]

    if response.status_code >= 400:
        await release_payment_attempt(scope, tool_name, fingerprint)
        request.state.x402_pending = None
        return response

    # Intelligence handlers report upstream / validation failures as a 200
    # body with success:false. That is not a deliverable: do not charge.
    soft_error = _soft_failure(response)
    if soft_error is not None:
        await release_payment_attempt(scope, tool_name, fingerprint)
        request.state.x402_pending = None
        return JSONResponse(
            status_code=502,
            content={
                "error": "tool_failed",
                "detail": soft_error,
                "payment_settled": False,
            },
        )

    settled = await x402_services.settle_verified_payment(pending["verify_ctx"])
    if not settled.get("payment_settled"):
        await release_payment_attempt(scope, tool_name, fingerprint)
        request.state.x402_pending = None
        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment settlement failed",
                "invalid_reason": settled.get("settlement_error")
                or settled.get("invalid_reason")
                or "settlement_failed",
                "settlement_error": settled.get("settlement_error"),
            },
            headers={
                "PAYMENT-REQUIRED": pending["auth_header"],
                "Access-Control-Expose-Headers": "PAYMENT-REQUIRED,PAYMENT-RESPONSE",
            },
        )

    settlement = settled.get("settlement") or {}
    if not await complete_payment_attempt(scope, tool_name, fingerprint, settlement):
        await release_payment_attempt(scope, tool_name, fingerprint)
        request.state.x402_pending = None
        return JSONResponse(
            status_code=402,
            content={
                "error": "replay_rejected",
                "detail": "settlement_tx_replay",
            },
            headers={"PAYMENT-REQUIRED": pending["auth_header"]},
        )

    receipt = settlement_receipt_header(settlement)
    request.state.x402_settlement = settlement
    request.state.x402_payment_settled = True
    request.state.x402_receipt_header = receipt
    request.state.x402_pending = None

    if receipt:
        response.headers["PAYMENT-RESPONSE"] = receipt
        response.headers.setdefault(
            "Access-Control-Expose-Headers",
            "PAYMENT-REQUIRED,PAYMENT-RESPONSE",
        )

    try:
        body_bytes = response.body
        body_text = body_bytes.decode() if isinstance(body_bytes, (bytes, bytearray)) else str(body_bytes)
        await cache_paid_response(
            scope,
            tool_name,
            fingerprint,
            status_code=response.status_code,
            body=body_text,
            payment_response_header=receipt,
        )
    except Exception as exc:
        logger.warning("failed to cache paid response: %s", exc)

    return response


def attach_payment_response(response: JSONResponse, request: Request) -> JSONResponse:
    receipt = getattr(request.state, "x402_receipt_header", None)
    if receipt:
        response.headers["PAYMENT-RESPONSE"] = receipt
        response.headers.setdefault(
            "Access-Control-Expose-Headers",
            "PAYMENT-REQUIRED,PAYMENT-RESPONSE",
        )
    return response
