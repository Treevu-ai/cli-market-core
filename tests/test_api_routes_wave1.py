"""Integration tests — v1 router mounted (wave 1 endpoints)."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from market_core.dev_app import app


@pytest.fixture
def client(isolated_db):
    return TestClient(app)


def _seed(db_path_unused, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
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
    finally:
        db.close()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_intel_affordability_envelope(client):
    r = client.get("/v1/intel/affordability?country=PE&days=30")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert "meta" in body
    assert "trace" in body
    assert body["data"]["country"] == "PE"
    assert "affordability_score" in body["data"]


def test_intel_regulatory(client):
    r = client.get("/v1/intel/regulatory?country=PE&days=365")
    assert r.status_code == 200
    events = r.json()["data"]["events"]
    assert isinstance(events, list)
    assert len(events) >= 3


def test_intel_price_deal_alerts(client, isolated_db):
    from market_core import get_db
    from datetime import datetime, timezone

    db = get_db()
    try:
        ts = datetime.now(timezone.utc).isoformat()
        db.execute(
            """INSERT INTO price_snapshots
               (product_id, store, store_name, name, price, list_price, line, currency, queried_at, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
            ("576341", "metro", "Metro", "Arroz Superior Paisana 1 kg", 4.4, 4.9, "supermercados", "PEN", ts),
        )
        db.commit()
    finally:
        db.close()
    r = client.get("/v1/intel/alerts?product=arroz&store=metro&threshold_pct=5&enveloped=false")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["results"][0]["store"] == "metro"


def test_products_substitutes(client, isolated_db):
    _seed(None, isolated_db)
    r = client.get("/v1/products/substitutes?query=leche&country=PE&limit=2")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["original"] is not None


def test_basket_tco(client, isolated_db):
    _seed(None, isolated_db)
    items = json.dumps([{"name": "leche", "qty": 2}])
    r = client.get(f"/v1/basket/tco?country=PE&store=wong&items={items}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["subtotal_shelf"] == 9.0
    assert data["tco_total"] >= 9.0


def test_existing_intel_price_risk(client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        db.execute("ALTER TABLE price_snapshots ADD COLUMN canonical_product_id TEXT")
        db.commit()
    finally:
        db.close()
    r = client.get("/v1/intel/price-risk?country=PE")
    assert r.status_code == 200
    assert "data" in r.json()
