"""Volatility analysis module - Statistical anomaly detection."""

import math
from typing import Optional
from datetime import datetime, timedelta
import logging

from app.config import settings
from app.intelligence.price_feed import get_price_history

logger = logging.getLogger(__name__)


def calculate_z_score(prices: list[float], threshold: float) -> dict:
    """Calculate Z-score based volatility anomalies.
    
    Z-score = (price - mean) / std_dev
    
    Args:
        prices: List of price values
        threshold: Z-score threshold for anomaly detection (default 2.0σ)
        
    Returns:
        Anomaly detection results with scores and alerts
    """
    if len(prices) < 2:
        return {
            "anomalies_detected": False,
            "message": "Insufficient data points",
            "z_scores": [],
        }
    
    n = len(prices)
    mean = sum(prices) / n
    variance = sum((x - mean) ** 2 for x in prices) / (n - 1)
    std_dev = math.sqrt(variance) if variance > 0 else 0.0
    
    if std_dev == 0:
        return {
            "anomalies_detected": False,
            "message": "Zero volatility detected",
            "mean": mean,
            "std_dev": 0,
            "z_scores": [],
        }
    
    # Calculate Z-scores for each point
    z_scores = [(p - mean) / std_dev for p in prices]
    
    # Detect anomalies beyond threshold
    anomalies = [
        {"index": i, "price": p, "z_score": z}
        for i, (p, z) in enumerate(zip(prices, z_scores))
        if abs(z) > threshold
    ]
    
    # Determine alert level
    max_z = max(abs(z) for z in z_scores)
    if max_z > 3.0:
        alert_level = "CRITICAL"
    elif max_z > 2.5:
        alert_level = "HIGH"
    elif max_z > 2.0:
        alert_level = "MODERATE"
    else:
        alert_level = "NORMAL"
    
    return {
        "anomalies_detected": len(anomalies) > 0,
        "alert_level": alert_level,
        "mean": mean,
        "std_dev": std_dev,
        "threshold": threshold,
        "z_scores": z_scores[-24:],  # Last 24 points
        "anomalies": anomalies[-5:],  # Last 5 anomalies
        "data_points": n,
    }


async def analyze_volatility_endpoint(
    symbol: str,
    window_minutes: int = 60,
    z_threshold: float = 2.0
) -> dict:
    """Analyze price volatility with statistical anomaly detection.
    
    This endpoint is called AFTER x402 payment verification.
    
    Args:
        symbol: Crypto symbol
        window_minutes: Historical window for analysis (1-1440)
        z_threshold: Standard deviations for anomaly threshold (0.1-5.0)
        
    Returns:
        Volatility analysis results
        
    Raises:
        ValueError for invalid parameters
    """
    try:
        # Validate parameters
        if not (1 <= window_minutes <= 1440):
            raise ValueError("Window must be 1-1440 minutes")
        if not (0.1 <= z_threshold <= 5.0):
            raise ValueError("Z-threshold must be 0.1-5.0")
        
        # Get historical data
        # Convert minutes to days (CoinGecko API uses days)
        days = max(1, round(window_minutes / (24 * 60)))
        
        history = await get_price_history(symbol, days=days)
        prices = [point["price"] for point in history]
        
        if not prices:
            return {
                "success": False,
                "error": "No price data available",
                "symbol": symbol,
            }
        
        # Calculate volatility metrics
        volatility_metrics = calculate_z_score(prices, z_threshold)
        
        # Add price trend analysis
        if len(prices) >= 2:
            first_price = prices[0]
            last_price = prices[-1]
            price_change_pct = ((last_price - first_price) / first_price) * 100
            
            volatility_metrics["price_trend"] = {
                "first_price": first_price,
                "last_price": last_price,
                "change_usd": last_price - first_price,
                "change_pct": price_change_pct,
                "direction": "up" if price_change_pct > 0 else "down",
            }
        
        return {
            "success": True,
            "data": volatility_metrics,
            "symbol": symbol,
            "window_minutes": window_minutes,
            "threshold_used": z_threshold,
            "cost_usd": settings.volatility_alerts_price_usd,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        return {
            "success": False,
            "error": f"Invalid parameters: {str(e)}",
            "symbol": symbol,
            "window_range": "1-1440 minutes",
            "threshold_range": "0.1-5.0 σ",
        }
    except Exception as e:
        logger.error(f"Volatility analysis error: {e}")
        return {
            "success": False,
            "error": f"Analysis failed: {str(e)}",
            "symbol": symbol,
        }


def classify_volatility(alert_level: str) -> str:
    """Classify volatility level from alert string.
    
    Returns: LOW, MEDIUM, HIGH, or CRITICAL
    """
    classification_map = {
        "NORMAL": "LOW",
        "MODERATE": "MEDIUM", 
        "HIGH": "HIGH",
        "CRITICAL": "CRITICAL",
    }
    return classification_map.get(alert_level, "UNKNOWN")
