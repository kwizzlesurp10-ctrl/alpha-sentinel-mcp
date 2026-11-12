"""Read Uniswap V3–style pool slot0 on Base for onchain mid prices (research only)."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.stocksmaxxing.onchain_price_constants import USDC_BASE, WETH_BASE
from app.stocksmaxxing.onchain_price_sources import (
    PoolQuoteCandidate,
    _addr_key,
    _now_iso,
)
from app.stocksmaxxing.result import Err, Ok, Result

logger = logging.getLogger(__name__)

SLOT0_SELECTOR = "0x3850c7bd"  # slot0()
TOKEN0_SELECTOR = "0x0dfe1681"
TOKEN1_SELECTOR = "0xd21220a7"
DECIMALS_SELECTOR = "0x313ce567"

WETH_USDC_POOL = "0xd0b53D9277642d8994115D87b615aB58570feE5"  # Aerodrome Slipstream WETH/USDC (Base)


async def _eth_call(rpc_url: str, to: str, data: str) -> bytes:
    from hexbytes import HexBytes
    from web3 import Web3

    def _call() -> bytes:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 12}))
        raw = w3.eth.call({"to": Web3.to_checksum_address(to), "data": HexBytes(data)})
        return bytes(raw)

    return await asyncio.to_thread(_call)


def _decode_address(ret: bytes) -> str:
    if len(ret) < 32:
        return ""
    return "0x" + ret[-20:].hex()


def _decode_uint(ret: bytes) -> int:
    if len(ret) < 32:
        return 0
    return int.from_bytes(ret[-32:], "big")


def _price_token1_per_token0(sqrt_price_x96: int, dec0: int, dec1: int) -> float | None:
    if sqrt_price_x96 <= 0:
        return None
    ratio = (sqrt_price_x96 / (2**96)) ** 2
    adj = (10**dec0) / (10**dec1)
    return ratio * adj


async def _weth_usd(rpc_url: str) -> float | None:
    """WETH priced in USDC via a liquid WETH/USDC pool on Base."""
    try:
        slot0 = await _eth_call(rpc_url, WETH_USDC_POOL, SLOT0_SELECTOR)
        t0 = _decode_address(await _eth_call(rpc_url, WETH_USDC_POOL, TOKEN0_SELECTOR))
        t1 = _decode_address(await _eth_call(rpc_url, WETH_USDC_POOL, TOKEN1_SELECTOR))
        d0 = _decode_uint(await _eth_call(rpc_url, t0, DECIMALS_SELECTOR))
        d1 = _decode_uint(await _eth_call(rpc_url, t1, DECIMALS_SELECTOR))
        sqrt_price = _decode_uint(slot0)
        p1_per_0 = _price_token1_per_token0(sqrt_price, d0, d1)
        if p1_per_0 is None:
            return None
        if _addr_key(t0) == _addr_key(WETH_BASE):
            return p1_per_0
        if _addr_key(t1) == _addr_key(WETH_BASE):
            return 1.0 / p1_per_0 if p1_per_0 else None
    except Exception as exc:
        logger.warning("WETH/USD rpc read failed: %s", exc)
    return None


async def rpc_pool_price_usd(
    pool_address: str,
    catalog_token: str,
    *,
    quote_symbol: str | None,
) -> Result[PoolQuoteCandidate]:
    rpc_url = (settings.base_rpc_url or "").strip()
    if not rpc_url:
        return Err(code="rpc_unconfigured", message="BASE_RPC_URL required for onchain pool reads")

    try:
        slot0 = await _eth_call(rpc_url, pool_address, SLOT0_SELECTOR)
        t0 = _decode_address(await _eth_call(rpc_url, pool_address, TOKEN0_SELECTOR))
        t1 = _decode_address(await _eth_call(rpc_url, pool_address, TOKEN1_SELECTOR))
        d0 = _decode_uint(await _eth_call(rpc_url, t0, DECIMALS_SELECTOR))
        d1 = _decode_uint(await _eth_call(rpc_url, t1, DECIMALS_SELECTOR))
        sqrt_price = _decode_uint(slot0)
        token_per_quote = _price_token1_per_token0(sqrt_price, d0, d1)
        if token_per_quote is None:
            return Err(code="rpc_slot0_invalid", message="Could not decode slot0 price")

        catalog = _addr_key(catalog_token)
        quote = (quote_symbol or "").upper()
        price_usd: float | None = None

        if _addr_key(t0) == catalog:
            other = t1
            if _addr_key(other) == _addr_key(USDC_BASE):
                # token0 is stock; token1 is USDC → USD per token0
                if _addr_key(t1) == _addr_key(USDC_BASE) and _addr_key(t0) == catalog:
                    price_usd = token_per_quote
            elif _addr_key(other) == _addr_key(WETH_BASE):
                weth_usd = await _weth_usd(rpc_url)
                if weth_usd and token_per_quote:
                    price_usd = token_per_quote * weth_usd
        elif _addr_key(t1) == catalog:
            if _addr_key(t0) == _addr_key(USDC_BASE):
                # token0 USDC, token1 stock → invert
                price_usd = (1.0 / token_per_quote) if token_per_quote else None
            elif _addr_key(t0) == _addr_key(WETH_BASE):
                weth_usd = await _weth_usd(rpc_url)
                inv = (1.0 / token_per_quote) if token_per_quote else None
                if weth_usd and inv:
                    price_usd = inv * weth_usd

        if price_usd is None or price_usd <= 0:
            return Err(code="rpc_price_unresolved", message="RPC pool read did not yield a USD price")

        return Ok(
            PoolQuoteCandidate(
                provider="base_rpc_slot0",
                pool_address=pool_address,
                price_usd=price_usd,
                liquidity_usd=None,
                volume_24h_usd=None,
                priced_at=_now_iso(),
                pair_label=f"rpc:{pool_address[:10]}…",
                dex_id="onchain",
                quote_symbol=quote or None,
            )
        )
    except Exception as exc:
        logger.warning("RPC pool price failed for %s: %s", pool_address, exc)
        return Err(code="rpc_pool_error", message=str(exc))
