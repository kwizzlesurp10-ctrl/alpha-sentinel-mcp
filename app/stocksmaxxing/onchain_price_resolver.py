"""Fallback chain for Base onchain USDC prices (peg-gap)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.stocksmaxxing.onchain_pool_rpc import rpc_pool_price_usd
from app.stocksmaxxing.onchain_price_cache import (
    get_cached,
    get_negative_cached,
    hydrate_cached_from_kv,
    persist_cached_to_kv,
    set_cached,
    set_negative_cached,
)
from app.stocksmaxxing.onchain_price_sources import (
    PoolQuoteCandidate,
    dexscreener_search_pairs,
    dexscreener_token_pairs,
    geckoterminal_pool_candidates,
    geckoterminal_token_price,
)
from app.stocksmaxxing.result import Err, Ok, Result

logger = logging.getLogger(__name__)


def _cache_key(contract_address: str, symbol: str | None) -> str:
    return f"onchain:{contract_address.lower()}:{(symbol or '').upper()}"


def _min_liquidity_usd() -> float:
    return float(settings.peg_gap_min_pool_liquidity_usd)


def _min_volume_24h_usd() -> float:
    return float(settings.peg_gap_min_pool_volume_24h_usd)


def _passes_liquidity_floor(candidate: PoolQuoteCandidate) -> tuple[bool, str | None]:
    min_liq = _min_liquidity_usd()
    min_vol = _min_volume_24h_usd()
    liq = candidate.liquidity_usd
    vol = candidate.volume_24h_usd

    if candidate.provider == "geckoterminal_token" and liq is None:
        return True, None

    if min_liq > 0 and (liq is None or liq < min_liq):
        return False, f"pool liquidity ${liq or 0:.2f} below floor ${min_liq:.2f}"
    if min_vol > 0 and (vol is None or vol < min_vol):
        return False, f"pool 24h volume ${vol or 0:.2f} below floor ${min_vol:.2f}"
    return True, None


def _candidate_to_payload(
    candidate: PoolQuoteCandidate,
    *,
    contract_address: str,
    attempts: list[str],
) -> dict[str, Any]:
    return {
        "provider": candidate.provider,
        "network": "base",
        "contract_address": contract_address,
        "price_usd": candidate.price_usd,
        "pool_address": candidate.pool_address or None,
        "liquidity_usd": candidate.liquidity_usd,
        "volume_24h_usd": candidate.volume_24h_usd,
        "priced_at": candidate.priced_at,
        "pair_label": candidate.pair_label,
        "dex_id": candidate.dex_id,
        "quote_symbol": candidate.quote_symbol,
        "source_attempts": attempts,
        "as_of_hint": "DEX-derived research price on Base — not an executable quote",
        "onchain_market_status": "priced",
    }


async def _try_candidate(
    candidate: PoolQuoteCandidate,
    *,
    contract_address: str,
    attempts: list[str],
) -> Result[dict[str, Any]]:
    ok, reason = _passes_liquidity_floor(candidate)
    if not ok:
        attempts.append(f"{candidate.provider}:rejected_liquidity:{reason}")
        return Err(code="below_liquidity_floor", message=reason or "below liquidity floor")
    attempts.append(candidate.provider)
    return Ok(_candidate_to_payload(candidate, contract_address=contract_address, attempts=attempts))


async def _pick_from_list(
    candidates: list[PoolQuoteCandidate],
    *,
    contract_address: str,
    attempts: list[str],
) -> Result[dict[str, Any]]:
    last_reason = "no eligible pool"
    for cand in candidates:
        result = await _try_candidate(cand, contract_address=contract_address, attempts=attempts)
        if isinstance(result, Ok):
            return result
        last_reason = result.message
    return Err(code="all_candidates_rejected", message=last_reason)


async def _resolve_inner(
    contract_address: str,
    *,
    symbol: str | None,
) -> Result[dict[str, Any]]:
    attempts: list[str] = []
    sym = (symbol or "").strip()
    label = sym or contract_address[:8]

    gt_token, gt_pools, ds_token = await asyncio.gather(
        geckoterminal_token_price(contract_address),
        geckoterminal_pool_candidates(contract_address, symbol=label),
        dexscreener_token_pairs(contract_address),
    )

    if isinstance(gt_token, Ok):
        tried = await _try_candidate(gt_token.value, contract_address=contract_address, attempts=attempts)
        if isinstance(tried, Ok):
            return tried
    elif isinstance(gt_token, Err):
        attempts.append(f"geckoterminal_token:{gt_token.code}")

    pool_addrs: list[tuple[str, str | None]] = []

    if isinstance(gt_pools, Ok):
        picked = await _pick_from_list(gt_pools.value, contract_address=contract_address, attempts=attempts)
        if isinstance(picked, Ok):
            return picked
        for c in gt_pools.value:
            if c.pool_address:
                pool_addrs.append((c.pool_address, c.quote_symbol))
    elif isinstance(gt_pools, Err):
        attempts.append(f"geckoterminal_pools:{gt_pools.code}")

    if isinstance(ds_token, Ok):
        picked = await _pick_from_list(ds_token.value, contract_address=contract_address, attempts=attempts)
        if isinstance(picked, Ok):
            return picked
        for c in ds_token.value:
            if c.pool_address:
                pool_addrs.append((c.pool_address, c.quote_symbol))
    elif isinstance(ds_token, Err):
        attempts.append(f"dexscreener_token:{ds_token.code}")

    skip_search = settings.peg_gap_skip_dexscreener_search and isinstance(gt_pools, Err)
    if sym and not skip_search:
        ds_search = await dexscreener_search_pairs(sym, contract_address)
        if isinstance(ds_search, Ok):
            picked = await _pick_from_list(ds_search.value, contract_address=contract_address, attempts=attempts)
            if isinstance(picked, Ok):
                return picked
            for c in ds_search.value:
                if c.pool_address:
                    pool_addrs.append((c.pool_address, c.quote_symbol))
        elif isinstance(ds_search, Err):
            attempts.append(f"dexscreener_search:{ds_search.code}")

    if settings.peg_gap_enable_rpc_pool_read and pool_addrs:
        seen: set[str] = set()
        for pool_address, quote_sym in pool_addrs:
            pk = pool_address.lower()
            if pk in seen:
                continue
            seen.add(pk)
            rpc = await rpc_pool_price_usd(pool_address, contract_address, quote_symbol=quote_sym)
            if isinstance(rpc, Ok):
                merged = PoolQuoteCandidate(
                    provider=rpc.value.provider,
                    pool_address=rpc.value.pool_address,
                    price_usd=rpc.value.price_usd,
                    liquidity_usd=next(
                        (
                            c.liquidity_usd
                            for c in (gt_pools.value if isinstance(gt_pools, Ok) else [])
                            if c.pool_address.lower() == pk
                        ),
                        None,
                    ),
                    volume_24h_usd=None,
                    priced_at=rpc.value.priced_at,
                    pair_label=rpc.value.pair_label,
                    dex_id=rpc.value.dex_id,
                    quote_symbol=quote_sym,
                )
                tried = await _try_candidate(merged, contract_address=contract_address, attempts=attempts)
                if isinstance(tried, Ok):
                    return tried

    reason = (
        f"No liquid Base market for {sym or contract_address} "
        f"(tried: {', '.join(attempts) or 'none'})"
    )
    return Err(
        code="no_onchain_market",
        message=reason,
        hint="Token may have no USDC/WETH pool above configured liquidity floors",
    )


async def resolve_onchain_price_usd(
    contract_address: str,
    *,
    symbol: str | None = None,
) -> Result[dict[str, Any]]:
    """Resolve a Base onchain USD price using real market data only."""
    ttl = int(settings.peg_gap_onchain_cache_ttl_seconds)
    neg_ttl = int(settings.peg_gap_onchain_negative_cache_ttl_seconds)
    key = _cache_key(contract_address, symbol)

    cached = get_cached(key, ttl)
    if isinstance(cached, dict):
        return Ok(cached)

    negative = get_negative_cached(key, neg_ttl)
    if negative:
        return Err(code=negative["code"], message=negative["message"])

    if not cached and not negative:
        await hydrate_cached_from_kv(key)
        cached = get_cached(key, ttl)
        if isinstance(cached, dict):
            return Ok(cached)
        negative = get_negative_cached(key, neg_ttl)
        if negative:
            return Err(code=negative["code"], message=negative["message"])

    timeout = float(settings.peg_gap_onchain_resolve_timeout_seconds)
    try:
        outcome = await asyncio.wait_for(
            _resolve_inner(contract_address, symbol=symbol),
            timeout=timeout,
        )
    except TimeoutError:
        err = Err(
            code="onchain_resolve_timeout",
            message=f"Onchain price lookup timed out after {timeout}s",
        )
        set_negative_cached(key, err.code, err.message, min(neg_ttl, 300))
        await persist_cached_to_kv(key, positive=None, negative={"code": err.code, "message": err.message})
        return err

    if isinstance(outcome, Ok):
        set_cached(key, outcome.value, ttl)
        await persist_cached_to_kv(key, positive=outcome.value, negative=None)
        return outcome

    set_negative_cached(key, outcome.code, outcome.message, neg_ttl)
    await persist_cached_to_kv(
        key,
        positive=None,
        negative={"code": outcome.code, "message": outcome.message},
    )
    return outcome
