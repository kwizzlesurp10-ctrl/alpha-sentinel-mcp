"""Shared fixtures. Mock only outbound CoinGecko HTTP — never the ASGI handlers."""

from __future__ import annotations

import pytest

from app.config import settings

TEST_PAY_TO = "0x1111111111111111111111111111111111111111"
MOCK_BTC_USD = 67842.50


@pytest.fixture(autouse=True)
def test_seller_pay_to(monkeypatch):
    monkeypatch.setattr(settings, "x402_pay_to_address", TEST_PAY_TO)


@pytest.fixture
def mock_coingecko_api(monkeypatch):
    """Patch httpx.AsyncClient.get used by the live price_feed module."""

    async def mock_get(self, url, *args, **kwargs):
        url_s = str(url)

        class MockResponse:
            def __init__(self, payload, status=200):
                self._payload = payload
                self.status_code = status

            def json(self):
                return self._payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

        if "simple/price" in url_s or "coingecko" in url_s:
            return MockResponse(
                {
                    "bitcoin": {
                        "usd": MOCK_BTC_USD,
                        "usd_24h_change": 2.34,
                        "usd_24h_vol": 28500000000,
                    }
                }
            )
        if "ping" in url_s:
            return MockResponse({"gecko_says": "ok"})
        return MockResponse({})

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    return MOCK_BTC_USD
