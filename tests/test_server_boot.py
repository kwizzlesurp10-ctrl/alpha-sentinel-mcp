"""Boot guard and bind-address unit tests."""

from __future__ import annotations

import pytest

from app.server_boot import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    Err,
    Ok,
    assert_seller_safe,
    bind_address,
    seller_boot_guard,
)


def test_seller_boot_guard_ok_without_spend_key() -> None:
    result = seller_boot_guard({"HOST": "0.0.0.0", "PORT": "8403"})
    assert isinstance(result, Ok)
    assert result.value is None


def test_seller_boot_guard_refuses_spend_key() -> None:
    result = seller_boot_guard({"EVM_PRIVATE_KEY": "0xabc"})
    assert isinstance(result, Err)
    assert "EVM_PRIVATE_KEY" in result.error


def test_seller_boot_guard_allows_isolated_buyer_worker() -> None:
    result = seller_boot_guard(
        {
            "EVM_PRIVATE_KEY": "0xabc",
            "ALLOW_BUYER_KEY_ON_SERVER": "true",
        }
    )
    assert isinstance(result, Ok)


def test_assert_seller_safe_exits() -> None:
    with pytest.raises(SystemExit) as exc:
        assert_seller_safe({"EVM_PRIVATE_KEY": "0xdead"})
    assert "REFUSING" in str(exc.value)


def test_bind_address_defaults() -> None:
    addr = bind_address({})
    assert addr.host == DEFAULT_HOST
    assert addr.port == DEFAULT_PORT


def test_bind_address_honors_port_env() -> None:
    addr = bind_address({"HOST": "0.0.0.0", "PORT": "8080"})
    assert addr.host == "0.0.0.0"
    assert addr.port == 8080


def test_bind_address_rejects_garbage_port() -> None:
    addr = bind_address({"PORT": "not-a-port"})
    assert addr.port == DEFAULT_PORT
    addr = bind_address({"PORT": "99999"})
    assert addr.port == DEFAULT_PORT
