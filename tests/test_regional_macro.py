"""Regional macro fetchers — BCRP, bluelytics (live or shape)."""

import pytest

from market_core.market_enrich_sources import (
    fetch_bcrp_inflation_expectation_12m,
    fetch_bcrp_reference_rate,
    fetch_fx_ars_blue_gap,
)


@pytest.mark.integration
def test_bcrp_inflation_expectation_live():
    val = fetch_bcrp_inflation_expectation_12m()
    assert val is not None
    assert 0 < val < 30


@pytest.mark.integration
def test_bcrp_reference_rate_live():
    val = fetch_bcrp_reference_rate()
    assert val is not None
    assert 0 < val < 30


@pytest.mark.integration
def test_fx_ars_blue_gap_live():
    gap = fetch_fx_ars_blue_gap()
    assert gap is not None
    assert -50 < gap < 200
