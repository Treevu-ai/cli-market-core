"""Integration tests — v1 router wave 4 (action closure, delivery, flags)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from market_core import api_routes
from market_core.dev_app import app


@pytest.fixture
def client(isolated_db):
    return TestClient(app)


@pytest.fixture
def authed_client(isolated_db):
    api_routes._auth_fn = lambda _auth: "wave4_user"
    yield TestClient(app)
    api_routes._auth_fn = None


def _seed(db):
    ts = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
        ("p1", "wong", "Wong", "Leche Gloria Entera 1L", 4.5, "supermercados", "PEN", ts),
    )
    db.execute(
        """INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
        ("p2", "metro", "Metro", "Leche Laive Entera 1L", 3.9, "supermercados", "PEN", ts),
    )
    db.commit()


def test_basket_compare_with_tco_and_provenance(client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = client.post(
        "/v1/basket/compare",
        json={
            "country": "PE",
            "items": [{"name": "leche", "qty": 2}],
            "include_tco": True,
            "include_delivery": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "provenance" in body["meta"]
    data = body["data"]
    assert data["stores"]
    assert data["stores"][0].get("tco_total") is not None


def test_basket_compare_action_links(client, isolated_db, monkeypatch):
    from market_core import get_db

    monkeypatch.setenv("AFFILIATE_STORES", "wong,metro")
    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = client.post(
        "/v1/basket/compare",
        json={
            "country": "PE",
            "items": [{"name": "leche", "qty": 1}],
            "include_tco": True,
            "include_action_links": True,
        },
    )
    assert r.status_code == 200
    links = r.json()["data"]["action_links"]
    assert links
    deeplink = next(link for link in links if link["type"] == "retailer_deeplink")
    assert deeplink["affiliate"] is True


def test_basket_tco_delivery_block(client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = client.get(
        '/v1/basket/tco?country=PE&store=wong&items=[{"name":"leche","qty":2}]&include_delivery=true'
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["delivery"]["available"] is True
    assert data["tco_total"] > data["subtotal_shelf"]
    assert "delivery" in r.json()["meta"]["provenance"]["sources_used"]


def test_affiliate_click_endpoint(client):
    r = client.post(
        "/v1/action/affiliate-click",
        json={"store": "wong", "url": "https://www.wong.pe/123/p", "product_id": "123", "country": "PE"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["store"] == "wong"


def test_household_disabled_returns_503(authed_client, monkeypatch):
    monkeypatch.setenv("HOUSEHOLD_ENABLED", "0")
    r = authed_client.get("/v1/household")
    assert r.status_code == 503


def test_optimize_purchase_has_provenance(authed_client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = authed_client.post(
        "/v1/missions/optimize-purchase",
        json={"country": "PE", "items": [{"name": "leche", "qty": 1}], "constraints": {"include_tco": True}},
    )
    assert r.status_code == 200
    meta = r.json()["meta"]
    assert meta["provenance"]["methodology"] == "optimize_purchase_v1"
