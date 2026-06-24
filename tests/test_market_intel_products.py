"""Tests for market_intel_products.py and build_basket_compare."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from market_core import get_db
from market_core.market_intel_products import (
    _interpret_inflation_pressure,
    _interpret_price_risk,
    _interpret_procurement,
    compute_price_deal_alerts,
)
from market_core.market_basket import build_basket_compare


def _seed_snapshots(db, rows: list[tuple]):
    for pid, store, store_name, name, price, line, currency, age_hours in rows:
        ts = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
        db.execute(
            """INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
            (pid, store, store_name, name, price, line, currency, ts),
        )
    db.commit()


# ── interpretation helpers (pure functions) ─────────────────────────────────────

def test_interpret_price_risk_low():
    level, _ = _interpret_price_risk(10.0, 20.0, 1.0)
    assert level == "low"


def test_interpret_price_risk_high():
    level, _ = _interpret_price_risk(60.0, 35.0, 6.0)
    assert level == "high"


def test_interpret_price_risk_moderate():
    level, _ = _interpret_price_risk(30.0, 15.0, 0.0)
    assert level == "moderate"


def test_interpret_price_risk_none_signals():
    level, reason = _interpret_price_risk(None, None, None)
    assert level == "low"
    assert "stable" in reason


def test_interpret_inflation_pressure():
    assert _interpret_inflation_pressure(12.0, None, None) == "rising_fast"
    assert _interpret_inflation_pressure(6.0, None, None) == "rising"
    assert _interpret_inflation_pressure(-3.0, None, None) == "falling"
    assert _interpret_inflation_pressure(None, None, 3.0) == "above_official"
    assert _interpret_inflation_pressure(2.0, 1.0, 0.5) == "stable"


def test_interpret_procurement():
    s, _ = _interpret_procurement(90.0, 1.0, 0.0)
    assert s == "buy_now"
    s2, _ = _interpret_procurement(115.0, 1.0, 0.0)
    assert s2 == "wait"
    s3, _ = _interpret_procurement(100.0, 1.0, 0.0)
    assert s3 == "monitor"


def test_interpret_procurement_staples_rising():
    s, _ = _interpret_procurement(100.0, 1.0, 6.0)
    assert s == "wait"


def test_compute_price_deal_alerts(isolated_db):
    db = get_db()
    try:
        ts = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        db.execute(
            """INSERT INTO price_snapshots
               (product_id, store, store_name, name, price, list_price, line, currency, queried_at, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
            ("717238", "metro", "Metro", "Aceite Vegetal Máxima 900ml", 5.4, 5.7, "supermercados", "PEN", ts),
        )
        db.execute(
            """INSERT INTO price_snapshots
               (product_id, store, store_name, name, price, list_price, line, currency, queried_at, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
            ("959308", "plazavea", "Plaza Vea", "Aceite Vegetal BELL'S 900ml", 5.7, 5.7, "supermercados", "PEN", ts),
        )
        db.commit()
        result = compute_price_deal_alerts(
            db, product="aceite vegetal", store="metro", threshold_pct=5.0, limit=5
        )
        assert result["total"] == 1
        hit = result["results"][0]
        assert hit["store"] == "metro"
        assert hit["discount_pct"] == 5.3
        empty = compute_price_deal_alerts(db, product="aceite vegetal", store="plazavea", threshold_pct=5.0)
        assert empty["total"] == 0
    finally:
        db.close()


# ── intel products (DB schema dependent — skipped in unit test suite) ───────────

@pytest.mark.skip(reason="requires full DB schema with indicator_definitions seeded")
def test_compute_price_risk_shape():
    pass


@pytest.mark.skip(reason="requires full DB schema")
def test_compute_inflation_report_shape():
    pass


@pytest.mark.skip(reason="requires full DB schema")
def test_compute_procurement_signal_shape():
    pass


# ── basket compare ──────────────────────────────────────────────────────────────

def test_basket_compare_empty(isolated_db):
    db = get_db()
    try:
        result = build_basket_compare(db, items=[])
        assert result["items_searched"] == 0
        assert result["items_found"] == 0
        assert result["stores"] == []
    finally:
        db.close()


def test_basket_compare_with_items(isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong_pe", "Wong", "Leche entera 1L", 5.0, "supermercados", "PEN", 1),
            ("b", "wong_pe", "Wong", "Arroz extra 1kg", 4.0, "supermercados", "PEN", 1),
            ("c", "metro_pe", "Metro", "Leche entera 1L", 5.5, "supermercados", "PEN", 1),
            ("d", "metro_pe", "Metro", "Arroz extra 1kg", 3.5, "supermercados", "PEN", 1),
        ])
        result = build_basket_compare(db, items=[{"name": "leche", "qty": 2}, {"name": "arroz", "qty": 1}])
        assert result["items_searched"] == 2
        assert result["items_found"] == 2
        assert len(result["stores"]) >= 1
        for store in result["stores"]:
            assert "total" in store
            assert "currency" in store
            assert "breakdown" in store
    finally:
        db.close()


def test_basket_compare_store_filter(isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong_pe", "Wong", "Leche entera 1L", 5.0, "supermercados", "PEN", 1),
            ("b", "metro_pe", "Metro", "Leche entera 1L", 5.5, "supermercados", "PEN", 1),
        ])
        result = build_basket_compare(db, items=[{"name": "leche"}], store_filter={"wong_pe"})
        assert len(result["stores"]) == 1
        assert result["stores"][0]["store_name"] == "Wong"
    finally:
        db.close()


def test_basket_compare_filters_food_artifacts(isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("bat", "metro_pe", "Metro", "Batidor de Huevos Krea", 3.0, "supermercados", "PEN", 1),
            ("egg", "metro_pe", "Metro", "Huevos Pardos Metro Bandeja 8 Unid", 6.49, "supermercados", "PEN", 1),
            ("fish", "metro_pe", "Metro", "Filete de Atún en Aceite Vegetal 170g", 3.7, "supermercados", "PEN", 1),
            ("oil", "metro_pe", "Metro", "Aceite Vegetal Primor 900ml", 9.5, "supermercados", "PEN", 1),
        ])
        result = build_basket_compare(
            db,
            items=[{"name": "huevos", "qty": 1}, {"name": "aceite vegetal", "qty": 1}],
            store_filter={"metro_pe"},
        )
        assert result["items_found"] == 2
        breakdown = {b["item"]: b for b in result["stores"][0]["breakdown"]}
        assert "Bandeja" in breakdown["huevos"]["resolved_name"]
        assert "Primor" in breakdown["aceite vegetal"]["resolved_name"]
    finally:
        db.close()


def test_basket_compare_enveloped(isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, [("a", "wong_pe", "Wong", "Leche entera 1L", 5.0, "supermercados", "PEN", 1)])
        result = build_basket_compare(db, items=[{"name": "leche"}], enveloped=True)
        assert "data" in result
        assert "meta" in result
        assert "trace" in result
    finally:
        db.close()
