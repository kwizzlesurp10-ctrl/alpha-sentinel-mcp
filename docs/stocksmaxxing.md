# Base Stocks Maxxing Season — Alpha Sentinel extension

**Track:** Agentic Stock Finance (research-to-portfolio over tokenized stocks)  
**Built in window:** November 5 – December 5, 2026 (see `app/stocksmaxxing/CHANGELOG.md`)

## What it is

Alpha Sentinel MCP sells **research-only** tokenized-stock intelligence for **USDC on Base** via **x402** (`eip155:8453`). Season highlights:

1. **Proof-of-Research receipts** — every paid `tokenized_stock_research_brief` returns a canonical JSON hash + metadata; **Seal on Base** anchors the hash via a minimal `ResearchReceiptRegistry` contract; **public verify** recomputes the hash and reads `sealedAt` onchain.
2. **Peg-Gap Radar** — onchain DEX price (GeckoTerminal on Base) vs underlying reference, % gap, configurable alerts; paid MCP tool + live dashboard at `/stocksmaxxing/peg-gap`.

**Not investment advice.** No trading, execution, routing, custody, or swaps.

## Built in-window (for submission form)

| Component | Location |
|-----------|----------|
| Tokenized-stock adapters | `app/stocksmaxxing/` |
| Proof-of-Research hashing + seal/verify | `research_receipt.py`, `seal_registry.py`, `verify.py` |
| Peg-Gap Radar + dashboard | `peg_gap.py`, `onchain_price.py`, `static/stocksmaxxing/peg-gap.html` |
| Minimal seal contract (source) | `app/stocksmaxxing/contracts/ResearchReceiptRegistry.sol` |
| Eight paid x402 tools | `app/stocksmaxxing/registry.py` |
| Track-record hook (future) | `track_record.py` |
| Tests | `tests/test_stocksmaxxing.py`, `tests/test_research_receipt.py` |

## Paid tools (USDC on Base)

| Tool | Price | Purpose |
|------|-------|---------|
| `tokenized_stock_list` | $0.01 | Catalog search |
| `tokenized_stock_lookup` | $0.01 | Metadata / prospectus |
| `tokenized_stock_nav_deviation` | $0.02 | NAV vs underlying |
| `tokenized_stock_corporate_action` | $0.02 | Corporate action UUID |
| `tokenized_stock_research_brief` | $0.05 | Brief + **Proof-of-Research receipt** |
| `tokenized_stock_seal_receipt` | $0.03 | Seal hash on Base (unsigned tx by default) |
| `tokenized_stock_peg_gap_radar` | $0.03 | Peg-gap rows (chart-ready JSON) |
| `tokenized_stock_model_portfolio` | $0.08 | Model weights only |

**Free (rate-limited):** `/stocksmaxxing/verify-receipt`, `/stocksmaxxing/api/peg-gap`, `/stocksmaxxing/peg-gap` UI, `/tools/*/sample`.

## Proof-of-Research (headline)

### Canonical hash

Receipt covers: brief sections, `data_sources`, `generated_at`, `proof_of_research_version`, `tool_suite_version`. Serialized as **canonical JSON** (sorted keys, minimal separators) → **SHA-256** → `content_hash` (`0x…`).

### Seal on Base

- **Contract:** `ResearchReceiptRegistry` — `seal(bytes32 contentHash, bytes32 briefId)` writes `sealedAt[contentHash]` and emits `ResearchSealed`.
- **Default chain:** **Base Sepolia** (`STOCKSMAXXING_SEAL_CHAIN=base-sepolia`, chain id `84532`).
- **Mainnet:** only if `STOCKSMAXXING_SEAL_ALLOW_MAINNET=true` (off by default).
- **Default behavior:** returns **unsigned calldata** (`STOCKSMAXXING_SEAL_SUBMIT=false`). Cloud agents must **not** broadcast mainnet txs.
- **Optional broadcast:** `STOCKSMAXXING_SEAL_SUBMIT=true` + `STOCKSMAXXING_SEAL_PRIVATE_KEY` (Sepolia test key only for demo).

### Verify

`POST /stocksmaxxing/verify-receipt` with `canonical_attestation` + optional `content_hash` → recomputes hash, reads `sealedAt` from `RESEARCH_RECEIPT_REGISTRY_ADDRESS` when set.

### Future track record

`enqueue_receipt_for_track_record()` in `track_record.py` is a no-op hook for correlating sealed briefs with later outcomes.

## Peg-Gap Radar

