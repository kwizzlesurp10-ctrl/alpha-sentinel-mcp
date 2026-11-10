"""Onchain DEX-derived token prices on Base (research context only)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.stocksmaxxing.result import Err, Ok, Result

logger = logging.getLogger(__name__)


async def fetch_onchain_price_usd(contract_address: str) -> Result[dict[str, Any]]:
    provider = (settings.onchain_price_provider or "geckoterminal").lower().strip()
    if provider != "geckoterminal":
        return Err(
            code="unknown_onchain_price_provider",
            message=f"Unsupported ONCHAIN_PRICE_PROVIDER: {provider}",
            hint="Use geckoterminal (default, no API key)",
        )
    addr = contract_address.lower()
    url = f"https://api.geckoterminal.com/api/v2/networks/base/tokens/{addr}"
    headers = {"Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=settings.x402_http_timeout, headers=headers) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return Err(
                    code="onchain_price_unavailable",
                    message=f"No GeckoTerminal market data for {contract_address} on Base",
                )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        logger.warning("GeckoTerminal error for %s: %s", contract_address, exc)
        return Err(code="onchain_price_unreachable", message=str(exc))

    try:
        attrs = payload["data"]["attributes"]
        price_raw = attrs.get("price_usd")
        if price_raw is None:
            return Err(
                code="onchain_price_missing",
                message="GeckoTerminal returned no price_usd for this token",
            )
        price = float(price_raw)
        if price <= 0:
            return Err(code="onchain_price_invalid", message="Non-positive onchain price_usd")
    except (KeyError, TypeError, ValueError) as exc:
        return Err(code="onchain_price_parse_error", message=str(exc))

    return Ok(
        {
            "provider": "geckoterminal",
            "network": "base",
            "contract_address": contract_address,
            "price_usd": price,
            "volume_usd_h24": (attrs.get("volume_usd") or {}).get("h24"),
            "as_of_hint": "GeckoTerminal aggregated DEX price on Base — not an executable quote",
        }
    )
