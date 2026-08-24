"""Sentiment analysis module - Social media aggregation."""

from typing import Optional, Literal
from datetime import datetime, timedelta
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class SentimentSource:
    """Supported sentiment data sources."""
    TWITTER_X = "twitter"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    NEWS = "news"
    
    ALL = [TWITTER_X, REDDIT, TELEGRAM, NEWS]


def simulate_sentiment_from_sources(
    symbols: list[str],
    sources: list[str],
    window_minutes: int = 60
) -> dict:
    """Simulate sentiment aggregation from multiple sources.
    
    In production, this would integrate with:
    - Twitter/X API (developer tier)
    - Reddit API (pushshift or new OAuth)
    - Telegram channels (public feeds)
    - News APIs (CryptoPanic, etc.)
    
    For now, provides realistic simulation for testing.
    
    Args:
        symbols: List of crypto symbols to analyze
        sources: List of data sources to aggregate
        window_minutes: Time window for sentiment
        
    Returns:
        Aggregated sentiment scores and trends
    """
    import random
    
    # Simulate sentiment data (replace with real API calls in production)
    all_posts = []
    
    for symbol in symbols:
        for source in sources:
            # Simulate N posts per source
            num_posts = random.randint(50, 200)
            
            for i in range(num_posts):
                # Generate realistic sentiment distribution
                # ~40% positive, ~35% neutral, ~25% negative typically
                sentiment_weights = {
                    "positive": 0.40,
                    "neutral": 0.35,
                    "negative": 0.25,
                }
                
                rand_val = random.random()
                if rand_val < sentiment_weights["positive"]:
                    sentiment = "positive"
                    score = round(random.uniform(0.1, 1.0), 2)
                elif rand_val < sentiment_weights["positive"] + sentiment_weights["neutral"]:
                    sentiment = "neutral"
                    score = round(random.uniform(-0.1, 0.1), 2)
                else:
                    sentiment = "negative"
                    score = round(random.uniform(-1.0, -0.1), 2)
                
                # Add some momentum patterns
                if source == "twitter":
                    # More volatile on Twitter
                    score *= 1.2
                    
                all_posts.append({
                    "symbol": symbol,
                    "source": source,
                    "sentiment": sentiment,
                    "score": score,
                    "timestamp": (datetime.utcnow() - 
                                timedelta(minutes=random.randint(0, window_minutes))).isoformat(),
                })
    
    # Aggregate by symbol
    aggregated = {}
    
    for symbol in symbols:
        symbol_posts = [p for p in all_posts if p["symbol"] == symbol]
        
        if not symbol_posts:
            continue
        
        # Calculate average sentiment
        avg_score = sum(p["score"] for p in symbol_posts) / len(symbol_posts)
        
        # Count sentiment distribution
        sentiment_counts = {
            "positive": sum(1 for p in symbol_posts if p["sentiment"] == "positive"),
            "neutral": sum(1 for p in symbol_posts if p["sentiment"] == "neutral"),
            "negative": sum(1 for p in symbol_posts if p["sentiment"] == "negative"),
        }
        
        # Calculate momentum (rate of change over time window)
        sorted_posts = sorted(symbol_posts, key=lambda x: x["timestamp"])
        first_half_avg = sum(p["score"] for p in sorted_posts[:len(sorted_posts)//2]) / max(1, len(sorted_posts)//2)
        second_half_avg = sum(p["score"] for p in sorted_posts[len(sorted_posts)//2:]) / max(1, len(sorted_posts) - len(sorted_posts)//2)
        momentum = second_half_avg - first_half_avg
        
        # Determine overall sentiment category
        if avg_score > 0.15:
            category = "bullish"
        elif avg_score < -0.15:
            category = "bearish"
        else:
            category = "neutral"
        
        aggregated[symbol] = {
            "average_score": round(avg_score, 3),
            "category": category,
            "distribution": sentiment_counts,
            "total_posts": len(symbol_posts),
            "momentum": round(momentum, 3),
            "momentum_direction": "up" if momentum > 0.02 else "down" if momentum < -0.02 else "flat",
            "sources_analyzed": sources,
            "window_minutes": window_minutes,
        }
    
    return aggregated


async def sentiment_from_sources(
    symbols: list[str],
    sources: list[str],
    window_minutes: int = 60
) -> dict:
    """Real implementation using actual APIs.
    
    This will be replaced with real API integrations when credentials are set:
    - X API v2 (Twitter)
    - Reddit OAuth
    - Telegram public channel parsing
    
    Currently returns simulated data for development.
    """
    try:
        # Check if real credentials are configured
        if settings.x_api_key or settings.reddit_api_id:
            # TODO: Implement real API calls
            logger.warning("Production sentiment APIs not yet implemented")
            pass
        
        # Return simulated data for now
        return await simulate_sentiment_from_sources(symbols, sources, window_minutes)
        
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        raise


async def aggregate_sentiment_endpoint(
    symbols: list[str],
    sources: list[str] | None = None,
    window_minutes: int = 60
) -> dict:
    """Main endpoint wrapper for sentiment aggregation (x402-gated).
    
    Args:
        symbols: List of crypto symbols to analyze
        sources: Data sources to query (default: ["twitter", "reddit"])
        window_minutes: Time window for sentiment history
        
    Returns:
        Aggregated sentiment results
        
    Raises:
        ValueError for invalid inputs
    """
    try:
        # Validate inputs
        if not symbols:
            raise ValueError("At least one symbol required")
        if not (5 <= window_minutes <= 1440):
            raise ValueError("Window must be 5-1440 minutes")
        
        # Default sources if not specified
        if sources is None:
            sources = ["twitter", "reddit"]
        
        # Check source availability
        available_sources = []
        for source in sources:
            if source == "twitter" and not settings.x_api_key:
                logger.warning("X API key not configured, skipping twitter")
                continue
            elif source == "reddit" and not settings.reddit_api_id:
                logger.warning("Reddit API not configured, skipping reddit")
                continue
            available_sources.append(source)
        
        if not available_sources:
            available_sources = ["twitter"]  # Fallback to simulated
        
        # Get sentiment data
        sentiment_data = await sentiment_from_sources(
            symbols=symbols,
            sources=available_sources,
            window_minutes=window_minutes,
        )
        
        # Calculate aggregate across all symbols
        total_posts = sum(s["total_posts"] for s in sentiment_data.values())
        weighted_avg = sum(
            s["average_score"] * s["total_posts"] 
            for s in sentiment_data.values()
        ) / max(1, total_posts)
        
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
                },
                "by_symbol": sentiment_data,
            },
            "symbols": symbols,
            "sources_used": available_sources,
            "window_minutes": window_minutes,
            "cost_usd": float(settings.sentiment_analysis_price),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        return {
            "success": False,
            "error": str(e),
            "symbols": symbols,
        }
    except Exception as e:
        logger.error(f"Sentiment aggregation error: {e}")
        return {
            "success": False,
            "error": f"Analysis failed: {str(e)}",
            "symbols": symbols,
        }
