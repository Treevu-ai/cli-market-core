"""Tests for market_quality.py — coverage freshness, unit normalization, match confidence."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from market_core import get_db
from market_core.market_quality import (
    build_data_quality_scores,
    compute_coverage_freshness,
    compute_match_confidence_rate,
    compute_unit_normalization_rate,
)


def _seed_snapshots(db, rows: list[tuple]):
    for pid, store, store_name, name, price, line, currency, age_hours in rows:
        ts = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
        conf = "ok" if age_hours < 24 else "suspect"
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pid, store, store_name, name, price, line, currency, ts, conf),
        )
    db.commit()


def test_coverage_freshness_empty(isolated_db):
    db = get_db()
    try:
        result = compute_coverage_freshness(db, days=7)
        assert result["global"]["total_snapshots"] == 0
        assert result["global"]["freshness_pct"] == 0.0
        assert result["cells"] == []
    finally:
        db.close()


def test_coverage_freshness_with_data(isolated_db, monkeypatch):
    monkeypatch.setattr(
        "market_core.market_quality.STORES",
        {"wong_pe": {"country": "PE"}, "metro_pe": {"country": "PE"}},
    )
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong_pe", "Wong", "Leche 1L", 5.0, "supermercados", "PEN", 1),
            ("b", "wong_pe", "Wong", "Arroz 1kg", 4.0, "supermercados", "PEN", 1),
            ("c", "metro_pe", "Metro", "Leche 1L", 5.5, "supermercados", "PEN", 200),
            ("d", "metro_pe", "Metro", "Aspirina", 3.0, "farmacias", "PEN", 3),
        ])
        result = compute_coverage_freshness(db, days=7)
        assert result["global"]["total_snapshots"] == 4
        assert result["global"]["fresh_snapshots"] == 3
        assert result["global"]["freshness_pct"] == 75.0
        assert result["global"]["window_days"] == 7
        assert len(result["cells"]) >= 2
        pct_sum = sum(c["freshness_pct"] for c in result["cells"])
        assert pct_sum > 0
    finally:
        db.close()


def test_coverage_freshness_custom_days(isolated_db, monkeypatch):
    monkeypatch.setattr("market_core.market_quality.STORES", {"wong_pe": {"country": "PE"}})
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong_pe", "Wong", "L1", 5.0, "s", "PEN", 0.5),
            ("b", "wong_pe", "Wong", "L2", 5.0, "s", "PEN", 25),
        ])
        r = compute_coverage_freshness(db, days=1)
        assert r["global"]["fresh_snapshots"] == 1
    finally:
        db.close()


def test_unit_normalization_empty(isolated_db):
    db = get_db()
    try:
        result = compute_unit_normalization_rate(db)
        assert result["total_products_sampled"] == 0
        assert result["normalization_pct"] == 0.0
    finally:
        db.close()


def test_unit_normalization_with_data(isolated_db, monkeypatch):
    monkeypatch.setattr("market_core.market_quality.STORES", {})
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "s1", "S1", "Leche Gloria 1L", 5.0, "supermercados", "PEN", 1),
            ("b", "s1", "S1", "Arroz Costeno 750g", 4.0, "supermercados", "PEN", 1),
            ("c", "s1", "S1", "Producto Sin Unidad", 10.0, "supermercados", "PEN", 1),
        ])
        result = compute_unit_normalization_rate(db)
        assert result["total_products_sampled"] == 3
        assert result["normalized_products"] == 2
        assert result["normalization_pct"] > 50.0
    finally:
        db.close()


def test_match_confidence_empty(isolated_db):
    db = get_db()
    try:
        result = compute_match_confidence_rate(db)
        assert result["total_snapshots"] == 0
        assert result["confidence_pct"] == 0.0
    finally:
        db.close()


def test_match_confidence_with_data(isolated_db, monkeypatch):
    monkeypatch.setattr("market_core.market_quality.STORES", {})
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "s1", "S1", "L1", 5.0, "s", "PEN", 1),
            ("b", "s1", "S1", "L2", 5.0, "s", "PEN", 26),
            ("c", "s1", "S1", "L3", 5.0, "s", "PEN", 0.1),
        ])
        result = compute_match_confidence_rate(db)
        assert result["total_snapshots"] == 3
        assert result["ok_snapshots"] == 2
        assert result["suspect_snapshots"] == 1
        assert result["confidence_pct"] == round(2 / 3 * 100, 1)
    finally:
        db.close()


def test_build_data_quality_scores(isolated_db, monkeypatch):
    monkeypatch.setattr("market_core.market_quality.STORES", {"s1": {"country": "PE"}})
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "s1", "S1", "Leche 1L", 5.0, "s", "PEN", 1),
            ("b", "s1", "S1", "Arroz 1kg", 4.0, "s", "PEN", 1),
            ("c", "s1", "S1", "Sin Unidad", 10.0, "s", "PEN", 1),
        ])
        result = build_data_quality_scores(db, days=7)
        assert "composite_score" in result
        assert "freshness" in result
        assert "unit_normalization" in result
        assert "match_confidence" in result
        assert 0 <= result["composite_score"] <= 100
        assert result["freshness"]["global"]["total_snapshots"] == 3
        assert result["unit_normalization"]["total_products_sampled"] == 3
        assert result["unit_normalization"]["normalized_products"] == 2
    finally:
        db.close()


def test_coverage_matrix_freshness(isolated_db, monkeypatch):
    from market_core.data_v1_service import build_coverage_matrix

    monkeypatch.setattr(
        "market_core.data_v1_service.STORES",
        {"wong_pe": {"country": "PE"}, "metro_pe": {"country": "PE"}},
    )
    db = get_db()
    try:
        _seed_snapshots(db, [
            ("a", "wong_pe", "Wong", "Leche", 5.0, "supermercados", "PEN", 1),
            ("b", "wong_pe", "Wong", "Arroz", 4.0, "supermercados", "PEN", 1),
            ("c", "metro_pe", "Metro", "Pan", 3.0, "supermercados", "PEN", 200),
        ])
        result = build_coverage_matrix(db)
        assert len(result["cells"]) >= 1
        for cell in result["cells"]:
            assert "freshness_pct" in cell
            assert isinstance(cell["freshness_pct"], (int, float)) or cell["freshness_pct"] is None
    finally:
        db.close()
