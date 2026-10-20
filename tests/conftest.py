"""Shared fixtures. Mock only outbound CoinGecko HTTP — never the ASGI handlers."""

from __future__ import annotations

import pytest

from app.config import settings

TEST_PAY_TO = "0x1111111111111111111111111111111111111111"
MOCK_BTC_USD = 67842.50


@pytest.fixture(autouse=True)
def test_seller_pay_to(monkeypatch):
    monkeypatch.setattr(settings, "x402_pay_to_address", TEST_PAY_TO)


@pytest.fixture(autouse=True)
def idempotency_memory_store(monkeypatch):
    """Allow paid-path tests without Upstash (production uses fail-closed)."""
    from app import payment_idempotency as pid
    from app.kv_store import InMemoryKvStore, set_store_override

    store = InMemoryKvStore()
    set_store_override(store)
    monkeypatch.setattr(pid, "must_persist_idempotency", lambda: False)
    yield
    set_store_override(None)
    store.clear()
    pid.clear()


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


def make_payment_signature(tag: str, pay_to: str | None = None) -> str:
    """A well-formed (but unsigned) x402 v2 PAYMENT-SIGNATURE; unique per tag."""
    import base64
    import hashlib
    import json

    to = pay_to or TEST_PAY_TO
    nonce = "0x" + hashlib.sha256(tag.encode()).hexdigest()
    body = {
        "x402Version": 2,
        "accepted": {
            "scheme": "exact",
            "network": "eip155:8453",
            "amount": "5000",
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "payTo": to,
            "maxTimeoutSeconds": 300,
            "extra": {"name": "USD Coin", "version": "2"},
        },
        "payload": {
            "signature": "0x" + "11" * 65,
            "authorization": {
                "from": "0x" + "22" * 20,
                "to": to,
                "value": "5000",
                "validAfter": "0",
                "validBefore": "9999999999",
                "nonce": nonce,
            },
        },
    }
    return base64.b64encode(json.dumps(body).encode()).decode()
