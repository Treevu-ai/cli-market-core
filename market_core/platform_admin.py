"""Platform operator identity — CEO/admin bypass for billing gates.

Configured exclusively via env (Railway / Workers secrets):

  MARKET_ADMIN_USERS      comma-separated CLI Market usernames (from sk- keys / register)
  MARKET_ADMIN_API_KEYS   comma-separated sk-... keys that resolve to the admin identity

``MARKET_API_TOKEN`` (Bearer) maps to username ``admin``; bypass applies only when
``MARKET_API_TOKEN`` or ``MARKET_ADMIN_API_KEYS`` is set on the server (not in tests).
"""

from __future__ import annotations

import os

_ADMIN_USERNAME = "admin"


def platform_admin_usernames() -> frozenset[str]:
    raw = os.getenv("MARKET_ADMIN_USERS", "")
    return frozenset(u.strip() for u in raw.split(",") if u.strip())


def _ops_admin_bypass_enabled() -> bool:
    """True when production ops credentials are configured on the server."""
    return bool(
        os.getenv("MARKET_API_TOKEN", "").strip()
        or os.getenv("MARKET_ADMIN_API_KEYS", "").strip()
    )


def is_platform_admin(username: str | None) -> bool:
    if not username:
        return False
    name = username.strip()
    if name in platform_admin_usernames():
        return True
    # Bearer MARKET_API_TOKEN (and admin sk- keys) resolve to username ``admin``.
    if name == _ADMIN_USERNAME and _ops_admin_bypass_enabled():
        return True
    return False


def platform_admin_api_keys() -> frozenset[str]:
    raw = os.getenv("MARKET_ADMIN_API_KEYS", "")
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def is_platform_admin_api_key(api_key: str | None) -> bool:
    if not api_key:
        return False
    return api_key.strip() in platform_admin_api_keys()
