"""Full coverage for price_confidence helpers."""

from market_core.price_confidence import (
    compute_snapshot_confidence,
    discount_is_scrape_error,
    discount_pct,
    discount_public_ok,
    median_outlier_bounds,
    price_vs_median_confidence,
    spread_confidence,
    spread_public_ok,
)


def test_discount_helpers():
    assert discount_public_ok(10.0) is True
    assert discount_public_ok(3.0) is False
    assert discount_is_scrape_error(95.0) is True
    assert discount_pct(8.0, 10.0) == 20.0
    assert discount_pct(10.0, 8.0) is None


def test_median_and_spread_confidence():
    lo, hi = median_outlier_bounds(10.0, band=5.0)
    assert lo == 2.0
    assert hi == 50.0
    assert price_vs_median_confidence(100.0, 10.0) == "suspect"
    assert price_vs_median_confidence(12.0, 10.0) == "ok"
    assert spread_confidence(15.0) == "crit"
    assert spread_confidence(5.0) == "warn"
    assert spread_confidence(1.0) == "ok"
    assert spread_public_ok(5.0) is True
    assert spread_public_ok(15.0) is False


def test_compute_snapshot_confidence():
    assert compute_snapshot_confidence(5.0, 100.0) == "suspect"
    assert compute_snapshot_confidence(5.0, 6.0) == "ok"