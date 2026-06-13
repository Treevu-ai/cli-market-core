"""Unit tests for market_missions.run_investigate (mock request_fn)."""

from __future__ import annotations

from market_core.market_missions import run_investigate


def _mock_api(responses: dict[tuple[str, str], dict]):
    def request_fn(method: str, path: str, json_data: dict | None = None) -> dict:
        key = (method, path.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"unexpected call: {method} {path}")
        return responses[key]

    return request_fn


def test_run_investigate_empty_query():
    report = run_investigate("", country="PE", request_fn=_mock_api({}))
    assert report["status"] == "error"
    assert report["error"] == "query required"


def test_run_investigate_complete_report():
    responses = {
        ("POST", "/products/search"): {
            "query": "arroz",
            "total": 42,
            "results": [
                {"store": "metro", "store_name": "Metro", "name": "Arroz", "price": 4.89},
                {"store": "wong", "store_name": "Wong", "name": "Arroz", "price": 5.79},
            ],
        },
        ("POST", "/products/compare"): {
            "query": "arroz",
            "stores_compared": 2,
            "comparison": [
                {
                    "name": "Arroz costeño 1kg",
                    "brand": "Costeño",
                    "prices": {"metro": 4.89, "wong": 5.79},
                    "best_store": "metro",
                    "best_price": 4.89,
                }
            ],
        },
        ("GET", "/v1/intel/inflation"): {
            "days": 30,
            "avg_inflation_pct": 5.2,
            "items": [
                {
                    "line": "arroz",
                    "delta_pct": 5.2,
                    "currency": "PEN",
                }
            ],
        },
    }
    report = run_investigate("arroz", "PE", request_fn=_mock_api(responses))

    assert report["status"] == "complete"
    assert report["mission"] == "investigate"
    assert report["sections"]["search"]["status"] == "ok"
    assert report["sections"]["compare"]["status"] == "ok"
    assert report["sections"]["inflation"]["status"] == "ok"

    insights = report["insights"]
    assert insights["leader"]["store"] == "metro"
    assert insights["laggard"]["store"] == "wong"
    assert insights["spread_pct_max"] > 0
    assert insights["inflation_line"]["delta_pct"] == 5.2

    rules = {item["rule"] for item in report["recommendations"]}
    assert "baseline_leader" in rules
    assert "inflation_elevated" in rules


def test_run_investigate_partial_when_compare_fails():
    responses = {
        ("POST", "/products/search"): {
            "query": "leche",
            "total": 10,
            "results": [{"store": "plazavea", "name": "Leche", "price": 3.5}],
        },
        ("POST", "/products/compare"): {"error": "rate limited", "status": 429},
        ("GET", "/v1/intel/inflation"): {"error": "forbidden", "status": 403},
    }
    report = run_investigate("leche", "PE", request_fn=_mock_api(responses))

    assert report["status"] == "partial"
    assert report["sections"]["search"]["status"] == "ok"
    assert report["sections"]["compare"]["status"] == "unavailable"
    assert report["sections"]["inflation"]["status"] == "unavailable"
    assert report["insights"]["skus_matched"] == 10


def test_run_investigate_without_intel():
    responses = {
        ("POST", "/products/search"): {"query": "azucar", "total": 3, "results": []},
        ("POST", "/products/compare"): {
            "query": "azucar",
            "stores_compared": 1,
            "comparison": [
                {
                    "name": "Azúcar",
                    "brand": "Cartavio",
                    "prices": {"plazavea": 2.1},
                    "best_store": "plazavea",
                    "best_price": 2.1,
                }
            ],
        },
    }
    report = run_investigate("azucar", "PE", include_intel=False, request_fn=_mock_api(responses))

    assert report["status"] == "complete"
    assert "inflation" not in report["sections"]
    assert report["insights"]["leader"]["store"] == "plazavea"


def test_run_investigate_spread_high_recommendation():
    responses = {
        ("POST", "/products/search"): {"query": "aceite", "total": 5, "results": []},
        ("POST", "/products/compare"): {
            "query": "aceite",
            "stores_compared": 2,
            "comparison": [
                {
                    "name": "Aceite",
                    "brand": "Primor",
                    "prices": {"metro": 10.0, "wong": 16.0},
                    "best_store": "metro",
                    "best_price": 10.0,
                }
            ],
        },
        ("GET", "/v1/intel/inflation"): {"days": 30, "items": []},
    }
    report = run_investigate("aceite", "PE", request_fn=_mock_api(responses))

    rules = {item["rule"] for item in report["recommendations"]}
    assert "spread_high" in rules
    assert report["insights"]["spread_pct_max"] >= 25
