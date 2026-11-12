"""Base mainnet quote tokens for peg-gap onchain pricing."""

from __future__ import annotations

USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
WETH_BASE = "0x4200000000000000000000000000000000000006"

QUOTE_ALLOWLIST = {USDC_BASE, WETH_BASE}

GECKO_USER_AGENT = "Alpha-Sentinel-PegGap/1.0 (+https://alpha-sentinel-mcp.vercel.app)"
