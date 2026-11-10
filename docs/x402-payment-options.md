# Multi-option x402 payments (USDC)

Paid HTTP tools and MCP tools return x402 **402** challenges whose `accepts[]` array lists several **USDC** payment options at the same price. Buyers pick a rail; verification and settlement use the matching network, asset, `payTo`, and amount.

## Default behavior

With no extra configuration, behavior matches single-rail Base mainnet:

| Field | Value |
|-------|--------|
| Network (CAIP-2) | `eip155:8453` (Base) |
| Asset | USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| Pay-to | `X402_PAY_TO_ADDRESS` |

Source for Circle USDC contract addresses: [USDC on main networks](https://developers.circle.com/stablecoins/usdc-on-main-networks).

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `X402_PAY_TO_ADDRESS` | **yes** (EVM) | Seller USDC receive address on EVM chains (Base default) |
| `X402_EXTRA_NETWORKS` | no | Comma-separated list of extra EVM rails, e.g. `polygon,arbitrum,optimism` or CAIP-2 ids |
| `X402_SOLANA_PAY_TO` | no | When set, advertises Solana mainnet USDC (`solana:mainnet`) with this recipient |
| `CDP_API_KEY_ID` / `CDP_API_KEY_SECRET` | **yes** for mainnet settlement | Coinbase CDP x402 facilitator |
| `CDP_NETWORKS` | recommended | CAIP-2 list the facilitator should settle (include extras you enable) |

**Stablecoins only** — no volatile assets and no price oracles.

### Supported extra EVM networks (native USDC)

| Alias | CAIP-2 | USDC contract |
|-------|--------|-------------|
| `polygon` | `eip155:137` | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |
| `arbitrum` | `eip155:42161` | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` |
| `optimism` | `eip155:10` | `0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85` |

Solana USDC is only advertised when `X402_SOLANA_PAY_TO` is set. The server never invents a Solana address.

## Facilitator gating

A network appears in `accepts[]` only if the **configured facilitator** reports `exact` scheme support for that CAIP-2 id **and** settlement is available (CDP credentials for EVM mainnets). Rails the facilitator cannot settle are **not** advertised.

## Usage tracking and ranking

After each successful settlement, the server records `(network, asset)` counts (no additional buyer PII). Counts persist in Upstash/KV when configured; otherwise in-memory for dev/tests.

When building a challenge, `accepts[]` is ordered **most-used-first**. On equal counts, **Base USDC** (`eip155:8453`) is listed first (tie-break default).

### Read-only endpoints

- **HTTP:** `GET /x402/payment-options/usage`
- **MCP tool:** `payment_option_usage` (free, no payment)
