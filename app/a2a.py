"""A2A JSON-RPC Send Message + Get Task with x402-a2a payments.

Unpaid paid-skill calls return ``input-required`` + ``x402.payment.required``.
Data is returned only after verify+settle succeeds (``payment_settled``).
Free/unknown skills stay free. Tasks are stored in-process so Get Task by id
returns the same work item produced by Send Message.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.tools_registry import EXPECTED_TOOL_NAMES, PAID_TOOLS, get_tool_spec

logger = logging.getLogger(__name__)

META_STATUS = "x402.payment.status"
META_REQUIRED = "x402.payment.required"
META_PAYLOAD = "x402.payment.payload"
META_RECEIPTS = "x402.payment.receipts"
META_ERROR = "x402.payment.error"

A2A_X402_EXTENSION_URI = (
    "https://github.com/google-agentic-commerce/a2a-x402/blob/main/spec/v0.2"
)
A2A_X402_LEGACY_EXTENSION_URI = "https://github.com/google-a2a/a2a-x402/v0.1"
A2A_X402_EXTENSION_URIS = (A2A_X402_EXTENSION_URI, A2A_X402_LEGACY_EXTENSION_URI)

# In-memory task store (A2A streaming / eight-state machine is out of scope).
TASKS: dict[str, dict[str, Any]] = {}


TASK_TTL_SECONDS = 3600


def clear_task_store() -> None:
    """Test hook: drop in-memory A2A tasks."""
    TASKS.clear()


def _task_key(task_id: str) -> str:
    return f"a2a:task:{task_id}"


async def _persist_task(task_id: str) -> None:
    """Mirror a task to KV so a payment submission can land on another instance."""
    stored = TASKS.get(task_id)
    if stored is None:
        return
    try:
        from app.kv_store import get_store

        await get_store().set(_task_key(task_id), json.dumps(stored, default=str), TASK_TTL_SECONDS)
    except Exception as exc:
        logger.warning("a2a task persist failed: %s", exc)


async def _hydrate_task(task_id: str | None) -> None:
    """Load a task from KV into the local cache when this instance has not seen it."""
    if not task_id or task_id in TASKS:
        return
    try:
        from app.kv_store import get_store

        raw = await get_store().get(_task_key(str(task_id)))
    except Exception as exc:
        logger.warning("a2a task load failed: %s", exc)
        return
    if not raw:
        return
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
    if isinstance(data, dict) and data.get("id") == task_id:
        TASKS[str(task_id)] = data


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _extract_skill_and_params(params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(params, dict):
        params = {}
    skill = params.get("skill") or params.get("skillId") or params.get("name") or params.get("skill_id")
    inner: dict[str, Any] = {}
    nested = params.get("params")
    if isinstance(nested, dict):
        inner.update(nested)
        skill = skill or nested.get("skill") or nested.get("skillId") or nested.get("name")

    message = params.get("message") or params.get("input") or {}
    texts: list[str] = []
    if isinstance(message, dict):
        meta = message.get("metadata") or {}
        if isinstance(meta, dict):
            skill = skill or meta.get("skillId") or meta.get("skill")
        for part in message.get("parts") or []:
            if not isinstance(part, dict):
                continue
            data = part.get("data")
            if isinstance(data, dict):
                skill = skill or data.get("skill") or data.get("skillId") or data.get("name")
                inner.update({k: v for k, v in data.items() if k not in ("skill", "skillId", "name")})
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    elif isinstance(message, str) and message.strip():
        texts.append(message.strip())

    if not skill and texts:
        tokens = texts[0].replace(",", " ").split()
        if tokens:
            skill = tokens[0]
            if len(tokens) > 1 and "symbol" not in inner:
                inner["symbol"] = tokens[1]

    for key in (
        "symbol",
        "symbols",
        "window_minutes",
        "z_threshold",
        "sources",
        "include_factors",
        "report_type",
        "format",
    ):
        if key in params and key not in inner:
            inner[key] = params[key]

    if not skill:
        skill = "fetch_price"
    return str(skill), inner


def _flatten_price_usd(payload: Any) -> dict[str, Any]:
    """Ensure numeric price_usd is visible on the artifact (A2A clients + tests)."""
    if not isinstance(payload, dict):
        return {"result": payload}
    out = dict(payload)
    if "price_usd" not in out:
        data = payload.get("data")
        if isinstance(data, dict) and "price_usd" in data:
            out["price_usd"] = data["price_usd"]
    return out


async def invoke_skill(skill: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from app.intelligence.price_feed import fetch_price_endpoint
    from app.intelligence.reports import generate_market_report_endpoint
    from app.intelligence.risk import calculate_risk_score_endpoint
    from app.intelligence.sentiment import aggregate_sentiment_endpoint
    from app.intelligence.volatility import analyze_volatility_endpoint

    name = skill.strip()
    if name not in EXPECTED_TOOL_NAMES and get_tool_spec(name) is None:
        return {"success": False, "error": f"Unknown skill: {name}", "skill": name}

    if name == "fetch_price":
        return _flatten_price_usd(await fetch_price_endpoint(str(arguments.get("symbol") or "btc")))
    if name == "analyze_volatility":
        return await analyze_volatility_endpoint(
            str(arguments.get("symbol") or "btc"),
            int(arguments.get("window_minutes") or 60),
            float(arguments.get("z_threshold") or 2.0),
        )
    if name == "aggregate_sentiment":
        symbols = arguments.get("symbols") or [arguments.get("symbol") or "btc"]
        if isinstance(symbols, str):
            symbols = [symbols]
        return await aggregate_sentiment_endpoint(
            list(symbols),
            arguments.get("sources"),
            int(arguments.get("window_minutes") or 60),
        )
    if name == "calculate_risk_score":
        symbols = arguments.get("symbols") or [arguments.get("symbol") or "btc"]
        if isinstance(symbols, str):
            symbols = [symbols]
        return await calculate_risk_score_endpoint(list(symbols), arguments.get("include_factors"))
    if name == "generate_market_report":
        symbols = arguments.get("symbols")
        if isinstance(symbols, str):
            symbols = [symbols]
        return await generate_market_report_endpoint(
            str(arguments.get("report_type") or "daily"),
            symbols,
            str(arguments.get("format") or "json"),
        )
    return {"success": False, "error": f"Unhandled skill: {name}", "skill": name}


def _agent_message(text: str, metadata: dict[str, Any], message_id: str | None = None) -> dict[str, Any]:
    return {
        "role": "agent",
        "kind": "message",
        "messageId": message_id or str(uuid.uuid4()),
        "parts": [{"kind": "text", "text": text}],
        "metadata": metadata,
    }


def build_task(
    skill: str,
    *,
    state: str,
    message: dict[str, Any],
    payload: dict[str, Any] | None = None,
    message_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    tid = task_id or str(uuid.uuid4())
    context_id = str(uuid.uuid4())
    artifacts: list[dict[str, Any]] = []
    if payload is not None and state == "completed":
        artifacts.append(
            {
                "artifactId": str(uuid.uuid4()),
                "name": skill,
                "parts": [
                    {"kind": "data", "data": payload},
                    {"kind": "text", "text": json.dumps(payload)},
                ],
            }
        )
    task = {
        "id": tid,
        "contextId": context_id,
        "kind": "task",
        "status": {"state": state, "timestamp": _now(), "message": message},
        "metadata": {"skill": skill, "skillId": skill},
        "artifacts": artifacts,
        "history": [message],
    }
    return task


def get_task(task_id: str) -> dict[str, Any] | None:
    stored = TASKS.get(task_id)
    if stored is None:
        return None
    # Strip internal keys before returning to the client.
    return {
        k: v
        for k, v in stored.items()
        if k
        not in {
            "payment_required_header",
            "skill_input",
            "receipts_internal",
        }
    }


def jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _payment_required_body(header: str) -> dict[str, Any]:
    from x402.http import decode_payment_required_header

    pr = decode_payment_required_header(header)
    if hasattr(pr, "model_dump"):
        return pr.model_dump(by_alias=True, exclude_none=True)
    return dict(pr)


def _encode_payload_as_signature(payload: Any) -> str:
    from x402.http import encode_payment_signature_header
    from x402.schemas import PaymentPayload

    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        try:
            pp = PaymentPayload.model_validate(payload)
            return encode_payment_signature_header(pp)
        except Exception:
            return base64.b64encode(json.dumps(payload).encode()).decode()
    raise ValueError("payment payload must be a string or object")


def _settlement_receipt(settlement: dict[str, Any], *, network: str) -> dict[str, Any]:
    return {
        "success": bool(settlement.get("success")),
        "transaction": settlement.get("transaction") or settlement.get("txHash"),
        "network": settlement.get("network") or network,
        "payer": settlement.get("payer"),
        "errorReason": settlement.get("errorReason") or settlement.get("error"),
    }


async def _build_challenge_for_skill(skill: str) -> dict[str, Any]:
    from app.payments import public_base_url
    from app.tool_payment_gate import build_tool_challenge

    resource_url = f"{public_base_url()}/tools/{skill}"
    return await build_tool_challenge(skill, resource_url)


async def _challenge_task(
    skill: str,
    skill_input: dict[str, Any],
    message_id: str | None,
) -> dict[str, Any]:
    from app.config import settings

    if not (settings.x402_pay_to_address or "").strip():
        raise RuntimeError("seller not configured")

    built = await _build_challenge_for_skill(skill)
    header = built["payment_required_header"]
    required_body = built.get("payment_required") or _payment_required_body(header)
    pay_meta = {
        META_STATUS: "payment-required",
        META_REQUIRED: required_body,
    }
    msg = _agent_message(
        f"Payment is required to run {skill}.",
        pay_meta,
        message_id=message_id,
    )
    task = build_task(skill, state="input-required", message=msg, message_id=message_id)
    TASKS[task["id"]] = {
        **task,
        "skillId": skill,
        "skill_input": skill_input,
        "payment_required_header": header,
        "receipts": [],
    }
    return task


async def _continue_paid_task(
    task_id: str,
    payload_obj: Any,
) -> dict[str, Any]:
    from app import x402_services
    from app.payment_idempotency import IdempotencyStoreRequired

    stored = TASKS[task_id]
    skill = stored.get("skillId") or stored.get("metadata", {}).get("skillId") or "fetch_price"
    header = stored["payment_required_header"]
    network = x402_services.resolve_revenue_network()

    try:
        signature = _encode_payload_as_signature(payload_obj)
    except Exception as exc:
        receipt = _settlement_receipt(
            {"success": False, "errorReason": str(exc)},
            network=network,
        )
        receipts = list(stored.get("receipts") or []) + [receipt]
        msg = _agent_message(
            "Payment payload could not be parsed.",
            {
                META_STATUS: "payment-failed",
                META_ERROR: "INVALID_SIGNATURE",
                META_RECEIPTS: receipts,
            },
        )
        task = build_task(skill, state="failed", message=msg, task_id=task_id)
        stored.update(task)
        stored["receipts"] = receipts
        return get_task(task_id) or task

    from app.payment_idempotency import (
        begin_payment_attempt,
        complete_payment_attempt,
        release_payment_attempt,
    )

    def _payment_failed(reason: str, error_code: str = "INVALID_SIGNATURE") -> dict[str, Any]:
        receipt = _settlement_receipt({"success": False, "errorReason": reason}, network=network)
        receipts = list(stored.get("receipts") or []) + [receipt]
        msg = _agent_message(
            "Payment verification or settlement failed.",
            {
                META_STATUS: "payment-failed",
                META_ERROR: error_code,
                META_REQUIRED: _payment_required_body(header),
                META_RECEIPTS: receipts,
            },
        )
        # Stay input-required so the client can retry with a fresh payment.
        task = build_task(skill, state="input-required", message=msg, task_id=task_id)
        stored.update(task)
        stored["receipts"] = receipts
        return get_task(task_id) or task

    try:
        begin = await begin_payment_attempt("a2a", skill, signature)
    except IdempotencyStoreRequired:
        msg = _agent_message(
            "Payment idempotency store unavailable.",
            {META_STATUS: "payment-failed", META_ERROR: "STORE_UNAVAILABLE"},
        )
        task = build_task(skill, state="failed", message=msg, task_id=task_id)
        stored.update(task)
        return get_task(task_id) or task
    if not begin.allowed:
        return _payment_failed(begin.reason or "payment_already_consumed", "DUPLICATE_PAYMENT")

    # Verify → run the skill → settle only on success. A skill failure never
    # charges the buyer; data is returned only after settlement succeeds.
    try:
        verified = await x402_services.verify_from_headers(signature, header)
    except Exception as exc:
        await release_payment_attempt("a2a", skill, begin.fingerprint)
        return _payment_failed(f"verify_failed: {exc}"[:200])
    if not verified.get("is_valid"):
        await release_payment_attempt("a2a", skill, begin.fingerprint)
        return _payment_failed(verified.get("invalid_reason") or "verification_failed")
    verified["_payment_required"] = header

    skill_input = stored.get("skill_input") or {}
    try:
        deliverable = await invoke_skill(skill, skill_input)
        if isinstance(deliverable, dict) and deliverable.get("success") is False:
            raise RuntimeError(str(deliverable.get("error") or "skill failed"))
    except Exception as exc:
        await release_payment_attempt("a2a", skill, begin.fingerprint)
        logger.warning("a2a skill execution failed before settle: %s", exc)
        msg = _agent_message(
            f"Skill execution failed; payment was not settled: {str(exc)[:160]}",
            {META_STATUS: "payment-failed", META_ERROR: "SKILL_FAILED",
             META_RECEIPTS: list(stored.get("receipts") or [])},
        )
        task = build_task(skill, state="failed", message=msg, task_id=task_id)
        stored.update(task)
        return get_task(task_id) or task

    settled = await x402_services.settle_verified_payment(verified)
    settlement = settled.get("settlement") or {}
    if not settled.get("payment_settled"):
        await release_payment_attempt("a2a", skill, begin.fingerprint)
        return _payment_failed(
            settled.get("settlement_error") or settled.get("invalid_reason") or "settlement_failed",
            "SETTLEMENT_FAILED",
        )
    if not await complete_payment_attempt("a2a", skill, begin.fingerprint, settlement):
        await release_payment_attempt("a2a", skill, begin.fingerprint)
        return _payment_failed("settlement_tx_replay", "DUPLICATE_PAYMENT")

    receipts = list(stored.get("receipts") or []) + [
        _settlement_receipt(settlement, network=network)
    ]
    msg = _agent_message(
        "Payment completed. Skill result attached as artifact.",
        {META_STATUS: "payment-completed", META_RECEIPTS: receipts},
    )
    task = build_task(
        skill,
        state="completed",
        message=msg,
        payload=deliverable,
        task_id=task_id,
    )
    stored.update(task)
    stored["receipts"] = receipts
    return get_task(task_id) or task


async def send_message(params: dict[str, Any]) -> dict[str, Any]:
    message = params.get("message") if isinstance(params, dict) else None
    meta: dict[str, Any] = {}
    message_id = None
    if isinstance(message, dict):
        meta = message.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        message_id = message.get("messageId")

    pay_status = meta.get(META_STATUS)
    task_id = None
    if isinstance(message, dict):
        task_id = message.get("taskId") or message.get("task_id")
    payload_obj = meta.get(META_PAYLOAD)

    if pay_status == "payment-rejected":
        tid = task_id or str(uuid.uuid4())
        msg = _agent_message(
            "Payment requirements rejected by client.",
            {META_STATUS: "payment-rejected"},
            message_id=message_id,
        )
        task = build_task("unknown", state="canceled", message=msg, task_id=tid)
        TASKS[tid] = task
        return task

    if pay_status == "payment-submitted" or payload_obj is not None:
        await _hydrate_task(task_id)
        if not task_id or task_id not in TASKS:
            raise ValueError("task not found for payment submission")
        existing = TASKS[task_id]
        existing_state = (existing.get("status") or {}).get("state")
        # Idempotent: a completed (or canceled/failed) task must not be
        # rewound to input-required by a duplicate payment submission.
        if existing_state in ("completed", "canceled", "failed"):
            return get_task(task_id) or existing
        result = await _continue_paid_task(task_id, payload_obj)
        await _persist_task(task_id)
        return result

    skill, arguments = _extract_skill_and_params(params)
    skill = skill.strip()

    if skill not in PAID_TOOLS:
        # Unknown or free skills: execute without payment (same as before for free).
        payload = await invoke_skill(skill, arguments)
        if payload.get("success") is False and payload.get("error", "").startswith("Unknown"):
            msg = _agent_message(str(payload.get("error")), {})
            task = build_task(skill, state="failed", message=msg, message_id=message_id)
        else:
            msg = _agent_message("Skill completed.", {}, message_id=message_id)
            task = build_task(
                skill,
                state="completed",
                message=msg,
                payload=payload,
                message_id=message_id,
            )
        TASKS[task["id"]] = task
        return task

    task = await _challenge_task(skill, arguments, message_id)
    await _persist_task(task["id"])
    return task


async def handle_jsonrpc(payload: dict[str, Any]) -> dict[str, Any]:
    method = str(payload.get("method") or "")
    req_id = payload.get("id")
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    normalized = method.replace(".", "/").replace("_", "/").lower()

    if normalized in ("message/send", "tasks/send", "send/message", "sendmessage"):
        try:
            task = await send_message(params)
            return jsonrpc_result(req_id, task)
        except ValueError as exc:
            return jsonrpc_error(req_id, -32602, str(exc))
        except RuntimeError as exc:
            return jsonrpc_error(req_id, -32004, str(exc))
        except Exception as exc:
            logger.warning("a2a send_message failed: %s", exc)
            return jsonrpc_error(req_id, -32000, f"a2a error: {exc}")

    if normalized in ("tasks/get", "get/task", "gettask"):
        task_id = params.get("id") or params.get("taskId") or params.get("task_id")
        if not task_id:
            return jsonrpc_error(req_id, -32602, "tasks/get requires id")
        await _hydrate_task(str(task_id))
        found = get_task(str(task_id))
        if found is None:
            return jsonrpc_error(req_id, -32001, f"Task not found: {task_id}")
        task = found
        return jsonrpc_result(req_id, task)

    return jsonrpc_error(req_id, -32601, f"Method not found: {method}")
