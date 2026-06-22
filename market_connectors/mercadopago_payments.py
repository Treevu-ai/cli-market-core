"""
market_connectors/mercadopago_payments.py — Mercado Pago Checkout Pro integration.

Creates payment preferences and resolves payment notifications (webhooks/IPN).
Supports separate sandbox/production tokens or a single token + MERCADOPAGO_SANDBOX.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Mapping

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


def webhook_secret() -> str:
    return _first_env(
        "MERCADOPAGO_WEBHOOK_SECRET",
        "MERCADOPAGO_WEBHOOK_TOKEN",
        "MERCADOPAGO_SECRET_SIGNATURE",
        "MERCADOPAGO_WEBHOOK_KEY",
        "MP_WEBHOOK_SECRET",
        "MP_WEBHOOK_TOKEN",
        "MERCADO_PAGO_WEBHOOK_SECRET",
    )


def notification_url() -> str:
    base = _api_base_url() + "/checkout/mercadopago-webhook"
    return base + "?source_news=webhooks"


def validate_webhook_signature(
    *,
    x_signature: str,
    x_request_id: str,
    data_id: str,
    secret: str = "",
) -> bool:
    """Validate Mercado Pago x-signature per official webhook docs."""
    secret = (secret or webhook_secret()).strip()
    if not secret or not x_signature:
        return not secret
    ts = ""
    v1 = ""
    for part in x_signature.split(","):
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "ts":
            ts = value
        elif key == "v1":
            v1 = value
    if not ts or not v1:
        return False
    event_id = (data_id or "").strip()
    if event_id.isalnum():
        event_id = event_id.lower()
    parts = []
    if event_id:
        parts.append(f"id:{event_id}")
    if x_request_id:
        parts.append(f"request-id:{x_request_id}")
    if ts:
        parts.append(f"ts:{ts}")
    manifest = ";".join(parts) + (";" if parts else "")
    computed = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, v1)


def parse_webhook_payment_id(
    *,
    query_params: Mapping[str, str],
    body: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Return (payment_id, notification_type). Prefers body.type=payment."""
    body = body or {}
    ntype = str(body.get("type") or query_params.get("type") or "")
    data_id = str(query_params.get("data.id") or query_params.get("data_id") or "")
    if not data_id and isinstance(body.get("data"), dict):
        data_id = str(body["data"].get("id") or "")
    if not data_id:
        data_id = str(query_params.get("id") or "")
    return data_id, ntype


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


# ── MercadoPago Card Tokenization ────────────────────────────────────────────
# Enables embedded card payment without redirect to MP Checkout Pro.
# Flow: frontend collects card_token_id via MercadoPago.js SDK
#       → POST /v1/payments with token (server-side)
# Also supports saved cards via customer_id for returning buyers.


async def create_card_payment(
    card_token_id: str,
    amount: float,
    *,
    currency: str = "PEN",
    description: str = "CLI Market",
    payer_email: str = "",
    installments: int = 1,
    external_reference: str = "",
) -> dict[str, Any]:
    """Process a card payment using a MercadoPago card token.

    The card_token_id comes from the MercadoPago.js frontend SDK
    (cardForm.createCardToken or mp.createCardToken). This avoids
    the buyer being redirected to Checkout Pro.
    """
    body: dict[str, Any] = {
        "transaction_amount": float(amount),
        "token": card_token_id,
        "description": description[:256],
        "installments": max(1, installments),
        "payment_method_id": "",  # auto-detected from token
        "statement_descriptor": "CLI MARKET",
    }
    if currency:
        body["currency_id"] = currency.upper()
    if payer_email:
        body["payer"] = {"email": payer_email}
    if external_reference:
        body["external_reference"] = external_reference[:256]
    body["notification_url"] = notification_url()

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{MP_API}/v1/payments",
            json=body,
            headers=_auth_headers(),
        )
        if resp.status_code not in (200, 201):
            return {"error": resp.text[:300], "status": resp.status_code}
        data = resp.json()
        return {
            "payment_id": data.get("id"),
            "status": data.get("status"),
            "status_detail": data.get("status_detail"),
            "payment_method_id": data.get("payment_method_id"),
            "card_last_four": (data.get("card") or {}).get("last_four_digits"),
            "installments": data.get("installments"),
            "amount": data.get("transaction_amount"),
            "external_reference": data.get("external_reference"),
        }


async def save_card_for_customer(
    card_token_id: str,
    customer_id: str,
) -> dict[str, Any]:
    """Save a card to a MercadoPago customer for future one-click payments.

    Requires an existing MP customer_id (from create_customer or previous save).
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{MP_API}/v1/customers/{customer_id}/cards",
            json={"token": card_token_id},
            headers=_auth_headers(),
        )
        if resp.status_code not in (200, 201):
            return {"error": resp.text[:300], "status": resp.status_code}
        data = resp.json()
        return {
            "card_id": data.get("id"),
            "last_four": data.get("last_four_digits"),
            "expiration_month": data.get("expiration_month"),
            "expiration_year": data.get("expiration_year"),
            "payment_method_id": (data.get("payment_method") or {}).get("id"),
            "issuer_name": (data.get("issuer") or {}).get("name"),
        }


async def create_customer(email: str, description: str = "") -> dict[str, Any]:
    """Create a MercadoPago customer for card vault / saved cards."""
    body: dict[str, Any] = {"email": email}
    if description:
        body["description"] = description[:256]
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{MP_API}/v1/customers",
            json=body,
            headers=_auth_headers(),
        )
        if resp.status_code not in (200, 201):
            return {"error": resp.text[:300], "status": resp.status_code}
        data = resp.json()
        return {
            "customer_id": data.get("id"),
            "email": data.get("email"),
        }


async def list_customer_cards(customer_id: str) -> dict[str, Any]:
    """List saved cards for a MercadoPago customer."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{MP_API}/v1/customers/{customer_id}/cards",
            headers=_auth_headers(),
        )
        if resp.status_code != 200:
            return {"error": resp.text[:300], "status": resp.status_code}
        cards = resp.json()
        return {
            "customer_id": customer_id,
            "cards": [
                {
                    "card_id": c.get("id"),
                    "last_four": c.get("last_four_digits"),
                    "expiration_month": c.get("expiration_month"),
                    "expiration_year": c.get("expiration_year"),
                    "payment_method_id": (c.get("payment_method") or {}).get("id"),
                }
                for c in (cards if isinstance(cards, list) else [])
            ],
        }


async def charge_saved_card(
    card_id: str,
    customer_id: str,
    amount: float,
    *,
    currency: str = "PEN",
    description: str = "CLI Market",
    external_reference: str = "",
) -> dict[str, Any]:
    """Charge a previously saved card — no card_token needed.

    Uses the saved card_id + customer_id for one-click recurring payment.
    """
    body: dict[str, Any] = {
        "transaction_amount": float(amount),
        "description": description[:256],
        "payment_method_id": "",  # auto-detected
        "payer": {
            "id": customer_id,
        },
        "token": card_id,
        "installments": 1,
        "statement_descriptor": "CLI MARKET",
    }
    if currency:
        body["currency_id"] = currency.upper()
    if external_reference:
        body["external_reference"] = external_reference[:256]
    body["notification_url"] = notification_url()

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{MP_API}/v1/payments",
            json=body,
            headers=_auth_headers(),
        )
        if resp.status_code not in (200, 201):
            return {"error": resp.text[:300], "status": resp.status_code}
        data = resp.json()
        return {
            "payment_id": data.get("id"),
            "status": data.get("status"),
            "status_detail": data.get("status_detail"),
            "amount": data.get("transaction_amount"),
        }