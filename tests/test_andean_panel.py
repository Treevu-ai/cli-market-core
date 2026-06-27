"""P1/P2 — canasta confidence bands and CAF Andean panel."""

from __future__ import annotations

from market_core import ensure_db_initialized, get_db
from market_core.market_intel_products import (
    _canasta_band_confidence,
    _canastas_per_wage_band,
    build_andean_panel,
)


def test_canastas_per_wage_band_math():
    band = _canastas_per_wage_band(
        1130.0,
        best_total=100.0,
        avg_total=120.0,
        worst_total=150.0,
    )
    assert band == {"low": 7.53, "point": 9.42, "high": 11.3}


def test_canasta_band_confidence_levels():
    assert _canasta_band_confidence(stores_compared=1, spread_pct=10.0) == "low"
    assert _canasta_band_confidence(stores_compared=2, spread_pct=10.0) == "moderate"
    assert _canasta_band_confidence(stores_compared=4, spread_pct=60.0) == "moderate"
    assert _canasta_band_confidence(stores_compared=5, spread_pct=20.0) == "ok"


def test_build_andean_panel_shape():
    ensure_db_initialized()
    db = get_db()
    try:
        panel = build_andean_panel(db, line="supermercados", days=30)
    finally:
        db.close()

    assert panel["panel"] == "CAF_andean_food_affordability"
    assert panel["methodology"] == "andean_panel_v1"
    assert len(panel["countries"]) == 3
    codes = {c["country"] for c in panel["countries"]}
    assert codes == {"PE", "BO", "EC"}

    pe = next(c for c in panel["countries"] if c["country"] == "PE")
    bo = next(c for c in panel["countries"] if c["country"] == "BO")
    ec = next(c for c in panel["countries"] if c["country"] == "EC")

    assert pe["data_status"] == "retail_and_macro"
    assert pe["channel"] == "online_modern_retail"
    assert bo["data_status"] == "macro_only"
    assert ec["data_status"] == "macro_only"
    assert "note" in bo
    assert panel["macro_only_countries"] == ["BO", "EC"]
