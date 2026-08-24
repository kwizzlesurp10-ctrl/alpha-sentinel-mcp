"""Commerce Layer - Quota, payments, and tier management."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging
import uuid

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class QuotaState:
    """User quota state."""
    agent_id: str
    tier: str  # "free" or "pro"
    remaining: int
    limit: int
    rate_limit_per_min: int
    reset_at: Optional[datetime] = None
    
    def is_exhausted(self) -> bool:
        return self.remaining <= 0
    
    def can_execute(self) -> bool:
        return not self.is_exhausted()


class CommerceLayer:
    """Manages quotas, tiers, and tool credit purchases."""
    
    def __init__(self, config):
        self.config = config
        self.quotas: dict[str, QuotaState] = {}  # In-memory (use Redis in production)
        self.stats = {
            "total_agents": 0,
            "free_active": 0,
            "pro_active": 0,
            "tool_credits_sold": 0,
            "revenue_today_usd": 0.0,
            "calls_today": 0,
            "avg_latency_ms": 0.0,
        }
        
    def get_quota(self, agent_id: str) -> QuotaState:
        """Get or initialize quota state for an agent."""
        if agent_id not in self.quotas:
            self._initialize_agent(agent_id)
        
        return self.quotas[agent_id]
    
    def _initialize_agent(self, agent_id: str):
        """Create new free tier quota for agent."""
        now = datetime.utcnow()
        reset_at = now + timedelta(days=1)
        
        self.quotas[agent_id] = QuotaState(
            agent_id=agent_id,
            tier="free",
            remaining=self.config.free_tier_monthly_quota,
            limit=self.config.free_tier_monthly_quota,
            rate_limit_per_min=self.config.free_tier_rate_limit_per_min,
            reset_at=reset_at,
        )
        
        self.stats["total_agents"] += 1
        
        logger.info(f"Initialized free tier quota for agent: {agent_id}")
    
    def upgrade_to_pro(self, agent_id: str, payment_verified: bool = True):
        """Upgrade agent to pro tier after payment verification."""
        if not payment_verified:
            raise ValueError("Payment verification required for upgrade")
        
        if agent_id not in self.quotas:
            self._initialize_agent(agent_id)
        
        quota = self.quotas[agent_id]
        quota.tier = "pro"
        quota.remaining = self.config.pro_tier_monthly_quota
        quota.limit = self.config.pro_tier_monthly_quota
        quota.rate_limit_per_min = self.config.pro_tier_rate_limit_per_min
        
        self.stats["pro_active"] += 1
        self.stats["free_active"] -= 1
        
        logger.info(f"Upgraded agent {agent_id} to PRO tier")
    
    def purchase_tool_credits(self, agent_id: str, num_credits: int = 100) -> tuple[int, float]:
        """Purchase tool credits bundle.
        
        Args:
            agent_id: Agent purchasing credits
            num_credits: Number of credits to buy (default: 100)
            
        Returns:
            (new_total_credits, total_cost_usd)
            
        Raises:
            ValueError if payment not verified
        """
        # In production: verify Stripe/x402 payment first
        
        if agent_id not in self.quotas:
            self._initialize_agent(agent_id)
        
        # Add credits to remaining quota
        self.quotas[agent_id].remaining += num_credits
        self.quotas[agent_id].limit += num_credits
        
        cost = (num_credits / 100) * self.config.tool_credit_pack_price
        
        self.stats["tool_credits_sold"] += num_credits
        self.stats["revenue_today_usd"] += cost
        
        logger.info(f"Agent {agent_id} purchased {num_credits} credits (${cost})")
        
        return self.quotas[agent_id].remaining, cost
    
    def consume_call(self, agent_id: str, cost_usd: float = 0.0) -> bool:
        """Consume one call from agent's quota.
        
        Args:
            agent_id: Agent making the call
            cost_usd: Cost of this specific call (for revenue tracking)
            
        Returns:
            True if call allowed, False if quota exhausted
        """
        quota = self.get_quota(agent_id)
        
        if not quota.can_execute():
            logger.warning(f"Quota exhausted for agent: {agent_id}")
            return False
        
        quota.remaining -= 1
        self.stats["calls_today"] += 1
        self.stats["revenue_today_usd"] += cost_usd
        
        return True
    
    def check_rate_limit(self, agent_id: str, requests_per_min: int = 1) -> bool:
        """Check if agent is within rate limit.
        
        Simplified implementation - use Redis for precise sliding window.
        """
        quota = self.get_quota(agent_id)
        return requests_per_min <= quota.rate_limit_per_min
    
    def status(self) -> dict:
        """Get commerce layer health status."""
        return {
            "status": "operational",
            "active_agents": len(self.quotas),
            "free_tier_count": sum(1 for q in self.quotas.values() if q.tier == "free"),
            "pro_tier_count": sum(1 for q in self.quotas.values() if q.tier == "pro"),
        }
    
    def get_stats(self) -> dict:
        """Get current usage statistics."""
        return self.stats.copy()


# ============================================================================
# Payment Verification Helpers
# ============================================================================

async def verify_x402_payment(
    agent_id: str,
    resource_url: str,
    challenge_response: dict,
    settlement_tx_hash: str | None = None
) -> bool:
    """Verify x402 payment has been settled.
    
    Args:
        agent_id: Agent ID making the request
        resource_url: Paid resource being accessed
        challenge_response: Signed challenge response
        settlement_tx_hash: Blockchain transaction hash (optional)
        
    Returns:
        True if payment verified and settled
    """
    # In production:
    # 1. Verify challenge signature
    # 2. Check settlement on Base network via CDP facilitator
    # 3. Record spend in ledger
    # 4. Deduct from quota
    
    logger.info(f"Verifying x402 payment for agent {agent_id}: {resource_url}")
    
    # TODO: Implement actual blockchain verification
    # For now, simulate successful verification
    return True


def calculate_cost_for_tool(tool_name: str, num_calls: int = 1) -> float:
    """Calculate total cost for multiple calls to a tool."""
    from app.tools_registry import TOOL_PRICES
    
    price_str = TOOL_PRICES.get(tool_name, "$0.01")
    price_usd = float(price_str.replace("$", ""))
    
    return round(price_usd * num_calls, 2)
