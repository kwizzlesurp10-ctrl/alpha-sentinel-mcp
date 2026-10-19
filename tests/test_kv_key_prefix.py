"""Shared Upstash DB: every key alpha-sentinel writes must carry its own prefix."""

from __future__ import annotations

import pytest

from app import kv_store


@pytest.fixture
def calls(monkeypatch):
    seen: list[tuple] = []

    async def fake_command(*parts):
        seen.append(parts)
        return "OK" if parts[0] == "SET" else None

    monkeypatch.setattr("app.redis_client.command", fake_command)
    return seen


@pytest.mark.asyncio
async def test_all_upstash_commands_are_prefixed(monkeypatch, calls):
    monkeypatch.delenv("KV_KEY_PREFIX", raising=False)
    store = kv_store.UpstashKvStore()
    assert await store.set_nx("x402:idem:http:t:fp", "inflight", 60)
    await store.set("x402:resp:http:t:fp", "{}", 60)
    await store.get("x402:resp:http:t:fp")
    await store.delete("x402:idem:http:t:fp")
    keys = [c[1] for c in calls]
    assert keys == [
        "alpha-sentinel:x402:idem:http:t:fp",
        "alpha-sentinel:x402:resp:http:t:fp",
        "alpha-sentinel:x402:resp:http:t:fp",
        "alpha-sentinel:x402:idem:http:t:fp",
    ]


def test_prefix_env_override_and_blank_falls_back(monkeypatch):
    monkeypatch.setenv("KV_KEY_PREFIX", "as2:")
    assert kv_store.namespaced("k") == "as2:k"
    assert kv_store.namespaced("as2:k") == "as2:k"
    monkeypatch.setenv("KV_KEY_PREFIX", "  ")
    assert kv_store.namespaced("k") == "alpha-sentinel:k"


@pytest.mark.asyncio
async def test_ping_reports_host_and_error_type(monkeypatch):
    from app import redis_client

    monkeypatch.setattr(redis_client, "_kv_url", lambda: "https://gone-db.upstash.io")
    monkeypatch.setattr(redis_client, "_kv_token", lambda: "t")

    async def boom(*parts):
        raise OSError(16, "Device or resource busy")

    monkeypatch.setattr(redis_client, "command", boom)
    out = await redis_client.ping()
    assert out["ok"] is False
    assert out["host"] == "gone-db.upstash.io"
    assert out["error_type"] == "OSError"
    assert "t" not in out.get("host", "x").replace("gone-db.upstash.io", "")
