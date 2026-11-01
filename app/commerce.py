"""Commerce Layer - Quota, payments, and tier management."""

import logging
import json
from dataclasses import dataclass, asdict
from datetime import UTC, datetime, timedelta

from app.redis_client import command as redis_cmd

logger = logging.getLogger(__name__)


@dataclass
class QuotaState:
    """User quota state."""
    agent_id: str
    tier: str  # "free" or "pro"
    remaining: int
    limit: int
    rate_limit_per_min: int
    reset_at: str | None = None # Store as ISO string in Redis
    
    def is_exhausted(self) -> bool:
        return self.remaining <= 0
    
    def can_execute(self) -> bool:
        return not self.is_exhausted()


class CommerceLayer:
    """Manages quotas, tiers, and tool credit purchases via Redis persistence."""
    
    def __init__(self, config):
        self.config = config
        self.stats_key = "stats:global"
        self.quota_prefix = "quota:"
        
    async def get_quota(self, agent_id: str) -> QuotaState:
        """Get or initialize quota state for an agent from Redis."""
        key = f"{self.quota_prefix}{agent_id}"
        data = await redis_cmd("GET", key)
        
        if data is None:
            return await self._initialize_agent(agent_id)
        
        return QuotaState(**json.loads(data))
    
    async def _initialize_agent(self, agent_id: str) -> QuotaState:
        """Create new free tier quota for agent and store in Redis."""
        now = datetime.now(UTC)
        reset_at = (now + timedelta(days=1)).isoformat()
        
        quota = QuotaState(
            agent_id=agent_id,
            tier="free",
            remaining=self.config.free_tier_monthly_quota,
            limit=self.config.free_tier_monthly_quota,
            rate_limit_per_min=self.config.free_tier_rate_limit_per_min,
            reset_at=reset_at,
        )
        
        await self._save_quota(quota)
        
        # Increment global stats in Redis
        await redis_cmd("HINCRBY", self.stats_key, "total_agents", 1)
        await redis_cmd("HINCRBY", self.stats_key, "free_active", 1)
        
        logger.info(f"Initialized free tier quota for agent: {agent_id}")
        return quota
    
    async def _save_quota(self, quota: QuotaState):
        key = f"{self.quota_prefix}{quota.agent_id}"
        await redis_cmd("SET", key, json.dumps(asdict(quota)))
    
    async def upgrade_to_pro(self, agent_id: str, payment_verified: bool = True):
        """Upgrade agent to pro tier after payment verification."""
        if not payment_verified:
            raise ValueError("Payment verification required for upgrade")
        
        quota = await self.get_quota(agent_id)
        quota.tier = "pro"
        quota.remaining = self.config.pro_tier_monthly_quota
        quota.limit = self.config.pro_tier_monthly_quota
        quota.rate_limit_per_min = self.config.pro_tier_rate_limit_per_min
        
        await self._save_quota(quota)
        
        await redis_cmd("HINCRBY", self.stats_key, "pro_active", 1)
        await redis_cmd("HINCRBY", self.stats_key, "free_active", -1)
        
        logger.info(f"Upgraded agent {agent_id} to PRO tier")
    
    async def purchase_tool_credits(self, agent_id: str, num_credits: int = 100) -> tuple[int, float]:
        """Purchase tool credits bundle."""
        quota = await self.get_quota(agent_id)
        
        quota.remaining += num_credits
        quota.limit += num_credits
        await self._save_quota(quota)
        
        cost = (num_credits / 100) * self.config.tool_credit_pack_price
        
        await redis_cmd("HINCRBY", self.stats_key, "tool_credits_sold", num_credits)
        # Revenue is float, so we use HINCRBYFLOAT if available, or manual read-modify-write
        # For simplicity with the custom redis_cmd, we'll handle revenue separately or use cents
        current_rev = float(await redis_cmd("HGET", self.stats_key, "revenue_today_usd") or 0)
        await redis_cmd("HSET", self.stats_key, "revenue_today_usd", str(current_rev + cost))
        
        logger.info(f"Agent {agent_id} purchased {num_credits} credits (${cost})")
        return quota.remaining, cost
    
    async def consume_call(self, agent_id: str, cost_usd: float = 0.0) -> bool:
        """Consume one call from agent's quota."""
        quota = await self.get_quota(agent_id)
        
        if not quota.can_execute():
            logger.warning(f"Quota exhausted for agent: {agent_id}")
            return False
        
        quota.remaining -= 1
        await self._save_quota(quota)
        
        await redis_cmd("HINCRBY", self.stats_key, "calls_today", 1)
        current_rev = float(await redis_cmd("HGET", self.stats_key, "revenue_today_usd") or 0)
        await redis_cmd("HSET", self.stats_key, "revenue_today_usd", str(current_rev + cost_usd))
        
        return True
    
    async def check_rate_limit(self, agent_id: str, requests_per_min: int = 1) -> bool:
        """Check if agent is within rate limit."""
        quota = await self.get_quota(agent_id)
        return requests_per_min <= quota.rate_limit_per_min
    
    async def status(self) -> dict:
        """Get commerce layer health status."""
        # We can't easily count keys in Redis without SCAN, so we'll use the stats key
        stats = await redis_cmd("HGETALL", self.stats_key) or {}
        # HGETALL in Upstash REST returns a list of [key, val, key, val...]
        # We need to convert it to a dict
        stats_dict = {}
        if isinstance(stats, list):
            for i in range(0, len(stats), 2):
                stats_dict[stats[i]] = stats[i+1]
        
        return {
            "status": "operational",
            "active_agents": int(stats_dict.get("total_agents", 0)),
            "free_tier_count": int(stats_dict.get("free_active", 0)),
            "pro_tier_count": int(stats_dict.get("pro_active", 0)),
        }
    
    async def get_stats(self) -> dict:
        """Get current usage statistics from Redis."""
        stats = await redis_cmd("HGETALL", self.stats_key) or {}
        stats_dict = {}
        if isinstance(stats, list):
            for i in range(0, len(stats), 2):
                stats_dict[stats[i]] = stats[i+1]
        
        return {
            "total_agents": int(stats_dict.get("total_agents", 0)),
            "free_active": int(stats_dict.get("free_active", 0)),
            "pro_active": int(stats_dict.get("pro_active", 0)),
            "tool_credits_sold": int(stats_dict.get("tool_credits_sold", 0)),
            "revenue_today_usd": float(stats_dict.get("revenue_today_usd", 0.0)),
            "calls_today": int(stats_dict.get("calls_today", 0)),
            "avg_latency_ms": float(stats_dict.get("avg_latency_ms", 0.0)),
        }


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
    
    logger.info("Verifying x402 payment for agent %s: %s", agent_id, resource_url)
    from app.x402_services import verify_and_settle_from_headers

    sig = challenge_response.get("payment_signature") or challenge_response.get("signature")
    required = challenge_response.get("payment_required")
    if not sig or not required:
        return False
    result = await verify_and_settle_from_headers(str(sig), str(required))
    return bool(result.get("is_valid") and result.get("payment_settled"))


def calculate_cost_for_tool(tool_name: str, num_calls: int = 1) -> float:
    """Calculate total cost for multiple calls to a tool."""
    from app.tools_registry import TOOL_PRICES
    
    price_str = TOOL_PRICES.get(tool_name, "$0.01")
    price_usd = float(price_str.replace("$", ""))
    
    return round(price_usd * num_calls, 2)
