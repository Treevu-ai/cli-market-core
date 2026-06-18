"""Extended indicator tests — latest values, scores, basket stress."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from market_core import get_db
from market_core.golden_taxonomy import set_taxonomy_registry
from market_core.market_indicators import (
    _scores_from_latest,
    compute_basket_stress,
    compute_internal_inflation_avg,
    get_latest_values,
    get_scores,
    seed_indicator_definitions,
)


@pytest.fixture
def pe_stores(monkeypatch):
    stores = {
        "wong_pe": {"country": "PE", "disabled": False, "line": "supermercados"},
    }
    monkeypatch.setattr("market_core.market_core.STORES", stores)
    monkeypatch.setattr("market_core.market_indicators.STORES", stores)


def test_get_latest_values_dedupes_scopes(pe_stores, isolated_db):
    db = get_db()
    try:
        seed_indicator_definitions(db)
        db.execute(
            """
            INSERT INTO indicator_values
                (indicator_key, scope, country, line, value, metadata_json, recorded_at)
            VALUES
                ('promo_intensity', 'PE:supermercados', 'PE', 'supermercados', 12.0, '{}', datetime('now')),
                ('promo_intensity', 'PE:supermercados', 'PE', 'supermercados', 10.0, '{}', datetime('now', '-1 day'))
            """
        )
        db.commit()
        rows = get_latest_values(db, country="PE", line="supermercados")
        promo = [r for r in rows if r["key"] == "promo_intensity"]
        assert len(promo) == 1
        assert promo[0]["value"] == 12.0
    finally:
        db.close()


def test_compute_basket_stress_with_golden(pe_stores, isolated_db):
    db = get_db()
    try:
        try:
            db.execute("ALTER TABLE price_snapshots ADD COLUMN canonical_product_id TEXT")
        except Exception:
            pass
        set_taxonomy_registry(
            db,
            {
                "prod_leche": {"canasta_item": "leche"},
                "prod_arroz": {"canasta_item": "arroz"},
                "prod_aceite": {"canasta_item": "aceite"},
            },
        )
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, name, price, canonical_product_id, line)
            VALUES ('a', 'wong_pe', 'Leche', 5.0, 'prod_leche', 'supermercados'),
                   ('b', 'wong_pe', 'Arroz', 4.0, 'prod_arroz', 'supermercados'),
                   ('c', 'wong_pe', 'Aceite', 9.0, 'prod_aceite', 'supermercados')
            """
        )
        db.commit()
        stress = compute_basket_stress(db, "PE")
        assert stress is not None
        assert stress >= 18.0
    finally:
        db.close()


def test_compute_internal_inflation_avg(pe_stores, isolated_db):
    db = get_db()
    try:
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        recent = now.strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """
            INSERT INTO price_history (product_id, store, price, recorded_at)
            VALUES ('p1', 'wong_pe', 4.0, ?),
                   ('p1', 'wong_pe', 5.0, ?)
            """,
            (old, recent),
        )
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, name, price, line)
            VALUES ('p1', 'wong_pe', 'Arroz', 5.0, 'supermercados')
            """
        )
        db.commit()
        val = compute_internal_inflation_avg(db, "PE", "supermercados", days=30)
        assert val is not None
        assert val > 0
    finally:
        db.close()


def test_scores_from_latest_and_get_scores(pe_stores, isolated_db):
    db = get_db()
    try:
        seed_indicator_definitions(db)
        scope = "PE:supermercados"
        for key, value in [
            ("promo_intensity", 20.0),
            ("price_dispersion", 15.0),
            ("moat_freshness", 80.0),
            ("basket_stress_index", 25.0),
        ]:
            db.execute(
                """
                INSERT INTO indicator_values
                    (indicator_key, scope, country, line, value, metadata_json, recorded_at)
                VALUES (?, ?, 'PE', 'supermercados', ?, '{}', datetime('now'))
                """,
                (key, scope, value),
            )
        db.commit()

        latest_rows = get_latest_values(db, country="PE", line="supermercados")
        latest_map = {r["key"]: r for r in latest_rows}
        scores = _scores_from_latest(latest_map)
        assert "retail_aggression" in scores
        assert scores["retail_aggression"]["score"] == 40.0

        result = get_scores(db, country="PE", line="supermercados")
        assert result["country"] == "PE"
        assert "scores" in result
    finally:
        db.close()