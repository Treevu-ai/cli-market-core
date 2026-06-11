"""Golden taxonomy bridge — enrichment_cache registry + canasta prices."""

import pytest

from market_core import ensure_db_initialized, get_db
from market_core.golden_taxonomy import (
    REGISTRY_CACHE_KEY,
    min_canasta_prices_golden,
    set_taxonomy_registry,
)
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
