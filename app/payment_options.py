"""Multi-rail USDC payment options for x402 seller challenges.

Stablecoins only — Circle native USDC on each EVM network; Solana USDC when
``X402_SOLANA_PAY_TO`` is configured. Networks the active facilitator cannot
settle are omitted from ``accepts[]``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app import config

logger = logging.getLogger(__name__)

BASE_MAINNET_CAIP2 = "eip155:8453"

# Circle USDC contract addresses on mainnet EVM chains (native USDC).
# Primary source: https://developers.circle.com/stablecoins/usdc-on-main-networks
USDC_EVM_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_EVM_POLYGON = "0x3c499c542cEF5E3811e1192aDc88583889c8a4b"
USDC_EVM_ARBITRUM = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
USDC_EVM_OPTIMISM = "0x0b2C639c533813f4Aa9D7837CAa886fef1908FF7"

# Solana mainnet USDC (SPL); see Circle / Solana token list — only enabled with pay_to.
USDC_SOLANA_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOLANA_MAINNET_CAIP2 = "solana:mainnet"

EIP712_EXTRA = {"name": "USD Coin", "version": "2"}

_facilitator_settleable_override: set[str] | None = None


@dataclass(frozen=True, slots=True)
class PaymentNetworkOption:
    caip2: str
    asset: str
    display_name: str
    source: str
    scheme: str = "exact"


EVM_PAYMENT_OPTIONS: dict[str, PaymentNetworkOption] = {
    "base": PaymentNetworkOption(
        caip2=BASE_MAINNET_CAIP2,
        asset=USDC_EVM_BASE,
        display_name="Base Mainnet",
        source="https://developers.circle.com/stablecoins/usdc-on-main-networks",
    ),
    "polygon": PaymentNetworkOption(
        caip2="eip155:137",
        asset=USDC_EVM_POLYGON,
        display_name="Polygon PoS",
        source="https://developers.circle.com/stablecoins/usdc-on-main-networks",
    ),
    "arbitrum": PaymentNetworkOption(
        caip2="eip155:42161",
        asset=USDC_EVM_ARBITRUM,
        display_name="Arbitrum One",
        source="https://developers.circle.com/stablecoins/usdc-on-main-networks",
    ),
    "optimism": PaymentNetworkOption(
        caip2="eip155:10",
        asset=USDC_EVM_OPTIMISM,
        display_name="Optimism",
        source="https://developers.circle.com/stablecoins/usdc-on-main-networks",
    ),
}

ALIAS_TO_OPTION_KEY: dict[str, str] = {
    "base": "base",
    "8453": "base",
    "eip155:8453": "base",
    "polygon": "polygon",
    "matic": "polygon",
    "137": "polygon",
    "eip155:137": "polygon",
    "arbitrum": "arbitrum",
    "arb": "arbitrum",
    "42161": "arbitrum",
    "eip155:42161": "arbitrum",
    "optimism": "optimism",
    "op": "optimism",
    "10": "optimism",
    "eip155:10": "optimism",
}


def parse_extra_network_tokens(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def configured_candidate_caip2() -> list[str]:
    """Networks the seller wants to offer (before facilitator filtering)."""
    out: list[str] = []
    if config.settings.revenue_network:
        from app.x402_services import primary_caip2_network

        primary = primary_caip2_network(config.settings.revenue_network)
        if primary and primary not in out:
            out.append(primary)
    elif BASE_MAINNET_CAIP2 not in out:
        out.append(BASE_MAINNET_CAIP2)

    for token in parse_extra_network_tokens(config.settings.x402_extra_networks):
        key = ALIAS_TO_OPTION_KEY.get(token, token)
        opt = EVM_PAYMENT_OPTIONS.get(key)
        if opt and opt.caip2 not in out:
            out.append(opt.caip2)
        elif token.startswith("eip155:") and token not in out:
            out.append(token)

    sol_pay = (config.settings.x402_solana_pay_to or "").strip()
    if sol_pay and SOLANA_MAINNET_CAIP2 not in out:
        out.append(SOLANA_MAINNET_CAIP2)

    if not out:
        out.append(BASE_MAINNET_CAIP2)
    return out


def option_for_caip2(caip2: str) -> PaymentNetworkOption | None:
    for opt in EVM_PAYMENT_OPTIONS.values():
        if opt.caip2 == caip2:
            return opt
    if caip2 == SOLANA_MAINNET_CAIP2:
        return PaymentNetworkOption(
            caip2=caip2,
            asset=USDC_SOLANA_MINT,
            display_name="Solana Mainnet",
            source="https://developers.circle.com/stablecoins/usdc-on-main-networks",
        )
    return None


def pay_to_for_network(caip2: str) -> str:
    if caip2 == SOLANA_MAINNET_CAIP2:
        sol = (config.settings.x402_solana_pay_to or "").strip()
        if not sol:
            raise ValueError("X402_SOLANA_PAY_TO required for Solana payment options")
        return sol
    pay = (config.settings.x402_pay_to_address or "").strip()
    if not pay:
        raise ValueError("X402_PAY_TO_ADDRESS required for EVM payment options")
    return pay


def usdc_asset_for_network(caip2: str) -> str:
    opt = option_for_caip2(caip2)
    if not opt:
        raise ValueError(f"unsupported payment network: {caip2}")
    return opt.asset


def eip712_extra_for_network(caip2: str) -> dict[str, str]:
    if caip2.startswith("solana:"):
        return {"name": "USD Coin", "version": "2"}
    return dict(EIP712_EXTRA)


def set_facilitator_settleable_override(networks: set[str] | None) -> None:
    global _facilitator_settleable_override
    _facilitator_settleable_override = networks


def facilitator_exact_networks() -> set[str]:
    """CAIP-2 networks the configured facilitator advertises for scheme ``exact``."""
    if _facilitator_settleable_override is not None:
        return set(_facilitator_settleable_override)
    from app.x402_services import _facilitator_client

    try:
        supported = _facilitator_client().get_supported()
        kinds = supported.model_dump().get("kinds", [])
    except Exception as exc:
        logger.warning("facilitator get_supported unavailable: %s", exc)
        kinds = []
    nets: set[str] = set()
    for kind in kinds:
        if not isinstance(kind, dict):
            continue
        if str(kind.get("scheme") or "").lower() != "exact":
            continue
        net = kind.get("network")
        if net:
            nets.add(str(net))
    if not nets:

        nets.add("eip155:84532")
        if _cdp_configured():
            nets.add(BASE_MAINNET_CAIP2)
    return nets


def _cdp_configured() -> bool:
    return bool(config.settings.cdp_api_key_id and config.settings.cdp_api_key_secret)


def network_is_settleable(caip2: str) -> bool:
    from app.x402_services import parse_caip2_networks, svm_available

    if caip2 not in facilitator_exact_networks():
        return False
    if caip2 == SOLANA_MAINNET_CAIP2:
        return bool((config.settings.x402_solana_pay_to or "").strip()) and svm_available()
    if caip2 == BASE_MAINNET_CAIP2:
        return _cdp_configured()
    if caip2 == "eip155:84532":
        return True
    if caip2.startswith("eip155:"):
        if not _cdp_configured():
            return False
        allowed = set(parse_caip2_networks(config.settings.cdp_networks))
        allowed.add(BASE_MAINNET_CAIP2)
        for token in parse_extra_network_tokens(config.settings.x402_extra_networks):
            key = ALIAS_TO_OPTION_KEY.get(token, token)
            opt = EVM_PAYMENT_OPTIONS.get(key)
            if opt:
                allowed.add(opt.caip2)
        return caip2 in allowed
    return False


def advertised_networks_for_seller() -> list[str]:
    """Settleable networks to embed in seller ``accepts[]``, Base tie-break preserved."""
    candidates = configured_candidate_caip2()
    settleable = [n for n in candidates if network_is_settleable(n)]
    if not settleable:
        base_only = [n for n in candidates if n == BASE_MAINNET_CAIP2]
        settleable = base_only if base_only else [BASE_MAINNET_CAIP2]
    return settleable


def advertised_networks_csv() -> str:
    return ",".join(advertised_networks_for_seller())


def catalog_for_docs() -> list[dict[str, str]]:
    """Public catalog of known USDC options (including unsettleable extras)."""
    rows: list[dict[str, str]] = []
    for caip2 in configured_candidate_caip2():
        opt = option_for_caip2(caip2)
        if not opt:
            continue
        rows.append(
            {
                "network": opt.caip2,
                "asset": opt.asset,
                "name": opt.display_name,
                "source": opt.source,
                "advertised": str(network_is_settleable(opt.caip2)).lower(),
            }
        )
    return rows


def rank_payment_requirements(requirements: list[Any]) -> list[Any]:
    from app.payment_option_usage import option_key, usage_count_snapshot

    counts = usage_count_snapshot()

    def sort_key(req: Any) -> tuple[int, int, str]:
        if isinstance(req, dict):
            net = str(req.get("network") or "")
            asset = str(req.get("asset") or "")
        else:
            net = str(getattr(req, "network", "") or "")
            asset = str(getattr(req, "asset", "") or "")
        key = option_key(net, asset)
        count = int(counts.get(key, 0))
        base_tie = 0 if net == BASE_MAINNET_CAIP2 else 1
        return (-count, base_tie, net)

    return sorted(requirements, key=sort_key)
