# Stocks Maxxing (Nov 5–Dec 5, 2026)

Built during Base Stocks Maxxing Season — Agentic Stock Finance track. Research-only; no trading.

## In-window deliverables

- `app/stocksmaxxing/` module: Coinbase Tokenized Stocks adapter, underlying equity reference prices, paid x402 MCP/HTTP tools on Base (`eip155:8453`, USDC).
- Eight paid tools: list, lookup, NAV deviation, corporate-action digest, research brief (**+ Proof-of-Research receipt**), **seal receipt**, **peg-gap radar**, model portfolio.
- **Proof-of-Research:** canonical JSON hash, `ResearchReceiptRegistry` seal on Base (Sepolia default), public `/stocksmaxxing/verify-receipt`.
- **Peg-Gap Radar:** GeckoTerminal onchain vs underlying reference; dashboard `/stocksmaxxing/peg-gap`.
- Track-record hook: `track_record.py` (placeholder).
- Tests with fixture-backed HTTP mocks (no fabricated production prices).
- `docs/stocksmaxxing.md`: season scope, demo script, submission blurb, env vars.

Pre-existing repo code (crypto intel, x402 settlement) is unchanged except wiring for the new tools.
