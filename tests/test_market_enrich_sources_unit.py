"""Unit tests for market_enrich_sources helpers and cache layer."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from market_core import get_db
from market_core.market_enrich_sources import (
    _looks_like_ean,
    _normalize_off,
    _off_search_term,
    _wiki_momentum_for_articles,
    cache_get,
    cache_set,
    clear_tier2_cache,
    resolve_off_for_product,
    sample_off_coverage,
)


def test_ean_and_off_search_term():
    assert _looks_like_ean("7501234567890") is True
    assert _looks_like_ean("abc") is False
    assert _off_search_term("Leche Gloria Entera 1L x 12 und") == "leche gloria entera"


def test_normalize_off_maps_fields():
    payload = _normalize_off(
        {
            "product_name": "Yogur Natural",
            "brands": "Gloria",
            "nutriscore_grade": "b",
            "ecoscore_grade": "c",
            "nova_group": "3",
            "categories": "Dairy",
        },
        "12345678",
    )
    assert payload["name"] == "Yogur Natural"
    assert payload["nutriscore"] == "B"
    assert payload["nova_group"] == 3


def test_cache_get_set_and_expiry(isolated_db):
    db = get_db()
    try:
        cache_set(db, "test:key", "unit", {"ok": True})
        db.commit()
        assert cache_get(db, "test:key") == {"ok": True}

        db.execute(
            "UPDATE enrichment_cache SET recorded_at = ? WHERE cache_key = ?",
            ((datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"), "test:key"),
        )
        db.commit()
        assert cache_get(db, "test:key", max_age_hours=24) is None
    finally:
        db.close()


def test_resolve_off_for_product_uses_cache(isolated_db, monkeypatch):
    db = get_db()
    try:
        cache_set(db, "off:search:leche gloria entera", "openfoodfacts", {"code": "1", "name": "Leche"})
        db.commit()

        def _should_not_call(*_a, **_k):
            raise AssertionError("network fetch should not run when cache is warm")

        monkeypatch.setattr("market_core.market_enrich_sources.fetch_off_by_search", _should_not_call)
        monkeypatch.setattr("market_core.market_enrich_sources.fetch_off_by_barcode", _should_not_call)

        result = resolve_off_for_product(db, "not-ean", "Leche Gloria Entera 1L")
        assert result["name"] == "Leche"
    finally:
        db.close()


def test_resolve_off_for_product_fetches_barcode(isolated_db, monkeypatch):
    db = get_db()
    try:
        monkeypatch.setattr(
            "market_core.market_enrich_sources.fetch_off_by_barcode",
            lambda code: {"code": code, "name": "From OFF"},
        )
        monkeypatch.setattr("market_core.market_enrich_sources.time.sleep", lambda *_a: None)
        result = resolve_off_for_product(db, "7501234567890", "Leche")
        assert result["code"] == "7501234567890"
        cached = cache_get(db, "off:barcode:7501234567890")
        assert cached["name"] == "From OFF"
    finally:
        db.close()


def test_wiki_momentum_for_articles(monkeypatch):
    calls: list[str] = []

    class FakeResp:
        status_code = 200

        def json(self):
            return {"items": [{"views": 100}, {"views": 50}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            calls.append(url)
            return FakeResp()

    monkeypatch.setattr("market_core.market_enrich_sources.httpx.Client", FakeClient)
    monkeypatch.setattr("market_core.market_enrich_sources.time.sleep", lambda *_a: None)
    val = _wiki_momentum_for_articles("es", ["Leche", "Arroz"])
    assert val is not None
    assert val > 0
    assert len(calls) == 4


def test_sample_off_coverage_no_stores(monkeypatch, isolated_db):
    from market_core import market_core as mc

    monkeypatch.setattr(mc, "STORES", {})
    db = get_db()
    try:
        out = sample_off_coverage(db, "PE")
        assert out["sampled"] == 0
        assert out["match_rate_pct"] is None
    finally:
        db.close()


def test_clear_tier2_cache():
    clear_tier2_cache()
    # Idempotent — no exception means success.


def test_sample_off_coverage_counts_matches(monkeypatch, isolated_db):
    from market_core import market_core as mc

    monkeypatch.setattr(
        mc,
        "STORES",
        {"wong_pe": {"country": "PE", "disabled": False, "line": "supermercados"}},
    )

    monkeypatch.setattr(
        "market_core.market_enrich_sources.resolve_off_for_product",
        lambda _db, _pid, _name: {
            "code": "1",
            "name": "Leche",
            "nutriscore": "A",
            "ecoscore": "B",
            "nova_group": 3,
        },
    )
    monkeypatch.setattr("market_core.market_enrich_sources.time.sleep", lambda *_a: None)

    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, name, price, line)
            VALUES ('7501234567890', 'wong_pe', 'Leche entera 1L', 5.0, 'supermercados'),
                   ('sku-2', 'wong_pe', 'Arroz 1kg', 4.0, 'supermercados')
            """
        )
        db.commit()
        out = sample_off_coverage(db, "PE", limit=5)
        assert out["sampled"] == 2
        assert out["matched"] == 2
        assert out["match_rate_pct"] == 100.0
        assert out["nutriscore_ab_pct"] == 100.0
    finally:
        db.close()


def test_fetch_wiki_demand_momentum(monkeypatch):
    from market_core.market_enrich_sources import fetch_wiki_demand_momentum

    monkeypatch.setattr(
        "market_core.market_enrich_sources._wiki_momentum_for_articles",
        lambda _lang, _arts: 1.25,
    )
    val = fetch_wiki_demand_momentum("PE")
    assert val == 1.25
    assert fetch_wiki_demand_momentum("ZZ") is None


def test_fetch_imf_inflation_yoy(monkeypatch):
    from market_core.market_enrich_sources import fetch_imf_inflation_yoy

    monkeypatch.setattr(
        "market_core.market_enrich_sources._imf_for_country",
        lambda _ind, cc: 4.5 if cc == "PE" else None,
    )
    assert fetch_imf_inflation_yoy("PE") == 4.5
    assert fetch_imf_inflation_yoy("XX") is None