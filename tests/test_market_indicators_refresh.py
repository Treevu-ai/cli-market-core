"""Mocked refresh paths for external and enrichment indicators."""

from __future__ import annotations

import pytest

from market_core import get_db
from market_core.market_indicators import (
    fetch_fx_rates,
    fetch_worldbank_indicator,
    refresh_enrichment_indicators,
    refresh_external_indicators,
    refresh_indicators,
    seed_indicator_definitions,
)


@pytest.fixture
def pe_stores(monkeypatch):
    stores = {"wong_pe": {"country": "PE", "disabled": False, "line": "supermercados"}}
    monkeypatch.setattr("market_core.market_core.STORES", stores)
    monkeypatch.setattr("market_core.market_indicators.STORES", stores)


def test_fetch_fx_rates_and_worldbank(monkeypatch):
    class FakeFxResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": "success", "rates": {"PEN": 3.7, "USD": 1.0}}

    class FakeWbResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [{}, [{"value": "4.2"}]]

    class FakeClient:
        def __init__(self, *a, **k):
            self._wb = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            if "worldbank" in url:
                return FakeWbResp()
            return FakeFxResp()

    monkeypatch.setattr("market_core.market_indicators.httpx.Client", FakeClient)
    assert fetch_fx_rates()["PEN"] == 3.7
    assert fetch_worldbank_indicator("PE", "FP.CPI.TOTL.ZG") == 4.2


def test_refresh_external_indicators_pe(monkeypatch, pe_stores, isolated_db):
    db = get_db()
    try:
        seed_indicator_definitions(db)
        db.commit()
        monkeypatch.setattr(
            "market_core.market_indicators.fetch_fx_rates",
            lambda: {"PEN": 3.75},
        )
        monkeypatch.setattr(
            "market_core.market_indicators.fetch_worldbank_indicator",
            lambda cc, ind: 5.5 if ind == "FP.CPI.TOTL.ZG" else 110.0,
        )
        monkeypatch.setattr(
            "market_core.market_indicators.compute_internal_inflation_avg",
            lambda *a, **k: 6.0,
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_bcrp_inflation_expectation_12m",
            lambda: 3.2,
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_bcrp_reference_rate",
            lambda: 5.75,
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_fuel_price_index_pe",
            lambda: 18.5,
        )
        n = refresh_external_indicators(db, "PE")
        assert n >= 4
        row = db.execute(
            "SELECT value FROM indicator_values WHERE indicator_key = 'fx_usd_local' ORDER BY recorded_at DESC LIMIT 1"
        ).fetchone()
        assert float(row["value"]) == 3.75
    finally:
        db.close()


def test_refresh_enrichment_indicators(monkeypatch, pe_stores, isolated_db):
    db = get_db()
    try:
        seed_indicator_definitions(db)
        db.commit()
        monkeypatch.setenv("ENRICHMENT_AUTO_REFRESH", "1")
        monkeypatch.setattr(
            "market_core.market_enrich_sources.sample_off_coverage",
            lambda _db, _cc: {
                "sampled": 10,
                "matched": 6,
                "match_rate_pct": 60.0,
                "nutriscore_ab_pct": 50.0,
                "nova_avg": 3.1,
                "ultra_processed_pct": 20.0,
                "ecoscore_avg": 3.5,
                "samples": [],
            },
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_wiki_demand_momentum",
            lambda _cc: 1.1,
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_wiki_staple_momentum",
            lambda _cc: 0.95,
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_weather_logistics_stress",
            lambda _cc: 12.0,
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_food_cpi_yoy",
            lambda _cc: 7.5,
        )
        monkeypatch.setattr(
            "market_core.market_indicators.compute_staple_price_momentum",
            lambda *a, **k: 2.5,
        )
        n = refresh_enrichment_indicators(db, "PE")
        assert n >= 5
    finally:
        db.close()


def test_refresh_phase2_indicators(pe_stores, isolated_db, monkeypatch):
    db = get_db()
    try:
        from market_core.market_indicators import _upsert_indicator_value, refresh_phase2_indicators

        seed_indicator_definitions(db)
        _upsert_indicator_value(
            db,
            indicator_key="bcrp_inflation_expectation_12m",
            scope="PE:macro",
            value=4.0,
            country="PE",
        )
        _upsert_indicator_value(
            db,
            indicator_key="staple_price_momentum",
            scope="PE:enrichment",
            value=1.5,
            country="PE",
        )
        _upsert_indicator_value(
            db,
            indicator_key="commodity_input_pressure",
            scope="global:macro",
            value=8.0,
        )
        db.commit()
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_commodity_input_pressure",
            lambda: 8.0,
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_real_wage_cepal_index",
            lambda _cc: 120.0,
        )
        monkeypatch.setattr(
            "market_core.market_indicators.compute_basket_stress",
            lambda *a, **k: 100.0,
        )
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_gtrends_search_momentum",
            lambda _db, _cc: 1.2,
        )
        n = refresh_phase2_indicators(db, "PE")
        assert n >= 3
    finally:
        db.close()


def test_refresh_indicators_orchestrates(pe_stores, isolated_db, monkeypatch):
    db = get_db()
    try:
        seed_indicator_definitions(db)
        db.commit()
        monkeypatch.setattr(
            "market_core.market_indicators.refresh_internal_indicators",
            lambda *a, **k: 3,
        )
        monkeypatch.setattr(
            "market_core.market_indicators.refresh_external_indicators",
            lambda *a, **k: 2,
        )
        monkeypatch.setattr(
            "market_core.market_indicators.refresh_enrichment_indicators",
            lambda *a, **k: 4,
        )
        monkeypatch.setattr(
            "market_core.market_indicators.refresh_phase2_indicators",
            lambda *a, **k: 1,
        )
        summary = refresh_indicators("PE", "supermercados")
        assert summary["internal_written"] == 3
        assert summary["external_written"] == 2
        assert summary["enrichment_written"] == 4
        assert summary["phase2_written"] == 1
    finally:
        db.close()