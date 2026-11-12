# Alpha Sentinel Developer Playbooks — Predictive Alpha, On-Chain Market Intelligence & x402 Agent Research

This document contains the complete Markdown technical guides corresponding to the live HTML playbooks hosted under `/docs`:

- **Documentation Hub:** [`/docs`](https://alpha-sentinel-mcp.vercel.app/docs)
- **Playbook 01:** [`/docs/automate-volatility-alerts`](https://alpha-sentinel-mcp.vercel.app/docs/automate-volatility-alerts) — *How to automate volatility alerts using Alpha Sentinel*
- **Playbook 02:** [`/docs/integrate-predictive-alpha`](https://alpha-sentinel-mcp.vercel.app/docs/integrate-predictive-alpha) — *Integrating predictive alpha into an autonomous research agent*
- **Playbook 03:** [`/docs/reduce-slippage-sentiment`](https://alpha-sentinel-mcp.vercel.app/docs/reduce-slippage-sentiment) — *Grounding agent research with real-time sentiment analysis*
- **Interactive OpenAPI Explorer:** [`/openapi`](https://alpha-sentinel-mcp.vercel.app/openapi)

---

## Tool Catalog & x402 Base Mainnet Pricing (`eip155:8453`)

| Tool Name | HTTP Path | Price (USDC) | Atomic Units (6 dec) | Primary Signal Output |
| :--- | :--- | :--- | :--- | :--- |
| `fetch_price` | `POST /tools/fetch_price` | **$0.005** (Free MCP) | `5000` | Spot price USD, 24h change %, 24h volume USD |
| `analyze_volatility` | `POST /tools/analyze_volatility` | **$0.02** | `20000` | Rolling Z-scores, anomaly indices, `NORMAL`/`MODERATE`/`HIGH`/`CRITICAL` |
| `aggregate_sentiment` | `POST /tools/aggregate_sentiment` | **$0.01** | `10000` | Polarity score (`-1.0` to `+1.0`), `bullish`/`neutral`/`bearish`, Fear & Greed |
| `calculate_risk_score` | `POST /tools/calculate_risk_score` | **$0.03** | `30000` | 4-factor risk score (`0.0`–`1.0`): Volatility 40%, Liquidity 25%, Cap 20%, BTC Corr 15% |
| `generate_market_report` | `POST /tools/generate_market_report` | **$0.15** | `150000` | Daily/weekly/monthly executive synthesis across all 4 intelligence primitives |

---

# How to automate volatility alerts using Alpha Sentinel

**Playbook 01 • Canonical URL:** `/docs/automate-volatility-alerts`  
**Primary Tool:** `analyze_volatility` (`$0.02 USDC` per call on Base `eip155:8453`)

## 1. Architecture of an Automated Volatility Sentinel

```text
[Cron / Async Loop (1m - 15m)]
       │
       ▼
POST /tools/analyze_volatility  {"symbol":"btc","window_minutes":60,"z_threshold":2.0}
       │
       ├──► HTTP 402 Payment Required (PAYMENT-REQUIRED Header, 20000 atomic USDC on Base)
       ├──► Sign EIP-3009 TransferWithAuthorization & Retry with PAYMENT-SIGNATURE Header
       ▼
HTTP 200 OK + PAYMENT-RESPONSE Receipt
       │
       ├──► NORMAL   (|Z| ≤ 2.0σ) ──► Record baseline telemetry
       ├──► MODERATE (|Z| > 2.0σ) ──► Send Discord / Slack warning webhook
       ├──► HIGH     (|Z| > 2.5σ) ──► Tighten trailing stops + Telegram page
       └──► CRITICAL (|Z| > 3.0σ) ──► ENGAGE CIRCUIT BREAKER (Halt entries, cancel resting orders)
```

## 2. Z-Score Alert Level Classification (`app/intelligence/volatility.py`)

Alpha Sentinel computes the sample mean ($\mu$) and unbiased sample standard deviation ($s$) across the lookback window (`window_minutes`: `1`–`1440`, default `60`) and assigns each observation $Z_i = (x_i - \mu)/s$:

- **`NORMAL`** ($\max |Z| \le 2.0\sigma$): Standard Gaussian regime ($95.45\%$). Keep baseline quoting/trading active.
- **`MODERATE`** ($2.0\sigma < \max |Z| \le 2.5\sigma$): Early breakout or order-book sweep. Notify Slack/Discord and widen LP spreads by 15–25 bps.
- **`HIGH`** ($2.5\sigma < \max |Z| \le 3.0\sigma$): Tail dispersion ($1.24\%$). Halve position sizing and switch to passive TWAP execution.
- **`CRITICAL`** ($\max |Z| > 3.0\sigma$): Extreme black-swan tail ($0.27\%$). Trigger automated circuit breakers immediately.

## 3. Working Python Implementation (`httpx` + x402 Payment Header)

```python
import asyncio
import os
import httpx

ALPHA_SENTINEL_URL = os.getenv("ALPHA_SENTINEL_URL", "https://alpha-sentinel-mcp.vercel.app")
PAYMENT_SIG = os.getenv("X402_PAYMENT_SIGNATURE", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")


async def poll_volatility(symbol: str = "btc", window_minutes: int = 60, z_threshold: float = 2.0) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        url = f"{ALPHA_SENTINEL_URL}/tools/analyze_volatility"
        body = {"symbol": symbol, "window_minutes": window_minutes, "z_threshold": z_threshold}
        resp = await client.post(url, json=body)

        if resp.status_code == 402:
            # Challenge returned in resp.json()["accepts"][0] for eip155:8453 ($0.02 USDC = "20000")
            headers = {"PAYMENT-SIGNATURE": PAYMENT_SIG, "X-Agent-Id": "vol-sentinel-01"}
            resp = await client.post(url, json=body, headers=headers)

        resp.raise_for_status()
        result = resp.json()
        vol = result.get("data", {})
        level = vol.get("alert_level", "NORMAL")

        if level in ("MODERATE", "HIGH", "CRITICAL") and DISCORD_WEBHOOK:
            max_z = max((abs(z) for z in vol.get("z_scores") or [0.0]), default=0.0)
            await client.post(
                DISCORD_WEBHOOK,
                json={"content": f"🚨 [{symbol.upper()}] Volatility={level} (max |Z|={max_z:.2f}σ)"},
            )
        return result
```

## 4. MCP JSON-RPC `tools/call` Example

```bash
curl -sX POST https://alpha-sentinel-mcp.vercel.app/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "vol-1",
    "method": "tools/call",
    "params": {
      "name": "analyze_volatility",
      "arguments": {"symbol": "btc", "window_minutes": 60, "z_threshold": 2.0},
      "_meta": {"x402/payment": "<BASE64_PAYMENT_SIGNATURE>"}
    }
  }'
```

---

# Integrating predictive alpha into an autonomous research agent

**Playbook 02 • Canonical URL:** `/docs/integrate-predictive-alpha`  
**Primary Tools:** `fetch_price` → `analyze_volatility` → `calculate_risk_score` → `generate_market_report`

## 1. Zero-Signup Discovery Endpoints

Autonomous agents (LangGraph, Claude MCP, Coinbase AgentKit / AgentCash, A2A) discover capabilities dynamically:
1. **`GET /.well-known/mcp.json`**: Streamable HTTP MCP endpoint (`POST /mcp`) and full JSON Schemas.
2. **`GET /.well-known/x402`**: Paid catalog, USDC asset address (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`), and Base network (`eip155:8453`).
3. **`GET /.well-known/agent-card.json`**: A2A Protocol v1.0 Agent Card for `POST /a2a` (`message/send` and `tasks/get`).

## 2. Multi-Factor Risk Score Weights (`app/intelligence/risk.py`)

`calculate_risk_score` ($0.03 USDC) synthesizes four risk dimensions into `overall_score` ($0.0$ to $1.0$) and `risk_level` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`):

- **Volatility Risk (40% weight):** $\min(1.0, |Z_{\max}| / 3.0)$
- **Liquidity Risk (25% weight):** $1.0 - \min(1.0, \text{Volume}_{24\text{h}} / \$5\text{B})$
- **Market Cap Tier (20% weight):** `large=0.1`, `mid=0.3`, `small=0.6`, `micro=0.9`
- **BTC Correlation (15% weight):** $|\rho_{\text{asset, BTC}}| \times 0.30$

### Position Sizing Rules by `risk_level`
- **`LOW` (`overall_score < 0.20`):** `1.00x` base notional allocation; standard 8–10% trailing stop.
- **`MEDIUM` (`0.20 <= overall_score < 0.40`):** `0.70x` base allocation; rebalance quarterly.
- **`HIGH` (`0.40 <= overall_score < 0.60`):** `0.35x` base allocation; spot only (no leverage), 4–5% trailing stop.
- **`CRITICAL` (`overall_score >= 0.60`):** `0.00x` new long exposure; tight stop-loss ($\le 5\%$ below entry) and deleverage.

## 3. AgentCash CLI Integration

```bash
# Discover all priced endpoints on Base
npx agentcash@latest discover https://alpha-sentinel-mcp.vercel.app

# Execute multi-factor risk assessment ($0.03 USDC settled automatically)
npx agentcash@latest fetch https://alpha-sentinel-mcp.vercel.app/tools/calculate_risk_score \
  --method POST \
  --body '{"symbols":["btc","eth","sol"],"include_factors":["volatility","liquidity","correlation"]}'
```

---

# Grounding agent research with real-time sentiment analysis

**Playbook 03 • Canonical URL:** `/docs/reduce-slippage-sentiment`  
**Primary Tools:** `aggregate_sentiment` (`$0.01 USDC`) + `analyze_volatility` (`$0.02 USDC`) + `calculate_risk_score` (`$0.03 USDC`)

## 1. Preventing Toxic Order Flow & Liquidity Thinning

Executing a large single-block swap or market order during a narrative social surge causes severe slippage because passive market makers widen spreads while retail flow sweeps the book. By spending **$0.06 USDC** across `aggregate_sentiment`, `analyze_volatility`, and `calculate_risk_score` prior to order routing, an execution agent computes an **Execution Stress Index (ESI)**:

$$\text{ESI} = 0.45 \cdot |\text{weighted\_score}| + 0.35 \cdot \min\left(1.0, \frac{|Z_{\max}|}{3.0}\right) + 0.20 \cdot r_{\text{liquidity}}$$

## 2. Dynamic Order Routing Table (Single Fill vs. TWAP/VWAP vs. Delay)

| Execution Regime | Condition | Order Slicing Strategy | Max Slippage Tolerance |
| :--- | :--- | :--- | :--- |
| **Regime A: Calm Book** | $\text{ESI} < 0.30$ and `alert_level == "NORMAL"` | Single immediate limit/IOC fill (100% notional) | `25 bps` |
| **Regime B: Moderate Momentum** | $0.30 \le \text{ESI} < 0.55$ | **TWAP (4 slices)** over 8 minutes (25% per 2m interval) | `20 bps` |
| **Regime C: Crowded Surge** | $\text{ESI} \ge 0.55$ or buying into bullish FOMO (`score > +0.35`) | **Passive TWAP/VWAP (10 slices)** over 30 minutes (`POST_ONLY`) | `15 bps` |
| **Regime D: Black Swan** | `alert_level == "CRITICAL"` aligned with extreme sentiment | **Delay Execution (15m cooldown)** or route via private RFQ | `10 bps` |

## 3. Calling `aggregate_sentiment` via HTTP & x402

```bash
curl -sX POST https://alpha-sentinel-mcp.vercel.app/tools/aggregate_sentiment \
  -H "Content-Type: application/json" \
  -H "PAYMENT-SIGNATURE: <BASE64_PAYMENT_SIGNATURE>" \
  -d '{
    "symbols": ["btc", "eth", "sol"],
    "sources": ["twitter", "reddit", "telegram", "news"],
    "window_minutes": 60
  }' | jq .
```
