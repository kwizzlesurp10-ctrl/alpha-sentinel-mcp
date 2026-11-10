"""Peg-Gap Radar: onchain DEX price vs underlying reference (research alerts only)."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.stocksmaxxing.coinbase_client import (
    CoinbaseTokenizedStocksClient,
    parse_nav_staleness,
)
from app.stocksmaxxing.onchain_price import fetch_onchain_price_usd
from app.stocksmaxxing.result import Err, Ok
from app.stocksmaxxing.underlying_equity import fetch_underlying_for_tokenized_symbol


async def build_peg_gap_rows(
    *,
    alert_threshold_pct: float,
    page_size: int = 40,
    symbols: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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

    rows: list[dict[str, Any]] = []
    for rec in tokens:
        symbol = str(rec.get("symbol") or "")
        contract = rec.get("contract_address")
        if not symbol or not contract:
            continue

        reference_price: float | None = None
        reference_kind = "underlying_spot"
        nav = rec.get("nav_price")
        underlying = await fetch_underlying_for_tokenized_symbol(symbol)
        if isinstance(underlying, Ok):
            reference_price = float(underlying.value["price_usd"])
        elif nav is not None:
            reference_price = float(nav)
            reference_kind = "nav_price"

        onchain = await fetch_onchain_price_usd(str(contract))
        onchain_price = float(onchain.value["price_usd"]) if isinstance(onchain, Ok) else None

        gap_pct: float | None = None
        if reference_price and onchain_price and reference_price > 0:
            gap_pct = round(((onchain_price - reference_price) / reference_price) * 100.0, 4)

        alert = gap_pct is not None and abs(gap_pct) >= alert_threshold_pct
        staleness = parse_nav_staleness(
            rec.get("nav_price_updated_at"),
            max_age_hours=settings.tokenized_stock_nav_max_age_hours,
        )

        row: dict[str, Any] = {
            "symbol": symbol,
            "contract_address": contract,
            "onchain_price_usd": onchain_price,
            "onchain_price_source": onchain.value.get("provider") if isinstance(onchain, Ok) else None,
            "onchain_price_error": onchain.message if isinstance(onchain, Err) else None,
            "reference_price_usd": reference_price,
            "reference_kind": reference_kind,
            "nav_price_usd": nav,
            "gap_pct": gap_pct,
            "alert_threshold_pct": alert_threshold_pct,
            "peg_gap_alert": alert,
            "nav_staleness": staleness if nav is not None else None,
        }
        rows.append(row)

    rows.sort(key=lambda r: (not r.get("peg_gap_alert"), -(abs(r["gap_pct"]) if r.get("gap_pct") is not None else -1)))

    meta = {
        "alert_threshold_pct": alert_threshold_pct,
        "row_count": len(rows),
        "alerts_triggered": sum(1 for r in rows if r.get("peg_gap_alert")),
        "onchain_price_provider": settings.onchain_price_provider,
        "underlying_provider": settings.underlying_equity_price_provider,
        "interpretation": (
            "gap_pct = (onchain DEX price − reference) / reference. Alerts are research signals only, "
            "not trade instructions."
        ),
        "chart_ready": True,
    }
    return rows, meta
