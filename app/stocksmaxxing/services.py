"""Stocks Maxxing tool implementations (research-only)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.stocksmaxxing.coinbase_client import (
    CoinbaseTokenizedStocksClient,
    parse_nav_staleness,
    underlying_equity_ticker,
)
from app.stocksmaxxing.disclaimer import with_disclaimer
from app.stocksmaxxing.peg_gap import build_peg_gap_rows
from app.stocksmaxxing.research_receipt import build_proof_of_research_receipt
from app.stocksmaxxing.result import Err, Ok
from app.stocksmaxxing.seal_registry import seal_receipt_on_base
from app.stocksmaxxing.track_record import enqueue_receipt_for_track_record
from app.stocksmaxxing.underlying_equity import fetch_underlying_for_tokenized_symbol


def _err_payload(err: Err) -> dict[str, Any]:
    body: dict[str, Any] = {"success": False, "error": err.message, "code": err.code}
    if err.hint:
        body["hint"] = err.hint
    return with_disclaimer(body)


def _ok_payload(data: dict[str, Any]) -> dict[str, Any]:
    return with_disclaimer({"success": True, "data": data, "generated_at": datetime.now(UTC).isoformat()})


async def tokenized_stock_list_endpoint(
    *,
    query: str | None = None,
    page_size: int = 25,
    page_token: str | None = None,
) -> dict[str, Any]:
    client = CoinbaseTokenizedStocksClient()
    page_size = max(1, min(page_size, 100))
    result = await client.list_tokens(page_size=page_size, page_token=page_token)
    if isinstance(result, Err):
        return _err_payload(result)
    tokens = list(result.value.get("tokens") or [])
    if query:
        q = query.strip().lower()
        tokens = [
            t
            for t in tokens
            if q in str(t.get("symbol", "")).lower()
            or q in str(t.get("name", "")).lower()
            or q in str(t.get("isin", "")).lower()
        ]
    return _ok_payload(
        {
            "tokens": tokens,
            "count": len(tokens),
            "next_page_token": result.value.get("next_page_token"),
            "source": "coinbase_tokenized_stocks_api",
            "base_chain_id": 8453,
        }
    )


async def tokenized_stock_lookup_endpoint(symbol: str) -> dict[str, Any]:
    client = CoinbaseTokenizedStocksClient()
    token = await client.find_token(symbol)
    if isinstance(token, Err):
        return _err_payload(token)
    meta = await client.get_metadata(symbol)
    chains = await client.get_chains()
    data: dict[str, Any] = {
        "catalog_record": token.value,
        "metadata": meta.value if isinstance(meta, Ok) else None,
        "chains": chains.value if isinstance(chains, Ok) else None,
        "underlying_ticker_guess": underlying_equity_ticker(symbol),
        "prospectus_url": f"{settings.tokenized_stocks_api_base_url.rstrip('/')}/prospectus/{symbol.strip()}.pdf",
    }
    return _ok_payload(data)


async def tokenized_stock_nav_deviation_endpoint(symbol: str) -> dict[str, Any]:
    client = CoinbaseTokenizedStocksClient()
    token = await client.find_token(symbol)
    if isinstance(token, Err):
        return _err_payload(token)
    record = token.value
    nav_price = record.get("nav_price")
    if nav_price is None:
        return _err_payload(
            Err(
                code="nav_unavailable",
                message=f"No nav_price published for {symbol}",
                hint="NAV is not present for every token; try another symbol such as CRCLc",
            )
        )
    staleness = parse_nav_staleness(
        record.get("nav_price_updated_at"),
        max_age_hours=settings.tokenized_stock_nav_max_age_hours,
    )
    underlying = await fetch_underlying_for_tokenized_symbol(symbol)
    if isinstance(underlying, Err):
        return _err_payload(underlying)
    u_price = float(underlying.value["price_usd"])
    nav_f = float(nav_price)
    deviation_pct = ((nav_f - u_price) / u_price) * 100.0 if u_price else None
    return _ok_payload(
        {
            "symbol": record.get("symbol"),
            "nav_price_usd": nav_f,
            "underlying_price_usd": u_price,
            "deviation_pct": round(deviation_pct, 4) if deviation_pct is not None else None,
            "multiplier": record.get("multiplier"),
            "staleness": staleness,
            "underlying_quote": underlying.value,
            "interpretation": (
                "Positive deviation_pct means NAV/reference is above the underlying spot "
                "quote from the configured provider — not an executable spread."
            ),
        }
    )


async def tokenized_stock_corporate_action_endpoint(corporate_action_id: str) -> dict[str, Any]:
    client = CoinbaseTokenizedStocksClient()
    result = await client.get_corporate_action(corporate_action_id)
    if isinstance(result, Err):
        return _err_payload(result)
    return _ok_payload(
        {
            "corporate_action": result.value,
            "source": "coinbase_tokenized_stocks_api",
            "note": (
                "Corporate actions are fetched by UUID from onchain Announcement URIs; "
                "this tool does not scan chain events."
            ),
        }
    )


async def tokenized_stock_research_brief_endpoint(symbols: list[str]) -> dict[str, Any]:
    if not symbols:
        return _err_payload(Err(code="invalid_input", message="symbols must be a non-empty list"))
    client = CoinbaseTokenizedStocksClient()
    sections: list[dict[str, Any]] = []
    for sym in symbols[:10]:
        token = await client.find_token(sym)
        if isinstance(token, Err):
            sections.append({"symbol": sym, "error": token.message})
            continue
        rec = token.value
        nav = rec.get("nav_price")
        staleness = parse_nav_staleness(
            rec.get("nav_price_updated_at"),
            max_age_hours=settings.tokenized_stock_nav_max_age_hours,
        )
        deviation_note = None
        if nav is not None:
            und = await fetch_underlying_for_tokenized_symbol(sym)
            if isinstance(und, Ok):
                u = float(und.value["price_usd"])
                deviation_note = round(((float(nav) - u) / u) * 100.0, 4)
        desc = str(rec.get("description") or "")
        summary = desc.split("\n\n")[0][:480] if desc else rec.get("name")
        sections.append(
            {
                "symbol": rec.get("symbol"),
                "name": rec.get("name"),
                "contract_address": rec.get("contract_address"),
                "multiplier": rec.get("multiplier"),
                "nav_price_usd": nav,
                "nav_staleness": staleness,
                "nav_vs_underlying_deviation_pct": deviation_note,
                "summary": summary,
                "isin": rec.get("isin"),
            }
        )
    data_sources = [
        "https://api.coinbase.com/v1/tokenized-stocks",
        settings.underlying_equity_price_provider,
    ]
    generated_at = datetime.now(UTC).isoformat()
    receipt = build_proof_of_research_receipt(
        symbols=symbols[:10],
        sections=sections,
        data_sources=data_sources,
        generated_at=generated_at,
    )
    enqueue_receipt_for_track_record(receipt)
    return _ok_payload(
        {
            "sections": sections,
            "brief_type": "tokenized_stock_research",
            "data_sources": data_sources,
            "proof_of_research_receipt": receipt,
        }
    )


async def tokenized_stock_seal_receipt_endpoint(
    *,
    content_hash: str,
    brief_id: str | None = None,
) -> dict[str, Any]:
    content_hash = content_hash.strip()
    if not content_hash.startswith("0x") or len(content_hash) != 66:
        return _err_payload(
            Err(code="invalid_content_hash", message="content_hash must be 0x-prefixed 32-byte hex")
        )
    try:
        seal = await seal_receipt_on_base(content_hash=content_hash, brief_id=brief_id)
    except ValueError as exc:
        return _err_payload(Err(code="seal_config_error", message=str(exc)))
    return _ok_payload(
        {
            "seal": seal,
            "attestation_type": "research_receipt_registry",
            "contract_source": "app/stocksmaxxing/contracts/ResearchReceiptRegistry.sol",
        }
    )


async def tokenized_stock_peg_gap_radar_endpoint(
    *,
    alert_threshold_pct: float = 2.0,
    page_size: int = 40,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    try:
        rows, meta = await build_peg_gap_rows(
            alert_threshold_pct=alert_threshold_pct,
            page_size=page_size,
            symbols=symbols,
        )
    except ValueError as exc:
        return _err_payload(Err(code="peg_gap_error", message=str(exc)))
    return _ok_payload({"rows": rows, "meta": meta, "dashboard_url": "/stocksmaxxing/peg-gap"})


async def peg_gap_public_preview(
    *,
    alert_threshold_pct: float = 2.0,
    page_size: int = 25,
) -> dict[str, Any]:
    """Unpaid radar slice for the dashboard (same data rules as paid tool)."""
    try:
        rows, meta = await build_peg_gap_rows(
            alert_threshold_pct=alert_threshold_pct,
            page_size=min(page_size, 40),
            symbols=None,
        )
    except ValueError as exc:
        return with_disclaimer({"success": False, "error": str(exc), "code": "peg_gap_error"})
    return with_disclaimer({"success": True, "rows": rows, "meta": meta, "demo": False})


async def tokenized_stock_model_portfolio_endpoint(
    symbols: list[str],
    current_weights: dict[str, float] | None = None,
    objective: str = "balanced",
) -> dict[str, Any]:
    if not symbols:
        return _err_payload(Err(code="invalid_input", message="symbols must be a non-empty list"))
    if len(symbols) > 12:
        return _err_payload(Err(code="invalid_input", message="At most 12 symbols per portfolio suggestion"))

    client = CoinbaseTokenizedStocksClient()
    scores: list[tuple[str, float, dict[str, Any]]] = []
    for sym in symbols:
        token = await client.find_token(sym)
        if isinstance(token, Err):
            scores.append((sym, 0.0, {"error": token.message}))
            continue
        rec = token.value
        staleness = parse_nav_staleness(
            rec.get("nav_price_updated_at"),
            max_age_hours=settings.tokenized_stock_nav_max_age_hours,
        )
        freshness = 1.0 if not staleness.get("stale") else 0.35
        nav = rec.get("nav_price")
        stability = 1.0 if rec.get("multiplier") == 1 else 0.7
        nav_bonus = 0.2 if nav is not None else 0.0
        if objective == "low_staleness_nav":
            weight_score = freshness * 2 + nav_bonus
        elif objective == "diversified":
            weight_score = 1.0
        else:
            weight_score = freshness * stability + nav_bonus
        scores.append((str(rec.get("symbol") or sym), weight_score, {"catalog": rec, "staleness": staleness}))

    positive = [(s, w, m) for s, w, m in scores if w > 0]
    if not positive:
        return _err_payload(Err(code="no_eligible_symbols", message="No valid symbols for portfolio suggestion"))
    total = sum(w for _, w, _ in positive)
    suggested = {s: round(w / total, 4) for s, w, _ in positive}

    rebalance_actions: list[dict[str, Any]] = []
    if current_weights:
        for sym, target in suggested.items():
            cur = float(current_weights.get(sym, 0.0))
            delta = round(target - cur, 4)
            if abs(delta) >= 0.01:
                rebalance_actions.append(
                    {
                        "symbol": sym,
                        "current_weight": cur,
                        "suggested_weight": target,
                        "delta": delta,
                        "action_hint": "research_only_adjustment_not_execution",
                    }
                )

    return _ok_payload(
        {
            "objective": objective,
            "suggested_weights": suggested,
            "rebalance_suggestions": rebalance_actions,
            "rationale": (
                "Weights are heuristic scores from NAV freshness, multiplier stability, and "
                "catalog availability — not optimized returns and not trade instructions."
            ),
            "symbols_analyzed": [s for s, _, _ in scores],
        }
    )
