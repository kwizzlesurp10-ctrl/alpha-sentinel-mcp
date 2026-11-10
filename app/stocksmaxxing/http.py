"""HTTP parameter helpers and route handlers for Stocks Maxxing tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, Request

from app.stocksmaxxing import services

Handler = Callable[[Request], Awaitable[dict[str, Any]]]


async def _params(request: Request) -> dict[str, Any]:
    params: dict[str, Any] = {k: v for k, v in request.query_params.multi_items()}
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = None
        if isinstance(body, dict):
            params.update({k: v for k, v in body.items() if v is not None})
    return params


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return [str(value)]


async def http_tokenized_stock_list(request: Request) -> dict[str, Any]:
    p = await _params(request)
    return await services.tokenized_stock_list_endpoint(
        query=p.get("query"),
        page_size=int(p.get("page_size") or 25),
        page_token=p.get("page_token"),
    )


async def http_tokenized_stock_lookup(request: Request) -> dict[str, Any]:
    p = await _params(request)
    symbol = p.get("symbol")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    return await services.tokenized_stock_lookup_endpoint(str(symbol))


async def http_tokenized_stock_nav_deviation(request: Request) -> dict[str, Any]:
    p = await _params(request)
    symbol = p.get("symbol")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    return await services.tokenized_stock_nav_deviation_endpoint(str(symbol))


async def http_tokenized_stock_corporate_action(request: Request) -> dict[str, Any]:
    p = await _params(request)
    action_id = p.get("corporate_action_id")
    if not action_id:
        raise HTTPException(status_code=400, detail="corporate_action_id is required")
    return await services.tokenized_stock_corporate_action_endpoint(str(action_id))


async def http_tokenized_stock_research_brief(request: Request) -> dict[str, Any]:
    p = await _params(request)
    symbols = _as_list(p.get("symbols"))
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols is required")
    return await services.tokenized_stock_research_brief_endpoint(symbols)


async def http_tokenized_stock_seal_receipt(request: Request) -> dict[str, Any]:
    p = await _params(request)
    content_hash = p.get("content_hash")
    if not content_hash:
        raise HTTPException(status_code=400, detail="content_hash is required")
    return await services.tokenized_stock_seal_receipt_endpoint(
        content_hash=str(content_hash),
        brief_id=p.get("brief_id"),
    )


async def http_tokenized_stock_peg_gap_radar(request: Request) -> dict[str, Any]:
    p = await _params(request)
    symbols = _as_list(p.get("symbols")) or None
    return await services.tokenized_stock_peg_gap_radar_endpoint(
        alert_threshold_pct=float(p.get("alert_threshold_pct") or 2.0),
        page_size=int(p.get("page_size") or 40),
        symbols=symbols,
    )


async def http_tokenized_stock_model_portfolio(request: Request) -> dict[str, Any]:
    p = await _params(request)
    symbols = _as_list(p.get("symbols"))
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols is required")
    weights = p.get("current_weights")
    if weights is not None and not isinstance(weights, dict):
        raise HTTPException(status_code=400, detail="current_weights must be an object")
    objective = str(p.get("objective") or "balanced")
    return await services.tokenized_stock_model_portfolio_endpoint(
        symbols,
        current_weights=weights,
        objective=objective,
    )


STOCKSMAXXING_HTTP_HANDLERS: dict[str, Handler] = {
    "tokenized_stock_list": http_tokenized_stock_list,
    "tokenized_stock_lookup": http_tokenized_stock_lookup,
    "tokenized_stock_nav_deviation": http_tokenized_stock_nav_deviation,
    "tokenized_stock_corporate_action": http_tokenized_stock_corporate_action,
    "tokenized_stock_research_brief": http_tokenized_stock_research_brief,
    "tokenized_stock_seal_receipt": http_tokenized_stock_seal_receipt,
    "tokenized_stock_peg_gap_radar": http_tokenized_stock_peg_gap_radar,
    "tokenized_stock_model_portfolio": http_tokenized_stock_model_portfolio,
}
