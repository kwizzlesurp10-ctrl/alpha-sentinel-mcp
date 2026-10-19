"""Refuse retired / wrong seller receive addresses.

Canonical production payTo is Keith's Base USDC receive wallet
``0x0d25A44f74868eCE53B305C97139CF4B62963410``. The addresses below were used
in earlier experiments and must never appear in a live PAYMENT-REQUIRED.
"""

from __future__ import annotations

# Lowercase for comparison. Do not reintroduce these anywhere in challenges.
RETIRED_PAY_TO: frozenset[str] = frozenset(
    {
        "0xab745e5f576667037696e78ba7da28e193e4423d",
        "0x05e1720bb82f86b5bc7940a99fdc702e32256357",
    }
)

CANONICAL_PAY_TO = "0x0d25A44f74868eCE53B305C97139CF4B62963410"


def normalize_pay_to(addr: str | None) -> str | None:
    if not addr:
        return None
    cleaned = addr.strip()
    if not cleaned:
        return None
    return cleaned.lower()


def is_retired_pay_to(addr: str | None) -> bool:
    n = normalize_pay_to(addr)
    return bool(n and n in RETIRED_PAY_TO)


def assert_pay_to_allowed(addr: str | None) -> None:
    """Raise ValueError when *addr* is a retired seller wallet."""
    if is_retired_pay_to(addr):
        raise ValueError(
            f"X402_PAY_TO_ADDRESS {addr!r} is a retired seller wallet and must not "
            f"be used. Set it to {CANONICAL_PAY_TO}."
        )
