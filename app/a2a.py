"""A2A JSON-RPC Send Message + Get Task over the live intelligence handlers.

Skills map 1:1 onto TOOL_SPECS. Tasks are stored in-process so Get Task by id
returns the same work item produced by Send Message.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.tools_registry import EXPECTED_TOOL_NAMES, get_tool_spec

logger = logging.getLogger(__name__)

# In-memory task store (A2A streaming / eight-state machine is out of scope).
TASKS: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def build_task(skill: str, payload: dict[str, Any], message_id: str | None = None) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    context_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "contextId": context_id,
        "kind": "task",
        "status": {"state": "completed", "timestamp": _now()},
        "metadata": {"skill": skill, "skillId": skill},
        "artifacts": [
            {
                "artifactId": artifact_id,
                "name": skill,
                "parts": [
                    {"kind": "data", "data": payload},
                    {"kind": "text", "text": json.dumps(payload)},
                ],
            }
        ],
        "history": [
            {
                "role": "agent",
                "kind": "message",
                "messageId": message_id or str(uuid.uuid4()),
                "parts": [{"kind": "data", "data": payload}],
            }
        ],
    }
    TASKS[task_id] = task
    return task


def get_task(task_id: str) -> dict[str, Any] | None:
    return TASKS.get(task_id)


async def send_message(params: dict[str, Any]) -> dict[str, Any]:
    skill, arguments = _extract_skill_and_params(params)
    payload = await invoke_skill(skill, arguments)
    message = params.get("message") if isinstance(params, dict) else None
    message_id = None
    if isinstance(message, dict):
        message_id = message.get("messageId")
    return build_task(skill, payload, message_id=message_id)


def jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def handle_jsonrpc(payload: dict[str, Any]) -> dict[str, Any]:
    method = str(payload.get("method") or "")
    req_id = payload.get("id")
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    normalized = method.replace(".", "/").replace("_", "/").lower()

    if normalized in ("message/send", "tasks/send", "send/message", "sendmessage"):
        task = await send_message(params)
        return jsonrpc_result(req_id, task)

    if normalized in ("tasks/get", "get/task", "gettask"):
        task_id = params.get("id") or params.get("taskId") or params.get("task_id")
        if not task_id:
            return jsonrpc_error(req_id, -32602, "tasks/get requires id")
        task = get_task(str(task_id))
        if task is None:
            return jsonrpc_error(req_id, -32001, f"Task not found: {task_id}")
        return jsonrpc_result(req_id, task)

    return jsonrpc_error(req_id, -32601, f"Method not found: {method}")
