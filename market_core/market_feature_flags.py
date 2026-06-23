"""Runtime feature flags for Cost-of-Living OS rollout (wave 4)."""

from __future__ import annotations

import os


def _env_truthy(name: str, *, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def household_enabled() -> bool:
    """Gate household profile CRUD (default on)."""
    return _env_truthy("HOUSEHOLD_ENABLED")


def crowd_receipts_enabled() -> bool:
    """Gate receipt crowd submissions (default on)."""
    return _env_truthy("CROWD_RECEIPTS_ENABLED")


def ecosystem_radar_enabled() -> bool:
    """Gate ecosystem launches radar (default on)."""
    return _env_truthy("ECOSYSTEM_RADAR_ENABLED")


def external_cart_handoff_enabled() -> bool:
    """L4 partner cart handoff stub (default off until partner contract)."""
    return _env_truthy("EXTERNAL_CART_HANDOFF_ENABLED", default="0")


def affiliate_enabled() -> bool:
    """Global affiliate UTM toggle (default off; per-store via AFFILIATE_STORES)."""
    return _env_truthy("AFFILIATE_ENABLED", default="0")
