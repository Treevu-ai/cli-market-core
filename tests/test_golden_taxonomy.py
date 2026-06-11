"""Golden taxonomy bridge — enrichment_cache registry + canasta prices."""

import pytest

from market_core import ensure_db_initialized, get_db
from market_core.golden_taxonomy import (
    REGISTRY_CACHE_KEY,
    canonical_price_buckets,
    min_canasta_prices_golden,
    set_taxonomy_registry,
    staple_price_deltas_golden,
)
from market_core.market_indicators import compute_price_dispersion, compute_staple_price_momentum
from market_core.market_enrich_sources import cache_get


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "golden_taxonomy_test.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr("market_core.market_core.DB_FILE", db_file)
    monkeypatch.setattr("market_core.market_core.USE_PG", False)
    monkeypatch.setattr("market_core.market_core._pg_fell_back", False)
    monkeypatch.setattr("market_core.market_core._db_initialized", False)
    ensure_db_initialized()
    yield db_file


def test_min_canasta_prices_golden_uses_registry(isolated_db, monkeypatch):
    from market_core import market_core as mc

    monkeypatch.setattr(mc, "STORES", {
        "wong_pe": {"country": "PE", "disabled": False},
    })
    db = get_db()
    try:
        db.execute("ALTER TABLE price_snapshots ADD COLUMN canonical_product_id TEXT")
    except Exception:
        pass
    set_taxonomy_registry(
        db,
        {
            "prod_gloria_leche_1l": {"canasta_item": "leche"},
            "prod_costeno_arroz_1kg": {"canasta_item": "arroz"},
            "prod_primor_aceite_1l": {"canasta_item": "aceite"},
        },
    )
    db.execute(
        """
        INSERT INTO price_snapshots (product_id, store, name, price, canonical_product_id)
        VALUES ('a', 'wong_pe', 'Leche', 5.0, 'prod_gloria_leche_1l'),
               ('b', 'wong_pe', 'Arroz', 4.0, 'prod_costeno_arroz_1kg'),
               ('c', 'wong_pe', 'Aceite', 9.0, 'prod_primor_aceite_1l')
        """
    )
    db.commit()
    prices = min_canasta_prices_golden(db, "PE")
    assert prices["leche"] == 5.0
    assert prices["arroz"] == 4.0
    assert len(prices) == 3


def test_taxonomy_registry_cached(isolated_db):
    db = get_db()
    set_taxonomy_registry(db, {"prod_x": {"canasta_item": "leche"}}, registry_size=1)
    db.commit()
    payload = cache_get(db, REGISTRY_CACHE_KEY, max_age_hours=168)
    assert payload["products"]["prod_x"]["canasta_item"] == "leche"


def test_canonical_dispersion_and_staple_momentum(isolated_db, monkeypatch):
    from market_core import market_core as mc

    monkeypatch.setattr(mc, "STORES", {"wong_pe": {"country": "PE", "disabled": False}})
    db = get_db()
    for col in ("canonical_product_id",):
        try:
            db.execute(f"ALTER TABLE price_snapshots ADD COLUMN {col} TEXT")
        except Exception:
            pass
    try:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT, store TEXT, price REAL, recorded_at TEXT
            )
            """
        )
    except Exception:
        pass

    set_taxonomy_registry(db, {"prod_leche": {"canasta_item": "leche"}}, registry_size=1)
    db.execute(
        """
        INSERT INTO price_snapshots (product_id, store, name, price, canonical_product_id)
        VALUES ('a', 'wong_pe', 'Leche A', 5.0, 'prod_leche'),
               ('b', 'wong_pe', 'Leche B', 7.0, 'prod_leche')
        """
    )
    db.execute(
        """
        INSERT INTO price_history (product_id, store, price, recorded_at)
        VALUES ('a', 'wong_pe', 4.0, '2026-01-01 00:00:00'),
               ('a', 'wong_pe', 5.0, '2026-06-10 00:00:00')
        """
    )
    db.execute(
        """
        UPDATE price_snapshots SET canonical_product_id = 'prod_leche'
        WHERE product_id = 'a' AND store = 'wong_pe'
        """
    )
    db.commit()

    buckets = canonical_price_buckets(db, "PE")
    assert len(buckets["prod_leche"]) == 2
    dispersion = compute_price_dispersion(db, "PE")
    assert dispersion is not None and dispersion > 0

    deltas = staple_price_deltas_golden(db, "PE", days=365)
    assert len(deltas) >= 1
    mom = compute_staple_price_momentum(db, "PE", days=365)
    assert mom is not None
