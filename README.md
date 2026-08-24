# Alpha Sentinel - Market Intelligence x402 MCP Server

⭐ **Predictive intelligence agent earning rewards on-chain!** ★

A production-grade x402 marketplace service that provides real-time crypto market monitoring, volatility alerts, and sentiment analysis as paid MCP tools for AI agents.

## 🎯 Mission

Deliver actionable, real-time market intelligence with <30s latency through micropayment-gated API endpoints and MCP tools. Success = actionable alerts with measurable ROI per call!

## 💰 Pricing Strategy

Based on x402 market research (median $0.014, ~90% under $0.10):

| Resource | Price | Quota (Pro) | Description |
|----------|-------|-------------|-------------|
| `price_feed()` | $0.005 | 5000/mo | Real-time price lookup |
| `volatility_alerts()` | $0.02 | 500/mo | Anomaly detection + thresholds |
| `sentiment_analysis()` | $0.01 | 1000/mo | Social sentiment aggregation |
| `risk_assessment()` | $0.03 | 300/mo | Multi-factor risk scoring |
| `market_report()` | $0.15 | 50/mo | Comprehensive daily report |
| **Tool Credit Pack** | $1.00 | 100 calls | Flexible credits bundle |

**Free Tier:** 50 calls/month, 5/min rate limit  
**Pro Tier:** Unlimited quota, 120/min, priority settlement

## 🛠️ MCP Tools

### Core Intelligence Tools

1. **`fetch_price()`** ⭐ Free tier included
   - Fetch current price from CoinGecko API
   - Supports: BTC, ETH, top 100 altcoins
   - Response: `{ symbol, price_usd, change_24h, volume }`

2. **`analyze_volatility()`** 
   - Detect price anomalies using Z-score statistical analysis
   - Configurable thresholds (default: 2σ)
   - Returns anomaly scores + alert levels

3. **`aggregate_sentiment()`**
   - Aggregate from X/Twitter, Reddit, Telegram sources
   - NLP-powered sentiment scoring (-1.0 to +1.0)
   - Trend detection and momentum indicators

4. **`calculate_risk_score()`**
   - Multi-factor risk assessment (volatility, liquidity, correlation)
   - Risk level: LOW/MEDIUM/HIGH/CRITICAL
   - Includes confidence intervals

5. **`generate_market_report()`**
   - Comprehensive daily/weekly/monthly reports
   - Combines all data sources
   - PDF + JSON output formats

## 📦 Paid Composite Products

- **US Rental Diligence Pack** (via city compliance integration): $1.50
  - Cross-references rental licenses, violations, tenant rights
  - Multi-property batch processing
  - Municipal open-data joins

- **Pulse Report**: $0.05
  - Base network synthesis + market metrics
  - 12-block sample depth
  - Real-time spot price integration

- **TX Decision Fee**: $0.01
  - Cheap loop-resident tier for pre-trade checks
  - Immediate feedback before mainnet transactions

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│           Alpha Sentinel MCP Server                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  [MCP Layer]                                         │
│    ├─ FastMCP Server (stdio + SSE)                  │
│    └─ Tool Registry (SSOT)                          │
│                      │                              │
│  [Commerce Layer]                                    │
│    ├─ x402 Middleware (verify+settle)               │
│    ├─ Quota Management (free/pro tiers)             │
│    ├─ Challenge Cache (sync, 10s TTL)               │
│    └─ Stripe Integration (fiat rail fallback)       │
│                      │                              │
│  [Intelligence Layer]                                │
│    ├─ Price Feed (CoinGecko API)                    │
│    ├─ Sentiment Engine (X/Reddit/NLP)               │
│    ├─ Volatility Analyzer (statistical models)      │
│    └─ Risk Calculator (ML-enhanced)                 │
│                      │                              │
│  [On-Chain Layer]                                    │
│    ├─ CDP Facilitator (Base mainnet)                │
│    ├─ Ledger (spend/revenue tracking)               │
│    └─ Swarm Agency (buy-compose-resell)             │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Redis (optional, for production)
- x402 seller credentials (separate from buyer!)
- CoinGecko API key (free tier works)

### Setup

```bash
# Clone and setup
git clone https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp
cd alpha-sentinel-mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your credentials

# Run locally
make up  # API (8403) + dashboard (5174)
```

### Environment Variables

```bash
# Seller (receive revenue)
X402_PAY_TO_ADDRESS=0xAB745e5F...  # Separate from buyer!

# Buyer (hot wallet for spending)
EVM_PRIVATE_KEY=<your_buyer_key>    # NEVER on Render!

# APIs
COINGECKO_API_KEY=<your_key>
X_API_KEY=<twitter/x_api_key>       # Optional

# Commerce
STRIPE_SECRET_KEY=<your_stripe_key>  # Optional
REDIS_URL=redis://localhost:6379     # Optional

# Network
X402_DEFAULT_NETWORK=eip155:84532    # Base Sepolia dev
CDP_API_KEY_ID=<cdp_id>              # For mainnet selling
CDP_API_KEY_SECRET=<cdp_secret>
```

## 🔧 Development

### Running Tests
```bash
# Full test suite
make test

# Specific tests
pytest tests/test_mcp_tools.py -v
pytest tests/test_commerce.py -v

# Dashboard tests
cd dashboard && pnpm vitest run
```

