"""Unit tests for VTEX connector helpers and search (mocked HTTP)."""

from __future__ import annotations

import pytest

from market_connectors.vtex import (
    VtexConnector,
    _client_headers,
    _vtex_headers,
    _vtex_json_list,
)


class _FakeResp:
    def __init__(self, status_code: int, content_type: str, payload):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._payload = payload

    def json(self):
        return self._payload


def test_vtex_headers_with_credentials():
    cfg = {"vtex_app_key": "key-1", "vtex_app_token": "tok-1"}
    assert _vtex_headers(cfg)["X-VTEX-API-AppKey"] == "key-1"
    headers = _client_headers(cfg)
    assert "User-Agent" in headers
    assert headers["X-VTEX-API-AppToken"] == "tok-1"


def test_vtex_headers_without_credentials():
    assert _vtex_headers({}) == {}


def test_vtex_normalize_product():
    connector = VtexConnector()
    raw = {
        "productId": "42",
        "productReference": "REF-42",
        "productName": "Leche-Gloria-1L",
        "brand": "Gloria",
        "categoryId": "100",
        "items": [
            {
                "sellers": [
                    {
                        "commertialOffer": {
                            "Price": 5.5,
                            "ListPrice": 6.0,
                            "AvailableQuantity": 12,
                        }
                    }
                ]
            }
        ],
        "link": "https://shop.example/leche",
    }
    store_config = {
        "name": "Wong",
        "currency": "PEN",
        "line": "supermercados",
        "base": "https://www.wong.pe",
    }
    out = connector.normalize(raw, "wong_pe", store_config)
    assert out["product_id"] == "REF-42"
    assert out["name"] == "Leche Gloria 1L"
    assert out["price"] == 5.5
    assert out["discount"] == 8
    assert out["stock"] == 12
    assert out["currency"] == "PEN"


def test_vtex_api_url_respects_io_path():
    connector = VtexConnector()
    cfg = {"base": "https://shop.example", "_io_path": "/io"}
    url = connector._api_url(cfg, "catalog_system/pub/products/search")
    assert url == "https://shop.example/io/api/catalog_system/pub/products/search"


@pytest.mark.asyncio
async def test_vtex_search_direct_http(monkeypatch):
    connector = VtexConnector()
    store_config = {
        "name": "Wong",
        "base": "https://www.wong.pe",
        "_io_path": "",
        "_store_key": "wong_pe",
        "currency": "PEN",
    }
    payload = [{"productId": "1", "productName": "Leche"}]

    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            return _FakeResp(206, "application/json", payload)

    monkeypatch.setattr("market_connectors.vtex.httpx.AsyncClient", FakeAsyncClient)
    results = await connector.search(store_config, "leche", page=1, limit=20)
    assert len(results) == 1
    assert results[0]["productId"] == "1"


@pytest.mark.asyncio
async def test_vtex_detect_io_standard_path(monkeypatch):
    connector = VtexConnector()
    store_config = {"base": "https://www.wong.pe", "name": "Wong"}

    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            if "/io/" in url:
                return _FakeResp(404, "text/html", "")
            return _FakeResp(200, "application/json", [])

    monkeypatch.setattr("market_connectors.vtex.httpx.AsyncClient", FakeAsyncClient)
    io = await connector._detect_io(store_config)
    assert io == ""
    assert store_config["_io_path"] == ""


def test_vtex_json_list_rejects_non_list_payload():
    resp = _FakeResp(200, "application/json", {"products": []})
    assert _vtex_json_list(resp) is None