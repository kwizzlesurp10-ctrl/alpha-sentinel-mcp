"""Bazaar discovery backfill + indexing status (CDP facilitator).

CDP catalogs a resource only when the settled PaymentPayload carries
``resource`` (absolute URL) and the echoed ``extensions.bazaar``. Many buyers
omit both. Before settle we force the payload to carry exactly what this
service advertised in its own PAYMENT-REQUIRED (set when missing, replace when
foreign or altered). After settle we read the EXTENSION-RESPONSES / body
``extensions.bazaar`` status and log one line per payment.

Docs: https://docs.cdp.coinbase.com/x402/bazaar
      https://docs.x402.org/extensions/bazaar
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

logger = logging.getLogger("x402")

BAZAAR_KEY = "bazaar"


def _is_obj(v: Any) -> bool:
    return isinstance(v, dict)


def _stable_json(v: Any) -> str:
    def _norm(x: Any) -> Any:
        if isinstance(x, dict):
            return {k: _norm(x[k]) for k in sorted(x)}
        if isinstance(x, list):
            return [_norm(i) for i in x]
        return x

    return json.dumps(_norm(v), separators=(",", ":"), default=str)


def _model_dump(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(by_alias=True, exclude_none=True)
    if _is_obj(obj):
        return obj
    return obj


def backfill_discovery(
    payload: Any,
    *,
    advertised_resource: dict[str, Any] | None,
    advertised_bazaar: Any,
) -> dict[str, bool]:
    """Force payload.resource / extensions.bazaar to our advertised values.

    Mutates *payload* in place when it is a pydantic model or dict. Returns
    ``{resource, bazaar}`` booleans indicating whether we set/replaced each.
    """
    out = {"resource": False, "bazaar": False}
    if advertised_resource is None:
        return out
    url = advertised_resource.get("url") or ""
    if not isinstance(url, str) or not url.startswith(("http://", "https://", "mcp://")):
        return out

    canonical_resource = {"url": url}
    for k in ("description", "mimeType", "serviceName", "tags"):
        if advertised_resource.get(k) is not None:
            canonical_resource[k] = advertised_resource[k]

    current_resource = _model_dump(getattr(payload, "resource", None) if not _is_obj(payload) else payload.get("resource"))
    if _stable_json(current_resource) != _stable_json(canonical_resource):
        if _is_obj(payload):
            payload["resource"] = dict(canonical_resource)
        else:
            try:
                from x402.schemas import ResourceInfo

                payload.resource = ResourceInfo.model_validate(canonical_resource)
            except Exception:
                payload.resource = canonical_resource  # type: ignore[attr-defined]
        out["resource"] = True

    if advertised_bazaar is None:
        return out

    if _is_obj(payload):
        exts = payload.get("extensions") if _is_obj(payload.get("extensions")) else {}
        current_bazaar = exts.get(BAZAAR_KEY) if _is_obj(exts) else None
    else:
        exts_obj = getattr(payload, "extensions", None)
        exts = _model_dump(exts_obj) if exts_obj is not None else {}
        if not _is_obj(exts):
            exts = {}
        current_bazaar = exts.get(BAZAAR_KEY)

    if _stable_json(current_bazaar) != _stable_json(advertised_bazaar):
        new_exts = {**exts, BAZAAR_KEY: json.loads(json.dumps(advertised_bazaar))}
        if _is_obj(payload):
            payload["extensions"] = new_exts
        else:
            payload.extensions = new_exts  # type: ignore[attr-defined]
        out["bazaar"] = True

    return out


def decode_extension_responses(header: str | None) -> dict[str, Any] | None:
    if not header:
        return None
    try:
        raw = header.strip()
        text = raw if raw.startswith("{") else base64.b64decode(raw).decode()
        parsed = json.loads(text)
        return parsed if _is_obj(parsed) else None
    except Exception:
        return None


def bazaar_indexing_status(
    *,
    extension_responses_header: str | None = None,
    settle_body: Any = None,
    extension_responses: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return {status, rejectedReason?, source} for Bazaar indexing outcome."""

    def _pick(v: Any, source: str) -> dict[str, Any] | None:
        if not _is_obj(v) or not isinstance(v.get("status"), str):
            return None
        out: dict[str, Any] = {"status": v["status"], "source": source}
        reason = v.get("rejectedReason") or v.get("reason")
        if isinstance(reason, str) and reason:
            out["rejectedReason"] = reason[:500]
        return out

    if extension_responses and BAZAAR_KEY in extension_responses:
        got = _pick(extension_responses.get(BAZAAR_KEY), "extension-responses")
        if got:
            return got

    decoded = decode_extension_responses(extension_responses_header)
    if decoded:
        got = _pick(decoded.get(BAZAAR_KEY), "extension-responses-header")
        if got:
            return got

    body = settle_body if _is_obj(settle_body) else _model_dump(settle_body)
    if _is_obj(body):
        exts = body.get("extensions") if _is_obj(body.get("extensions")) else None
        if _is_obj(exts):
            got = _pick(exts.get(BAZAAR_KEY), "settle-body")
            if got:
                return got
        # SDK may attach extension_responses on the settle result object
        er = body.get("extension_responses")
        if _is_obj(er):
            got = _pick(er.get(BAZAAR_KEY), "extension-responses")
            if got:
                return got

    return {"status": "not_reported", "source": "none"}


def log_bazaar_indexing(entry: dict[str, Any]) -> None:
    logger.info("[x402] bazaar_indexing %s", json.dumps(entry, default=str))


def mcp_tool_resource_url(public_base_url: str, tool_name: str) -> str:
    """Per-tool absolute resource URL so CDP does not collapse all MCP tools onto /mcp."""
    base = public_base_url.rstrip("/")
    return f"{base}/tools/{tool_name}"
