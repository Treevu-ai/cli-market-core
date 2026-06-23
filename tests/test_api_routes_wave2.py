"""Integration tests — v1 router wave 2 (household, optimize-purchase, exports)."""

from __future__ import annotations

import json
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
    api_routes._auth_fn = lambda _auth: "wave2_user"
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


def test_household_requires_auth(client):
    r = client.get("/v1/household")
    assert r.status_code == 401


def test_household_put_get_summary(authed_client, isolated_db):
    from market_core import get_db

    payload = {
        "size": 3,
        "country": "PE",
        "currency": "PEN",
        "budget_monthly": 1200.0,
        "restrictions": {"vegetarian": True},
    }
    r = authed_client.put("/v1/household", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["budget_monthly"] == 1200.0
    assert body["data"]["restrictions"]["vegetarian"] is True

    r2 = authed_client.get("/v1/household")
    assert r2.status_code == 200
    assert r2.json()["data"]["size"] == 3

    r3 = authed_client.get("/v1/household/summary")
    assert r3.status_code == 200
    summary = r3.json()["data"]
    assert summary["budget_remaining"] == 1200.0
    assert summary["suggested_action"] in {"monitor", "buy_now", "wait", "setup_profile"}


def test_household_put_invalid_budget(authed_client):
    r = authed_client.put("/v1/household", json={"budget_monthly": -10})
    assert r.status_code == 422


def test_optimize_purchase_mission(authed_client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = authed_client.post(
        "/v1/missions/optimize-purchase",
        json={
            "country": "PE",
            "items": [{"name": "leche", "qty": 2}],
            "constraints": {"include_tco": True, "allow_substitutes": True},
            "include_intel": True,
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["mission"] == "optimize_purchase"
    assert data["status"] == "ok"
    assert data["recommendation"]["tco_total"] >= data["recommendation"]["shelf_total"]
    assert len(data["action_links"]) >= 1


def test_shopping_list_export_roundtrip(authed_client, isolated_db):
    from market_core import get_db

    db = get_db()
    try:
        _seed(db)
    finally:
        db.close()

    r = authed_client.post(
        "/v1/missions/optimize-purchase",
        json={"country": "PE", "items": [{"name": "leche", "qty": 1}]},
    )
    links = r.json()["data"]["action_links"]
    export = next(link for link in links if link.get("type") == "export_list")
    token = export["token"]
    r2 = authed_client.get(f"/v1/export/shopping-list/{token}")
    assert r2.status_code == 200
    payload = r2.json()
    assert payload["country"] == "PE"
    assert payload["items"]
