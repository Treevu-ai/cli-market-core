"""Total Cost of Ownership — shelf price + delivery + payment fees."""

from __future__ import annotations

from typing import Any

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


def payment_fee_amount(subtotal: float, payment_method: str) -> tuple[float, float]:
    """Return (fee_pct, fee_amount) for *subtotal*."""
    method = (payment_method or "yape").strip().lower()
    pct = PAYMENT_FEE_PCT.get(method, 0.0)
    return pct, round(subtotal * pct, 2)


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
