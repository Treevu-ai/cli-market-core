"""Tests for market_matcher equivalence helpers."""

from __future__ import annotations

from market_core.market_matcher import evaluate_equivalence, variant_group_key


def test_variant_group_key_strips_pack_size():
    a = variant_group_key("Leche Gloria Entera 1L")
    b = variant_group_key("Leche Gloria Entera 1 L")
    assert a == b
    assert "1l" not in a


def test_evaluate_equivalence_fuzzy_name():
    result = evaluate_equivalence(
        {"name": "Leche Gloria Entera 1L"},
        {"name": "Leche Gloria Entera 1 L"},
    )
    assert result["equivalent"] is True
    assert result["score"] >= 0.82


def test_evaluate_equivalence_different_products():
    result = evaluate_equivalence(
        {"name": "Arroz Costeño 1kg"},
        {"name": "Leche Gloria Entera 1L"},
    )
    assert result["equivalent"] is False
