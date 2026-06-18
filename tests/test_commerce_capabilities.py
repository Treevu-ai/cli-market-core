"""Smoke test for commerce capability matrix."""

from market_core.commerce_capabilities import get_commerce_capabilities


def test_commerce_capabilities_shape():
    caps = get_commerce_capabilities()
    assert caps["checkout"]["scope"] == "cli_market_internal"
    assert "yape" in caps["payments"]["methods"]
    assert caps["search_compare"]["health_endpoint"] == "/v1/sources/health"