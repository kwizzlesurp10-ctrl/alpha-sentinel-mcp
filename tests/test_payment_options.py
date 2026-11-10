"""Multi-option x402 payment accepts, ranking, and verification."""

from __future__ import annotations

import pytest

from app.payment_option_usage import (
    option_key,
    record_payment_option_usage,
    reset_counts_for_tests,
)
from app.payment_options import (
    BASE_MAINNET_CAIP2,
    USDC_EVM_POLYGON,
    advertised_networks_for_seller,
    rank_payment_requirements,
    set_facilitator_settleable_override,
)
from app.payto_guard import CANONICAL_PAY_TO


@pytest.fixture(autouse=True)
def _reset_payment_option_state(monkeypatch):

    reset_counts_for_tests()
    set_facilitator_settleable_override({BASE_MAINNET_CAIP2})
    monkeypatch.setenv("X402_EXTRA_NETWORKS", "")
    monkeypatch.delenv("X402_SOLANA_PAY_TO", raising=False)
    from app.config import Settings

    monkeypatch.setattr("app.config.settings", Settings())
    yield
    set_facilitator_settleable_override(None)
    reset_counts_for_tests()


def test_default_config_single_base_option(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(
        "app.config.settings",
        Settings(
            x402_pay_to_address=CANONICAL_PAY_TO,
            x402_extra_networks="",
        ),
    )
    nets = advertised_networks_for_seller()
    assert nets == [BASE_MAINNET_CAIP2]


def test_extra_networks_advertised_when_settleable(monkeypatch):
    from app.config import Settings

    set_facilitator_settleable_override({BASE_MAINNET_CAIP2, "eip155:137"})
    monkeypatch.setattr(
        "app.config.settings",
        Settings(
            x402_pay_to_address=CANONICAL_PAY_TO,
            x402_extra_networks="polygon",
            cdp_api_key_id="kid",
            cdp_api_key_secret="sec",
            cdp_networks="eip155:8453,eip155:137",
        ),
    )
    nets = advertised_networks_for_seller()
    assert BASE_MAINNET_CAIP2 in nets
    assert "eip155:137" in nets


def test_ranking_most_used_first_base_tie_break():
    from x402.schemas import PaymentRequirements

    base = PaymentRequirements(
        scheme="exact",
        network=BASE_MAINNET_CAIP2,
        pay_to=CANONICAL_PAY_TO,
        amount="5000",
        asset="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        max_timeout_seconds=300,
        extra={"name": "USD Coin", "version": "2"},
    )
    poly = PaymentRequirements(
        scheme="exact",
        network="eip155:137",
        pay_to=CANONICAL_PAY_TO,
        amount="5000",
        asset=USDC_EVM_POLYGON,
        max_timeout_seconds=300,
        extra={"name": "USD Coin", "version": "2"},
    )
    ranked = rank_payment_requirements([base, poly])
    assert ranked[0].network == BASE_MAINNET_CAIP2

    from app.payment_option_usage import _memory_counts

    _memory_counts[option_key("eip155:137", USDC_EVM_POLYGON)] = 5
    ranked = rank_payment_requirements([base, poly])
    assert ranked[0].network == "eip155:137"
    _memory_counts.clear()


@pytest.mark.asyncio
async def test_ranking_after_recorded_usage():
    from x402.schemas import PaymentRequirements

    await record_payment_option_usage("eip155:137", USDC_EVM_POLYGON)
    await record_payment_option_usage("eip155:137", USDC_EVM_POLYGON)
    base = PaymentRequirements(
        scheme="exact",
        network=BASE_MAINNET_CAIP2,
        pay_to=CANONICAL_PAY_TO,
        amount="5000",
        asset="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        max_timeout_seconds=300,
        extra={"name": "USD Coin", "version": "2"},
    )
    poly = PaymentRequirements(
        scheme="exact",
        network="eip155:137",
        pay_to=CANONICAL_PAY_TO,
        amount="5000",
        asset=USDC_EVM_POLYGON,
        max_timeout_seconds=300,
        extra={"name": "USD Coin", "version": "2"},
    )
    ranked = rank_payment_requirements([base, poly])
    assert ranked[0].network == "eip155:137"


def test_build_seller_default_single_accept(monkeypatch):
    from app import x402_services
    from app.config import Settings
    from app.models import BuildSellerRequirementsInput

    monkeypatch.setattr(
        "app.config.settings",
        Settings(x402_pay_to_address=CANONICAL_PAY_TO),
    )

    class Boom:
        def initialize(self):
            raise RuntimeError("offline")

        def build_payment_requirements(self, *_a, **_k):
            raise AssertionError("must not be called after initialize fail")

    monkeypatch.setattr(x402_services, "_facilitator_client", lambda *_a, **_k: object())
    monkeypatch.setattr(x402_services, "_register_server_schemes", lambda *_a, **_k: None)
    import x402 as x402_pkg

    monkeypatch.setattr(x402_pkg, "x402ResourceServer", lambda *_a, **_k: Boom())

    built = x402_services.build_seller_requirements(
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
    reqs = built.get("requirements") or []
    assert len(reqs) == 1
    assert reqs[0]["network"] == BASE_MAINNET_CAIP2


def test_wrong_network_payment_rejected():
    from x402.http import encode_payment_required_header
    from x402.schemas import PaymentPayload, PaymentRequired, PaymentRequirements

    from app import x402_services

    base_req = PaymentRequirements(
        scheme="exact",
        network=BASE_MAINNET_CAIP2,
        pay_to=CANONICAL_PAY_TO,
        amount="5000",
        asset="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        max_timeout_seconds=300,
        extra={"name": "USD Coin", "version": "2"},
    )
    header = encode_payment_required_header(
        PaymentRequired(x402_version=2, accepts=[base_req], error="test")
    )
    payload = PaymentPayload.model_validate(
        {
            "x402Version": 2,
            "scheme": "exact",
            "network": "eip155:137",
            "payload": {},
            "accepted": {
                "scheme": "exact",
                "network": "eip155:137",
                "asset": USDC_EVM_POLYGON,
                "amount": "5000",
                "payTo": CANONICAL_PAY_TO,
                "maxTimeoutSeconds": 300,
            },
        }
    )
    from x402.http import encode_payment_signature_header

    sig = encode_payment_signature_header(payload)
    with pytest.raises(ValueError, match="payment_option_not_accepted"):
        x402_services._decode_payment_inputs(sig, header)
