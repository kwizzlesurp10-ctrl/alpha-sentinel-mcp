"""Price feed module - CoinGecko API integration."""

import httpx
from typing import Optional
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)


SYMBOL_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "dot": "polkadot",
    "xrp": "ripple",
    "doge": "dogecoin",
    "bnb": "binancecoin",
    "avax": "avalanche-2",
    "link": "chainlink",
    "matic": "matic-network",
    "pol": "polygon-ecosystem-token",
    "wbtc": "wrapped-bitcoin",
    "ltc": "litecoin",
    "shib": "shiba-inu",
    "uni": "uniswap",
    "usdc": "usd-coin",
    "usdt": "tether",
}


def resolve_coingecko_id(symbol: str) -> str:
    """Resolve symbol or ticker to CoinGecko coin ID."""
    sym = symbol.lower().strip()
    return SYMBOL_MAP.get(sym, sym)


async def fetch_price_from_coingecko(symbol: str) -> dict:
    """Fetch real-time price from CoinGecko API.
    
    Args:
        symbol: Crypto symbol or ticker (e.g., 'btc', 'bitcoin', 'eth')
        
    Returns:
        Price data dict with symbol, price_usd, change_24h, volume
        
    Raises:
        HTTPError on API failure
    """
    coin_id = resolve_coingecko_id(symbol)
    url = f"{settings.coingecko_base_url}/simple/price"
    params = {
        "ids": coin_id,
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
        if coin_id not in data:
            raise ValueError(f"Symbol '{symbol}' (CoinGecko ID: '{coin_id}') not found on CoinGecko")
        
        price_data = data[coin_id]
        return {
            "symbol": symbol.lower(),
            "coingecko_id": coin_id,
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
    coin_id = resolve_coingecko_id(symbol)
    url = f"{settings.coingecko_base_url}/coins/{coin_id}/market_chart"
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


async def fetch_price_from_coinbase(symbol: str) -> dict:
    """Fetch spot price from Coinbase API fallback.
    
    Args:
        symbol: Crypto symbol or ticker (e.g., 'btc', 'eth')
    """
    base = symbol.upper()
    rev_map = {v: k.upper() for k, v in SYMBOL_MAP.items()}
    if symbol.lower() in rev_map:
        base = rev_map[symbol.lower()]
    url = f"https://api.coinbase.com/v2/prices/{base}-USD/spot"
    async with httpx.AsyncClient(timeout=settings.x402_http_timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        amount = float(data["data"]["amount"])
        return {
            "symbol": symbol.lower(),
            "coingecko_id": resolve_coingecko_id(symbol),
            "price_usd": amount,
            "change_24h": 0.0,
            "volume_24h": 0.0,
            "source": "coinbase_spot_fallback",
            "timestamp": datetime.utcnow().isoformat(),
        }


async def fetch_price_endpoint(symbol: str) -> dict:
    """Main endpoint wrapper for price fetching (x402-gated).
    
    This function is called AFTER payment verification via x402.
    Direct calls should go through MCP tool interface.
    
    Args:
        symbol: Crypto symbol
        
    Returns:
        Structured price response
    """
    try:
        price_data = await fetch_price_from_coingecko(symbol)
        return {
            "success": True,
            "data": price_data,
            "source": "coingecko",
            "cost_usd": settings.price_feed_price_usd,
        }
    except Exception as e:
        logger.warning(f"CoinGecko price fetch failed ({e}), attempting Coinbase fallback...")
        try:
            price_data = await fetch_price_from_coinbase(symbol)
            return {
                "success": True,
                "data": price_data,
                "source": "coinbase_fallback",
                "cost_usd": settings.price_feed_price_usd,
            }
        except Exception as cb_err:
            logger.error(f"Price fetch error on all sources: {cb_err}")
            return {
                "success": False,
                "error": f"Failed to fetch price: {str(e)} (fallback: {str(cb_err)})",
                "symbol": symbol,
                "suggestions": ["btc", "eth", "sol", "ada", "dot"],
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
    sym = symbol.lower().strip()
    return sym in SYMBOL_MAP or sym in popular_symbols
