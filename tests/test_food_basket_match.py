"""Tests for food basket artifact filtering."""

from __future__ import annotations

from market_core.market_food_match import (
    food_search_hint,
    infer_staple_from_query,
    matches_food_basket_query,
    pick_best_food_match,
    score_food_basket_match,
)


def _row(name: str, *, price: float = 5.0, line: str = "supermercados") -> dict:
    return {"name": name, "price": price, "line": line, "store": "metro", "product_id": "1"}


def test_infer_staple_from_query():
    assert infer_staple_from_query("leche gloria lata") == "leche"
    assert infer_staple_from_query("huevos bandeja 8") == "huevos"
    assert infer_staple_from_query("fideos canuto") == "pasta"


def test_huevos_rejects_batidor():
    assert matches_food_basket_query("huevos", _row("Batidor de Huevos Krea")) is False
    assert matches_food_basket_query("huevos", _row("Huevos Pardos Metro Bandeja 8 Unid")) is True


def test_aceite_rejects_canned_fish():
    assert matches_food_basket_query(
        "aceite vegetal",
        _row("Filete de Atún en Aceite Vegetal Metro 170g"),
    ) is False
    assert matches_food_basket_query(
        "aceite vegetal",
        _row("Aceite Vegetal Primor Clásico Botella 900ml"),
    ) is True


def test_pick_best_food_match_prefers_real_sku_over_cheap_artifact():
    rows = [
        _row("Batidor de Huevos Krea", price=3.0),
        _row("Huevos Pardos Metro Bandeja 8 Unid", price=6.49),
    ]
    best = pick_best_food_match("huevos", rows)
    assert best is not None
    assert "Bandeja" in best["name"]


def test_fideos_matches_pasta_not_tools():
    assert matches_food_basket_query("fideos", _row("Fideos Cuisine & Co Canuto 250g")) is True
    assert matches_food_basket_query("fideos", _row("Sarten Antiadherente 24cm")) is False


def test_food_search_hint_disambiguates():
    assert food_search_hint("huevos") == "huevos bandeja"
    assert "aceite" in food_search_hint("aceite vegetal")
