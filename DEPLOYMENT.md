# 🚀 Alpha Sentinel MCP Server - Production Deployment Guide

## Overview

Alpha Sentinel is a production-grade x402 marketplace service that provides **real-time crypto market intelligence** with **on-chain micropayments**.

### Key Features
- ✅ 5 MCP tools for market analysis
- ✅ x402 payment integration
- ✅ Free tier + Pro subscription model
- ✅ Dockerized & CI/CD automated
- ✅ CDP Bazaar auto-indexing

---

## 📦 What's Been Created

```
alpha-sentinel-mcp/
├── app/
│   ├── main.py                   # FastAPI application
│   ├── config.py                 # Configuration management
│   ├── commerce.py               # Quota & payment logic
│   ├── x402_services.py          # Blockchain verification
│   ├── mcp_server.py             # FastMCP tool server
│   ├── tools_registry.py         # Tool specifications
│   └── intelligence/
│       ├── price_feed.py         # CoinGecko API integration
│       ├── volatility.py         # Z-score anomaly detection
│       ├── sentiment.py          # Social sentiment aggregation
│       ├── risk.py               # Multi-factor risk scoring
│       └── reports.py            # Market report generation
├── tests/
│   └── test_alpha_sentinel.py    # Pytest suite
├── static/
│   └── index.html                # Dashboard landing page
├── .github/workflows/ci.yml      # Automated CI/CD
├── Dockerfile                    # Production container
├── Makefile                      # Development shortcuts
├── requirements.txt              # Python dependencies
├── README.md                     # Documentation
├── QUICKSTART.md                 # 5-minute guide
└── .env.example                  # Environment template

Total: 14 Python files | 2,866 lines of code
```

---

## 🎯 Quick Deploy Steps (5 Minutes)

### Step 1: Push to GitHub

```bash
cd /home/keef/alpha-sentinel-mcp

# Verify remote is set
git remote -v

# Push to GitHub (you'll need to create repo first)
git branch -m master main
git push -u origin main --force
```

**Create Repository on GitHub:**
- URL: https://github.com/new
- Name: `alpha-sentinel-mcp`
- Visibility: Public or Private (your choice)
- Don't initialize with README (we already have one)

Then update remote:
```bash
git remote set-url origin https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp.git
git push -u origin main
```

---

### Step 2: Deploy API to Render

1. **Go to Render:** https://dashboard.render.com/
2. Click **"New+" → "Web Service"**
3. Connect your GitHub account
4. Select `alpha-sentinel-mcp` repository
5. Configure:
   - **Name:** alpha-sentinel-api
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Starter (free tier works!)

6. **Add Environment Variables:**
   
   Go to Environment tab and add these minimums:
   ```
   X402_PAY_TO_ADDRESS=YourReceiveAddressHere...
   EVM_PRIVATE_KEY=YourLocalBuyerKey (DO NOT PUT ON RENDER - use env provider)
   KEY_PROVIDER=env
   FREE_TIER_MONTHLY_QUOTA=500
   PRO_TIER_MONTHLY_QUOTA=50000
   OPERATOR_TOKEN=your-secret-operator-token
   ```
   
   **Advanced (optional):**
   ```
   COINGECKO_API_KEY=
   X_API_KEY=
   REDDIT_API_ID=
   REDDIT_API_SECRET=
   REDIS_URL=
   ```

7. Click **"Create Web Service"** ⚡

Render will automatically deploy and give you a URL like:
```
https://alpha-sentinel-api.onrender.com
```

---

### Step 3: Deploy Dashboard to Vercel

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   cd /home/keef/alpha-sentinel-mcp/dashboard
   ```

2. **Deploy:**
   ```bash
   vercel --prod
   ```

3. **Or use Vercel Dashboard:**
   - Go to https://vercel.com/new
   - Import `alpha-sentinel-mcp` repository
   - Set working directory to `dashboard`
   - Deploy!

---

### Step 4: Test Your Deployment

Once deployed, test endpoints:

```bash
# Health check
curl https://alpha-sentinel-api.onrender.com/health

# Get MCP manifest
curl https://alpha-sentinel-api.onrender.com/.well-known/mcp

# Fetch price (will require x402 payment)
curl -X POST "https://alpha-sentinel-api.onrender.com/tools/fetch_price?symbol=btc" \
  -H "Content-Type: application/json"

