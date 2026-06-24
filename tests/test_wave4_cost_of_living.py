"""Wave 4 — action closure L3/L4, delivery simulation, feature flags."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from market_core import get_db
from market_core.market_action_links import (
    build_action_links,
    enrich_basket_items_with_urls,
    external_cart_handoff,
    retailer_deeplink,
)
from market_core.market_feature_flags import (
    affiliate_enabled,
    crowd_receipts_enabled,
    ecosystem_radar_enabled,
    external_cart_handoff_enabled,
    household_enabled,
)
from market_core.market_missions import run_optimize_purchase
from market_core.market_tco import simulate_delivery_quote


def _seed(db):
    ts = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
        ("p1", "wong", "Wong", "Leche Gloria Entera 1L", 4.5, "supermercados", "PEN", ts),
    )
    db.execute(
        """INSERT INTO price_snapshots (product_id, store, store_name, name, price, line, currency, queried_at, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ok')""",
        ("p2", "metro", "Metro", "Leche Laive Entera 1L", 3.9, "supermercados", "PEN", ts),
    )
    db.commit()


def test_feature_flags_default_on(monkeypatch):
    monkeypatch.delenv("HOUSEHOLD_ENABLED", raising=False)
    monkeypatch.delenv("CROWD_RECEIPTS_ENABLED", raising=False)
    monkeypatch.delenv("ECOSYSTEM_RADAR_ENABLED", raising=False)
    assert household_enabled()
    assert crowd_receipts_enabled()
    assert ecosystem_radar_enabled()
    assert not affiliate_enabled()
    assert not external_cart_handoff_enabled()


def test_affiliate_deeplink_utm(monkeypatch):
    monkeypatch.setenv("AFFILIATE_STORES", "wong")
    monkeypatch.setenv("AFFILIATE_UTM_SOURCE", "climarket")
    link = retailer_deeplink("wong", name="leche gloria")
    assert link is not None
    assert link["affiliate"] is True
    assert "utm_source=climarket" in link["url"]


def test_external_cart_handoff_stub(monkeypatch):
    monkeypatch.setenv("EXTERNAL_CART_HANDOFF_ENABLED", "1")
    monkeypatch.setenv("CART_HANDOFF_PARTNER", "rappi")
    handoff = external_cart_handoff("wong", items=[{"name": "leche"}], country="PE")
    assert handoff is not None
    assert handoff["type"] == "external_cart_handoff"
    assert handoff["partner"] == "rappi"
    assert handoff["status"] == "stub"


def test_build_action_links_includes_handoff_when_enabled(monkeypatch, isolated_db):
    monkeypatch.setenv("EXTERNAL_CART_HANDOFF_ENABLED", "1")
    db = get_db()
    try:
        links = build_action_links(
            db,
            store="wong",
            items=[{"name": "leche", "qty": 1, "product_id": "p1"}],
            country="PE",
            totals={"shelf": 4.5, "tco": 11.5, "currency": "PEN"},
        )
        types = {link["type"] for link in links}
        assert "retailer_deeplink" in types
        assert "export_list" in types
        assert "external_cart_handoff" in types
    finally:
        db.close()


def test_build_action_links_prefers_store_matching_product_id(isolated_db):
    db = get_db()
    try:
        links = build_action_links(
            db,
            store="plazavea",
            items=[
                {
                    "requested": "arroz extra",
                    "resolved_product_id": "391212",
                    "resolved_name": "Arroz Superior Metro 750g",
                    "store": "metro",
                },
                {
                    "requested": "leche gloria",
                    "resolved_product_id": "20402654",
                    "resolved_name": "Leche GLORIA Niños Lata 390g",
                    "store": "plazavea",
                },
            ],
            country="PE",
            totals={"shelf": 50.99, "tco": 58.49, "currency": "PEN"},
            include_handoff=False,
        )
        deeplink = next(link for link in links if link["type"] == "retailer_deeplink")
        assert deeplink["store"] == "plazavea"
        assert deeplink["link_mode"] == "search"
        assert deeplink["url"] == "https://www.plazavea.com.pe/search?ft=Leche%20GLORIA%20Ni%C3%B1os%20Lata%20390g"
    finally:
        db.close()


def test_build_action_links_search_fallback_when_no_store_product(isolated_db):
    db = get_db()
    try:
        links = build_action_links(
            db,
            store="plazavea",
            items=[
                {
                    "requested": "arroz extra",
                    "resolved_product_id": "391212",
                    "resolved_name": "Arroz Superior Metro 750g",
                    "store": "metro",
                }
            ],
            country="PE",
            totals={"shelf": 7.0, "tco": 14.5, "currency": "PEN"},
            include_handoff=False,
        )
        deeplink = next(link for link in links if link["type"] == "retailer_deeplink")
        assert deeplink["product_id"] is None
        assert deeplink["link_mode"] == "search"
        assert deeplink["url"] == "https://www.plazavea.com.pe/search?ft=arroz%20extra"
    finally:
        db.close()


def test_retailer_deeplink_uses_explicit_url():
    link = retailer_deeplink(
        "plazavea",
        product_id="ignored",
        url="https://www.plazavea.com.pe/arroz-extra-costeno-bolsa-750g/p",
    )
    assert link is not None
    assert link["link_mode"] == "canonical"
    assert link["url"] == "https://www.plazavea.com.pe/arroz-extra-costeno-bolsa-750g/p"


def test_enrich_basket_items_with_urls(monkeypatch):
    def _fake_resolve(store, query, *, target_price=None, limit=10):
        return {
            "name": f"{query} product",
            "product_id": "abc123",
            "price": target_price or 1.0,
            "url": f"https://www.metro.pe/{query.replace(' ', '-')}-abc123/p",
            "store": store,
        }

    monkeypatch.setattr(
        "market_core.market_action_links.resolve_store_product_link_sync",
        _fake_resolve,
    )
    rows = enrich_basket_items_with_urls(
        "metro",
        [{"item": "arroz extra", "qty": 2, "unit_price": 3.5}],
    )
    assert len(rows) == 1
    assert rows[0]["url"].startswith("https://www.metro.pe/")
    assert rows[0]["link_mode"] == "canonical"


def test_simulate_delivery_defaults():
    quote = simulate_delivery_quote("wong", subtotal=10.0, product_id="p1")
    assert quote["available"] is True
    assert quote["fee"] == 7.0
    assert quote["source"] == "vtex_shipping_defaults"


def test_simulate_delivery_unavailable_store():
    quote = simulate_delivery_quote("unknown_store", subtotal=10.0)
    assert quote["available"] is False


def test_run_optimize_purchase_with_delivery_tco(isolated_db):
    db = get_db()
    try:
        _seed(db)
        result = run_optimize_purchase(
            db,
            country="PE",
            items=[{"name": "leche", "qty": 2}],
            constraints={"include_tco": True},
        )
        assert result["status"] == "ok"
        stores = result["sections"]["compare"]["stores"]
        assert any(s.get("tco", {}).get("delivery", {}).get("available") for s in stores)
        assert result["recommendation"]["tco_total"] >= result["recommendation"]["shelf_total"]
    finally:
        db.close()
