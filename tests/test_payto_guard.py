"""Refuse retired seller wallets; no offline empty-extra challenges."""

from __future__ import annotations

import pytest

from app.payto_guard import (
    CANONICAL_PAY_TO,
    assert_pay_to_allowed,
    is_retired_pay_to,
)


def test_retired_addresses_detected():
    assert is_retired_pay_to("0xAB745e5F576667037696e78ba7dA28E193E4423D")
    assert is_retired_pay_to("0xab745e5f576667037696e78ba7da28e193e4423d")
    assert is_retired_pay_to("0x05e1720bB82F86B5bc7940a99FDC702E32256357")
    assert not is_retired_pay_to(CANONICAL_PAY_TO)
    assert not is_retired_pay_to(None)
    assert not is_retired_pay_to("")


def test_assert_raises_on_retired():
    with pytest.raises(ValueError, match="retired"):
        assert_pay_to_allowed("0xAB745e5F576667037696e78ba7dA28E193E4423D")
    assert_pay_to_allowed(CANONICAL_PAY_TO)
    assert_pay_to_allowed(None)


def test_settings_refuse_retired_pay_to(monkeypatch):
    from app.config import Settings

    with pytest.raises(ValueError, match="retired"):
        Settings(x402_pay_to_address="0xAB745e5F576667037696e78ba7dA28E193E4423D")


@pytest.mark.asyncio
async def test_build_seller_requirements_fails_closed_when_facilitator_offline(monkeypatch):
    """Offline facilitator must raise — never emit extra={} challenges."""
    from app import x402_services
    from app.models import BuildSellerRequirementsInput

    class Boom:
        def initialize(self):
            raise RuntimeError("offline")

        def build_payment_requirements(self, *_a, **_k):
            raise AssertionError("must not be called after initialize fail")

    monkeypatch.setattr(x402_services, "_facilitator_client", lambda *_a, **_k: object())
    monkeypatch.setattr(x402_services, "_register_server_schemes", lambda *_a, **_k: None)
    import x402 as x402_pkg

    monkeypatch.setattr(x402_pkg, "x402ResourceServer", lambda *_a, **_k: Boom())

    with pytest.raises(RuntimeError, match="facilitator unavailable"):
        x402_services.build_seller_requirements(
            BuildSellerRequirementsInput(
                network="eip155:8453",
                pay_to=CANONICAL_PAY_TO,
                price="$0.005",
                scheme="exact",
                description="test",
                resource_url="https://example.com/tools/fetch_price",
                mime_type="application/json",
                discoverable=False,
            )
        )


def test_setup_script_default_is_canonical():
    text = open("setup-payment-address.sh", encoding="utf-8").read()
    assert f'DEFAULT_ADDRESS="{CANONICAL_PAY_TO}"' in text
    # Retired addresses may appear only in the refuse case list.
    assert 'DEFAULT_ADDRESS="0xAB745e5F576667037696e78ba7dA28E193E4423D"' not in text
    assert "retired seller wallet" in text
