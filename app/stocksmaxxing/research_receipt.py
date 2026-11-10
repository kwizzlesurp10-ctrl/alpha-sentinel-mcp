"""Proof-of-Research receipt: canonical payload hashing and receipt envelopes."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

PROOF_OF_RESEARCH_VERSION = "alpha-sentinel-por/1.0.0"
TOOL_SUITE_VERSION = "stocksmaxxing/2026.11"


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"0x{digest}"


def bytes32_from_hex(hex_str: str) -> bytes:
    h = hex_str.lower().removeprefix("0x")
    if len(h) != 64:
        raise ValueError("content_hash must be 32 bytes hex")
    return bytes.fromhex(h)


def brief_id_from_hash(content_hash: str) -> str:
    return content_hash.lower().removeprefix("0x")[:16]


def build_attestation_payload(
    *,
    symbols: list[str],
    sections: list[dict[str, Any]],
    data_sources: list[str],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "brief_type": "tokenized_stock_research",
        "symbols": sorted(symbols),
        "sections": sections,
        "data_sources": sorted(data_sources),
        "generated_at": generated_at,
        "proof_of_research_version": PROOF_OF_RESEARCH_VERSION,
        "tool_suite_version": TOOL_SUITE_VERSION,
    }


def build_proof_of_research_receipt(
    *,
    symbols: list[str],
    sections: list[dict[str, Any]],
    data_sources: list[str],
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or datetime.now(UTC).isoformat()
    attestation_body = build_attestation_payload(
        symbols=symbols,
        sections=sections,
        data_sources=data_sources,
        generated_at=ts,
    )
    content_hash = sha256_hex(attestation_body)
    brief_id = brief_id_from_hash(content_hash)
    return {
        "receipt_id": str(uuid.uuid4()),
        "brief_id": brief_id,
        "content_hash": content_hash,
        "canonical_attestation": attestation_body,
        "proof_of_research_version": PROOF_OF_RESEARCH_VERSION,
        "tool_suite_version": TOOL_SUITE_VERSION,
        "seal_hint": (
            "Call tokenized_stock_seal_receipt with content_hash and brief_id to anchor on Base "
            "(Sepolia by default). Verify via /stocksmaxxing/verify-receipt."
        ),
        "track_record_hook": "receipt_ready_for_outcome_correlation",
    }


def verify_content_hash(attestation_body: dict[str, Any], claimed_hash: str) -> bool:
    computed = sha256_hex(attestation_body)
    return computed.lower() == claimed_hash.lower()
