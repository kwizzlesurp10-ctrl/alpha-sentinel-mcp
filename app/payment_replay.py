"""In-memory tx replay guard (local/test fallback only)."""

from __future__ import annotations

_settled_txs: set[str] = set()


def clear() -> None:
    _settled_txs.clear()


def claim_settlement_tx(tx_hash: str | None) -> bool:
    """Return True if this tx may be used; False if already consumed (replay)."""
    if not tx_hash:
        return True
    key = str(tx_hash).strip().lower()
    if not key:
        return True
    if key in _settled_txs:
        return False
    _settled_txs.add(key)
    return True
