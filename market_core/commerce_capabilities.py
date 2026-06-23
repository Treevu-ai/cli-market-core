"""Public commerce capability matrix for API and MCP consumers."""

from __future__ import annotations


def get_commerce_capabilities() -> dict:
    """Describe what CLI Market checkout does and does not do."""
    return {
        "checkout": {
            "scope": "cli_market_internal",
            "description": (
                "Creates an order in CLI Market and initiates LATAM payment "
                "(Yape, Plin, PayPal, Mercado Pago, Wise). Does not execute "
                "checkout on individual retailer websites."
            ),
            "retailer_fulfillment": False,
            "receipt": "manual_boleta_not_sunat",
        },
        "payments": {
            "methods": ["yape", "plin", "paypal", "mercadopago", "lemon", "wise"],
            "confirmation_modes": {
                "yape": "manual",
                "plin": "manual",
                "paypal": "aggregator",
                "mercadopago": "aggregator",
                "lemon": "aggregator",
                "wise": "manual",
            },
        },
        "search_compare": {
            "source": "scraping_and_connectors",
            "health_endpoint": "/v1/sources/health",
        },
        "tco": {
            "scope": "shelf_plus_payment_fees_plus_delivery",
            "description": (
                "TCO = subtotal_shelf + delivery (when available) + payment fee. "
                "Free tier: shelf + payment only (include_delivery=false). "
                "Starter+: full TCO when delivery data exists."
            ),
            "delivery_data": "vtex_shipping_simulation_with_defaults_fallback",
            "delivery_sources": ["vtex_shipping_simulation", "vtex_shipping_defaults"],
        },
        "action_closure": {
            "levels_available": ["analysis", "retailer_deeplink", "export_list", "affiliate", "external_cart_handoff"],
            "deeplinks": "wave_2",
            "affiliate_utm": "wave_4_l3",
            "export_list": "wave_2",
            "external_cart_handoff": "wave_4_l4_stub",
            "feature_flags": [
                "HOUSEHOLD_ENABLED",
                "CROWD_RECEIPTS_ENABLED",
                "ECOSYSTEM_RADAR_ENABLED",
                "AFFILIATE_ENABLED",
                "EXTERNAL_CART_HANDOFF_ENABLED",
            ],
        },
    }
