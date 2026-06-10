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
    }
