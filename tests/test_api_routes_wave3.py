"""Integration tests — v1 router wave 3 endpoints."""

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
    api_routes._auth_fn = lambda _auth: "wave3_user"
    yield TestClient(app)
    api_routes._auth_fn = None


def _seed(db):
    ts = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
        ("p1", "wong", "Wong", "Leche Gloria Entera 1L", 4.2, "supermercados", "PEN", ts),
    )
    db.commit()


def test_receipts_submit_and_get(client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = client.post(
        "/v1/receipts/submit",
        json={
            "url": "https://example.com/boleta.jpg",
            "country": "PE",
            "line_items": [{"name": "Leche Gloria Entera 1L", "unit_price": 4.8}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["status"] == "confirmed"
    rid = body["data"]["id"]
    r2 = client.get(f"/v1/receipts/{rid}")
    assert r2.status_code == 200
    assert r2.json()["data"]["id"] == rid


def test_moat_confidence(client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = client.get("/v1/moat/confidence?product_id=p1&store=wong")
    assert r.status_code == 200
    assert "confidence_tier" in r.json()["data"]


def test_ecosystem_launches(client):
    r = client.get("/v1/ecosystem/launches?topic=food&limit=3")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["launches"]
    assert data["disclaimer"]


def test_procurement_bulk_requires_auth(client):
    r = client.post("/v1/intel/procurement-bulk", json={"lines": [{"sku_query": "leche"}]})
    assert r.status_code == 401


def test_procurement_bulk_ok(authed_client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = authed_client.post(
        "/v1/intel/procurement-bulk",
        json={
            "country": "PE",
            "organization_id": "org-test",
            "lines": [{"sku_query": "leche gloria", "qty": 5}],
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "ok"
    assert data["aggregate_signal"] in {"buy_now", "monitor", "wait"}
