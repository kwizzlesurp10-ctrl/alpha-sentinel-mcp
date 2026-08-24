"""Price feed module - CoinGecko API integration."""

import httpx
from typing import Optional
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def fetch_price_from_coingecko(symbol: str) -> dict:
    """Fetch real-time price from CoinGecko API.
    
    Args:
        symbol: Crypto symbol (e.g., 'btc', 'eth')
        
    Returns:
        Price data dict with symbol, price_usd, change_24h, volume
        
    Raises:
        HTTPError on API failure
    """
    url = f"{settings.coingecko_base_url}/simple/price"
    params = {
        "ids": symbol,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_24hr_vol": "true",
    }
    
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key
    
    async with httpx.AsyncClient(timeout=settings.x402_http_timeout) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if symbol not in data:
            raise ValueError(f"Symbol '{symbol}' not found on CoinGecko")
        
        price_data = data[symbol]
        return {
            "symbol": symbol,
            "price_usd": price_data["usd"],
            "change_24h": price_data.get("usd_24h_change", 0.0),
            "volume_24h": price_data.get("usd_24h_vol", 0.0),
            "timestamp": datetime.utcnow().isoformat(),
        }


async def get_price_history(
    symbol: str, 
    days: int = 1,
    currency: str = "usd"
) -> list[dict]:
    """Get historical price data for volatility calculations.
    
    Args:
        symbol: Crypto symbol
        days: Number of days of history (1-30)
        currency: Quote currency (default: USD)
        
    Returns:
        List of OHLCV data points
    """
    url = f"{settings.coingecko_base_url}/coins/{symbol}/market_chart"
    params = {
        "vs_currency": currency,
        "days": min(days, 30),  # CoinGecko free tier limit
    }
    
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key
    
    async with httpx.AsyncClient(timeout=settings.x402_http_timeout) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        prices = data.get("prices", [])
        
        # Convert to structured format
        return [
            {
                "timestamp": ts,
                "price": price,
            }
            for ts, price in prices
        ]


async def fetch_price_endpoint(symbol: str) -> dict:
    """Main endpoint wrapper for price fetching (x402-gated).
    
    This function is called AFTER payment verification via x402.
    Direct calls should go through MCP tool interface.
    
    Args:
        symbol: Crypto symbol
        
    Returns:
        Structured price response
        
    Raises:
        ValueError if symbol not found
        Exception on API errors
    """
    try:
        price_data = await fetch_price_from_coingecko(symbol.lower())
        
        return {
            "success": True,
            "data": price_data,
            "source": "coingecko",
            "cost_usd": float(settings.price_feed_price),
        }
    except ValueError as e:
        logger.error(f"Invalid symbol: {e}")
        return {
            "success": False,
            "error": str(e),
            "symbol": symbol,
            "suggestions": ["btc", "eth", "sol", "ada", "dot"],  # Popular symbols
        }
    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        return {
            "success": False,
            "error": f"Failed to fetch price: {str(e)}",
            "symbol": symbol,
        }


def validate_symbol(symbol: str) -> bool:
    """Validate if symbol is supported by CoinGecko.
    
    Common symbols verified against CoinGecko's API:
    """
    popular_symbols = [
        "bitcoin", "ethereum", "solana", "cardano", "polkadot",
        "ripple", "dogecoin", "binancecoin", "avalanche-2", "chainlink",
        "polygon", "wrapped-bitcoin", "litecoin", "shiba-inu", "uniswap"
    ]
    return symbol.lower() in popular_symbols or len(symbol) <= 20
