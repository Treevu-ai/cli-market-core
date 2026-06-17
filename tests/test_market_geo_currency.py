"""Tests for line/country/currency helpers."""

from market_core.market_geo_currency import LINES, canonical_line_name


def test_canonical_line_name():
    assert canonical_line_name("supermercados") == "Supermercados"
    assert canonical_line_name("farmacias") == "Farmacias y Salud"
    assert canonical_line_name("") == "Sin categoría"
    assert canonical_line_name("custom_line") == "Custom Line"


def test_lines_catalog_has_industrial():
    assert "industrial" in LINES
    assert LINES["industrial"]["emoji"] == "🏭"