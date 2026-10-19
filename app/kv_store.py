"""Key-value backends for payment idempotency (Upstash REST + in-memory for tests)."""

from __future__ import annotations

import os
from typing import Protocol

from app.config import settings


class KvStore(Protocol):
    def available(self) -> bool: ...

    async def set_nx(self, key: str, value: str, ttl_seconds: int) -> bool: ...

    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    async def get(self, key: str) -> str | None: ...

    async def delete(self, key: str) -> None: ...


class InMemoryKvStore:
    """Process-local NX store (tests / local dev only)."""

    def __init__(self) -> None:
        import asyncio

        self._data: dict[str, str] = {}
        self._lock = asyncio.Lock()

    def available(self) -> bool:
        return True

    async def set_nx(self, key: str, value: str, ttl_seconds: int) -> bool:
        async with self._lock:
            if key in self._data:
                return False
            self._data[key] = value
            return True

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        async with self._lock:
            self._data[key] = value

    async def get(self, key: str) -> str | None:
        async with self._lock:
            return self._data.get(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()


DEFAULT_KEY_PREFIX = "alpha-sentinel:"


def key_prefix() -> str:
    """Namespace for every key we write (the Upstash DB is shared with x402-mcp)."""
    raw = os.environ.get("KV_KEY_PREFIX")
    prefix = DEFAULT_KEY_PREFIX if raw is None else raw.strip()
    return prefix or DEFAULT_KEY_PREFIX


def namespaced(key: str) -> str:
    prefix = key_prefix()
    return key if key.startswith(prefix) else f"{prefix}{key}"


class UpstashKvStore:
    """Upstash Redis REST — SET with NX and EX for atomic claim.

    All keys are namespaced with ``key_prefix()`` so this service never reads,
    overwrites or deletes another tenant's keys on a shared database.
    """

    def available(self) -> bool:
        from app.redis_client import kv_configured

        return kv_configured()

    async def set_nx(self, key: str, value: str, ttl_seconds: int) -> bool:
        from app.redis_client import command

        # SET key value EX ttl NX → null when not set
        result = await command("SET", namespaced(key), value, "EX", ttl_seconds, "NX")
        if result is None:
            return False
        text = str(result).upper()
        return text in ("OK", "TRUE", "1") or (text not in ("", "NULL", "NONE", "FALSE"))

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        from app.redis_client import command

        await command("SET", namespaced(key), value, "EX", ttl_seconds)

    async def get(self, key: str) -> str | None:
        from app.redis_client import command

        result = await command("GET", namespaced(key))
        if result is None:
            return None
        return str(result)

    async def delete(self, key: str) -> None:
        from app.redis_client import command

        await command("DEL", namespaced(key))


_store_override: KvStore | None = None
_memory_singleton: InMemoryKvStore | None = None


def set_store_override(store: KvStore | None) -> None:
    global _store_override
    _store_override = store


def resolve_kv_url() -> str | None:
    return (
        settings.kv_rest_api_url
        or os.environ.get("KV_REST_API_URL")
        or os.environ.get("UPSTASH_REDIS_REST_URL")
    )


def resolve_kv_token() -> str | None:
    return (
        settings.kv_rest_api_token
        or os.environ.get("KV_REST_API_TOKEN")
        or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    )


def get_store() -> KvStore:
    global _memory_singleton
    if _store_override is not None:
        return _store_override
    from app.redis_client import kv_configured

    if kv_configured():
        return UpstashKvStore()
    if _memory_singleton is None:
        _memory_singleton = InMemoryKvStore()
    return _memory_singleton


def reset_memory_singleton() -> None:
    global _memory_singleton
    if _memory_singleton is not None:
        _memory_singleton.clear()
    _memory_singleton = None
