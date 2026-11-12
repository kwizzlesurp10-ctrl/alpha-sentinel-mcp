"""HTTP sources for Base onchain token prices (research only)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings
from app.stocksmaxxing.onchain_price_constants import (
    GECKO_USER_AGENT,
    QUOTE_ALLOWLIST,
    USDC_BASE,
)
from app.stocksmaxxing.result import Err, Ok, Result

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PoolQuoteCandidate:
    provider: str
    pool_address: str
    price_usd: float
    liquidity_usd: float | None
    volume_24h_usd: float | None
    priced_at: str
    pair_label: str | None
    dex_id: str | None
    quote_symbol: str | None


def _addr_key(address: str) -> str:
    return address.lower()


def _is_quote_token(address: str | None) -> bool:
    if not address:
        return False
    return _addr_key(address) in QUOTE_ALLOWLIST


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out <= 0:
        return None
    return out


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def _http_get_json(url: str) -> Result[dict[str, Any]]:
    headers = {"Accept": "application/json", "User-Agent": GECKO_USER_AGENT}
    last_error: str | None = None
    for attempt in range(4):
        try:
            async with httpx.AsyncClient(timeout=settings.x402_http_timeout, headers=headers) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return Err(code="http_404", message=f"Not found: {url}")
                if response.status_code == 429:
                    last_error = "429 Too Many Requests"
                    await asyncio.sleep(0.6 * (attempt + 1))
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    return Err(code="invalid_json", message="Expected JSON object")
                return Ok(payload)
        except httpx.HTTPError as exc:
            last_error = str(exc)
            logger.warning("onchain HTTP error %s: %s", url, exc)
            break
    return Err(code="http_error", message=last_error or "http_error")


def _relationship_addr(pool: dict[str, Any], side: str) -> str | None:
    rel = (pool.get("relationships") or {}).get(side) or {}
    data = rel.get("data") or {}
    token_id = str(data.get("id") or "")
    if "_" in token_id:
        return token_id.split("_", 1)[1]
    return None


def _pool_candidate_from_gecko(
    pool: dict[str, Any],
    *,
    catalog_addr: str,
    symbol: str,
) -> PoolQuoteCandidate | None:
    attrs = pool.get("attributes") or {}
    base_addr = _relationship_addr(pool, "base_token")
    quote_addr = _relationship_addr(pool, "quote_token")
    if not base_addr or not quote_addr:
        return None
    catalog = _addr_key(catalog_addr)
    base_k = _addr_key(base_addr)
    quote_k = _addr_key(quote_addr)

    price: float | None = None
    quote_sym: str | None = None
    if base_k == catalog and _is_quote_token(quote_addr):
        price = _parse_float(attrs.get("base_token_price_usd"))
        quote_sym = "USDC" if quote_k == _addr_key(USDC_BASE) else "WETH"
    elif quote_k == catalog and _is_quote_token(base_addr):
        price = _parse_float(attrs.get("quote_token_price_usd"))
        quote_sym = "USDC" if _addr_key(base_addr) == _addr_key(USDC_BASE) else "WETH"
    else:
        return None
    if price is None:
        return None

    liq = _parse_float(attrs.get("reserve_in_usd"))
    vol_raw = (attrs.get("volume_usd") or {}).get("h24")
    vol = _parse_float(vol_raw)
    pool_address = str(attrs.get("address") or "")
    if not pool_address:
        return None
    dex = ((pool.get("relationships") or {}).get("dex") or {}).get("data") or {}
    return PoolQuoteCandidate(
        provider="geckoterminal_pools",
        pool_address=pool_address,
        price_usd=price,
        liquidity_usd=liq,
        volume_24h_usd=vol,
        priced_at=_now_iso(),
        pair_label=str(attrs.get("name") or symbol),
        dex_id=str(dex.get("id") or ""),
        quote_symbol=quote_sym,
    )


async def geckoterminal_token_price(contract_address: str) -> Result[PoolQuoteCandidate]:
    addr = _addr_key(contract_address)
    url = f"https://api.geckoterminal.com/api/v2/networks/base/tokens/{addr}"
    fetched = await _http_get_json(url)
    if isinstance(fetched, Err):
        return fetched
    payload = fetched.value
    attrs = (payload.get("data") or {}).get("attributes") or {}
    price = _parse_float(attrs.get("price_usd"))
    if price is None:
        return Err(code="geckoterminal_token_missing_price", message="GeckoTerminal token has no price_usd")
    vol = _parse_float((attrs.get("volume_usd") or {}).get("h24"))
    return Ok(
        PoolQuoteCandidate(
            provider="geckoterminal_token",
            pool_address="",
            price_usd=price,
            liquidity_usd=None,
            volume_24h_usd=vol,
            priced_at=_now_iso(),
            pair_label=None,
            dex_id=None,
            quote_symbol=None,
        )
    )


async def geckoterminal_pool_candidates(
    contract_address: str,
    *,
    symbol: str,
) -> Result[list[PoolQuoteCandidate]]:
    addr = _addr_key(contract_address)
    url = f"https://api.geckoterminal.com/api/v2/networks/base/tokens/{addr}/pools?page=1"
    fetched = await _http_get_json(url)
    if isinstance(fetched, Err):
        return fetched
    pools = fetched.value.get("data") or []
    candidates: list[PoolQuoteCandidate] = []
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        cand = _pool_candidate_from_gecko(pool, catalog_addr=contract_address, symbol=symbol)
        if cand:
            candidates.append(cand)
    if not candidates:
        return Err(
            code="geckoterminal_no_eligible_pools",
            message="No USDC/WETH pools with a price for this token on GeckoTerminal",
        )
    candidates.sort(
        key=lambda c: (
            -(c.liquidity_usd or 0),
            -(c.volume_24h_usd or 0),
        )
    )
    return Ok(candidates)


def _ds_pair_candidate(pair: dict[str, Any], *, catalog_addr: str) -> PoolQuoteCandidate | None:
    base = pair.get("baseToken") or {}
    quote = pair.get("quoteToken") or {}
    base_addr = str(base.get("address") or "")
    quote_addr = str(quote.get("address") or "")
    catalog = _addr_key(catalog_addr)
    price: float | None = None
    quote_sym: str | None = None
    if _addr_key(base_addr) == catalog and _is_quote_token(quote_addr):
        price = _parse_float(pair.get("priceUsd"))
        quote_sym = str(quote.get("symbol") or "")
    elif _addr_key(quote_addr) == catalog and _is_quote_token(base_addr):
        # DexScreener priceUsd is the base token only — skip quote-side stock to avoid mispricing.
        return None
    else:
        return None
    if price is None:
        return None
    liq = _parse_float((pair.get("liquidity") or {}).get("usd"))
    vol = _parse_float((pair.get("volume") or {}).get("h24"))
    pool_address = str(pair.get("pairAddress") or "")
    return PoolQuoteCandidate(
        provider="dexscreener",
        pool_address=pool_address,
        price_usd=price,
        liquidity_usd=liq,
        volume_24h_usd=vol,
        priced_at=_now_iso(),
        pair_label=f"{base.get('symbol')}/{quote.get('symbol')}",
        dex_id=str(pair.get("dexId") or ""),
        quote_symbol=quote_sym,
    )


def _filter_base_pairs(pairs: list[dict[str, Any]], catalog_addr: str) -> list[PoolQuoteCandidate]:
    out: list[PoolQuoteCandidate] = []
    for pair in pairs:
        if pair.get("chainId") != "base":
            continue
        cand = _ds_pair_candidate(pair, catalog_addr=catalog_addr)
        if cand:
            out.append(cand)
    out.sort(key=lambda c: (-(c.liquidity_usd or 0), -(c.volume_24h_usd or 0)))
    return out


async def dexscreener_token_pairs(contract_address: str) -> Result[list[PoolQuoteCandidate]]:
    url = f"https://api.dexscreener.com/latest/dex/tokens/{contract_address}"
    fetched = await _http_get_json(url)
    if isinstance(fetched, Err):
        return fetched
    candidates = _filter_base_pairs(fetched.value.get("pairs") or [], contract_address)
    if not candidates:
        return Err(code="dexscreener_no_pairs", message="DexScreener returned no eligible Base pairs")
    return Ok(candidates)


async def dexscreener_search_pairs(symbol: str, contract_address: str) -> Result[list[PoolQuoteCandidate]]:
    url = f"https://api.dexscreener.com/latest/dex/search?q={quote(symbol)}"
    fetched = await _http_get_json(url)
    if isinstance(fetched, Err):
        return fetched
    pairs = fetched.value.get("pairs") or []
    sym_u = symbol.upper()
    catalog = _addr_key(contract_address)
    filtered = [
        p
        for p in pairs
        if (p.get("baseToken") or {}).get("symbol", "").upper() == sym_u
        and _addr_key(str((p.get("baseToken") or {}).get("address") or "")) == catalog
    ]
    candidates = _filter_base_pairs(filtered or pairs, contract_address)
    if not candidates:
        return Err(code="dexscreener_search_miss", message=f"DexScreener search found no {symbol} on Base")
    return Ok(candidates)
