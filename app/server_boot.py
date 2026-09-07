"""Seller-host boot guards and bind settings for VM/Docker/systemd."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final, Generic, Mapping, TypeVar

DEFAULT_HOST: Final[str] = "0.0.0.0"
DEFAULT_PORT: Final[int] = 8403
REFUSAL: Final[str] = (
    "REFUSING: EVM_PRIVATE_KEY must not be set on the public seller host. "
    "Keep the buyer spend key on a local workstation only. "
    "Set ALLOW_BUYER_KEY_ON_SERVER=true only for an isolated buyer worker."
)

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E


@dataclass(frozen=True)
class BindAddress:
    host: str
    port: int


def _truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def seller_boot_guard(environ: Mapping[str, str] | None = None) -> Ok[None] | Err[str]:
    env = os.environ if environ is None else environ
    key = (env.get("EVM_PRIVATE_KEY") or "").strip()
    if not key:
        return Ok(None)
    if _truthy(env.get("ALLOW_BUYER_KEY_ON_SERVER")):
        return Ok(None)
    return Err(REFUSAL)


def bind_address(environ: Mapping[str, str] | None = None) -> BindAddress:
    env = os.environ if environ is None else environ
    host = (env.get("HOST") or DEFAULT_HOST).strip() or DEFAULT_HOST
    raw_port = (env.get("PORT") or str(DEFAULT_PORT)).strip()
    try:
        port = int(raw_port)
    except ValueError:
        port = DEFAULT_PORT
    if port < 1 or port > 65535:
        port = DEFAULT_PORT
    return BindAddress(host=host, port=port)


def assert_seller_safe(environ: Mapping[str, str] | None = None) -> None:
    result = seller_boot_guard(environ)
    if isinstance(result, Err):
        raise SystemExit(result.error)
