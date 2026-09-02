# Application configuration.

from __future__ import annotations

from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_price(val: str | float) -> float:
    """Helper to parse dollar string or float into a float value."""
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).replace("$", "").strip())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Drop empty-string env vars so field defaults apply (Vercel often sets "").
    @model_validator(mode="before")
    @classmethod
    def drop_empty_strings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        cleaned: dict[str, Any] = {}
        for k, v in data.items():
            if v is None:
                continue
            if isinstance(v, str):
                v = v.strip()
                if v == "":
                    continue
            cleaned[k] = v
        return cleaned

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8403
    upgrade_url: str = "http://localhost:8403/upgrade"
    public_base_url: str = "https://alpha-sentinel-mcp.vercel.app"

    free_tier_monthly_quota: int = 500
    free_tier_rate_limit_per_min: int = 10

    pro_tier_monthly_quota: int = 50_000
    pro_tier_rate_limit_per_min: int = 120
    pro_tier_price: str = "$29.00"

    tool_credit_pack_size: int = 100
    tool_credit_pack_price: str = "$1.00"

    price_feed_price: str = "$0.005"
    volatility_alerts_price: str = "$0.02"
    sentiment_analysis_price: str = "$0.01"
    risk_assessment_price: str = "$0.03"
    market_report_price: str = "$0.15"

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

    diligence_pack_price: str = "$1.50"
    diligence_pack_min_usdc: float = 0.75
    diligence_pack_max_usdc: float = 2.50
    diligence_pack_max_properties: int = 5

    pulse_price: str = "$0.05"
    tx_decision_price: str = "$0.01"

    operator_token: str | None = None
    redis_url: str | None = None

    evm_private_key: str | None = None
    key_provider: str = "env"

    x402_pay_to_address: str | None = None

    base_rpc_url: str = "https://mainnet.base.org"
    eth_price_url: str = "https://api.coinbase.com/v2/prices/ETH-USD/spot"

    coingecko_api_key: str | None = None
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    x_api_key: str | None = None
    reddit_api_id: str | None = None
    reddit_api_secret: str | None = None

    cdp_api_key_id: str | None = None
    cdp_api_key_secret: str | None = None
    cdp_facilitator_url: str = "https://api.cdp.coinbase.com/platform/v2/x402"
    cdp_networks: str = "eip155:8453"

    x402_default_network: str = "eip155:8453"
    revenue_network: str | None = None
    x402_default_price: str = "$0.01"
    x402_http_timeout: float = 90.0
    x402_facilitator_url: str = "https://x402.org/facilitator"

    bazaar_discoverable: bool = True
    bazaar_service_name: str = "Alpha Sentinel Market Intelligence"
    bazaar_service_tags: str = "base,intelligence,crypto,market,x402,mcp"

    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_publishable_key: str | None = None

    dashboard_actions: bool = False
    trust_forwarded_host: bool = False

    swarm_enabled: bool = False
    swarm_markup: float = 3.0
    swarm_min_price_usdc: float = 0.01
    swarm_max_upstream_calls: int = 3
    swarm_allow_paid_inputs: bool = False
    swarm_upstream_urls: str = ""
    operator_wallets: str = ""
    swarm_target_ltv_cac: float = 3.0
    swarm_min_margin_ratio: float = 0.5
    swarm_sell_network: str = "eip155:8453"

    contact_email: str = "kwizzlesurp10@gmail.com"
    ownership_proofs: str = ""

    volatility_z_score_threshold: float = 2.0
    sentiment_momentum_window: int = 60
    alert_cooldown_seconds: int = 300
    max_properties_per_diligence: int = 5

    reflection_interval_seconds: int = 3600
    accuracy_threshold_for_patch: float = 0.5

    @field_validator(
        "bazaar_discoverable",
        "dashboard_actions",
        "trust_forwarded_host",
        "swarm_enabled",
        "swarm_allow_paid_inputs",
        mode="before",
    )
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on"}
        return v


settings = Settings()
