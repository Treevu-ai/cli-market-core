"""Canonical business-line labels for dashboard aggregations."""

from market_core.market_core import LINES, canonical_line_name


def test_canonical_line_name_known():
    assert canonical_line_name("supermercados") == LINES["supermercados"]["name"]
    assert canonical_line_name("electro") == "Electro y Tecnología"
    assert canonical_line_name("farmacias") == "Farmacias y Salud"


def test_canonical_line_name_legacy_ignored():
    # Snapshots may carry stale labels; display always uses LINES catalog.
    assert canonical_line_name("moda") == "Moda y Vestimenta"


def test_canonical_line_name_empty():
    assert canonical_line_name("") == "Sin categoría"
    assert canonical_line_name(None) == "Sin categoría"