# Base Stocks Maxxing Season — Alpha Sentinel extension

**Track:** Agentic Stock Finance (research-to-portfolio over tokenized stocks)  
**Built in window:** November 5 – December 5, 2026 (see `app/stocksmaxxing/CHANGELOG.md`)

## What it is

Alpha Sentinel MCP already sells crypto market-intelligence tools for **USDC on Base** via **x402** (`eip155:8453`). This season add-on is a **research-only** layer over **Coinbase Tokenized Stocks** reference data on Base: catalog lookup, NAV vs underlying deviation, corporate-action lookup by UUID, multi-symbol research briefs, and **model portfolio / rebalance suggestions** (weights only — **no orders**).

**Not investment advice.** No trading, execution, routing, custody, or swaps. Coinbase tokenized stocks are **not offered to U.S. persons**; integrators must enforce jurisdictional restrictions.

## Built in-window (for submission form)

| Component | Location |
|-----------|----------|
| Tokenized-stock adapters (Coinbase + underlying quotes) | `app/stocksmaxxing/` |
| Six paid x402 MCP/HTTP tools | `app/tools_registry.py` (merged specs), `app/application.py` routes |
| Tests (fixture-backed) | `tests/test_stocksmaxxing.py`, `tests/fixtures/` |
| Season changelog | `app/stocksmaxxing/CHANGELOG.md` |
| This doc (demo + blurb) | `docs/stocksmaxxing.md` |

Pre-existing (reused, not counted as new stock feature): x402 settlement, payTo from `X402_PAY_TO_ADDRESS`, CDP facilitator, crypto intel tools.

## Paid tools (USDC on Base)

| Tool | Price | Purpose |
|------|-------|---------|
| `tokenized_stock_list` | $0.01 | Paginated catalog search |
| `tokenized_stock_lookup` | $0.01 | Metadata, chains, prospectus link |
| `tokenized_stock_nav_deviation` | $0.02 | NAV vs underlying spot + staleness |
| `tokenized_stock_corporate_action` | $0.02 | Corporate action by Announcement UUID |
| `tokenized_stock_research_brief` | $0.05 | Multi-symbol brief |
| `tokenized_stock_model_portfolio` | $0.08 | Suggested weights / rebalance deltas |

Unpaid previews: `GET /tools/{tool}/sample` (rate-limited).

## Data sources & env vars

| Source | Required? | Env |
|--------|-----------|-----|
| [Coinbase Tokenized Stocks API](https://api.coinbase.com/v1/tokenized-stocks) | No key | `TOKENIZED_STOCKS_API_BASE_URL` (optional override) |
| Underlying equity spot (default: Yahoo chart API) | No key | `UNDERLYING_EQUITY_PRICE_PROVIDER=yahoo` |
| Finnhub quotes (optional) | `FINNHUB_API_KEY` | `UNDERLYING_EQUITY_PRICE_PROVIDER=finnhub` |
| x402 seller | `X402_PAY_TO_ADDRESS` | USDC on Base; use configured payTo (not hardcoded) |
| CDP facilitator (mainnet settle) | `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET` | Existing Alpha Sentinel vars |

`TOKENIZED_STOCK_NAV_MAX_AGE_HOURS` (default `24`) controls NAV staleness warnings.

## Draft submission blurb

> **Alpha Sentinel — Tokenized Stock Research (Stocks Maxxing)**  
> We extended our live x402 MCP agent storefront with six paid, research-only tools for Coinbase tokenized stocks on Base. Agents pay USDC on `eip155:8453` for catalog lookup, NAV deviation vs underlying quotes, corporate-action reference, research briefs, and model portfolio weight suggestions — no trading or execution paths. Data comes from the public Tokenized Stocks API plus configurable underlying quote providers. Built Nov 5–Dec 5, 2026 in `app/stocksmaxxing/`. Demo: unpaid `/tools/*/sample` then x402-paid tool calls on Base.

## 1–2 minute Loom demo script (@buildonbase)

1. **10s — Hook:** “Alpha Sentinel now sells tokenized-stock *research* to other agents on Base via x402 — not trading.”
2. **20s — Catalog:** Browser or `curl` `GET /tools/tokenized_stock_list/sample` → show `CRCLc` in results; mention Base chain id 8453 in response.
3. **25s — Lookup + NAV:** `GET /tools/tokenized_stock_lookup/sample?symbol=CRCLc` then `GET /tools/tokenized_stock_nav_deviation/sample` → call out NAV, underlying quote, deviation %, staleness, and on-screen disclaimer fields.
4. **25s — Agent path:** Open `/.well-known/mcp` or POST `/mcp` `tools/list` → show six `tokenized_stock_*` tools; explain unpaid sample vs paid call returning **402** with USDC on Base (do **not** send a real payment on the recording unless you intend to).
5. **20s — Portfolio:** `GET /tools/tokenized_stock_model_portfolio/sample` → suggested weights + “research_only_adjustment_not_execution”.
6. **10s — Close:** “Built this month in `app/stocksmaxxing/`, settles on Base x402 USDC. Research only — tag @buildonbase.”

## Before live demo

- Set `X402_PAY_TO_ADDRESS` and CDP keys on the deployment used for the video.
- Confirm outbound HTTPS to `api.coinbase.com` and Yahoo (or configure Finnhub).
- Optional: register Builder Code and attribute a test x402 payment on Base testnet/mainnet per season guidance.
