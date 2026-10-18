"""Sentiment analysis — Fear & Greed (real) plus optional API keys."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

FEAR_GREED_URL = "https://api.alternative.me/fng/"


async def fetch_fear_greed_index() -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(FEAR_GREED_URL, params={"limit": 1, "format": "json"})
        response.raise_for_status()
        payload = response.json()
    entries = payload.get("data") or []
    if not entries:
        raise ValueError("Fear & Greed API returned no data")
    row = entries[0]
    value = int(row.get("value", 0))
    classification = str(row.get("value_classification") or "Unknown")
    if value >= 55:
        category = "bullish"
        score = min(1.0, (value - 50) / 50.0)
    elif value <= 45:
        category = "bearish"
        score = max(-1.0, (value - 50) / 50.0)
    else:
        category = "neutral"
        score = (value - 50) / 100.0
    return {
        "source": "alternative.me_fear_greed",
        "index_value": value,
        "classification": classification,
        "category": category,
        "score": round(score, 3),
        "timestamp": row.get("timestamp"),
    }


def _symbol_sentiment_from_fng(symbol: str, fng: dict) -> dict:
    return {
        "average_score": fng["score"],
        "category": fng["category"],
        "distribution": {
            "positive": 1 if fng["score"] > 0.1 else 0,
            "neutral": 1 if abs(fng["score"]) <= 0.1 else 0,
            "negative": 1 if fng["score"] < -0.1 else 0,
        },
        "total_posts": 0,
        "momentum": 0.0,
        "momentum_direction": "flat",
        "sources_analyzed": ["fear_greed_index"],
        "window_minutes": 1440,
        "macro_proxy": True,
        "symbol": symbol,
        "fear_greed": fng,
    }


async def sentiment_from_sources(
    symbols: list[str],
    sources: list[str],
    window_minutes: int = 60,
) -> dict:
    degraded: list[str] = []
    fng = await fetch_fear_greed_index()

    if settings.x_api_key:
        degraded.append("twitter_configured_but_not_implemented")
    if settings.reddit_api_id:
        degraded.append("reddit_configured_but_not_implemented")

    aggregated = {sym: _symbol_sentiment_from_fng(sym, fng) for sym in symbols}
    if degraded:
        for sym in symbols:
            aggregated[sym]["degraded_sources"] = degraded

    return aggregated


async def aggregate_sentiment_endpoint(
    symbols: list[str],
    sources: list[str] | None = None,
    window_minutes: int = 60,
) -> dict:
    try:
        if not symbols:
            raise ValueError("At least one symbol required")
        if not (5 <= window_minutes <= 1440):
            raise ValueError("Window must be 5-1440 minutes")

        if sources is None:
            sources = ["news"]

        try:
            sentiment_data = await sentiment_from_sources(symbols, sources, window_minutes)
        except Exception as exc:
            logger.error("Fear & Greed fetch failed: %s", exc)
            return {
                "success": False,
                "error": f"Sentiment upstream unavailable: {exc}",
                "symbols": symbols,
                "sources_requested": sources,
            }

        total_posts = sum(s.get("total_posts", 0) for s in sentiment_data.values())
        weighted_avg = sum(s["average_score"] for s in sentiment_data.values()) / max(
            1, len(sentiment_data)
        )
        overall_category = "neutral"
        if weighted_avg > 0.1:
            overall_category = "bullish"
        elif weighted_avg < -0.1:
            overall_category = "bearish"

        return {
            "success": True,
            "data": {
                "overall": {
                    "sentiment": overall_category,
                    "weighted_score": round(weighted_avg, 3),
                    "total_posts_analyzed": total_posts,
                    "method": "fear_greed_macro_proxy",
                },
                "by_symbol": sentiment_data,
            },
            "symbols": symbols,
            "sources_used": ["fear_greed_index"],
            "sources_requested": sources,
            "window_minutes": window_minutes,
            "cost_usd": settings.sentiment_analysis_price_usd,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        logger.error("Invalid parameters: %s", e)
        return {"success": False, "error": str(e), "symbols": symbols}
    except Exception as e:
        logger.error("Sentiment aggregation error: %s", e)
        return {"success": False, "error": f"Analysis failed: {e!s}", "symbols": symbols}
