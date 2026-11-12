"""Peg-Gap Radar: onchain DEX price vs underlying reference (research alerts only)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.config import settings
from app.stocksmaxxing.coinbase_client import (
    CoinbaseTokenizedStocksClient,
    parse_nav_staleness,
)
from app.stocksmaxxing.onchain_price import fetch_onchain_price_usd
from app.stocksmaxxing.result import Err, Ok
from app.stocksmaxxing.underlying_equity import fetch_underlying_for_tokenized_symbol


async def _peg_gap_row(
    rec: dict[str, Any],
    *,
    alert_threshold_pct: float,
) -> dict[str, Any] | None:
    symbol = str(rec.get("symbol") or "")
    contract = rec.get("contract_address")
    if not symbol or not contract:
        return None

    onchain_task = asyncio.create_task(fetch_onchain_price_usd(str(contract), symbol=symbol))
    underlying_task = asyncio.create_task(fetch_underlying_for_tokenized_symbol(symbol))
    onchain, underlying = await asyncio.gather(onchain_task, underlying_task)

    reference_price: float | None = None
    reference_kind = "underlying_spot"
    nav = rec.get("nav_price")
    if isinstance(underlying, Ok):
        reference_price = float(underlying.value["price_usd"])
    elif nav is not None:
        reference_price = float(nav)
        reference_kind = "nav_price"

    onchain_price = float(onchain.value["price_usd"]) if isinstance(onchain, Ok) else None
    onchain_meta = onchain.value if isinstance(onchain, Ok) else None

    gap_pct: float | None = None
    if reference_price and onchain_price and reference_price > 0:
        gap_pct = round(((onchain_price - reference_price) / reference_price) * 100.0, 4)

    alert = gap_pct is not None and abs(gap_pct) >= alert_threshold_pct
    staleness = parse_nav_staleness(
        rec.get("nav_price_updated_at"),
        max_age_hours=settings.tokenized_stock_nav_max_age_hours,
    )

    market_status = "priced" if onchain_meta else "no_onchain_market"
    return {
        "symbol": symbol,
        "contract_address": contract,
        "onchain_price_usd": onchain_price,
        "onchain_price_source": onchain_meta.get("provider") if onchain_meta else None,
        "onchain_pool_address": onchain_meta.get("pool_address") if onchain_meta else None,
        "onchain_liquidity_usd": onchain_meta.get("liquidity_usd") if onchain_meta else None,
        "onchain_volume_24h_usd": onchain_meta.get("volume_24h_usd") if onchain_meta else None,
        "onchain_priced_at": onchain_meta.get("priced_at") if onchain_meta else None,
        "onchain_pair_label": onchain_meta.get("pair_label") if onchain_meta else None,
        "onchain_quote_symbol": onchain_meta.get("quote_symbol") if onchain_meta else None,
        "onchain_market_status": market_status,
        "onchain_price_error": onchain.message if isinstance(onchain, Err) else None,
        "onchain_price_error_code": onchain.code if isinstance(onchain, Err) else None,
        "reference_price_usd": reference_price,
        "reference_kind": reference_kind,
        "nav_price_usd": nav,
        "gap_pct": gap_pct,
        "alert_threshold_pct": alert_threshold_pct,
        "peg_gap_alert": alert,
        "nav_staleness": staleness if nav is not None else None,
    }


async def build_peg_gap_rows(
    *,
    alert_threshold_pct: float,
    page_size: int = 40,
    symbols: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    client = CoinbaseTokenizedStocksClient()
    page_size = max(1, min(page_size, 100))
    tokens: list[dict[str, Any]] = []

    if symbols:
        for sym in symbols[:page_size]:
            found = await client.find_token(sym)
            if isinstance(found, Ok):
                tokens.append(found.value)
    else:
        listed = await client.list_tokens(page_size=page_size)
        if isinstance(listed, Err):
            raise ValueError(listed.message)
        tokens = list(listed.value.get("tokens") or [])

    parallelism = max(1, int(settings.peg_gap_onchain_parallelism))
    sem = asyncio.Semaphore(parallelism)
    delay = float(settings.peg_gap_onchain_request_delay_seconds)

    async def _limited_row(rec: dict[str, Any]) -> dict[str, Any] | None:
        async with sem:
            if delay > 0:
                await asyncio.sleep(delay)
            return await _peg_gap_row(rec, alert_threshold_pct=alert_threshold_pct)

    built = await asyncio.gather(*(_limited_row(rec) for rec in tokens))
    rows = [r for r in built if r is not None]

    rows.sort(key=lambda r: (not r.get("peg_gap_alert"), -(abs(r["gap_pct"]) if r.get("gap_pct") is not None else -1)))

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    meta = {
        "alert_threshold_pct": alert_threshold_pct,
        "row_count": len(rows),
        "alerts_triggered": sum(1 for r in rows if r.get("peg_gap_alert")),
        "onchain_priced_count": sum(1 for r in rows if r.get("onchain_market_status") == "priced"),
        "onchain_price_provider": settings.onchain_price_provider,
        "onchain_liquidity_floor_usd": settings.peg_gap_min_pool_liquidity_usd,
        "onchain_cache_ttl_seconds": settings.peg_gap_onchain_cache_ttl_seconds,
        "onchain_parallelism": parallelism,
        "build_time_ms": elapsed_ms,
        "underlying_provider": settings.underlying_equity_price_provider,
        "interpretation": (
            "gap_pct = (onchain DEX price − reference) / reference. Onchain prices use GeckoTerminal "
            "(token + pools), DexScreener, and optional Base RPC pool reads — real liquidity only. "
            "Alerts are research signals only, not trade instructions."
        ),
        "chart_ready": True,
    }
    return rows, meta
