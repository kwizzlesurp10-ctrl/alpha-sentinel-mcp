"""Market report generation module - Comprehensive analysis synthesis."""

from typing import Optional, Literal
from datetime import datetime, timedelta
import logging

from app.config import settings
from app.intelligence.price_feed import fetch_price_from_coingecko
from app.intelligence.volatility import analyze_volatility_endpoint
from app.intelligence.sentiment import aggregate_sentiment_endpoint
from app.intelligence.risk import calculate_risk_score_endpoint

logger = logging.getLogger(__name__)


async def generate_market_report_endpoint(
    report_type: str = "daily",
    symbols: list[str] | None = None,
    format: str = "json"
) -> dict:
    """Generate comprehensive market intelligence report.
    
    Combines price data, volatility, sentiment, and risk into a single report.
    
    Report types:
    - daily: 24-hour overview with key metrics
    - weekly: 7-day trends and patterns  
    - monthly: 30-day strategic analysis
    
    Args:
        report_type: Type of report (daily/weekly/monthly)
        symbols: Coins to include (default: BTC, ETH)
        format: Output format (json/pdf)
        
    Returns:
        Comprehensive market report
        
    Raises:
        ValueError for invalid parameters
    """
    try:
        # Validate parameters
        valid_types = ["daily", "weekly", "monthly"]
        if report_type not in valid_types:
            raise ValueError(f"Report type must be one of: {valid_types}")
        
        if format not in ["json", "pdf"]:
            raise ValueError("Format must be 'json' or 'pdf'")
        
        # Default symbols
        if symbols is None:
            symbols = ["bitcoin", "ethereum"]
        
        # Calculate lookback period
        lookback_days = {"daily": 1, "weekly": 7, "monthly": 30}[report_type]
        
        # Gather all intelligence data
        intelligence_bundle = {}
        
        for symbol in symbols:
            logger.info(f"Generating report data for {symbol}...")
            
            # Fetch current price
            try:
                price_data = await fetch_price_from_coingecko(symbol)
            except Exception as e:
                logger.warning(f"Price fetch failed for {symbol}: {e}")
                price_data = {"error": str(e)}
            
            # Analyze volatility
            try:
                vol_data = await analyze_volatility_endpoint(
                    symbol=symbol,
                    window_minutes=lookback_days * 24 * 60,
                    z_threshold=settings.volatility_z_score_threshold,
                )
            except Exception as e:
                logger.warning(f"Volatility analysis failed for {symbol}: {e}")
                vol_data = {"error": str(e)}
            
            # Aggregate sentiment
            try:
                sent_data = await aggregate_sentiment_endpoint(
                    symbols=[symbol],
                    sources=["twitter", "reddit"],
                    window_minutes=lookback_days * 24 * 60,
                )
            except Exception as e:
                logger.warning(f"Sentiment analysis failed for {symbol}: {e}")
                sent_data = {"error": str(e)}
            
            # Calculate risk
            try:
                risk_data = await calculate_risk_score_endpoint(
                    symbols=[symbol],
                    include_factors=["volatility", "liquidity", "correlation"],
                )
            except Exception as e:
                logger.warning(f"Risk assessment failed for {symbol}: {e}")
                risk_data = {"error": str(e)}
            
            intelligence_bundle[symbol] = {
                "price": price_data,
                "volatility": vol_data,
                "sentiment": sent_data,
                "risk": risk_data,
            }
        
        # Generate executive summary
        exec_summary = generate_executive_summary(intelligence_bundle, report_type)
        
        # Calculate total cost
        total_cost = (
            float(settings.price_feed_price) * len(symbols) +
            float(settings.volatility_alerts_price) * len(symbols) +
            float(settings.sentiment_analysis_price) * len(symbols) +
            float(settings.risk_assessment_price) * len(symbols)
        )
        
        return {
            "success": True,
            "report": {
                "type": report_type,
                "generated_at": datetime.utcnow().isoformat(),
                "lookback_days": lookback_days,
                "symbols": symbols,
                "executive_summary": exec_summary,
                "intelligence_by_coin": intelligence_bundle,
                "recommendations": generate_recommendations(intelligence_bundle),
            },
            "metadata": {
                "total_symbols_analyzed": len(symbols),
                "cost_usd": round(total_cost, 2),
                "data_sources": ["coingecko", "twitter", "reddit"],
                "processing_time_seconds": 2.5,  # Simulated
            },
            "format_requested": format,
            "cost_usd": total_cost,
        }
        
    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        return {
            "success": False,
            "error": str(e),
            "report_type": report_type,
        }
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        return {
            "success": False,
            "error": f"Report generation failed: {str(e)}",
            "report_type": report_type,
        }


def generate_executive_summary(
    intelligence: dict,
    report_type: str
) -> dict:
    """Generate AI-readable executive summary from intelligence bundle.
    
    Creates a concise, actionable summary for downstream agents.
    """
    summary_points = []
    overall_trend = "neutral"
    
    for symbol, data in intelligence.items():
        # Extract key signals
        price_change = data.get("price", {}).get("data", {}).get("change_24h", 0)
        sentiment_cat = data.get("sentiment", {}).get("data", {}).get("overall", {}).get("sentiment", "neutral")
        risk_level = data.get("risk", {}).get("data", {}).get("individual", {}).get(symbol, {}).get("risk_level", "UNKNOWN")
        alert_level = data.get("volatility", {}).get("data", {}).get("alert_level", "NORMAL")
        
        # Build signal string
        signals = [
            f"{symbol.upper()} @${data['price']['data']['price_usd']:.2f}",
            f"{'▲' if price_change > 0 else '▼'}{abs(price_change):.2f}%",
            f"sentiment={sentiment_cat}",
            f"risk={risk_level}",
            f"volatility={alert_level}",
        ]
        
        summary_points.append(" | ".join(signals))
        
        # Determine overall trend
        if sentiment_cat == "bullish" and risk_level in ["LOW", "MEDIUM"]:
            overall_trend = max(overall_trend, "bullish", key=lambda x: ["neutral", "bearish", "bullish"].index(x))
        elif sentiment_cat == "bearish" and risk_level in ["LOW", "MEDIUM"]:
            overall_trend = max(overall_trend, "bearish", key=lambda x: ["neutral", "bearish", "bullish"].index(x))
    
    return {
        "report_type": report_type,
        "signal_count": len(summary_points),
        "key_signals": summary_points[:5],  # Top 5 signals
        "overall_market_trend": overall_trend,
        "high_risk_assets": [
            k for k, v in intelligence.items()
            if v.get("risk", {}).get("data", {}).get("individual", {}).get(k, {}).get("risk_level") == "CRITICAL"
        ],
        "actionable_opportunities": len([
            s for s in summary_points
            if "bullish" in s and "LOW" in s
        ]),
    }


def generate_recommendations(intelligence: dict) -> list[str]:
    """Generate AI-actionable recommendations from intelligence.
    
    For use by downstream agents executing trading strategies.
    """
    recommendations = []
    
    for symbol, data in intelligence.items():
        risk_data = data.get("risk", {}).get("data", {}).get("individual", {}).get(symbol, {})
        risk_level = risk_data.get("risk_level", "UNKNOWN")
        recommendations_list = risk_data.get("recommendations", [])
        
        for rec in recommendations_list[:2]:  # Top 2 recommendations per coin
            recommendations.append(f"{symbol}: {rec}")
    
    return recommendations[:10]  # Limit to top 10 across all coins
