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


def test_is_standard_canasta_pack():
    assert is_standard_canasta_pack("Leche entera 1L", "leche") is True
    assert is_standard_canasta_pack("Leche 250ml", "leche") is False
    assert is_standard_canasta_pack("Arroz 1kg", "arroz") is True