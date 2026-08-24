# 🚀 Alpha Sentinel MCP - Vercel Deployment Guide

**Status:** ✅ **Ready to Deploy!** (◕‿◕) ✨  
**Repository:** https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp

---

## ⚡ Quick Deploy (3 Steps)

### 1️⃣ Go to Vercel
Visit: https://vercel.com/new

### 2️⃣ Import Repository
- Click **"Import Git Repository"**
- Find/select `alpha-sentinel-mcp`
- Click **Import**

### 3️⃣ Configure & Deploy

**Framework Preset:** `Other`  
**Root Directory:** `/` (leave default)  

**Build Command:**
```bash
pnpm --prefix dashboard install && pnpm --prefix dashboard run build
```

**Output Directory:** `dashboard/dist`

**Environment Variables:**
Add these in Vercel dashboard:

| Variable | Value | Description |
|----------|-------|-------------|
| `VITE_API_URL` | Leave empty (auto-detects) | Will use same domain as backend |

Click **Deploy**! 🎉

---

## 🔧 What Gets Deployed

### Dashboard UI (Vercel)
✅ **Location:** Your Vercel project root (`/`)  
✅ **Files:** React + TypeScript dashboard  
✅ **URL Pattern:** `https://your-project.vercel.app`  

**Features:**
- Real-time stats monitoring (auto-refreshes every 30s)
- Agent count display (Free vs Pro tiers)
- Active tools tracking
- Direct links to API docs and GitHub
- Professional dark theme

### Proxy Configuration
✅ The dashboard automatically proxies API calls to your backend  
✅ No CORS issues - all requests go through Vercel server-side

---

## 🔗 Backend Integration

The deployed dashboard will proxy to your backend via these patterns:

### For Render Deployment:
If your backend is at: `https://alpha-sentinel-api.onrender.com`

Set in Vercel **Project Settings → Environment Variables**:
```
VITE_API_URL=https://alpha-sentinel-api.onrender.com
```

### For Local Testing:
Dashboard will default to `http://localhost:8403` during development.

---

## 📊 Vercel Dashboard Structure

After deployment, visit your dashboard URL to see:
- Total active agents
- Free tier agent count
- Pro tier subscriber count
- List of active tools being used
- Live refresh button

### Stats Endpoint Example
The dashboard fetches from: `https://your-domain.vercel.app/stats`

This endpoint proxies to your backend's `/stats` endpoint:
```json
{
  "total_agents": 42,
  "free_tier_active": 38,
  "pro_tier_active": 4,
  "active_tools": ["fetch_price", "analyze_volatility"]
}
```

---

## 🌐 Custom Domain Setup (Optional)

1. Go to Vercel Project → **Settings → Domains**
2. Add your custom domain (e.g., `alpha-sentinel.yourdomain.com`)
3. Update DNS records as instructed
4. SSL certificate auto-provisioned!

---

## 🔒 Security Headers

The `vercel.json` includes these headers:
- ✅ `X-Content-Type-Options: nosniff`
- ✅ `X-Frame-Options: DENY`
- ✅ `X-XSS-Protection: 1; mode=block`

No additional config needed!

---

## 🔄 Continuous Deployment

**Automatic deploys on:**
- ✅ Push to `main` branch
- ✅ Pull request previews
- ✅ Manual trigger from Vercel dashboard

Just commit changes and push to GitHub! ✨

---

## 🆘 Troubleshooting

### Build Fails with "Cannot find module"
→ Install dependencies first:
```bash
cd dashboard
pnpm install
pnpm build
```

### Dashboard Shows "Failed to fetch stats"
→ Check that `VITE_API_URL` is set correctly in Vercel env vars  
→ Verify backend is accessible at that URL  
→ Check CORS settings if using different domains

### 404 on Root Path
→ Ensure `vercel.json` has correct rewrites rule  
→ Check that `dashboard/dist` contains built files

### Need to Access Backend API Docs
→ Use separate subdomain or path:  
- Dashboard: `https://mission-control.vercel.app`
- API Docs: `https://api.vercel.app/docs` (or use Render directly)

---

## 📦 Deployment Checklist

Before clicking deploy:
- [ ] Code pushed to GitHub `main` branch
- [ ] `vercel.json` present in repository root
- [ ] `dashboard/package.json` exists with build scripts
- [ ] `dashboard/tsconfig.json` configured
- [ ] `dashboard/vite.config.ts` has correct proxy settings
- [ ] Backend API deployed and accessible
- [ ] Environment variables ready (if needed)

---

## 💡 Next Steps After Deploy

1. **Test the Dashboard**
   - Visit your Vercel URL
   - Check stats are loading
   - Test refresh button
   - Verify API doc links work

2. **Update README**
   - Replace placeholder URL with your live Vercel URL
   - Add badge image showing "Deployed on Vercel"

3. **Monitor Performance**
   - Check Vercel Analytics tab
   - Monitor error logs
   - Track deployment times

4. **Share Launch** 🎉
   - Announce on X/Twitter
   - Post in Discord communities
   - Share with AI developer networks
   - List on CDP Bazaar!

---

## 🌟 Bonus: Automatic API Documentation

Your dashboard can also proxy to API documentation:

Add to `vercel.json`:
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" },
    { 
      "source": "/docs", 
      "destination": "https://your-api-url.onrender.com/docs" 
    }
  ]
}
```

Then users can access both at:
- `https://your-project.vercel.app` - Dashboard
- `https://your-project.vercel.app/docs` - Swagger/OpenAPI docs

---

## 🎯 Summary

You now have:
✅ **Production-ready Vercel setup**  
✅ **Auto-deploy from GitHub**  
✅ **Proxy to backend API**  
✅ **Real-time monitoring dashboard**  
✅ **Professional dark theme UI**  

**Time to deploy and watch those micropayments roll in!** ★彡 (◕‿◕) ✨

---

*Questions? Check DEPLOYMENT.md for backend setup or README.md for full documentation!*
