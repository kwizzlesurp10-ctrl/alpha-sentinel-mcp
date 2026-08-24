# Application configuration.

from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_price(val: str | float) -> float:
    """Helper to parse dollar string or float into a float value."""
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).replace("$", "").strip())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8403
    upgrade_url: str = "http://localhost:8403/upgrade"
    public_base_url: str = "http://localhost:8403"

    # Free tier quotas (matches x402-mcp for consistency)
    free_tier_monthly_quota: int = 500
    free_tier_rate_limit_per_min: int = 10
    
    # Pro tier (scaled up for market intelligence volume)
    pro_tier_monthly_quota: int = 50_000
    pro_tier_rate_limit_per_min: int = 120
    pro_tier_price: str = "$29.00"

    # MCP Tool credits (flexible bundle)
    tool_credit_pack_size: int = 100
    tool_credit_pack_price: str = "$1.00"

    # Alpha Sentinel pricing strategy
    price_feed_price: str = "$0.005"      # Cheapest - high frequency
    volatility_alerts_price: str = "$0.02" # Statistical analysis
    sentiment_analysis_price: str = "$0.01" # NLP aggregation
    risk_assessment_price: str = "$0.03"   # Multi-factor scoring
    market_report_price: str = "$0.15"     # Comprehensive report

    @property
    def price_feed_price_usd(self) -> float:
        return parse_price(self.price_feed_price)

    @property
    def volatility_alerts_price_usd(self) -> float:
        return parse_price(self.volatility_alerts_price)

    @property
    def sentiment_analysis_price_usd(self) -> float:
        return parse_price(self.sentiment_analysis_price)

    @property
    def risk_assessment_price_usd(self) -> float:
        return parse_price(self.risk_assessment_price)

    @property
    def market_report_price_usd(self) -> float:
        return parse_price(self.market_report_price)

    # Diligence pack (via city compliance integration)
    diligence_pack_price: str = "$1.50"
    diligence_pack_min_usdc: float = 0.75
    diligence_pack_max_usdc: float = 2.50
    diligence_pack_max_properties: int = 5

    # Pulse and TX decision (from x402-mcp pattern)
    pulse_price: str = "$0.05"
    tx_decision_price: str = "$0.01"

    # Optional bearer token to protect /quota endpoint
    operator_token: str | None = None

    # Redis for production state persistence
    redis_url: str | None = None

    # Buyer (hot wallet) - NEVER on Render!
    evm_private_key: str | None = None
    key_provider: str = "env"

    # Seller (cold receive address) - SEPARATE from buyer!
    x402_pay_to_address: str | None = None

    # Base network config
    base_rpc_url: str = "https://mainnet.base.org"
    eth_price_url: str = "https://api.coinbase.com/v2/prices/ETH-USD/spot"

    # Data sources
    coingecko_api_key: str | None = None
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    x_api_key: str | None = None  # For Twitter/X sentiment
    reddit_api_id: str | None = None
    reddit_api_secret: str | None = None

    # CDP Facilitator (for mainnet selling)
    cdp_api_key_id: str | None = None
    cdp_api_key_secret: str | None = None
    cdp_facilitator_url: str = "https://api.cdp.coinbase.com/platform/v2/x402"
    cdp_networks: str = "eip155:8453"

    # Network routing
    x402_default_network: str = "eip155:84532"  # Base Sepolia dev
    revenue_network: str | None = None
    x402_default_price: str = "$0.01"
    x402_http_timeout: float = 90.0

    # Bazaar discovery
    bazaar_discoverable: bool = True
    bazaar_service_name: str = "Alpha Sentinel Market Intelligence"
    bazaar_service_tags: str = "base,intelligence,crypto,market,x402,mcp"

    # Stripe fiat rail (optional)
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_publishable_key: str | None = None

    # Dashboard actions gate
    dashboard_actions: bool = False

    # Trust forwarded headers (proxy scenarios)
    trust_forwarded_host: bool = False

    # Swarm agency (buy-compose-resell)
    swarm_enabled: bool = False
    swarm_markup: float = 3.0
    swarm_min_price_usdc: float = 0.01
    swarm_max_upstream_calls: int = 3
    swarm_allow_paid_inputs: bool = False
    swarm_upstream_urls: str = ""
    operator_wallets: str = ""
    swarm_target_ltv_cac: float = 3.0
    swarm_min_margin_ratio: float = 0.5
    swarm_sell_network: str = "eip155:84532"

    # Contact info (public, in OpenAPI)
    contact_email: str = "kwizzlesurp10@gmail.com"
    
    # Ownership proofs for Bazaar verification (sign with receive address)
    ownership_proofs: str = ""

    # Alpha Sentinel specific thresholds
    volatility_z_score_threshold: float = 2.0  # Standard deviations
    sentiment_momentum_window: int = 60  # minutes
    alert_cooldown_seconds: int = 300  # 5 min between similar alerts
    max_properties_per_diligence: int = 5

    # Meta-reflection loop (self-improvement)
    reflection_interval_seconds: int = 3600  # Hourly self-analysis
    accuracy_threshold_for_patch: float = 0.5  # Trigger patch if <50%


settings = Settings()
