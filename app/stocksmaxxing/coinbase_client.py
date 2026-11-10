"""Read-only Coinbase Tokenized Stocks API client (no API key required)."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings
from app.stocksmaxxing.result import Err, Ok, Result

logger = logging.getLogger(__name__)

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def normalize_tokenized_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def underlying_equity_ticker(tokenized_symbol: str) -> str:
    """Map Coinbase token ticker (e.g. CRCLc) to a conventional equity ticker."""
    sym = tokenized_symbol.strip()
    if sym.endswith("c") and len(sym) > 1:
        return sym[:-1].upper()
    return sym.upper()


class CoinbaseTokenizedStocksClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self._base = (base_url or settings.tokenized_stocks_api_base_url).rstrip("/")
        self._timeout = timeout or settings.x402_http_timeout

    async def list_tokens(
        self,
        *,
        page_size: int = 100,
        page_token: str | None = None,
        symbol_filter: str | None = None,
    ) -> Result[dict[str, Any]]:
        params: dict[str, Any] = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        if symbol_filter:
            params["symbol"] = normalize_tokenized_symbol(symbol_filter)
        return await self._get_json("", params)

    async def get_metadata(self, symbol: str) -> Result[dict[str, Any]]:
        sym = normalize_tokenized_symbol(symbol)
        return await self._get_json(f"/metadata/{sym}")

    async def get_corporate_action(self, action_id: str) -> Result[dict[str, Any]]:
        action_id = action_id.strip()
        if not UUID_RE.match(action_id):
            return Err(
                code="invalid_corporate_action_id",
                message="corporate_action_id must be a UUID from an onchain Announcement URI",
            )
        return await self._get_json(f"/corporate-actions/{action_id}")

    async def list_prospectuses(self) -> Result[dict[str, Any]]:
        return await self._get_json("/prospectuses")

    async def get_chains(self) -> Result[dict[str, Any]]:
        return await self._get_json("/chains")

    async def find_token(self, symbol: str) -> Result[dict[str, Any]]:
        sym = normalize_tokenized_symbol(symbol)
        listed = await self.list_tokens(page_size=500, symbol_filter=sym)
        if isinstance(listed, Err):
            return listed
        tokens = listed.value.get("tokens") or []
        for token in tokens:
            if str(token.get("symbol", "")).upper() == sym:
                return Ok(token)
        meta = await self.get_metadata(sym)
        if isinstance(meta, Err):
            return Err(
                code="token_not_found",
                message=f"Tokenized stock '{sym}' not found in Coinbase catalog",
                hint="Use tokenized_stock_list to browse available symbols",
            )
        return Ok(meta)

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Result[dict[str, Any]]:
        url = f"{self._base}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.warning("tokenized stocks HTTP error %s: %s", url, exc)
            return Err(
                code="upstream_unreachable",
                message=f"Coinbase Tokenized Stocks API unreachable: {exc!s}",
            )
        if response.status_code == 404:
            body = _safe_json(response)
            msg = str(body.get("message") or "not found")
            return Err(code="not_found", message=msg)
        if response.status_code >= 400:
            body = _safe_json(response)
            return Err(
                code="upstream_error",
                message=str(body.get("message") or f"HTTP {response.status_code}"),
            )
        try:
            return Ok(response.json())
        except ValueError as exc:
            return Err(code="invalid_json", message=str(exc))


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def parse_nav_staleness(nav_updated_at: str | None, *, max_age_hours: float) -> dict[str, Any]:
    if not nav_updated_at:
        return {"stale": True, "age_hours": None, "reason": "nav_price_updated_at missing"}
    try:
        updated = datetime.fromisoformat(nav_updated_at.replace("Z", "+00:00"))
    except ValueError:
        return {"stale": True, "age_hours": None, "reason": "invalid nav timestamp"}
    age = (datetime.now(UTC) - updated.astimezone(UTC)).total_seconds() / 3600.0
    stale = age > max_age_hours
    return {
        "stale": stale,
        "age_hours": round(age, 3),
        "max_age_hours": max_age_hours,
        "nav_price_updated_at": nav_updated_at,
    }
