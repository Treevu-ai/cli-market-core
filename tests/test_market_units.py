"""Tests for pack-size parsing and unit normalization."""

from market_core.market_units import (
    is_standard_canasta_pack,
    parse_pack_size,
    price_per_base_unit,
)


def test_parse_pack_size_variants():
    assert parse_pack_size("Leche entera 1L") == (1.0, "L")
    assert parse_pack_size("Arroz 1 kg") == (1.0, "kg")
    assert parse_pack_size("Huevos docena") == (12.0, "unit")
    assert parse_pack_size("") is None


def test_price_per_base_unit():
    out = price_per_base_unit(5.0, "Leche 1L")
    assert out is not None
    assert out["basis"] == "L"
    assert out["price_per"] == 5.0


def test_price_per_base_unit_rejects_typo_micro_pack():
    # retailer typo: 1 kg bag listed as "1 g" -> would imply S/9900/kg.
    # Fall back to nominal instead of polluting the per-kg comparison.
    assert price_per_base_unit(9.9, "Harina de Arroz Costeño 1 g") is None
    assert price_per_base_unit(3.0, "Bebida 1 ml") is None
    # a real small-but-sane pack is still normalized
    assert price_per_base_unit(2.0, "Sal 100 g") is not None


def test_is_standard_canasta_pack():
    assert is_standard_canasta_pack("Leche entera 1L", "leche") is True
    assert is_standard_canasta_pack("Leche 250ml", "leche") is False
    assert is_standard_canasta_pack("Arroz 1kg", "arroz") is True