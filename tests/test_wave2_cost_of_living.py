"""Wave 2 — household profile, action links, optimize_purchase mission."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from market_core import get_db
from market_core.market_action_links import (
    create_shopping_list_export,
    get_shopping_list_export,
    retailer_deeplink,
)
from market_core.market_billing import feature_allowed
from market_core.market_household import (
    get_household,
    household_summary,
    patch_household,
    put_household,
    substitute_constraints_from_household,
)
from market_core.market_missions import run_optimize_purchase


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


def test_household_crud(isolated_db):
    db = get_db()
    try:
        profile = put_household(db, "alice", {"size": 2, "budget_monthly": 800.0, "country": "PE"})
        assert profile["size"] == 2
        assert get_household(db, "alice")["budget_monthly"] == 800.0
        patched = patch_household(db, "alice", {"restrictions": {"lactose_free": True}})
        assert patched["restrictions"]["lactose_free"] is True
        summary = household_summary(db, "alice")
        assert summary["budget_remaining"] == 800.0
    finally:
        db.close()


def test_substitute_constraints_from_household():
    constraints = substitute_constraints_from_household({"restrictions": {"vegetarian": True}})
    assert constraints.get("max_nova") == 3


def test_retailer_deeplink():
    link = retailer_deeplink("wong", product_id="12345")
    assert link is not None
    assert link["url"].endswith("/12345/p")


def test_shopping_list_export_ttl(isolated_db):
    db = get_db()
    try:
        meta = create_shopping_list_export(db, {"title": "test", "items": []}, ttl_hours=72)
        loaded = get_shopping_list_export(db, meta["token"])
        assert loaded["title"] == "test"
        assert get_shopping_list_export(db, "missing") is None
    finally:
        db.close()


def test_run_optimize_purchase(isolated_db):
    db = get_db()
    try:
        _seed(db)
        put_household(db, "bob", {"budget_monthly": 500.0, "country": "PE"})
        result = run_optimize_purchase(
            db,
            country="PE",
            items=[{"name": "leche", "qty": 2}],
            username="bob",
        )
        assert result["status"] == "ok"
        assert result["recommendation"]["primary_store"]
        assert result["action_links"]
    finally:
        db.close()


def test_wave2_billing_gates():
    assert feature_allowed("starter", "optimize_purchase")
    assert feature_allowed("pro", "household_write")
    assert not feature_allowed("free", "household_write")
