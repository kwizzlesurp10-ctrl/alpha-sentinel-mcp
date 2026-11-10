"""Verify Proof-of-Research receipts (recompute hash + optional onchain read)."""

from __future__ import annotations

from typing import Any

from app.stocksmaxxing.disclaimer import with_disclaimer
from app.stocksmaxxing.research_receipt import sha256_hex, verify_content_hash
from app.stocksmaxxing.seal_registry import verify_receipt_onchain


async def verify_research_receipt_endpoint(
    *,
    canonical_attestation: dict[str, Any] | None,
    content_hash: str | None,
    brief_id: str | None = None,
) -> dict[str, Any]:
    if not canonical_attestation:
        body = {
            "success": False,
            "code": "attestation_required",
            "error": "Provide canonical_attestation JSON to recompute the content hash",
        }
        return with_disclaimer(body)

    computed_hash = sha256_hex(canonical_attestation)
    claimed_hash = (content_hash or computed_hash).lower()
    hash_matches_payload = computed_hash.lower() == claimed_hash

    onchain = await verify_receipt_onchain(claimed_hash, brief_id=brief_id)

    body: dict[str, Any] = {
        "success": True,
        "hash_matches_payload": hash_matches_payload,
        "content_hash": claimed_hash,
        "computed_hash": computed_hash,
        "brief_id": brief_id or onchain.get("brief_id"),
        "onchain": onchain,
        "verified": bool(hash_matches_payload and onchain.get("onchain_match")),
        "note": (
            "verified=true requires matching canonical hash AND a non-zero sealedAt on the registry "
            "(deploy RESEARCH_RECEIPT_REGISTRY_ADDRESS on Base Sepolia for demos)."
        ),
    }
    return with_disclaimer(body)
