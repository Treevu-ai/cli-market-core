"""
market_connectors/lemon_payments.py — Lemon Cash payment integration.

Handles Lemon checkout (Argentine crypto+fiat wallet).
Uses Lemon REST API v1.
"""

import os

from .http_retry import request_with_retry

LEMON_API_KEY = os.getenv("LEMON_API_KEY", "")
LEMON_API_URL = os.getenv("LEMON_API_URL", "https://api.lemon.me/rest/v1")


async def create_checkout(amount: float, currency: str = "ARS", reference: str = "",
                          description: str = "CLI Market checkout") -> dict:
    """Create a Lemon payment link."""
    if not LEMON_API_KEY:
        return {"error": "LEMON_API_KEY not configured"}
    body = {"amount": amount, "currency": currency, "description": description,
            "external_reference": reference,
            "success_url": "https://cli-market.dev?lemon=success",
            "cancel_url": "https://cli-market.dev?lemon=cancelled"}
    resp = await request_with_retry(
        "POST",
        f"{LEMON_API_URL}/checkout/",
        timeout=10.0,
        label="lemon_create_checkout",
        json=body,
        headers={"Authorization": f"Bearer {LEMON_API_KEY}", "Content-Type": "application/json"},
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        return {
            "checkout_id": data.get("id", ""),
            "checkout_url": data.get("checkout_url", ""),
            "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={data.get('checkout_url', '')}",
            "status": data.get("status", "pending"),
            "reference": reference,
        }
    return {"error": f"Lemon checkout failed: {resp.text}", "status": resp.status_code}