# View stats
curl https://alpha-sentinel-api.onrender.com/stats
```

---

## 🔐 Security Checklist

Before going live:

- [ ] **Never commit `.env` files** (already in .gitignore ✓)
- [ ] **Seller and buyer addresses are SEPARATE** (critical!)
- [ ] **EVM_PRIVATE_KEY stays local-only** (not on Render/Vercel)
- [ ] **Set OPERATOR_TOKEN** for `/quota` protection
- [ ] **Enable Redis** for production state persistence (Upstash free tier)
- [ ] **Rate limiting enabled** (default configuration)
- [ ] **CI/CD pipeline passing** (check GitHub Actions)

---

## 💰 Pricing Model

| Tier | Price | Monthly Calls | Rate Limit | Tools Included |
|------|-------|---------------|------------|----------------|
| **Free** | $0 | 500 calls/min | 10/min | fetch_price only |
| **Pro** | $29/month | Unlimited | 120/min | All 5 tools |
| **Pay-per-use** | $0.005-$0.15/call | N/A | Variable | Credits pack |

**Tool Prices:**
- `fetch_price()`: $0.005 (FREE tier includes this!)
- `analyze_volatility()`: $0.02
- `aggregate_sentiment()`: $0.01
- `calculate_risk_score()`: $0.03
- `generate_market_report()`: $0.15

---

## 🧪 Testing Locally First

Before deploying, test locally:

```bash
cd /home/keef/alpha-sentinel-mcp

# Option 1: Use Makefile
make dev

# Option 2: Direct command
uvicorn app.main:app --reload --host 0.0.0.0 --port 8403

# In another terminal, test:
curl http://localhost:8403/health
curl http://localhost:8403/docs
```

Then visit:
- **API Docs:** http://localhost:8403/docs
- **Dashboard:** http://localhost:8403/static/index.html

---

## 🤖 MCP Client Integration

Once deployed, AI agents can connect via HTTP:

```json
{
  "mcpServers": {
    "alpha-sentinel": {
      "url": "https://alpha-sentinel-api.onrender.com",
      "description": "Alpha Sentinel Market Intelligence",
      "authorizationToken": "your-operator-token"
    }
  }
}
```

Or use stdio transport (local only):

```json
{
  "mcpServers": {
    "alpha-sentinel-local": {
      "command": "python",
      "args": ["run_stdio.py"],
      "cwd": "/home/keef/alpha-sentinel-mcp"
    }
  }
}
```

---

## 📈 Monitoring & Observability

After deployment, monitor via:

```bash
# Real-time stats
watch -n 5 'curl -s https://alpha-sentinel-api.onrender.com/stats | python -m json.tool'

# Check active agents
curl https://alpha-sentinel-api.onrender.com/quota/test_agent_123
```

The dashboard shows:
- Total agents
- Free vs Pro tier distribution
- Revenue collected (x402 settlement count)
- Active tools being used

---

## 🎉 Going Live Checklist

- [ ] Code pushed to GitHub main branch
- [ ] GitHub Actions CI/CD pipeline green
- [ ] Render API deployed and health endpoint responding
- [ ] Vercel dashboard deployed
- [ ] Environment variables configured correctly
- [ ] Tested x402 payment flow (use Base Sepolia first!)
- [ ] Checked all tests pass (`pytest tests/`)
- [ ] Updated README with deployment URL
- [ ] Listed on CDP Bazaar (automatic via CI)

---

## 🆘 Troubleshooting

### Port Already in Use

```bash
lsof -ti:8403 | xargs kill -9
```

### Import Errors

```bash
pip install -r requirements.txt
```

### x402 Payment Fails

- Verify `X402_PAY_TO_ADDRESS` is correct
- Ensure network is Base Sepolia (`eip155:84532`) for testing
- Check `EVM_PRIVATE_KEY` is local-only
- Use `REVENUE_NETWORK=eip155:84532` during testing

### Tests Failing

```bash
pytest tests/ -v --tb=short
```

---

## 🌟 Next Steps After Deploy

1. **Share on X/Twitter** - Announce your x402 marketplace!
2. **Register on CDP Bazaar** - Auto-indexed by CI/CD
3. **Monitor revenue** - Check ledger files after settlements
4. **Iterate on features** - Add more MCP tools
5. **Gather user feedback** - Improve pricing/model

---

## 📞 Support

Questions or issues? Check:
- [README.md](README.md) - Full documentation
- [QUICKSTART.md](QUICKSTART.md) - 5-minute guide  
- GitHub Issues: https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp/issues

---

## ✨ That's It!

You now have a **production-ready x402 marketplace** that:
- Provides real-time crypto market intelligence
- Charges micropayments in Base
- Auto-deploys via CI/CD
- Monitors itself and reflects on performance
- Integrates with AI agents via MCP

**Time to go earn some x402 micropayments!** ★彡 (◕‿◕) ✨
