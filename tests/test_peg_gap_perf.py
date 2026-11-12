"""Peg-gap build latency — parallel row resolution with mocked slow sources."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.config import settings
from app.stocksmaxxing.onchain_price_cache import clear_cache
from app.stocksmaxxing.peg_gap import build_peg_gap_rows
from app.stocksmaxxing.peg_gap_snapshot import clear_snapshot_cache
from app.stocksmaxxing.result import Err, Ok


@pytest.fixture(autouse=True)
def _reset_caches():
    clear_cache()
    clear_snapshot_cache()
    yield
    clear_cache()
    clear_snapshot_cache()


def _token_batch(n: int) -> list[dict]:
    return [
        {
            "symbol": f"T{i:02d}c",
            "contract_address": f"0xB200000000000000000000000000000000{i:04x}",
            "nav_price": 50.0,
            "nav_price_updated_at": "2026-11-10T10:00:00+00:00",
        }
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_build_peg_gap_rows_parallel_under_budget(monkeypatch):
    monkeypatch.setattr(settings, "peg_gap_onchain_parallelism", 8)
    monkeypatch.setattr(settings, "peg_gap_onchain_request_delay_seconds", 0.0)
    batch = _token_batch(25)

    async def fake_list(self, page_size: int = 25, **_kwargs):
        return Ok({"tokens": batch[:page_size]})

    async def slow_onchain(_contract: str, *, symbol: str | None = None):
        await asyncio.sleep(0.06)
        return Err(code="no_onchain_market", message=f"fixture {symbol}")

    async def fast_underlying(_symbol: str):
        return Ok({"price_usd": 50.0})

    monkeypatch.setattr(
        "app.stocksmaxxing.coinbase_client.CoinbaseTokenizedStocksClient.list_tokens",
        fake_list,
    )
    monkeypatch.setattr("app.stocksmaxxing.peg_gap.fetch_onchain_price_usd", slow_onchain)
    monkeypatch.setattr(
        "app.stocksmaxxing.peg_gap.fetch_underlying_for_tokenized_symbol",
        fast_underlying,
    )

    started = time.perf_counter()
    rows, meta = await build_peg_gap_rows(alert_threshold_pct=2.0, page_size=25)
    elapsed = time.perf_counter() - started

    assert len(rows) == 25
    assert elapsed < 1.2, f"expected <1.2s parallel build, got {elapsed:.2f}s"
    assert meta["build_time_ms"] < 1200
