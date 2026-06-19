"""Tests for market_slas.py — p50/p95 freshness, error rates, per-retailer health."""

from __future__ import annotations

from market_core import get_db
from market_core.market_slas import _percentile, slas_by_retailer, slas_summary


def test_percentile():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert _percentile(values, 50) == 3.0
    assert _percentile(values, 0) == 1.0
    assert _percentile(values, 100) == 5.0
    assert _percentile([], 50) == 0.0


def test_percentile_p95():
    values = list(range(1, 101))
    p95 = _percentile(values, 95)
    assert 94 < p95 < 96


def test_slas_by_retailer_empty_db(isolated_db):
    db = get_db()
    try:
        result = slas_by_retailer(db)
        assert result["measured_stores"] == 0
        assert result["alive_24h"] == 0
        assert result["dead_24h"] == 0
        assert result["freshness_p50_secs"] is None
        assert result["freshness_p95_secs"] is None
        assert result["error_rate_pct"] == 0.0
    finally:
        db.close()


def test_slas_by_retailer_with_data(isolated_db, monkeypatch):
    monkeypatch.setattr(
        "market_core.market_slas.STORES",
        {
            "wong_pe": {"country": "PE"},
            "metro_pe": {"country": "PE"},
            "tottus_pe": {"country": "PE"},
        },
    )
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at)
            VALUES
                ('a', 'wong_pe', 'Wong', 'Leche', 5.0, 'supermercados', 'PEN', datetime('now', '-30 minutes')),
                ('b', 'wong_pe', 'Wong', 'Arroz', 4.0, 'supermercados', 'PEN', datetime('now', '-1 hour')),
                ('c', 'metro_pe', 'Metro', 'Pan', 3.0, 'supermercados', 'PEN', datetime('now', '-2 hours')),
                ('d', 'tottus_pe', 'Tottus', 'Aceite', 8.0, 'supermercados', 'PEN', datetime('now', '-30 hours'))
            """
        )
        db.commit()
        result = slas_by_retailer(db)
        assert result["measured_stores"] == 3
        assert result["defined_stores"] == 3
        assert result["alive_24h"] == 2  # wong and metro under 24h
        assert result["dead_24h"] == 1  # tottus over 24h
        assert result["freshness_p50_secs"] is not None
        assert result["freshness_p95_secs"] is not None
        assert result["error_rate_pct"] > 0
        assert len(result["retailers"]) == 3
    finally:
        db.close()


def test_slas_summary(isolated_db, monkeypatch):
    monkeypatch.setattr(
        "market_core.market_slas.STORES",
        {"wong_pe": {"country": "PE"}},
    )
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at)
            VALUES ('a', 'wong_pe', 'Wong', 'Leche', 5.0, 'supermercados', 'PEN', datetime('now'))
            """
        )
        db.commit()
        summary = slas_summary(db)
        assert summary["stores_alive"] == 1
        assert summary["stores_dead"] == 0
        assert summary["stores_total"] == 1
        assert summary["freshness_p50_secs"] is not None
        assert summary["error_rate_pct"] == 0.0
    finally:
        db.close()


def test_slas_by_retailer_with_line_filter(isolated_db, monkeypatch):
    monkeypatch.setattr(
        "market_core.market_slas.STORES",
        {"wong_pe": {"country": "PE"}},
    )
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at)
            VALUES
                ('a', 'wong_pe', 'Wong', 'Leche', 5.0, 'supermercados', 'PEN', datetime('now')),
                ('b', 'wong_pe', 'Wong', 'Aspirina', 3.0, 'farmacias', 'PEN', datetime('now'))
            """
        )
        db.commit()
        full = slas_by_retailer(db)
        filtered = slas_by_retailer(db, line="farmacias")
        assert filtered["measured_stores"] == 1
        assert filtered["retailers"][0]["snapshots"] == 1
    finally:
        db.close()
