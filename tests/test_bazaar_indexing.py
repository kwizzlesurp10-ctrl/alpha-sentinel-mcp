"""Bazaar backfill + per-tool MCP resource URLs."""

from __future__ import annotations

import base64
import json

import pytest

from app.bazaar_indexing import (
    backfill_discovery,
    bazaar_indexing_status,
    mcp_tool_resource_url,
)
from app.mcp_x402_payment import mcp_resource_url
CANONICAL_PAY_TO = "0x0d25A44f74868eCE53B305C97139CF4B62963410"


ADVERTISED = {
    "url": "https://alpha-sentinel-mcp.vercel.app/tools/fetch_price",
    "description": "Fetch price",
    "mimeType": "application/json",
    "serviceName": "Alpha Sentinel Market Intelligen",
    "tags": ["base", "intelligence"],
}
BAZAAR = {"info": {"input": {"type": "http", "method": "POST"}}, "schema": {"type": "object"}}


def test_backfill_sets_missing_resource_and_bazaar():
    payload: dict = {"x402Version": 2, "accepted": {}}
    r = backfill_discovery(payload, advertised_resource=ADVERTISED, advertised_bazaar=BAZAAR)
    assert r == {"resource": True, "bazaar": True}
    assert payload["resource"] == ADVERTISED
    assert payload["extensions"]["bazaar"] == BAZAAR


def test_backfill_replaces_foreign_or_altered_resource():
    payload = {
        "resource": {"url": "https://attacker.example/x", "serviceName": "Evil"},
        "extensions": {"other": 1},
    }
    r = backfill_discovery(payload, advertised_resource=ADVERTISED, advertised_bazaar=BAZAAR)
    assert r["resource"] is True and r["bazaar"] is True
    assert payload["resource"] == ADVERTISED
    assert payload["extensions"]["other"] == 1
    assert payload["extensions"]["bazaar"] == BAZAAR


def test_backfill_leaves_byte_equal_echo_alone():
    payload = {
        "resource": dict(ADVERTISED),
        "extensions": {"bazaar": json.loads(json.dumps(BAZAAR)), "other": 1},
    }
    r = backfill_discovery(payload, advertised_resource=ADVERTISED, advertised_bazaar=BAZAAR)
    assert r == {"resource": False, "bazaar": False}
    assert payload["extensions"]["other"] == 1


def test_indexing_status_from_header_and_body():
    hdr = base64.b64encode(json.dumps({"bazaar": {"status": "processing"}}).encode()).decode()
    assert bazaar_indexing_status(extension_responses_header=hdr)["status"] == "processing"
    assert (
        bazaar_indexing_status(
            settle_body={"extensions": {"bazaar": {"status": "rejected", "rejectedReason": "bad"}}}
        )["rejectedReason"]
        == "bad"
    )
    assert bazaar_indexing_status(settle_body={"success": True})["status"] == "not_reported"


def test_mcp_tool_resource_urls_are_per_tool():
    assert mcp_tool_resource_url("https://alpha-sentinel-mcp.vercel.app", "fetch_price").endswith(
        "/tools/fetch_price"
    )
    assert mcp_resource_url("fetch_price") != mcp_resource_url("analyze_volatility")
    assert mcp_resource_url("fetch_price").endswith("/tools/fetch_price")
    assert mcp_resource_url().endswith("/mcp")


@pytest.mark.asyncio
async def test_verify_and_settle_applies_backfill(monkeypatch):
    from app import x402_services
    from app.models import VerifyPaymentInput

    class FakePayload:
        def __init__(self):
            self.resource = None
            self.extensions = None
            self.x402_version = 2
            self.payload = {}
            self.accepted = {}

    payload = FakePayload()
    calls: list = []

    class FakeSettle:
        def model_dump(self):
            return {
                "success": True,
                "transaction": "0xabc",
                "network": "eip155:8453",
                "payer": "0x1",
                "extension_responses": {"bazaar": {"status": "processing"}},
            }

        extension_responses = {"bazaar": {"status": "processing"}}

    class FakeVerify:
        is_valid = True
        invalid_reason = None

    class FakeServer:
        async def verify_payment(self, p, r):
            return FakeVerify()

        async def settle_payment(self, p, r):
            calls.append(("settle", getattr(p, "resource", None), getattr(p, "extensions", None)))
            return FakeSettle()

    pr = {
        "x402Version": 2,
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "amount": "5000",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "payTo": CANONICAL_PAY_TO,
                "maxTimeoutSeconds": 300,
                "extra": {"name": "USD Coin", "version": "2"},
            }
        ],
        "resource": ADVERTISED,
        "extensions": {"bazaar": BAZAAR},
    }
    header = base64.b64encode(json.dumps(pr).encode()).decode()

    monkeypatch.setattr(
        x402_services,
        "_decode_payment_inputs",
        lambda sig, req: (payload, object()),
    )
    monkeypatch.setattr(x402_services, "_network_of", lambda r: "eip155:8453")
    monkeypatch.setattr(x402_services, "_resource_server", lambda n: FakeServer())
    monkeypatch.setattr(x402_services, "_facilitator_url_for", lambda n: "https://fac")

    result = await x402_services._verify_and_settle_payment(
        VerifyPaymentInput(payment_signature="sig", payment_required=header)
    )
    assert result["payment_settled"] is True
    assert result["discovery_backfilled"] == {"resource": True, "bazaar": True}
    assert result["bazaar_indexing"]["status"] == "processing"
    assert calls and calls[0][1] is not None
