"""Mocked HTTP tests for market_enrich_sources tier-2 fetchers."""

from __future__ import annotations

import pytest

from market_core.market_enrich_sources import (
    _imf_for_country,
    fetch_bcb_headline_inflation_mom,
    fetch_eurostat_food_hicp_yoy,
    fetch_food_cpi_yoy,
    fetch_weather_logistics_stress,
    fetch_wb_gdp_growth_yoy,
)


def test_imf_for_country_parses_table(monkeypatch):
    monkeypatch.setattr(
        "market_core.market_enrich_sources._imf_indicator_table",
        lambda _ind: {"PER": 4.5, "CHL": 3.1},
    )
    assert _imf_for_country("inflation", "PE") == 4.5
    assert _imf_for_country("inflation", "XX") is None


def test_fetch_food_cpi_yoy(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [{}, [{"value": "6.0"}]]

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return FakeResp()

    monkeypatch.setattr("market_core.market_enrich_sources.httpx.Client", FakeClient)
    assert fetch_food_cpi_yoy("PE") == 6.0


def test_fetch_weather_logistics_stress(monkeypatch):
    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "daily": {
                    "precipitation_sum": [0, 5, 20, 0, 0, 0, 0],
                }
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            return FakeResp()

    monkeypatch.setattr("market_core.market_enrich_sources.httpx.Client", FakeClient)
    val = fetch_weather_logistics_stress("PE")
    assert val is not None
    assert val >= 0


def test_fetch_eurostat_and_bcb(monkeypatch):
    monkeypatch.setattr(
        "market_core.market_enrich_sources._fetch_eurostat_hicp_yoy",
        lambda cc, coicop: 2.5,
    )
    assert fetch_eurostat_food_hicp_yoy("PT") == 2.5

    monkeypatch.setattr(
        "market_core.market_enrich_sources._fetch_bcb_series",
        lambda series: 0.4,
    )
    assert fetch_bcb_headline_inflation_mom("BR") == 0.4


def test_fetch_wb_gdp_growth(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [{}, [{"value": "3.3"}]]

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return FakeResp()

    monkeypatch.setattr("market_core.market_enrich_sources.httpx.Client", FakeClient)
    assert fetch_wb_gdp_growth_yoy("PE") == 3.3