"""Phase 2 indicators — commodity, CEPAL, composites (mocked + live smoke)."""

import json

import pytest

from market_core.market_enrich_sources import (
    _cepal_records,
    fetch_commodity_input_pressure,
    fetch_ipp_food_co,
)


def test_commodity_input_pressure_shape(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {},
                [
                    {"date": "2023", "value": "100.0"},
                    {"date": "2024", "value": "110.0"},
                ],
            ]

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
    val = fetch_commodity_input_pressure()
    assert val == 10.0


def test_cepal_records_filters_iso3(monkeypatch):
    payload = {
        "body": {
            "records": [
                {"iso3": "PER", "value": "42.5"},
                {"iso3": "COL", "value": "99.0"},
            ]
        }
    }

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return payload

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
    recs = _cepal_records(340, "PE")
    assert len(recs) == 1
    assert recs[0]["value"] == "42.5"


@pytest.mark.integration
def test_ipp_food_co_live():
    val = fetch_ipp_food_co()
    assert val is None or (-50 < val < 100)


@pytest.mark.integration
def test_commodity_input_pressure_live():
    val = fetch_commodity_input_pressure()
    assert val is None or (-50 < val < 100)
