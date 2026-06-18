"""Unit tests for market_spread analytics (no DB)."""

from __future__ import annotations

from market_core.market_spread import (
    CANASTA_ITEMS,
    build_spread_analytics,
    compare_key,
    compute_canasta_spreads,
    compute_dispersion,
    compute_marketing_spreads,
    find_median_outliers,
    infer_subcategory,
    matches_canasta_item,
)


def _super_row(
    name: str,
    *,
    store: str = "wong_pe",
    price: float = 5.0,
    currency: str = "PEN",
    brand: str = "",
) -> dict:
    return {
        "name": name,
        "store": store,
        "store_name": store,
        "price": price,
        "currency": currency,
        "line": "supermercados",
        "brand": brand,
    }


def test_infer_subcategory_super_and_farmacia():
    assert infer_subcategory("supermercados", "Leche entera Gloria 1L") == "leche"
    assert infer_subcategory("farmacias", "Ibuprofeno 400mg") == "ibuprofeno"
    assert infer_subcategory("electro", "Smartphone Motorola G") == "telefonia"
    assert infer_subcategory("unknown_line", "Foo", category="Snacks") == "cat:Snacks"
    assert infer_subcategory("unknown_line", "Foo") == "otros"


def test_canned_fish_in_oil_buckets_as_conservas_not_aceite():
    # canned fish packed "en aceite vegetal" must not pollute the aceite bucket
    for name in (
        "Filete de Atún en Aceite Vegetal Florida 140g",
        "Trozos de Jurel en Aceite Vegetal Campomar 150g",
        "Filete de Bonito en Aceite Vegetal 170g",
        "Filete de Caballa en Aceite Vegetal 170g",
        "Sardinas en Aceite Vegetal Vigilante 120g",
    ):
        assert infer_subcategory("supermercados", name) == "conservas", name
    # real cooking oil still buckets as aceite
    assert infer_subcategory("supermercados", "Aceite Vegetal Primor 900ml") == "aceite"


def test_compare_key_normalizes_brand_and_name():
    assert compare_key("Leche 1L", "Gloria") == "gloria|leche1l"


def test_matches_canasta_item_filters_false_positives():
    assert matches_canasta_item(_super_row("Leche entera 1L"), "leche") is True
    assert matches_canasta_item(_super_row("Leche condensada Nestle"), "leche") is False
    assert matches_canasta_item(_super_row("Apollo 11 DVD"), "pollo") is False
    assert matches_canasta_item({**_super_row("Leche 1L"), "line": "farmacias"}, "leche") is False


def test_compute_dispersion_groups_by_subcategory():
    products = [
        _super_row("Leche Gloria 1L", store="a", price=5.0),
        _super_row("Leche Ideal 1L", store="b", price=7.0),
        _super_row("Leche Sol 1L", store="c", price=6.0),
        _super_row("Arroz Costeño 1kg", store="a", price=4.0),
        _super_row("Arroz Paisana 1kg", store="b", price=5.0),
        _super_row("Arroz San Fernando 1kg", store="c", price=6.0),
    ]
    out = compute_dispersion(products)
    assert len(out) >= 2
    leche = next(d for d in out if d.get("subcategory") == "leche")
    assert leche["count"] == 3
    assert leche["spread_ratio"] > 0


def test_find_median_outliers_flags_extreme_prices():
    products = [
        _super_row("Leche A 1L", store=f"s{i}", price=p)
        for i, p in enumerate([5.0, 5.2, 5.1, 5.3, 5.0, 25.0], start=1)
    ]
    outliers = find_median_outliers(products, min_group=5, band=3.0, limit=5)
    assert len(outliers) >= 1
    assert outliers[0]["deviation"] == "high"


def test_compute_canasta_spreads_standard_pack():
    products = [
        _super_row("Leche entera 1L", store="wong_pe", price=5.0),
        _super_row("Leche entera 1L", store="metro_pe", price=8.0),
        _super_row("Arroz extra 1kg", store="wong_pe", price=4.0),
        _super_row("Arroz extra 1kg", store="metro_pe", price=4.5),
    ]
    spreads = compute_canasta_spreads(products)
    items = {s["item"] for s in spreads}
    assert "leche" in items
    assert all(s["stores"] >= 2 for s in spreads)


def test_compute_marketing_spreads_canasta_threshold(monkeypatch):
    monkeypatch.setattr("market_core.market_spread.MARKETING_CANASTA_MIN_SPREAD", 2.0)
    products = [
        _super_row("Leche entera 1L", store="wong_pe", price=3.0),
        _super_row("Leche entera 1L", store="metro_pe", price=4.0),
        _super_row("Leche entera 1L", store="tottus_pe", price=60.0),
    ]
    marketing = compute_marketing_spreads(products)
    assert any(m["seed"] == "leche" and m["marketing_ready"] for m in marketing)


def test_compute_marketing_spreads_farmacia_fuzzy(monkeypatch):
    monkeypatch.setattr("market_core.market_spread.MARKETING_FARMACIA_MIN_SPREAD", 1.5)
    products = [
        {
            "name": "Paracetamol 500mg 20 tabletas",
            "store": "inkafarma_pe",
            "store_name": "Inkafarma",
            "price": 5.0,
            "currency": "PEN",
            "line": "farmacias",
        },
        {
            "name": "Paracetamol 500mg 20 tabs",
            "store": "mifarma_pe",
            "store_name": "Mifarma",
            "price": 100.0,
            "currency": "PEN",
            "line": "farmacias",
        },
    ]
    marketing = compute_marketing_spreads(products)
    assert any(m["seed"] == "paracetamol" for m in marketing)


def test_build_spread_analytics_bundle():
    products = [
        _super_row("Leche entera 1L", store=f"s{i}", price=p)
        for i, p in enumerate([4.0, 5.0, 20.0], start=1)
    ]
    analytics = build_spread_analytics(products)
    assert "dispersion" in analytics
    assert "canasta_spreads" in analytics
    assert "marketing_spreads" in analytics
    assert analytics["marketing_canasta_min_spread"] == 2.5
    assert len(CANASTA_ITEMS) == 10