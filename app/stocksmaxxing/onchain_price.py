"""Onchain DEX-derived token prices on Base (research context only)."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.stocksmaxxing.onchain_price_resolver import resolve_onchain_price_usd
from app.stocksmaxxing.result import Err, Result

logger = logging.getLogger(__name__)


async def fetch_onchain_price_usd(
    contract_address: str,
    *,
    symbol: str | None = None,
) -> Result[dict[str, Any]]:
    """Resolve USD onchain price via GeckoTerminal → pools → DexScreener → optional RPC."""
    provider = (settings.onchain_price_provider or "geckoterminal").lower().strip()
    if provider not in {"geckoterminal", "multi", "fallback"}:
        return Err(
            code="unknown_onchain_price_provider",
            message=f"Unsupported ONCHAIN_PRICE_PROVIDER: {provider}",
            hint="Use geckoterminal (default) or multi for the peg-gap fallback chain",
        )
    return await resolve_onchain_price_usd(contract_address, symbol=symbol)