- **Onchain price:** [GeckoTerminal](https://api.geckoterminal.com) `networks/base/tokens/{contract}` (`ONCHAIN_PRICE_PROVIDER=geckoterminal`, no key).
- **Reference:** underlying spot (Yahoo default) or `nav_price` when underlying unavailable.
- **Alerts:** `peg_gap_alert` when `|gap_pct| >= alert_threshold_pct`.
- **UI:** [/stocksmaxxing/peg-gap](/stocksmaxxing/peg-gap) → `/stocksmaxxing/api/peg-gap`.

## Data sources & env vars

| Source | Env |
|--------|-----|
| Coinbase Tokenized Stocks API | `TOKENIZED_STOCKS_API_BASE_URL` (optional) |
| Underlying spot | `UNDERLYING_EQUITY_PRICE_PROVIDER`, `FINNHUB_API_KEY` (optional) |
| Onchain DEX price | `ONCHAIN_PRICE_PROVIDER=geckoterminal` |
| x402 seller | `X402_PAY_TO_ADDRESS` |
| Seal registry (deploy on Sepolia) | `RESEARCH_RECEIPT_REGISTRY_ADDRESS` |
| Seal chain | `STOCKSMAXXING_SEAL_CHAIN=base-sepolia` |
| Seal RPC | `STOCKSMAXXING_SEAL_RPC_URL` (default Sepolia Base RPC) |
| Allow mainnet seal | `STOCKSMAXXING_SEAL_ALLOW_MAINNET` (default false) |
| Submit seal tx | `STOCKSMAXXING_SEAL_SUBMIT`, `STOCKSMAXXING_SEAL_PRIVATE_KEY` |
| Gas knobs | `STOCKSMAXXING_SEAL_GAS_LIMIT`, `STOCKSMAXXING_SEAL_MAX_FEE_GWEI`, `STOCKSMAXXING_SEAL_PRIORITY_FEE_GWEI` |
| Peg-gap default threshold | `PEG_GAP_DEFAULT_ALERT_THRESHOLD_PCT` |

Deploy registry (one-time, operator):

```bash
# Deploy ResearchReceiptRegistry.sol on Base Sepolia (Foundry/Hardhat), then:
export RESEARCH_RECEIPT_REGISTRY_ADDRESS=0xYourRegistry
export STOCKSMAXXING_SEAL_CHAIN=base-sepolia
# Optional demo broadcast (test wallet only):
export STOCKSMAXXING_SEAL_SUBMIT=true
export STOCKSMAXXING_SEAL_PRIVATE_KEY=0x...
```

## Draft submission blurb

> **Alpha Sentinel — Proof-of-Research + Peg-Gap Radar (Stocks Maxxing)**  
> We extended our x402 MCP storefront with research-only tokenized stock tools on Base: multi-symbol briefs that ship **verifiable Proof-of-Research receipts** (canonical hash + optional **Seal on Base** via `ResearchReceiptRegistry` on Sepolia by default), public **verify-receipt**, and **Peg-Gap Radar** (onchain DEX vs underlying reference with a live dashboard). Agents pay USDC on Base; no trading paths. Built Nov 5–Dec 5, 2026 in `app/stocksmaxxing/`.

## 1–2 minute Loom demo script (@buildonbase)

1. **10s — Hook:** “Paid agent research on tokenized stocks — x402 USDC on Base — with **onchain Proof-of-Research**, not trading.”
2. **15s — x402 brief:** Show unpaid sample vs **402** on `POST /tools/tokenized_stock_research_brief` (or MCP `tools/call`); mention payTo from env, USDC `eip155:8453`.
3. **25s — Proof-of-Research:** Paid brief response → expand `proof_of_research_receipt` (`content_hash`, `canonical_attestation`, versions).
4. **20s — Seal:** `POST /tools/tokenized_stock_seal_receipt` with that `content_hash` → show `prepared_unsigned` calldata on **Base Sepolia** (or `submitted` if registry + test wallet configured).
5. **15s — Verify:** `POST /stocksmaxxing/verify-receipt` with same attestation → `hash_matches_payload` + `onchain_match` after seal confirms.
6. **20s — Peg-Gap Radar:** Open `/stocksmaxxing/peg-gap` → threshold alerts; mention paid `tokenized_stock_peg_gap_radar` for full JSON.
7. **5s — Close:** Research only, built in `app/stocksmaxxing/`, tag @buildonbase.

## Before live demo

- `X402_PAY_TO_ADDRESS` + CDP keys for paid tool 402/settlement demo.
- Deploy `ResearchReceiptRegistry` on **Base Sepolia** and set `RESEARCH_RECEIPT_REGISTRY_ADDRESS`.
- Outbound HTTPS: Coinbase, Yahoo, GeckoTerminal.
- Do **not** enable mainnet seal unless you explicitly want it (`STOCKSMAXXING_SEAL_ALLOW_MAINNET`).
