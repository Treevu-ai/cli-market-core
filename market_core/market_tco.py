"""Total Cost of Ownership — shelf price + delivery + payment fees."""

from __future__ import annotations

import logging
import os
from typing import Any

from .market_core import API, STORES

logger = logging.getLogger("market.tco")

# Default payment surcharge (aggregator methods). Yape/Plin manual = 0%.
PAYMENT_FEE_PCT: dict[str, float] = {
    "yape": 0.0,
    "plin": 0.0,
    "paypal": 0.034,
    "mercadopago": 0.029,
    "lemon": 0.029,
    "wise": 0.0,
    "tarjeta": 0.034,
}

# Offline fallback for PE VTEX grocers (wave 4 — used when live sim unavailable).
_PE_DELIVERY_DEFAULTS: dict[str, dict[str, float]] = {
    "wong": {"fee": 7.0, "min_order": 50.0},
    "metro": {"fee": 6.5, "min_order": 45.0},
    "plazavea": {"fee": 7.5, "min_order": 50.0},
}


def payment_fee_amount(subtotal: float, payment_method: str) -> tuple[float, float]:
    """Return (fee_pct, fee_amount) for *subtotal*."""
    method = (payment_method or "yape").strip().lower()
    pct = PAYMENT_FEE_PCT.get(method, 0.0)
    return pct, round(subtotal * pct, 2)


def _delivery_from_defaults(store: str, subtotal: float) -> dict[str, Any] | None:
    cfg = STORES.get(store) or {}
    if cfg.get("platform") != "vtex":
        return None
    defaults = _PE_DELIVERY_DEFAULTS.get(store)
    if not defaults:
        return None
    min_order = float(defaults["min_order"])
    fee = float(defaults["fee"])
    gap = round(max(0.0, min_order - subtotal), 2) if subtotal < min_order else 0.0
    return {
        "fee": fee,
        "min_order": min_order,
        "min_order_gap": gap if gap > 0 else None,
        "available": True,
        "source": "vtex_shipping_defaults",
    }


def _fetch_live_delivery_quote(
    *,
    store: str,
    product_id: str | None,
    zipcode: str | None,
) -> dict[str, Any] | None:
    if not product_id:
        return None
    if os.getenv("MARKET_SKIP_LIVE", "").strip() in {"1", "true", "yes"}:
        return None
    if os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}:
        return None
    try:
        import httpx

        qs = f"store={store}"
        if zipcode:
            qs += f"&zipcode={zipcode}"
        url = f"{API.rstrip('/')}/products/delivery/{product_id}?{qs}"
        timeout = float(os.getenv("MARKET_DELIVERY_TIMEOUT", "8"))
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if not isinstance(data, dict):
            return None
        fee = data.get("fee")
        if fee is None and data.get("delivery_fee") is not None:
            fee = data.get("delivery_fee")
        if fee is None:
            return None
        return {
            "fee": round(float(fee), 2),
            "min_order": data.get("min_order"),
            "min_order_gap": data.get("min_order_gap"),
            "available": True,
            "source": "vtex_shipping_simulation",
        }
    except Exception as exc:
        logger.debug("live delivery quote failed for %s: %s", store, exc)
        return None


def simulate_delivery_quote(
    store: str,
    *,
    subtotal: float,
    product_id: str | None = None,
    zipcode: str | None = None,
) -> dict[str, Any]:
    """Best-effort delivery fee for TCO (live VTEX sim → static defaults → unavailable)."""
    live = _fetch_live_delivery_quote(store=store, product_id=product_id, zipcode=zipcode)
    if live:
        min_order = live.get("min_order")
        if min_order is not None and subtotal < float(min_order):
            live["min_order_gap"] = round(float(min_order) - subtotal, 2)
        return live

    defaults = _delivery_from_defaults(store, subtotal)
    if defaults:
        return defaults

    return {
        "fee": 0.0,
        "min_order": None,
        "min_order_gap": None,
        "available": False,
        "source": None,
    }


def compute_line_tco(
    *,
    shelf_subtotal: float,
    delivery: dict[str, Any] | None = None,
    payment_method: str = "yape",
    include_delivery: bool = True,
) -> dict[str, Any]:
    """Compute TCO components for a basket or compare row."""
    shelf = round(float(shelf_subtotal or 0), 2)
    delivery_block: dict[str, Any] = {
        "fee": 0.0,
        "min_order": None,
        "min_order_gap": None,
        "available": False,
        "source": None,
    }
    delivery_fee = 0.0
    if include_delivery and delivery and delivery.get("available"):
        delivery_fee = float(delivery.get("fee") or 0)
        delivery_block = {
            "fee": round(delivery_fee, 2),
            "min_order": delivery.get("min_order"),
            "min_order_gap": delivery.get("min_order_gap"),
            "available": True,
            "source": delivery.get("source") or "unknown",
        }

    fee_pct, fee_amount = payment_fee_amount(shelf + delivery_fee, payment_method)
    tco_total = round(shelf + delivery_fee + fee_amount, 2)

    return {
        "subtotal_shelf": shelf,
        "delivery": delivery_block,
        "payment": {
            "method": (payment_method or "yape").lower(),
            "fee_pct": fee_pct,
            "fee_amount": fee_amount,
        },
        "fx": None,
        "tco_total": tco_total,
    }


def attach_tco_to_store(
    store_row: dict[str, Any],
    *,
    delivery: dict[str, Any] | None = None,
    payment_method: str = "yape",
    include_delivery: bool = True,
) -> dict[str, Any]:
    """Add ``tco`` block to a basket-compare store dict."""
    shelf = float(store_row.get("total") or 0)
    tco = compute_line_tco(
        shelf_subtotal=shelf,
        delivery=delivery,
        payment_method=payment_method,
        include_delivery=include_delivery,
    )
    items = max(1, int(store_row.get("items_found") or 1))
    store_row = dict(store_row)
    store_row["tco"] = tco
    store_row["tco_total"] = tco["tco_total"]
    store_row["tco_per_item"] = round(tco["tco_total"] / items, 2)
    return store_row
