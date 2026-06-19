"""
market_connectors/base.py — Abstract connector interface.

Every e-commerce platform connector implements this protocol.
The rest of the system never knows which platform a store runs on.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    platform: str = ""

    @abstractmethod
    async def search(self, store_config: dict, term: str,
                     page: int = 1, limit: int = 20) -> list[dict]:
        """Search products. Returns raw platform-specific dicts."""

    @abstractmethod
    def normalize(self, raw: dict, store_key: str, store_config: dict) -> dict:
        """Convert raw product into unified schema:
        {id, product_id, name, brand, category, price, list_price,
         discount, stock, store, store_name, currency, url, line, line_name}"""

    @abstractmethod
    async def categories(self, store_config: dict) -> list[dict]:
        """Return category tree."""


def parse_price(price: Any) -> float:
    try: return float(price or 0)
    except (ValueError, TypeError): return 0.0


# A ListPrice implying a discount at/above this percentage is treated as a bad
# scrape, not a real promo: some VTEX stores (e.g. Jumbo/Vea AR) return a
# ListPrice ~90-100x the selling price, producing fake ~99% discounts.
# Keep in sync with market_core.price_confidence.discount_is_scrape_error.
SCRAPE_ERROR_DISCOUNT_PCT = 90.0


def sane_list_price(price: float, list_price: float) -> float:
    """Drop an implausible list_price so fake near-100% discounts never enter the
    data. Returns ``price`` when the implied discount is a scrape error, else the
    original list_price unchanged."""
    if price > 0 and list_price > price:
        implied = (1 - price / list_price) * 100
        if implied >= SCRAPE_ERROR_DISCOUNT_PCT:
            return price
    return list_price

def clean_name(name: str) -> str:
    return name.replace("-", " ")
