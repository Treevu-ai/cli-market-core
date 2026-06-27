"""Platform operator identity — CEO/admin bypass for billing gates.

Configured exclusively via env (Railway / Workers secrets):

  MARKET_ADMIN_USERS      comma-separated CLI Market usernames (from sk- keys / register)
  MARKET_ADMIN_API_KEYS   comma-separated sk-... keys that resolve to the admin identity

``MARKET_API_TOKEN`` (Bearer) always maps to username ``admin``, which is included
in the admin set automatically.
"""

from __future__ import annotations

import os

_ADMIN_USERNAME = "admin"


def platform_admin_usernames() -> frozenset[str]:
    raw = os.getenv("MARKET_ADMIN_USERS", "")
    users = {u.strip() for u in raw.split(",") if u.strip()}
    users.add(_ADMIN_USERNAME)
    return frozenset(users)


def platform_admin_api_keys() -> frozenset[str]:
    raw = os.getenv("MARKET_ADMIN_API_KEYS", "")
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def is_platform_admin(username: str | None) -> bool:
    if not username:
        return False
    return username.strip() in platform_admin_usernames()


def is_platform_admin_api_key(api_key: str | None) -> bool:
    if not api_key:
        return False
    return api_key.strip() in platform_admin_api_keys()
