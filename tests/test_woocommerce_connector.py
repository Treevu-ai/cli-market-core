"""WooCommerce connector unit tests."""

from __future__ import annotations

import pytest

from market_connectors.woocommerce import (
    WooCommerceConnector,
    _brand_from_name,
    _minor_unit_price,
)


def test_minor_unit_price_conversion():
    prices = {
        "price": "9900",
        "regular_price": "12900",
        "sale_price": "9900",
        "currency_minor_unit": 2,
        "currency_code": "USD",
    }
    price, list_price = _minor_unit_price(prices)
    assert price == 99.0
    assert list_price == 129.0


def test_normalize_store_api_shape():
    connector = WooCommerceConnector()
    raw = {
        "id": 42,
        "name": "Aceite Primor 1L",
        "permalink": "https://demo.test/product/aceite-primor-1l/",
        "is_in_stock": True,
        "prices": {
            "price": "890",
            "regular_price": "990",
            "sale_price": "890",
            "currency_code": "PEN",
            "currency_minor_unit": 2,
        },
        "categories": [{"name": "Aceites"}],
        "brands": [{"name": "Primor"}],
    }
    cfg = {"name": "Demo PE", "base": "https://demo.test", "currency": "PEN"}
    out = connector.normalize(raw, "demo_pe", cfg)
    assert out["price"] == 8.9
    assert out["list_price"] == 9.9
    assert out["brand"] == "Primor"
    assert out["currency"] == "PEN"
    assert out["url"].endswith("/")


def test_minor_unit_zero_keeps_whole_currency():
    prices = {
        "price": "108",
        "regular_price": "108",
        "sale_price": "108",
        "currency_minor_unit": 0,
        "currency_code": "PEN",
    }
    price, list_price = _minor_unit_price(prices)
    assert price == 108.0
    assert list_price == 108.0


def test_brand_from_name_fmcg_titles():
    assert _brand_from_name("Galleta de Arroz Y Multicereales 60gr AndeanRice") == "AndeanRice"
    assert _brand_from_name("Pan de arroz GF 710gr LaPurita") == "LaPurita"
    assert _brand_from_name("Aceite Primor 1L") == ""


def test_normalize_store_api_infers_brand_from_title():
    connector = WooCommerceConnector()
    raw = {
        "id": 15552,
        "name": "Pan de arroz GF 710gr LaPurita",
        "permalink": "https://nunaorganica.pe/producto/pan-de-arroz/",
        "is_in_stock": True,
        "prices": {
            "price": "1253",
            "regular_price": "1790",
            "sale_price": "1253",
            "currency_code": "PEN",
            "currency_minor_unit": 2,
        },
        "categories": [{"name": "PANADERIA Y TOSTADAS"}],
    }
    cfg = {"name": "Nuna Orgánica", "base": "https://nunaorganica.pe", "currency": "PEN"}
    out = connector.normalize(raw, "nunaorganica_pe", cfg)
    assert out["brand"] == "LaPurita"


def test_normalize_rest_v3_shape():
    connector = WooCommerceConnector()
    raw = {
        "id": 7,
        "name": "Leche Gloria 1L",
        "regular_price": "4.50",
        "sale_price": "4.20",
        "stock_status": "instock",
        "stock_quantity": 12,
        "permalink": "https://demo.test/leche-gloria/",
        "categories": [{"name": "Lácteos"}],
    }
    cfg = {"name": "Demo", "base": "https://demo.test", "currency": "PEN"}
    out = connector.normalize(raw, "demo", cfg)
    assert out["price"] == 4.2
    assert out["stock"] == 12