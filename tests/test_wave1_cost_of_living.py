"""Wave 1 — Affordability OS, TCO, substitutes, regulatory context."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from market_core import get_db
from market_core.market_billing import feature_allowed, substitute_limit_for_tier
from market_core.market_intel_products import compute_affordability, compute_inflation_report
from market_core.market_regulatory import list_regulatory_events, seed_default_regulatory_events
from market_core.market_substitutes import find_substitutes
from market_core.market_tco import compute_line_tco, payment_fee_amount
from market_core.market_basket import build_basket_compare, build_basket_tco
from market_core.response_envelope import build_provenance, confidence_from_coverage


def _seed_snapshots(db, rows: list[tuple]):
    for pid, store, store_name, name, price, line, currency, age_hours in rows:
        ts = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
        db.execute(
            """INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
            (pid, store, store_name, name, price, line, currency, ts),
        )
    db.commit()


def test_compute_affordability_empty_db(isolated_db):
    db = get_db()
    try:
        result = compute_affordability(db, country="PE", line="supermercados", days=30)
        assert result["country"] == "PE"
        assert 0 <= result["affordability_score"] <= 100
        assert result["affordability_band"] in {"comfortable", "moderate", "strained", "critical"}
        assert result["disclaimer_es"]
        assert result["components"]["canasta_min"] is None or isinstance(result["components"]["canasta_min"], float)
    finally:
        db.close()


def test_compute_affordability_with_canasta(isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong", "Wong", "Leche Gloria Entera 1L", 4.5, "supermercados", "PEN", 1),
            ("b", "wong", "Wong", "Arroz Costeno 1kg", 3.8, "supermercados", "PEN", 1),
            ("c", "metro", "Metro", "Leche Laive Entera 1L", 3.9, "supermercados", "PEN", 1),
        ])
        result = compute_affordability(db, country="PE", days=30)
        assert result["headline_es"]
        assert "regulatory_headlines" in result
    finally:
        db.close()


def test_inflation_report_includes_regulatory(isolated_db):
    db = get_db()
    try:
        seed_default_regulatory_events(db)
        report = compute_inflation_report(db, country="PE", days=30)
        assert "regulatory_headlines" in report
        assert isinstance(report["regulatory_headlines"], list)
    finally:
        db.close()


def test_regulatory_events_list(isolated_db):
    db = get_db()
    try:
        seed_default_regulatory_events(db)
        events = list_regulatory_events(db, country="PE", days=365)
        assert len(events) >= 3
        assert events[0]["effective_at"] >= events[-1]["effective_at"]
    finally:
        db.close()


def test_find_substitutes(isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong", "Wong", "Leche Gloria Entera 1L", 4.5, "supermercados", "PEN", 1),
            ("b", "metro", "Metro", "Leche Laive Entera 1L", 3.9, "supermercados", "PEN", 1),
        ])
        result = find_substitutes(db, query="leche gloria", country="PE", limit=2)
        assert result["original"] is not None
        assert result["original"]["price"] == 4.5
    finally:
        db.close()


def test_compute_line_tco_without_delivery():
    tco = compute_line_tco(shelf_subtotal=42.0, delivery=None, payment_method="yape")
    assert tco["tco_total"] == 42.0
    assert tco["delivery"]["available"] is False


def test_compute_line_tco_with_payment_fee():
    tco = compute_line_tco(shelf_subtotal=100.0, payment_method="paypal")
    assert tco["tco_total"] > 100.0
    pct, amt = payment_fee_amount(100.0, "paypal")
    assert amt > 0


def test_basket_compare_include_tco(isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong", "Wong", "Leche 1L", 5.0, "supermercados", "PEN", 1),
        ])
        result = build_basket_compare(db, items=[{"name": "leche"}], include_tco=True)
        assert result["stores"][0]["tco_total"] >= result["stores"][0]["total"]
        assert "cheapest_tco_store" in result
    finally:
        db.close()


def test_build_basket_tco(isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong", "Wong", "Leche 1L", 5.0, "supermercados", "PEN", 1),
        ])
        result = build_basket_tco(db, country="PE", store="wong", items=[{"name": "leche", "qty": 2}])
        assert result["subtotal_shelf"] == 10.0
        assert result["tco_total"] >= 10.0
    finally:
        db.close()


def test_build_provenance_and_confidence():
    prov = build_provenance(
        primary_source="price_snapshots",
        stores_responded=4,
        stores_queried=10,
    )
    assert prov["coverage_pct"] == 40.0
    assert confidence_from_coverage(35.0) == "low"
    assert confidence_from_coverage(80.0) == "ok"


def test_feature_allowed_tiers():
    assert feature_allowed("free", "affordability")
    assert not feature_allowed("free", "tco_delivery")
    assert substitute_limit_for_tier("free") == 1
    assert substitute_limit_for_tier("starter") == 3
