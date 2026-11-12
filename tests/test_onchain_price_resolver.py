"""Onchain price fallback chain — fixture-backed, no live APIs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.stocksmaxxing.onchain_price_cache import clear_cache
from app.stocksmaxxing.onchain_price_resolver import resolve_onchain_price_usd
from app.stocksmaxxing.onchain_price_sources import PoolQuoteCandidate
from app.stocksmaxxing.result import Err, Ok

FX = Path(__file__).parent / "fixtures" / "onchain_price"
CONTRACT = "0xB20000000000000000000019f6E7C675b73C2e4D"


@pytest.fixture(autouse=True)
def _reset_onchain_cache():
    clear_cache()
    yield
    clear_cache()


def _load(name: str) -> dict:
    return json.loads((FX / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_resolver_gecko_pools_when_token_has_no_price(monkeypatch):
    payloads = {
        "token": _load("gecko_token_no_price.json"),
        "pools": _load("gecko_pools_crcl.json"),
    }

    async def fake_http(url: str):
        if url.endswith("/pools?page=1"):
            return Ok(payloads["pools"])
        if "/tokens/" in url and "/pools" not in url:
            return Ok(payloads["token"])
        return Err(code="unexpected_url", message=url)

    monkeypatch.setattr(
        "app.stocksmaxxing.onchain_price_sources._http_get_json",
        fake_http,
    )

    result = await resolve_onchain_price_usd(CONTRACT, symbol="CRCLc")
    assert isinstance(result, Ok)
    assert result.value["provider"] == "geckoterminal_pools"
    assert result.value["price_usd"] == pytest.approx(67.04)
    assert result.value["pool_address"] == "0x0000000000000000000000000000000000000a01"
    assert result.value["liquidity_usd"] == pytest.approx(125000.50)
    assert "geckoterminal_pools" in result.value["source_attempts"]


@pytest.mark.asyncio
async def test_resolver_falls_through_to_dexscreener(monkeypatch):
    async def fake_http(url: str):
        if "geckoterminal" in url:
            if "/pools" in url:
                return Err(code="geckoterminal_no_eligible_pools", message="none")
            return Ok(_load("gecko_token_no_price.json"))
        if "dexscreener.com" in url:
            return Ok(_load("dexscreener_crcl.json"))
        return Err(code="unexpected", message=url)

    monkeypatch.setattr(
        "app.stocksmaxxing.onchain_price_sources._http_get_json",
        fake_http,
    )

    result = await resolve_onchain_price_usd(CONTRACT, symbol="CRCLc")
    assert isinstance(result, Ok)
    assert result.value["provider"] == "dexscreener"
    assert result.value["price_usd"] == pytest.approx(68.10)
    assert "dexscreener" in result.value["source_attempts"]


@pytest.mark.asyncio
async def test_resolver_liquidity_floor_rejects_thin_pool(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "peg_gap_min_pool_liquidity_usd", 200_000.0)
    monkeypatch.setattr(settings, "peg_gap_min_pool_volume_24h_usd", 0.0)

    async def fake_http(url: str):
        if "dexscreener" in url:
            return Err(code="dexscreener_no_pairs", message="none")
        if "/pools" in url:
            return Ok(_load("gecko_pools_crcl.json"))
        return Ok(_load("gecko_token_no_price.json"))

    monkeypatch.setattr(
        "app.stocksmaxxing.onchain_price_sources._http_get_json",
        fake_http,
    )

    result = await resolve_onchain_price_usd(CONTRACT, symbol="CRCLc")
    assert isinstance(result, Err)
    assert result.code == "no_onchain_market"


@pytest.mark.asyncio
async def test_resolver_cache_returns_without_second_http(monkeypatch):
    calls: list[str] = []

    async def fake_http(url: str):
        calls.append(url)
        if "/pools" in url:
            return Ok(_load("gecko_pools_crcl.json"))
        return Ok(_load("gecko_token_no_price.json"))

    monkeypatch.setattr(
        "app.stocksmaxxing.onchain_price_sources._http_get_json",
        fake_http,
    )

    first = await resolve_onchain_price_usd(CONTRACT, symbol="CRCLc")
    second = await resolve_onchain_price_usd(CONTRACT, symbol="CRCLc")
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert first.value["price_usd"] == second.value["price_usd"]
    assert len(calls) >= 1
    # Second resolve should not add more HTTP calls (cached).
    call_count_after_first = len(calls)
    await resolve_onchain_price_usd(CONTRACT, symbol="CRCLc")
    assert len(calls) == call_count_after_first


@pytest.mark.asyncio
async def test_geckoterminal_token_endpoint_success(monkeypatch):
    from app.stocksmaxxing.onchain_price_sources import geckoterminal_token_price

    async def fake_http(url: str):
        return Ok(
            {
                "data": {
                    "attributes": {
                        "price_usd": "101.5",
                        "volume_usd": {"h24": "900"},
                    }
                }
            }
        )

    monkeypatch.setattr("app.stocksmaxxing.onchain_price_sources._http_get_json", fake_http)
    out = await geckoterminal_token_price(CONTRACT)
    assert isinstance(out, Ok)
    assert out.value.price_usd == pytest.approx(101.5)
    assert out.value.provider == "geckoterminal_token"


@pytest.mark.asyncio
async def test_pick_best_pool_by_liquidity(monkeypatch):
    from app.stocksmaxxing.onchain_price_sources import geckoterminal_pool_candidates

    thin = _load("gecko_pools_crcl.json")
    rich = json.loads(json.dumps(thin))
    rich["data"][0]["attributes"]["reserve_in_usd"] = "500000"
    rich["data"][0]["attributes"]["base_token_price_usd"] = "66.00"
    rich["data"][0]["attributes"]["address"] = "0x0000000000000000000000000000000000000c03"

    payload = {"data": thin["data"] + rich["data"]}

    async def fake_http(url: str):
        return Ok(payload)

    monkeypatch.setattr("app.stocksmaxxing.onchain_price_sources._http_get_json", fake_http)
    out = await geckoterminal_pool_candidates(CONTRACT, symbol="CRCLc")
    assert isinstance(out, Ok)
    assert out.value[0].pool_address.endswith("0c03")
    assert out.value[0].price_usd == pytest.approx(66.0)


@pytest.mark.asyncio
async def test_rpc_slot0_optional(monkeypatch):
    from app.config import settings
    from app.stocksmaxxing.onchain_price_resolver import _try_candidate

    monkeypatch.setattr(settings, "peg_gap_enable_rpc_pool_read", True)
    monkeypatch.setattr(settings, "peg_gap_min_pool_liquidity_usd", 0.0)

    cand = PoolQuoteCandidate(
        provider="base_rpc_slot0",
        pool_address="0xpool",
        price_usd=12.34,
        liquidity_usd=None,
        volume_24h_usd=None,
        priced_at="2026-11-10T00:00:00+00:00",
        pair_label="rpc",
        dex_id="onchain",
        quote_symbol="USDC",
    )
    picked = await _try_candidate(cand, contract_address=CONTRACT, attempts=["base_rpc_slot0"])
    assert isinstance(picked, Ok)
    assert picked.value["provider"] == "base_rpc_slot0"
