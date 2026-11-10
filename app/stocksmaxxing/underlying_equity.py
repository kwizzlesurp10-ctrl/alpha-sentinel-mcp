"""Underlying equity reference prices (research context only — not for execution)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.stocksmaxxing.coinbase_client import underlying_equity_ticker
from app.stocksmaxxing.result import Err, Ok, Result

logger = logging.getLogger(__name__)


async def fetch_underlying_spot_price(equity_ticker: str) -> Result[dict[str, Any]]:
    provider = (settings.underlying_equity_price_provider or "yahoo").lower().strip()
    if provider == "finnhub":
        return await _fetch_finnhub(equity_ticker)
    if provider == "yahoo":
        return await _fetch_yahoo(equity_ticker)
    return Err(
        code="unknown_provider",
        message=f"Unknown UNDERLYING_EQUITY_PRICE_PROVIDER: {provider}",
        hint="Set to 'yahoo' (default, no key) or 'finnhub' (requires FINNHUB_API_KEY)",
    )


async def fetch_underlying_for_tokenized_symbol(tokenized_symbol: str) -> Result[dict[str, Any]]:
    ticker = underlying_equity_ticker(tokenized_symbol)
    spot = await fetch_underlying_spot_price(ticker)
    if isinstance(spot, Err):
        return spot
    data = dict(spot.value)
    data["tokenized_symbol"] = tokenized_symbol.upper()
    data["underlying_ticker"] = ticker
    return Ok(data)


async def _fetch_yahoo(ticker: str) -> Result[dict[str, Any]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}"
    headers = {"User-Agent": "AlphaSentinel-StocksMaxxing/1.0 (research-only)"}
    try:
        async with httpx.AsyncClient(timeout=settings.x402_http_timeout, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Yahoo chart error for %s: %s", ticker, exc)
        return Err(
            code="underlying_price_unavailable",
            message=f"Could not fetch underlying quote for {ticker}",
            hint="Try FINNHUB_API_KEY with UNDERLYING_EQUITY_PRICE_PROVIDER=finnhub",
        )
    try:
        meta = payload["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        return Err(
            code="underlying_parse_error",
            message=f"Unexpected Yahoo response for {ticker}: {exc!s}",
        )
    return Ok(
        {
            "provider": "yahoo_chart",
            "ticker": ticker.upper(),
            "price_usd": price,
            "currency": meta.get("currency", "USD"),
            "exchange": meta.get("exchangeName"),
            "as_of_hint": "regularMarketPrice from Yahoo chart API",
        }
    )


async def _fetch_finnhub(ticker: str) -> Result[dict[str, Any]]:
    key = settings.finnhub_api_key
    if not key:
        return Err(
            code="finnhub_key_required",
            message="FINNHUB_API_KEY is not set",
            hint="Export FINNHUB_API_KEY or use UNDERLYING_EQUITY_PRICE_PROVIDER=yahoo",
        )
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": ticker.upper(), "token": key}
    try:
        async with httpx.AsyncClient(timeout=settings.x402_http_timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        return Err(code="finnhub_unreachable", message=str(exc))
    price = data.get("c")
    if price is None or float(price) <= 0:
        return Err(
            code="finnhub_no_price",
            message=f"Finnhub returned no current price for {ticker}",
        )
    return Ok(
        {
            "provider": "finnhub",
            "ticker": ticker.upper(),
            "price_usd": float(price),
            "currency": "USD",
            "as_of_hint": "Finnhub quote endpoint field 'c'",
        }
    )
