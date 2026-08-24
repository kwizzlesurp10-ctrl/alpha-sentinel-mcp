import json
from typing import Any, Dict, Optional
import os
from datetime import datetime
from fastapi import HTTPException

# Serverless runtime imports
from app.config import settings
from app.commerce import QuotaManager
from app.x402_services import X402Service
from app.intelligence.price_feed import PriceFetcher
from app.intelligence.volatility import VolatilityAnalyzer
from app.intelligence.sentiment import SentimentAggregator
from app.intelligence.risk import RiskScorer
from app.intelligence.reports import ReportGenerator

async def handle_health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "alpha-sentinel-api",
        "version": "1.0.0"
    }

async def handle_mcp_manifest():
    """Serve MCP manifest at /.well-known/mcp"""
    # Return simplified MCP config (you'll want to export this properly)
    return {
        "name": "alpha-sentinel-mcp",
        "description": "Market intelligence and analytics tools",
        "tools": [
            {
                "name": "fetch_price",
                "description": "Get current crypto prices",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Crypto symbol (e.g., btc)"}
                    },
                    "required": ["symbol"]
                }
            }
            # Add other tools...
        ]
    }

def get_volatility_interpretation(z_score: float) -> str:
    """Interpret z-score value"""
    if abs(z_score) > 3:
        return "Extreme anomaly detected"
    elif abs(z_score) > 2:
        return "Significant volatility"
    elif abs(z_score) > 1:
        return "Moderate deviation"
    else:
        return "Normal trading range"

def classify_risk(score: float) -> str:
    """Classify risk level based on score (0-10 scale)"""
    if score < 2:
        return "LOW"
    elif score < 4:
        return "MEDIUM"
    elif score < 6:
        return "MODERATE"
    elif score < 8:
        return "HIGH"
    else:
        return "EXTREME"
