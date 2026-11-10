"""Every paid tool advertises a non-empty Bazaar input example."""

from __future__ import annotations

import pytest

from app.tool_payment_gate import _tool_discovery_example
from app.tools_registry import PAID_TOOLS


@pytest.mark.parametrize("tool", PAID_TOOLS)
def test_discovery_example_non_empty(tool):
    assert _tool_discovery_example(tool)


def test_fetch_price_example():
    assert _tool_discovery_example("fetch_price") == {"symbol": "btc"}
