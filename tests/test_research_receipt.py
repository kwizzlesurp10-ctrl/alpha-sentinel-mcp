"""Unit tests for Proof-of-Research canonical hashing."""

from __future__ import annotations

from app.stocksmaxxing.research_receipt import (
    build_attestation_payload,
    build_proof_of_research_receipt,
    sha256_hex,
    verify_content_hash,
)


def test_hash_changes_when_payload_changes():
    a = build_attestation_payload(
        symbols=["A"],
        sections=[],
        data_sources=["x"],
        generated_at="2026-01-01T00:00:00+00:00",
    )
    b = dict(a)
    b["symbols"] = ["B"]
    assert sha256_hex(a) != sha256_hex(b)


def test_receipt_envelope_fields():
    r = build_proof_of_research_receipt(
        symbols=["CRCLc"],
        sections=[{"symbol": "CRCLc"}],
        data_sources=["coinbase"],
        generated_at="2026-01-01T00:00:00+00:00",
    )
    assert verify_content_hash(r["canonical_attestation"], r["content_hash"])
