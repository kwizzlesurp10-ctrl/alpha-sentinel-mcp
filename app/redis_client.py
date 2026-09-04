"""Upstash Redis REST client (Vercel Marketplace KV_* env vars).

Serverless-safe: no persistent TCP connection. Buyer keys never live here.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings


def configured() -> bool:
    return bool(settings.kv_rest_api_url and settings.kv_rest_api_token)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.kv_rest_api_token}"}


def _base() -> str:
    return (settings.kv_rest_api_url or "").rstrip("/")


async def command(*parts: Any) -> Any:
    """Run one Upstash REST command. Returns decoded JSON result or None."""
    if not configured():
        return None
    path = "/".join(quote(str(p), safe="") for p in parts)
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(f"{_base()}/{path}", headers=_headers())
        response.raise_for_status()
        payload = response.json()
    if isinstance(payload, dict) and "result" in payload:
        return payload["result"]
    return payload


async def ping() -> dict[str, Any]:
    if not configured():
        return {"enabled": False, "reason": "KV_REST_API_URL/TOKEN not set"}
    try:
        result = await command("PING")
        ok = str(result).upper() == "PONG" or result is True
        return {
            "enabled": True,
            "ok": ok,
            "provider": "upstash",
            "result": "PONG" if ok else result,
        }
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "ok": False, "error": str(exc)[:160]}
