# Alpha Sentinel MCP Server - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Prerequisites

- Python 3.12+
- Git
- A text editor (VS Code, Neovim, etc.)

### Step 1: Clone Repository

```bash
git clone https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp
cd alpha-sentinel-mcp
```

### Step 2: Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

#### Minimum Configuration for Testing

You can start with **NO API keys** - the system will use simulated data:

```bash
# At minimum, just set your seller receive address (optional)
X402_PAY_TO_ADDRESS=0xYourReceiveAddressHere...
```

#### For Full Functionality

Add API keys as needed:

```bash
# CoinGecko (free tier works!):
COINGECKO_API_KEY=your_coingecko_key

# Twitter/X (for sentiment):
X_API_KEY=your_x_api_key

# Reddit (for sentiment):
REDDIT_API_ID=your_reddit_app_id
REDDIT_API_SECRET=your_reddit_secret
```

### Step 5: Run Locally

```bash
# Start FastAPI server on port 8403
uvicorn app.main:app --reload --host 0.0.0.0 --port 8403
```

Now visit:
- **API Docs:** http://localhost:8403/docs
- **Health Check:** http://localhost:8403/health
- **MCP Manifest:** http://localhost:8403/.well-known/mcp

---

## 🧪 Testing Without Payment

### Option A: Use MCP Stdio Transport (Recommended for Local Testing)

```bash
# In one terminal: Start MCP server
python run_stdio.py

# In Cursor/VSCode: Configure settings.json to use this stdio transport
```

### Option B: Test HTTP Endpoints Directly

```bash
# Fetch price (will work without x402 payment for testing)
curl -X POST "http://localhost:8403/tools/fetch_price?symbol=btc" \
  -H "Content-Type: application/json"
```

---

## 📊 Understanding Pricing

| Tool | Price | Free Tier? |
|------|-------|------------|
| `fetch_price()` | $0.005 | ✅ Yes |
| `analyze_volatility()` | $0.02 | ❌ Pro/Credits |
| `aggregate_sentiment()` | $0.01 | ❌ Pro/Credits |
| `calculate_risk_score()` | $0.03 | ❌ Pro/Credits |
| `generate_market_report()` | $0.15 | ❌ Pro/Credits |

**Free Tier:** 500 calls/month  
**Pro Tier:** $29/month, unlimited quota  
**Tool Credits:** $1.00 per 100 flexible credits

---

## 🛠️ MCP Integration

### For AI Agents (Cursor, Copilot, etc.)

Add to your IDE's MCP configuration:

```json
{
  "mcpServers": {
    "alpha-sentinel": {
      "command": "python",
      "args": ["run_stdio.py"],
      "description": "Alpha Sentinel Market Intelligence",
      "env": {
        "X402_PAY_TO_ADDRESS": "your_receive_address",
        "EVM_PRIVATE_KEY": "your_buyer_key_local_only"
      }
    }
  }
}
```

### Available Tools After Setup

Once configured, agents can call:

1. **`fetch_price(symbol)`** - Real-time crypto prices
2. **`analyze_volatility(symbol, window, threshold)`** - Anomaly detection
3. **`aggregate_sentiment(symbols, sources)`** - Social sentiment
4. **`calculate_risk_score(symbols)`** - Risk assessment
5. **`generate_market_report(type, symbols)`** - Comprehensive reports

---

## 🐳 Docker Deployment

### Build & Run Locally

```bash
docker build -t alpha-sentinel-mcp .
docker run -p 8403:8403 \
  -e X402_PAY_TO_ADDRESS=$PAY_TO \
  -e EVM_PRIVATE_KEY=$BUYER_KEY \
  alpha-sentinel-mcp
```

### Production with Render

1. Push to GitHub
2. Import repository in Render.com
3. Add environment variables from `.env.example`
4. Deploy!

---

## 🧪 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx-test

# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=app --cov-report=html

# Open coverage report
open htmlcov/index.html
```

---

## 🔒 Security Checklist

- ✅ Never commit `.env` files
- ✅ Seller and buyer addresses must be SEPARATE
- ✅ Buyer key should NEVER go on render/vercel
- ✅ Use Redis for production state persistence
- ✅ Enable operator token for /quota protection
- ✅ Set up rate limiting per agent_id

---

## 📈 Next Steps

1. **Test Locally** - Verify endpoints work with mocked data
2. **Add API Keys** - Enable real-time data
3. **Configure x402** - Set up seller/buyer wallets
4. **Run Tests** - Ensure everything passes
5. **Deploy** - Push to Render/Vercel
6. **Register on Bazaar** - Auto-index via CI/CD

---

## 🆘 Troubleshooting

### Port Already in Use

```bash
# Kill process on port 8403
lsof -ti:8403 | xargs kill -9
```

### Import Errors

```bash
# Ensure virtualenv is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### x402 Payment Not Working

- Verify `X402_PAY_TO_ADDRESS` is set correctly
- Check `EVM_PRIVATE_KEY` is local-only (not on Render)
- Use Base Sepolia (`eip155:84532`) for testing first

---

## 🎉 You're Ready!

Start building market intelligence agents that earn on-chain revenue! ✨

Questions? Check out:
- [Full Documentation](docs/)
- [User Guide](docs/USER-GUIDE.md)
- [Setup Instructions](docs/SETUP.md)
