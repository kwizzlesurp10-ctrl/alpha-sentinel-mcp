"""Server-authored payment terms for paid intelligence tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.payments import USDC_BASE, tool_price_usd, usdc_atomic

BASE_SEPOLIA_USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"


@dataclass(frozen=True)
class StoredToolChallenge:
    tool_name: str
    resource_url: str
    payment_required_header: str
    min_amount_atomic: int


_tool_challenges: dict[str, StoredToolChallenge] = {}


def expected_usdc_asset(network: str) -> str:
    if network == "eip155:8453":
        return USDC_BASE
    if network == "eip155:84532":
        return BASE_SEPOLIA_USDC
    return USDC_BASE


def _normalize_address(addr: str | None) -> str:
    if not addr:
        return ""
    return str(addr).strip().lower()


def _requirement_amount_atomic(req: dict[str, Any]) -> int | None:
    amount = req.get("amount") or req.get("maxAmountRequired")
    if amount is None:
        return None
    try:
        return int(str(amount).strip())
    except (TypeError, ValueError):
        return None


def validate_tool_requirements(
    requirements: list[dict[str, Any]],
    *,
    tool_name: str,
    expected_network: str | None = None,
    expected_pay_to: str | None = None,
) -> None:
    pay_to = expected_pay_to or settings.x402_pay_to_address
    if not pay_to:
        raise ValueError("X402_PAY_TO_ADDRESS required for paid tools.")

    from app.x402_services import resolve_revenue_network

    network = expected_network or resolve_revenue_network()
    expected_asset = expected_usdc_asset(network)
    pay_norm = _normalize_address(pay_to)
    asset_norm = _normalize_address(expected_asset)
    min_atomic = int(usdc_atomic(tool_price_usd(tool_name)))

    if not requirements:
        raise ValueError("payment requirements missing accepts[]")

    for req in requirements:
        req_net = str(req.get("network") or "")
        if req_net != network:
            raise ValueError(f"payment network mismatch: expected {network}, got {req_net}")
        if _normalize_address(req.get("pay_to") or req.get("payTo")) != pay_norm:
            raise ValueError("payment pay_to does not match configured cashier")
        req_asset = _normalize_address(req.get("asset"))
        if req_asset not in (asset_norm, "usdc"):
            raise ValueError("payment asset must be USDC on the revenue network")
        amount = _requirement_amount_atomic(req)
        if amount is None or amount < min_atomic:
            raise ValueError(
                f"payment amount below minimum ({min_atomic} atomic units) for {tool_name}"
            )


def _requirements_from_header(payment_required_header: str) -> list[dict[str, Any]]:
    from x402.http import decode_payment_required_header

    pr = decode_payment_required_header(payment_required_header)
    accepts = list(getattr(pr, "accepts", []) or [])
    return [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in accepts]


def store_tool_challenge(tool_name: str, resource_url: str, built: dict[str, Any]) -> None:
    header = built.get("payment_required_header")
    if not header:
        raise ValueError("tool challenge missing payment_required_header")
    validate_tool_requirements(
        _requirements_from_header(header),
        tool_name=tool_name,
    )
    _tool_challenges[tool_name] = StoredToolChallenge(
        tool_name=tool_name,
        resource_url=resource_url,
        payment_required_header=header,
        min_amount_atomic=int(usdc_atomic(tool_price_usd(tool_name))),
    )


def clear_tool_challenges() -> None:
    _tool_challenges.clear()


def resolve_tool_authoritative_header(
    tool_name: str,
    *,
    rebuild: Any,
) -> StoredToolChallenge:
    stored = _tool_challenges.get(tool_name)
    if stored is None:
        rebuild()
        stored = _tool_challenges.get(tool_name)
    if stored is None:
        raise ValueError(f"failed to issue payment challenge for {tool_name}")
    validate_tool_requirements(
        _requirements_from_header(stored.payment_required_header),
        tool_name=tool_name,
    )
    return stored


def reject_tampered_client_header(
    tool_name: str,
    client_header: str | None,
    authoritative: StoredToolChallenge,
) -> None:
    if not client_header:
        return
    if client_header.strip() == authoritative.payment_required_header.strip():
        return
    raise ValueError(
        "tampered PAYMENT-REQUIRED: server-authored challenge required for "
        f"{tool_name}"
    )
