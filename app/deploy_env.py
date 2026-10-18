"""Deployment environment helpers (Vercel production vs local)."""

from __future__ import annotations

import os


def is_vercel_production() -> bool:
    return (os.environ.get("VERCEL_ENV") or "").strip().lower() == "production"


def strict_x402_enforcement() -> bool:
    """Paid tool HTTP/MCP paths must never bypass x402 (prod or Base mainnet)."""
    if is_vercel_production():
        return True
    from app.config import settings

    if settings.x402_default_network == "eip155:8453":
        return True
    from app import x402_services

    return x402_services.resolve_revenue_network() == "eip155:8453"
