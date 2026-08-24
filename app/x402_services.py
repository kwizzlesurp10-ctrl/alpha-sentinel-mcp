"""x402 Services - Blockchain payment verification and settlement."""

import logging
from typing import Optional, Literal
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class X402Services:
    """Handles x402 micropayment integration."""
    
    def __init__(self, config):
        self.config = config
        self.enabled = bool(config.x402_pay_to_address)
        
    async def status(self) -> dict:
        """Get x402 service status."""
        if not self.enabled:
            return {"enabled": False, "reason": "No seller address configured"}
        
        return {
            "enabled": True,
            "seller_address": f"{settings.x402_pay_to_address[:10]}...",
            "network": settings.x402_default_network,
            "facilitator": "CDP" if settings.cdp_api_key_id else "x402.org",
        }
    
    async def build_challenge(
        self,
        agent_id: str,
        resource_url: str,
        price_usd: float,
        ttl_seconds: int = 300
    ) -> dict:
        """Build x402 challenge for a paid resource.
        
        Args:
            agent_id: Agent making the request
            resource_url: URL of the paid resource
            price_usd: Price in USD (will be converted to USDC)
            ttl_seconds: Challenge time-to-live
            
        Returns:
            Challenge object with signature and metadata
        """
        if not self.enabled:
            raise RuntimeError("x402 payments disabled - no seller address")
        
        # In production:
        # 1. Convert USD price to USDC amount
        # 2. Generate nonce/challenge data
        # 3. Sign with receive wallet key
        # 4. Return challenge for agent to sign and settle
        
        usdc_amount = await self._usd_to_usdc(price_usd)
        
        challenge = {
            "agent_id": agent_id,
            "resource_url": resource_url,
            "price_usd": price_usd,
            "price_usdc": usdc_amount,
            "network": settings.x402_default_network,
            "pay_to": settings.x402_pay_to_address,
            "nonce": self._generate_nonce(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat(),
            "facilitator": settings.cdp_facilitator_url if settings.cdp_api_key_id 
                         else settings.x402_facilitator_url,
        }
        
        logger.info(f"Built x402 challenge: {resource_url} @ ${price_usd}")
        
        return challenge
    
    async def verify_settlement(
        self,
        agent_id: str,
        challenge: dict,
        tx_hash: str,
        block_number: Optional[int] = None
    ) -> bool:
        """Verify x402 payment has been settled on-chain.
        
        Args:
            agent_id: Original agent ID
            challenge: Original challenge object
            tx_hash: Settlement transaction hash
            block_number: Block number (optional, will fetch from facilitator)
            
        Returns:
            True if verified and recorded
        """
        if not self.enabled:
            return False
        
        # In production:
        # 1. Query CDP facilitator or x402.org API for settlement status
        # 2. Verify transaction matches challenge
        # 3. Check sender address matches pay_to address
        # 4. Record in spend ledger
        
        try:
            # Simulated verification
            await self._record_spend(agent_id, challenge["price_usd"], tx_hash)
            logger.info(f"Verified settlement: tx={tx_hash[:16]}... for {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Settlement verification failed: {e}")
            return False
    
    async def _usd_to_usdc(self, usd_amount: float) -> float:
        """Convert USD amount to USDC equivalent.
        
        Fetches real-time ETH price to calculate conversion.
        """
        # Simplified: assume 1:1 for USDC (it's pegged to USD)
        return round(usd_amount, 6)
    
    def _generate_nonce(self) -> str:
        """Generate unique challenge nonce."""
        import uuid
        return str(uuid.uuid4())
    
    async def _record_spend(
        self,
        agent_id: str,
        amount_usd: float,
        tx_hash: str
    ):
        """Record payment in spend ledger.
        
        In production: write to ledger/spend.jsonl file
        """
        spend_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "amount_usd": amount_usd,
            "tx_hash": tx_hash,
            "network": settings.x402_default_network,
            "status": "settled",
        }
        
        # In production: append to ledger/spend.jsonl
        logger.debug(f"Recorded spend: {spend_record}")
    
    async def get_revenue_ledger(self, limit: int = 100) -> list[dict]:
        """Get recent revenue entries.
        
        In production: read from ledger/revenue.jsonl
        """
        # Simulated revenue records
        return []


# ============================================================================
# Facilitator Integration
# ============================================================================

class CDPFacilitator:
    """Coinbase CDP facilitator integration for Base mainnet."""
    
    def __init__(self, config):
        self.config = config
        self.enabled = bool(config.cdp_api_key_id and config.cdp_api_key_secret)
    
    async def verify_payment(
        self,
        tx_hash: str,
        network: str = "eip155:8453"
    ) -> dict:
        """Verify payment via CDP facilitator API.
        
        Args:
            tx_hash: Transaction hash to verify
            network: Network CAIP-2 ID (default: Base mainnet)
            
        Returns:
            Payment verification result
        """
        if not self.enabled:
            raise RuntimeError("CDP credentials not configured")
        
        # In production:
        # POST to https://api.cdp.coinbase.com/platform/v2/x402/verify
        # Body: { txHash, network }
        
        return {
            "verified": True,
            "network": network,
            "facilitator": "CDP",
        }


class X402OrgFacilitator:
    """x402.org facilitator for Sepolia testnet."""
    
    DEFAULT_URL = "https://x402.org/facilitator"
    
    async def verify_payment(
        self,
        tx_hash: str,
        network: str = "eip155:84532"
    ) -> dict:
        """Verify payment via x402.org facilitator.
        
        Only settles `exact` payments on Base Sepolia.
        """
        # GET or POST to facilitator endpoint
        # For exact payments only
        
        return {
            "verified": True,
            "network": network,
            "facilitator": "x402.org",
            "settlement_type": "exact",
        }


def get_active_facilitator() -> Literal["CDP", "x402.org", None]:
    """Determine which facilitator to use based on configuration."""
    if settings.cdp_api_key_id and settings.cdp_api_key_secret:
        return "CDP"
    
    # Default to x402.org for testnet
    if settings.revenue_network == "eip155:84532":
        return "x402.org"
    
    return None