### Adding New MCP Tools

Follow the pattern in `app/tools_registry.py`:

1. Add tool spec to `TOOL_SPECS` list
2. Implement handler in `app/intelligence/` directory
3. Register in `app/mcp_server.py`
4. Update README with new tool table row
5. Run `scripts/capture_goal_evidence.py` to update test artifacts

**Remember:** The tool registry is the SINGLE SOURCE OF TRUTH! Touch all related files or CI will fail.

### CI/CD Pipeline

GitHub Actions runs:
- ✅ Pytest on Python 3.12
- ✅ Vitest on dashboard
- ✅ Security scans (secret detection, SAST)
- ✅ Coverage checks (>80%)
- ✅ Docker build & push

## 📊 Observability

### Metrics Endpoints
- `/stats` - Live usage statistics
- `/ledger/{name}` - Settlement history
- `/quota/{agent_id}` - Remaining quota
- `/swarm/stats` - Autonomous agency metrics

### Event Stream
Subscribe to SSE at `/events` for real-time:
- Tool execution logs
- Settlement confirmations
- Quota updates
- Swarm phase transitions

## 🔒 Security

- ✅ No private keys committed (`.env` always ignored)
- ✅ SSRF guards on all URL probes
- ✅ Rate limiting per agent_id
- ✅ Idempotency keys for settlements
- ✅ Key rotation support via `KEY_PROVIDER` seam
- ✅ Never expose exception internals in responses

**Seller vs Buyer Keys:**
- **RECEIVE ADDRESS:** Cold wallet for revenue (separate from buyer!)
- **BUYER KEY:** Hot wallet ONLY for paying upstream costs (never used for receiving)
- **NEVER put EVM_PRIVATE_KEY on Render** - local only!

|## 🌐 Deployment

**Live Dashboard:** https://alpha-sentinel-mcp.vercel.app/ (coming soon)

### Quick Deploy to Vercel

Click below or follow steps in [`DEPLOYMENT.md`](DEPLOYMENT.md):

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp&project-name=alpha-sentinel-mcp&demo-title=Alpha%20Sentinel%20Mission%20Control)

### Manual Deployment

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy dashboard
cd /home/keef/alpha-sentinel-mcp
vercel --prod
```

The dashboard will proxy API calls to your deployed backend automatically!

### Render (API)
Deploy via `render.yaml` - auto-configures:
- Web service on port 8403
- Redis instance (auto-provisioned)
- Environment variables from secure store
- Health check endpoint: `/health`

### Docker
```bash
docker build -t alpha-sentinel-mcp .
docker run -p 8403:8403 \
  -e X402_PAY_TO_ADDRESS=$PAY_TO \
  -e EVM_PRIVATE_KEY=$BUYER_KEY \
  alpha-sentinel-mcp
```

## 🤝 Swarm Agency Integration

When `SWARM_ENABLED=true`, Alpha Sentinel can:
1. **Scout** discover upstream x402 data sources
2. **Warden** enforce spend caps per `ledger/policy.json`
3. **Treasurer** pay for upstream data (sole spender role)
4. **Archivist** compose priced composites
5. **Sovereign** reprice for target LTV:CAC ≥ 3.0
6. **Merchant** list composite products

Example composite: Buy raw prices from 3 upstream → aggregate → resell as "Premium Bundle" @ 3x markup!

## 📈 Bazaar Discovery

Listed on CDP Bazaar with:
- Service name: `Alpha Sentinel Market Intelligence`
- Tags: `base,intelligence,crypto,market,x402,mcp`
- Ownership proof: signed with receive address
- Catalog URL: `https://alpha-sentinel-mcp.onrender.com/.well-known/x402`

## 🎓 Documentation

- [User Guide](docs/USER-GUIDE.md) - How to use the tools
- [Setup Instructions](docs/SETUP.md) - Local + deployment setup
- [Agent Ops](docs/agent-ops.md) - Cost-optimized operation modes
- [City Compliance](docs/CITY-NETWORK.md) - Multi-city compliance data

## 🏆 Success Metrics

- **Alert Latency:** <30s end-to-end
- **Settlement Success:** >95% first-attempt
- **LTV:CAC Ratio:** Target ≥ 3.0
- **Margin Floor:** ≥ 50% on composites
- **Quota Utilization:** >70% pro tier conversion

## 🙏 Credits

Built by Keith (`kwizzlesurp10-ctrl`) as part of the AI Agency Factory ecosystem. Inspired by Karpathy's LLM Wiki approach to knowledge organization and x402 micropayment revolution!

Special thanks to:
- Coinbase CDP team for x402 facilitator
- FastAPI + FastMCP maintainers
- The entire open-source x402 community

## 📄 License

MIT - Free for commercial use, attribution appreciated! ★彡

---

**Ready to monetize market intelligence?**  
👉 [Deploy Now](https://vercel.com/new/clone?repo-url=https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp)  
👉 [Read User Guide](docs/USER-GUIDE.md)  
👉 [View Dashboard](https://alpha-sentinel-mcp.vercel.app/dashboard)

(◕‿◕) ✨ *Predictive intelligence, powered by on-chain economics!* ♪
