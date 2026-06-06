"""
market_connectors/mercadopago_payments.py — Mercado Pago Checkout Pro integration.

Creates payment preferences and resolves payment notifications (webhooks/IPN).
Supports separate sandbox/production tokens or a single token + MERCADOPAGO_SANDBOX.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

MP_API = "https://api.mercadopago.com"


def is_sandbox() -> bool:
    return os.getenv("MERCADOPAGO_SANDBOX", os.getenv("MP_SANDBOX", "true")).lower() in (
        "1",
        "true",
        "yes",
    )


def _first_env(*keys: str) -> str:
    for key in keys:
        val = os.getenv(key, "").strip()
        if val:
            return val
    return ""


def access_token() -> str:
    """Resolve access token from Railway env (sandbox vs production)."""
    if is_sandbox():
        return _first_env(
            "MERCADOPAGO_ACCESS_TOKEN_SANDBOX",
            "MERCADOPAGO_ACCESS_TOKEN_TEST",
            "MERCADOPAGO_SANDBOX_ACCESS_TOKEN",
            "MP_ACCESS_TOKEN_SANDBOX",
            "MERCADO_PAGO_ACCESS_TOKEN_SANDBOX",
            "MERCADOPAGO_ACCESS_TOKEN",
            "MERCADO_PAGO_ACCESS_TOKEN",
            "MP_ACCESS_TOKEN",
        )
    return _first_env(
        "MERCADOPAGO_ACCESS_TOKEN_PRODUCTION",
        "MERCADOPAGO_ACCESS_TOKEN_PROD",
        "MERCADOPAGO_PRODUCTION_ACCESS_TOKEN",
        "MP_ACCESS_TOKEN_PRODUCTION",
        "MERCADO_PAGO_ACCESS_TOKEN_PRODUCTION",
        "MERCADOPAGO_ACCESS_TOKEN",
        "MERCADO_PAGO_ACCESS_TOKEN",
        "MP_ACCESS_TOKEN",
    )


def public_key() -> str:
    if is_sandbox():
        return (
            os.getenv("MERCADOPAGO_PUBLIC_KEY_SANDBOX", "").strip()
            or os.getenv("MERCADOPAGO_PUBLIC_KEY_TEST", "").strip()
            or os.getenv("MP_PUBLIC_KEY_SANDBOX", "").strip()
            or os.getenv("MERCADOPAGO_PUBLIC_KEY", "").strip()
            or os.getenv("MP_PUBLIC_KEY", "").strip()
        )
    return (
        os.getenv("MERCADOPAGO_PUBLIC_KEY_PRODUCTION", "").strip()
        or os.getenv("MERCADOPAGO_PUBLIC_KEY_PROD", "").strip()
        or os.getenv("MP_PUBLIC_KEY_PRODUCTION", "").strip()
        or os.getenv("MERCADOPAGO_PUBLIC_KEY", "").strip()
        or os.getenv("MP_PUBLIC_KEY", "").strip()
    )


def _api_base_url() -> str:
    """Public API host for webhooks (not the marketing landing)."""
    explicit = os.getenv("MERCADOPAGO_WEBHOOK_URL", "").strip()
    if explicit:
        return explicit.rstrip("/").rsplit("/checkout/mercadopago-webhook", 1)[0]

    railway = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway and railway not in ("cli-market.dev", "www.cli-market.dev"):
        return f"https://{railway}".rstrip("/")

    for key in ("PUBLIC_API_URL", "API_BASE_URL", "MARKET_API_URL"):
        base = os.getenv(key, "").strip()
        if not base:
            continue
        if not base.startswith("http"):
            base = f"https://{base}"
        if base.rstrip("/").endswith("cli-market.dev"):
            continue
        return base.rstrip("/")

    return "https://cli-market-production.up.railway.app"


def notification_url() -> str:
    return _api_base_url() + "/checkout/mercadopago-webhook"


def _auth_headers() -> dict[str, str]:
    token = access_token()
    if not token:
        raise ValueError("Mercado Pago access token not configured")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def check_connection() -> dict[str, Any]:
    """Verify credentials against Mercado Pago users/me."""
    token = access_token()
    if not token:
        return {"ok": False, "error": "access_token_missing", "sandbox": is_sandbox()}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{MP_API}/users/me", headers=_auth_headers())
        if resp.status_code != 200:
            return {
                "ok": False,
                "sandbox": is_sandbox(),
                "status": resp.status_code,
                "error": resp.text[:200],
            }
        data = resp.json()
        return {
            "ok": True,
            "sandbox": is_sandbox(),
            "user_id": data.get("id"),
            "site_id": data.get("site_id"),
            "country_id": data.get("country_id"),
            "token_preview": f"{token[:8]}...",
            "public_key_configured": bool(public_key()),
        }


async def create_preference(
    amount: float,
    currency: str = "PEN",
    reference: str = "",
    *,
    success_url: str = "https://cli-market.dev?mp=success",
    failure_url: str = "https://cli-market.dev?mp=failure",
    pending_url: str = "https://cli-market.dev?mp=pending",
    title: str = "CLI Market checkout",
) -> dict[str, Any]:
    """Create Checkout Pro preference; returns init_point redirect URL."""
    body = {
        "items": [
            {
                "title": title[:256],
                "quantity": 1,
                "unit_price": float(amount),
                "currency_id": currency.upper(),
            }
        ],
        "external_reference": reference[:256],
        "back_urls": {
            "success": success_url,
            "failure": failure_url,
            "pending": pending_url,
        },
        "auto_return": "approved",
        "notification_url": notification_url(),
        "statement_descriptor": "CLI MARKET",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{MP_API}/checkout/preferences",
            json=body,
            headers=_auth_headers(),
        )
        if resp.status_code not in (200, 201):
            return {"error": resp.text[:300], "status": resp.status_code}
        data = resp.json()
        checkout_url = data.get("sandbox_init_point") if is_sandbox() else data.get("init_point")
        if not checkout_url:
            checkout_url = data.get("sandbox_init_point") or data.get("init_point") or ""
        return {
            "preference_id": data.get("id", ""),
            "checkout_url": checkout_url,
            "status": "pending",
            "reference": reference,
            "sandbox": is_sandbox(),
        }


async def get_payment(payment_id: str) -> dict[str, Any]:
    """Fetch payment by id (used to validate webhooks)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{MP_API}/v1/payments/{payment_id}",
            headers=_auth_headers(),
        )
        if resp.status_code != 200:
            return {"error": resp.text[:200], "status": resp.status_code}
        return resp.json()


def parse_external_order_id(external_reference: str) -> str | None:
    """Extract ORD-xxx from CLI-Market-ORD-xxx reference."""
    ref = (external_reference or "").strip()
    if not ref:
        return None
    upper = ref.upper()
    if upper.startswith("ORD-"):
        return upper
    marker = "ORD-"
    idx = upper.find(marker)
    if idx >= 0:
        return upper[idx : idx + 12]
    return None