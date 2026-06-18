"""SQLite-backed tests for market_indicators compute/refresh paths."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from market_core import get_db
from market_core.market_indicators import (
    _indicator_is_stale,
    _upsert_indicator_value,
    compute_moat_freshness,
    compute_promo_intensity,
    compute_search_momentum,
    compute_store_coverage,
    get_indicator_catalog,
    refresh_internal_indicators,
    seed_indicator_definitions,
)


@pytest.fixture
def pe_stores(monkeypatch):
    stores = {
        "wong_pe": {"country": "PE", "disabled": False, "line": "supermercados"},
        "metro_pe": {"country": "PE", "disabled": False, "line": "supermercados"},
    }
    monkeypatch.setattr("market_core.market_core.STORES", stores)
    monkeypatch.setattr("market_core.market_indicators.STORES", stores)


def _seed_snapshots(db, *, fresh: bool = True) -> None:
    try:
        db.execute("ALTER TABLE price_snapshots ADD COLUMN canonical_product_id TEXT")
    except Exception:
        pass
    queried = datetime.now(timezone.utc) if fresh else datetime(2020, 1, 1, tzinfo=timezone.utc)
    ts = queried.strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        ("p1", "Leche 1L", "wong_pe", 5.0, 6.0, 10, ts),
        ("p2", "Arroz 1kg", "wong_pe", 4.0, 4.0, 0, ts),
        ("p3", "Aceite 1L", "metro_pe", 9.0, 10.0, 5, ts),
    ]
    for product_id, name, store, price, list_price, discount, queried_at in rows:
        db.execute(
            """
            INSERT INTO price_snapshots
                (product_id, name, store, price, list_price, discount, queried_at, line)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'supermercados')
            """,
            (product_id, name, store, price, list_price, discount, queried_at),
        )
    db.commit()


def test_compute_promo_intensity(pe_stores, isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db)
        val = compute_promo_intensity(db, "PE", "supermercados")
        assert val == pytest.approx(66.67, abs=0.1)
    finally:
        db.close()


def test_compute_moat_freshness(pe_stores, isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db, fresh=True)
        val = compute_moat_freshness(db, "PE")
        assert val == 100.0

        db.execute("UPDATE price_snapshots SET queried_at = '2020-01-01 00:00:00'")
        db.commit()
        stale = compute_moat_freshness(db, "PE")
        assert stale == 0.0
    finally:
        db.close()


def test_compute_store_coverage(pe_stores, isolated_db):
    db = get_db()
    try:
        _seed_snapshots(db)
        val = compute_store_coverage(db, "PE")
        assert val == 2.0
    finally:
        db.close()


def test_compute_search_momentum(pe_stores, isolated_db):
    db = get_db()
    try:
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        older = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO search_queries (query, country, created_at) VALUES ('leche', 'PE', ?)",
            (recent,),
        )
        db.execute(
            "INSERT INTO search_queries (query, country, created_at) VALUES ('arroz', 'PE', ?)",
            (older,),
        )
        db.commit()
        val = compute_search_momentum(db, "PE")
        assert val is not None and val >= 1.0
    finally:
        db.close()


def test_refresh_internal_indicators_writes_values(pe_stores, isolated_db):
    db = get_db()
    try:
        seed_indicator_definitions(db)
        _seed_snapshots(db)
        db.execute(
            "INSERT INTO search_queries (query, country, created_at) VALUES ('leche', 'PE', datetime('now'))"
        )
        db.commit()
        n = refresh_internal_indicators(db, "PE", "supermercados")
        assert n >= 4
        row = db.execute(
            "SELECT value FROM indicator_values WHERE indicator_key = 'promo_intensity' ORDER BY recorded_at DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert float(row["value"]) > 0
    finally:
        db.close()


def test_indicator_is_stale_and_catalog(pe_stores, isolated_db):
    db = get_db()
    try:
        seed_indicator_definitions(db)
        _upsert_indicator_value(
            db,
            indicator_key="promo_intensity",
            scope="PE:supermercados",
            value=12.5,
            country="PE",
            line="supermercados",
        )
        db.commit()
        assert _indicator_is_stale(db, "promo_intensity", "PE:supermercados", refresh_hours=24) is False
        assert _indicator_is_stale(db, "missing_key", "PE:all", refresh_hours=1) is True

        catalog = get_indicator_catalog()
        keys = {d["key"] for d in catalog}
        assert "promo_intensity" in keys
        assert "store_coverage" in keys
    finally:
        db.close()