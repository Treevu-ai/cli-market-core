"""
market_connectors/woocommerce.py — WooCommerce connector.

Read path (no merchant keys): WooCommerce Store API
  GET {base}/wp-json/wc/store/v1/products?search=&page=&per_page=

Collector path (merchant keys): WooCommerce REST API v3
  GET {base}/wp-json/wc/v3/products  (Basic auth: consumer_key / consumer_secret)

Store config:
  base          — shop origin, e.g. https://mi-tienda.pe
  currency      — ISO code fallback when Store API omits it
  wc_consumer_key / wc_consumer_secret — optional REST v3 credentials
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import BaseConnector, clean_name, parse_price

logger = logging.getLogger(__name__)

_STORE_API = "/wp-json/wc/store/v1/products"
_REST_API = "/wp-json/wc/v3/products"


def _store_base(store_config: dict) -> str:
    return str(store_config.get("base", "")).rstrip("/")


def _wc_auth(store_config: dict) -> tuple[str, str] | None:
    key = store_config.get("wc_consumer_key") or store_config.get("consumer_key", "")
    secret = store_config.get("wc_consumer_secret") or store_config.get("consumer_secret", "")
    if key and secret:
        return str(key), str(secret)
    return None


def _minor_unit_price(prices: dict[str, Any]) -> tuple[float, float]:
    """Store API returns integer minor units (e.g. 9900 + minor_unit=2 → 99.00)."""
    minor_raw = prices.get("currency_minor_unit")
    minor = 2 if minor_raw is None else int(minor_raw)
    divisor = 10**minor

    def _one(field: str) -> float:
        raw = prices.get(field)
        if raw in (None, ""):
            return 0.0
        try:
            return round(int(str(raw)) / divisor, 2)
        except (ValueError, TypeError):
            return parse_price(raw)

    sale = _one("sale_price") or _one("price")
    regular = _one("regular_price") or sale
    price = sale or regular
    list_price = max(regular, price)
    return price, list_price


def _brand_from_raw(raw: dict) -> str:
    brands = raw.get("brands") or []
    if brands and isinstance(brands, list):
        name = brands[0].get("name") if isinstance(brands[0], dict) else str(brands[0])
        if name:
            return name
    for attr in raw.get("attributes") or []:
        if not isinstance(attr, dict):
            continue
        slug = str(attr.get("slug") or attr.get("name") or "").lower()
        if slug in ("brand", "marca", "manufacturer", "fabricante"):
            terms = attr.get("terms") or attr.get("options") or []
            if terms:
                t0 = terms[0]
                return t0.get("name", t0) if isinstance(t0, dict) else str(t0)
    return str(raw.get("brand") or "—")


def _category_from_raw(raw: dict) -> str:
    cats = raw.get("categories") or []
    if cats and isinstance(cats, list):
        c0 = cats[0]
        if isinstance(c0, dict):
            return str(c0.get("name") or "")
        return str(c0)
    return ""


class WooCommerceConnector(BaseConnector):
    platform = "woocommerce"

    async def search(
        self,
        store_config: dict,
        term: str,
        page: int = 1,
        limit: int = 20,
    ) -> list[dict]:
        base = _store_base(store_config)
        params: dict[str, Any] = {"page": page, "per_page": min(limit, 100)}
        if term:
            params["search"] = term

        # Prefer authenticated REST when keys exist (richer catalog filters).
        auth = _wc_auth(store_config)
        if auth:
            items = await self._rest_get(base, auth, params={"search": term, "page": page, "per_page": limit})
            if items:
                return items

        url = f"{base}{_STORE_API}"
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else data.get("products", [])
            logger.debug("woocommerce store api %s -> %s", url, resp.status_code)
            return []

    async def fetch_all_products(self, store_config: dict, max_pages: int = 20) -> list[dict]:
        """Full catalog — requires REST v3 credentials."""
        auth = _wc_auth(store_config)
        if not auth:
            logger.warning("woocommerce fetch_all_products skipped: no REST credentials")
            return []

        base = _store_base(store_config)
        all_items: list[dict] = []
        for page in range(1, max_pages + 1):
            batch = await self._rest_get(
                base,
                auth,
                params={"page": page, "per_page": 100, "status": "publish"},
            )
            if not batch:
                break
            all_items.extend(batch)
            if len(batch) < 100:
                break
        return all_items

    async def _rest_get(
        self,
        base: str,
        auth: tuple[str, str],
        *,
        params: dict[str, Any],
    ) -> list[dict]:
        url = f"{base}{_REST_API}"
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url, params=params, auth=auth)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            logger.debug("woocommerce rest %s -> %s", url, resp.status_code)
            return []

    def normalize(self, raw: dict, store_key: str, store_config: dict) -> dict:
        currency = store_config.get("currency", "USD")
        name = raw.get("name", "")
        product_id = str(raw.get("id", ""))

        # Store API shape
        if "prices" in raw and isinstance(raw.get("prices"), dict):
            prices = raw["prices"]
            price, list_price = _minor_unit_price(prices)
            currency = prices.get("currency_code") or currency
            stock = 1 if raw.get("is_in_stock", True) else 0
            url = raw.get("permalink", "")
            brand = _brand_from_raw(raw)
            category = _category_from_raw(raw)
            discount = round((1 - price / list_price) * 100) if list_price > price > 0 else None
            return {
                "id": product_id,
                "product_id": product_id,
                "name": clean_name(name),
                "brand": brand,
                "category": category,
                "price": price,
                "list_price": list_price,
                "discount": discount,
                "stock": int(stock),
                "store": store_key,
                "store_name": store_config.get("name", store_key),
                "currency": currency,
                "url": url,
            }

        # REST v3 shape
        price = parse_price(raw.get("price") or raw.get("regular_price"))
        list_price = parse_price(raw.get("regular_price") or price)
        sale = parse_price(raw.get("sale_price"))
        if sale and sale < list_price:
            price = sale
        discount = round((1 - price / list_price) * 100) if list_price > price > 0 else None
        stock = int(raw.get("stock_quantity") or (1 if raw.get("stock_status") == "instock" else 0))
        brand = _brand_from_raw(raw)
        category = _category_from_raw(raw)
        url = raw.get("permalink", "")
        return {
            "id": product_id,
            "product_id": product_id,
            "name": clean_name(name),
            "brand": brand,
            "category": category,
            "price": round(price, 2),
            "list_price": round(list_price, 2),
            "discount": discount,
            "stock": stock,
            "store": store_key,
            "store_name": store_config.get("name", store_key),
            "currency": currency,
            "url": url,
        }

    async def categories(self, store_config: dict) -> list[dict]:
        base = _store_base(store_config)
        auth = _wc_auth(store_config)
        if auth:
            url = f"{base}/wp-json/wc/v3/products/categories"
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(url, params={"per_page": 100}, auth=auth)
                if resp.status_code == 200:
                    return resp.json()
        return []