"""Risk assessment module - Multi-factor risk scoring."""

import logging
from datetime import datetime

from app.config import settings
from app.intelligence.volatility import classify_volatility

logger = logging.getLogger(__name__)


class RiskLevel:
    """Risk classification levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def calculate_risk_factors(
    volatility_score: float,
    liquidity_estimate: float = 0.5,  # 0-1 scale
    market_cap_tier: str = "large",   # large, mid, small, micro
    correlation_btc: float = 0.7      # Correlation with Bitcoin
) -> dict:
    """Calculate multi-factor risk score.
    
    Factors weighted as:
    - Volatility: 40% weight
    - Liquidity: 25% weight  
    - Market Cap Tier: 20% weight
    - BTC Correlation: 15% weight
    
    Args:
        volatility_score: Z-score from volatility analysis
        liquidity_estimate: 0 (illiquid) to 1 (highly liquid)
        market_cap_tier: Market cap category
        correlation_btc: Correlation coefficient with BTC (-1 to 1)
        
    Returns:
        Risk assessment with factors and overall score
    """
    # Factor scores (0 = low risk, 1 = high risk)
    
    # Volatility risk (inverse of z-score threshold safety)
    vol_risk = min(1.0, abs(volatility_score) / 3.0)
    
    # Liquidity risk (inverse - lower liquidity = higher risk)
    liquidity_risk = 1.0 - liquidity_estimate
    
    # Market cap risk
    market_cap_risks = {
        "large": 0.1,    # Top 10 coins
        "mid": 0.3,      # Top 11-100
        "small": 0.6,    # Top 101-500
        "micro": 0.9,    # <500 rank
    }
    cap_risk = market_cap_risks.get(market_cap_tier, 0.5)
    
    # Correlation risk (higher correlation = more systemic risk)
    corr_risk = abs(correlation_btc) * 0.3  # Scale to 0-0.3 range
    
    # Overall weighted score
    weights = {
        "volatility": 0.40,
        "liquidity": 0.25,
        "market_cap": 0.20,
        "correlation": 0.15,
    }
    
    overall_score = (
        vol_risk * weights["volatility"] +
        liquidity_risk * weights["liquidity"] +
        cap_risk * weights["market_cap"] +
        corr_risk * weights["correlation"]
    )
    
    # Classify risk level
    if overall_score < 0.2:
        risk_level = RiskLevel.LOW
    elif overall_score < 0.4:
        risk_level = RiskLevel.MEDIUM
    elif overall_score < 0.6:
        risk_level = RiskLevel.HIGH
    else:
        risk_level = RiskLevel.CRITICAL
    
    return {
        "overall_score": round(overall_score, 3),
        "risk_level": risk_level,
        "factors": {
            "volatility": {
                "score": round(vol_risk, 3),
                "weight": weights["volatility"],
                "input_z_score": volatility_score,
            },
            "liquidity": {
                "score": round(liquidity_risk, 3),
                "weight": weights["liquidity"],
                "estimate": liquidity_estimate,
            },
            "market_cap": {
                "score": round(cap_risk, 3),
                "weight": weights["market_cap"],
                "tier": market_cap_tier,
            },
            "correlation": {
                "score": round(corr_risk, 3),
                "weight": weights["correlation"],
                "btc_correlation": correlation_btc,
            },
        },
        "recommendations": get_risk_recommendations(risk_level, overall_score),
    }


def get_risk_recommendations(risk_level: str, score: float) -> list[str]:
    """Generate recommendations based on risk assessment.
    
    Args:
        risk_level: Risk classification
        score: Overall risk score (0-1)
        
    Returns:
        List of actionable recommendations
    """
    recommendations = []
    
    if risk_level == RiskLevel.CRITICAL:
        recommendations.extend([
            "⚠️ Extremely high risk - Consider position sizing reduction",
            "🔒 Set tight stop-losses (≤5% below entry)",
            "💡 Diversify across uncorrelated assets",
            "📊 Monitor volatility closely (15-min intervals)",
        ])
    elif risk_level == RiskLevel.HIGH:
        recommendations.extend([
            "⚡ Elevated risk - Use conservative position sizing",
            "🛡️ Implement trailing stops",
            "📉 Watch for correlation breakdown signals",
        ])
    elif risk_level == RiskLevel.MEDIUM:
        recommendations.extend([
            "⚖️ Moderate risk - Standard position sizing appropriate",
            "🔄 Rebalance portfolio quarterly",
            "📈 Track correlation with BTC trends",
        ])
    else:  # LOW
        recommendations.extend([
            "✅ Lower risk profile - Suitable for strategic allocation",
            "🎯 Focus on long-term fundamentals",
            "🏦 Consider dollar-cost averaging strategy",
        ])
    
    # Add volatility-specific advice
    if score > 0.5:
        recommendations.append("🌪️ High volatility detected - Avoid leveraged positions")
    
    return recommendations


async def calculate_risk_score_endpoint(
    symbols: list[str],
    include_factors: list[str] | None = None
) -> dict:
    """Main endpoint wrapper for risk assessment (x402-gated).
    
    Args:
        symbols: List of crypto symbols to assess
        include_factors: Specific risk factors to analyze
        
    Returns:
        Comprehensive risk assessment results
        
    Raises:
        ValueError for invalid inputs
    """
    try:
        # Validate inputs
        if not symbols:
            raise ValueError("At least one symbol required")
        
        # Default factors if not specified
        if include_factors is None:
            include_factors = ["volatility", "liquidity", "correlation"]
        
        from app.intelligence.price_feed import (
            fetch_price_from_coingecko,
            get_price_history,
        )
        from app.intelligence.volatility import calculate_z_score

        risk_assessments = {}

        for symbol in symbols:
            history = await get_price_history(symbol, days=7)
            prices = [float(p["price"]) for p in history if p.get("price")]
            vol = calculate_z_score(prices, threshold=settings.volatility_z_score_threshold)
            max_z = max((abs(z) for z in vol.get("z_scores") or [0.0]), default=0.0)

            price_row = await fetch_price_from_coingecko(symbol)
            volume = float(price_row.get("volume_24h") or 0.0)
            liquidity = min(1.0, volume / 5_000_000_000.0) if volume > 0 else 0.35

            sym = symbol.lower()
            if sym in ("bitcoin", "btc", "ethereum", "eth", "solana", "sol"):
                market_cap = "large"
            elif sym in ("cardano", "ada", "polkadot", "dot", "ripple", "xrp"):
                market_cap = "mid"
            else:
                market_cap = "small"

            btc_hist = await get_price_history("btc", days=7)
            btc_prices = [float(p["price"]) for p in btc_hist if p.get("price")]
            correlation = 0.7
            n = min(len(prices), len(btc_prices))
            if n > 2:
                a = prices[-n:]
                b = btc_prices[-n:]
                mean_a = sum(a) / n
                mean_b = sum(b) / n
                cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / (n - 1)
                var_a = sum((x - mean_a) ** 2 for x in a) / (n - 1)
                var_b = sum((y - mean_b) ** 2 for y in b) / (n - 1)
                denom = (var_a * var_b) ** 0.5
                if denom > 0:
                    correlation = max(-1.0, min(1.0, cov / denom))

            risk_data = calculate_risk_factors(
                volatility_score=max_z,
                liquidity_estimate=liquidity,
                market_cap_tier=market_cap,
                correlation_btc=float(correlation),
            )
            risk_assessments[symbol] = risk_data
        
        # Calculate portfolio-level risk (if multiple symbols)
        if len(symbols) > 1:
            avg_score = sum(
                r["overall_score"] for r in risk_assessments.values()
            ) / len(risk_assessments)
            
            portfolio_risk = calculate_risk_factors(avg_score)
        else:
            portfolio_risk = None
        
        return {
            "success": True,
            "data": {
                "individual": risk_assessments,
                "portfolio": portfolio_risk,
            },
            "symbols": symbols,
            "factors_analyzed": include_factors,
            "cost_usd": settings.risk_assessment_price_usd * len(symbols),
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
        logger.error(f"Risk calculation error: {e}")
        return {
            "success": False,
            "error": f"Analysis failed: {e!s}",
            "symbols": symbols,
        }
