"""Tests for MCP tool registry: metadata, aliases, profiles, legacy compat."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from market_core.market_mcp import handle_tool
from market_core.market_mcp_registry import (
    ALIASES,
    ORIGINAL_TOOL_NAMES,
    TOOLS,
    get_deprecation,
    get_profile,
    get_tool_meta,
    list_tools,
    public_tool_count,
    resolve_tool_name,
)


BUNDLE_PREFIXES = ("[Shop]", "[Intel]", "[Account]", "[Advanced]", "[Admin]")


def test_registry_has_46_tools():
    assert len(TOOLS) == 57
    names = [t["name"] for t in TOOLS]
    assert len(names) == len(set(names))


def test_original_43_names_still_registered():
    assert len(ORIGINAL_TOOL_NAMES) == 51
    for name in ORIGINAL_TOOL_NAMES:
        assert name in {t["name"] for t in TOOLS}


def test_pr2_new_canonical_tools():
    names = {t["name"] for t in TOOLS}
    assert "market_discover" in names
    assert "market_price_alerts" in names
    assert "market_intel_brief" in names


def test_every_tool_has_metadata():
    for tool in TOOLS:
        meta = tool.get("_meta")
        assert meta is not None, tool["name"]
        assert meta["bundle"] in ("shop", "intel", "account", "advanced", "admin")
        assert isinstance(meta["order"], int)
        assert meta["min_tier"] in ("free", "starter", "pro", "enterprise")
        assert "icp" in meta
        assert "pairs_with" in meta


def test_descriptions_english_with_bundle_prefix():
    for tool in TOOLS:
        desc = tool["description"]
        assert desc.startswith(BUNDLE_PREFIXES), f"{tool['name']} missing bundle prefix"
        assert "verificados" not in desc.lower()
        assert "listar" not in desc.lower()


def test_dynamic_retailer_stats_in_search_description():
    from market_core.market_stats import COUNTRIES, RETAILERS_VERIFIED

    search = next(t for t in TOOLS if t["name"] == "market_search")
    assert str(RETAILERS_VERIFIED) in search["description"]
    assert str(COUNTRIES) in search["description"]


def test_get_profile_defaults_to_default(monkeypatch):
    monkeypatch.delenv("MCP_TOOL_PROFILE", raising=False)
    assert get_profile() == "default"


def test_get_profile_legacy_env(monkeypatch):
    monkeypatch.setenv("MCP_TOOL_PROFILE", "legacy")
    assert get_profile() == "legacy"


def test_legacy_profile_lists_all_46():
    assert len(list_tools("legacy")) == 57


def test_default_profile_includes_pr2_canonicals():
    names = {t["name"] for t in list_tools("default")}
    assert "market_discover" in names
    assert "market_price_alerts" in names
    assert "market_intel_brief" in names
    assert "market_lines" not in names
    assert "market_alerts" not in names
    assert "market_notify" not in names
    assert "market_indicators" not in names
    assert "market_enrichment" not in names


def test_default_profile_is_curated_size():
    default_count = public_tool_count("default")
    assert 20 <= default_count <= 35  # wave 2: +optimize_purchase, +household_get/update


def test_admin_profile_includes_scan():
    names = {t["name"] for t in list_tools("admin")}
    assert "market_scan" in names


def test_default_profile_includes_wave1_intel():
    names = {t["name"] for t in list_tools("default")}
    assert "market_affordability" in names
    assert "market_substitutes" in names


def test_default_profile_includes_wave2_mission():
    names = {t["name"] for t in list_tools("default")}
    assert "market_optimize_purchase" in names
    assert "market_household_get" in names
    assert "market_household_update" in names


def test_default_profile_hides_admin_and_advanced():
    names = {t["name"] for t in list_tools("default")}
    assert "market_scan" not in names
    assert "market_intel_refresh" not in names
    assert "market_preferences" not in names
    # P2-7: market_ticket and market_barcode promoted to default
    assert "market_ticket" in names
    assert "market_barcode" in names


def test_list_tools_strips_meta():
    for tool in list_tools("legacy"):
        assert "_meta" not in tool
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool


@pytest.mark.parametrize("alias,canonical", list(ALIASES.items()))
def test_pr2_aliases_resolve(alias: str, canonical: str):
    assert resolve_tool_name(alias) == canonical


@pytest.mark.parametrize("name", sorted(ORIGINAL_TOOL_NAMES))
def test_handle_tool_accepts_original_43_names(name: str):
    """All 43 original tool names must dispatch without 'Unknown tool'."""
    with patch("market_core.market_mcp.api", return_value={"ok": True}) as mock_api:
        if name == "market_login":
            raw = handle_tool(name, {"username": "u", "password": "p"})
        elif name in ("market_search", "market_compare"):
            raw = handle_tool(name, {"query": "arroz"})
        elif name == "market_add":
            raw = handle_tool(
                name,
                {"product_id": "1", "name": "x", "price": 1.0, "store": "metro"},
            )
        elif name == "market_cart_update":
            raw = handle_tool(name, {"product_id": "1", "quantity": 0})
        elif name == "market_cart_remove":
            raw = handle_tool(name, {"product_id": "1"})
        elif name == "market_ask":
            raw = handle_tool(name, {"prompt": "leche"})
        elif name == "market_basket":
            raw = handle_tool(name, {"items": [{"name": "leche", "qty": 1}]})
        elif name == "market_categories":
            raw = handle_tool(name, {"store": "metro"})
        elif name == "market_barcode":
            raw = handle_tool(name, {"code": "123"})
        elif name == "market_enrich":
            raw = handle_tool(name, {"query": "leche"})
        elif name == "market_ticket":
            raw = handle_tool(name, {"url": "https://example.com/t.jpg"})
        elif name == "market_voice":
            raw = handle_tool(name, {"url": "https://example.com/a.ogg"})
        elif name in ("market_alerts", "market_notify"):
            raw = handle_tool(name, {"product": "leche"})
        elif name == "market_stock":
            raw = handle_tool(name, {"product_id": "1", "store": "metro"})
        elif name == "market_exchange":
            raw = handle_tool(name, {"amount": 10, "from_currency": "PEN", "to_currency": "USD"})
        elif name == "market_delivery":
            raw = handle_tool(name, {"product_id": "1", "store": "metro"})
        elif name == "market_affordability":
            raw = handle_tool(name, {"country": "PE"})
        elif name == "market_substitutes":
            raw = handle_tool(name, {"query": "leche", "country": "PE"})
        elif name == "market_optimize_purchase":
            raw = handle_tool(name, {"items": [{"name": "leche", "qty": 1}], "country": "PE"})
        elif name == "market_household_get":
            raw = handle_tool(name, {})
        elif name == "market_household_update":
            raw = handle_tool(name, {"payload": {"size": 2, "country": "PE"}})
        elif name == "market_moat_confidence":
            raw = handle_tool(name, {"product_id": "p1", "store": "wong"})
        elif name == "market_ecosystem_radar":
            raw = handle_tool(name, {"topic": "food"})
        elif name == "market_procurement_bulk":
            raw = handle_tool(name, {"lines": [{"sku_query": "leche"}]})
        else:
            raw = handle_tool(name, {})
    data = json.loads(raw)
    assert "error" not in data or "Unknown tool" not in str(data.get("error", ""))


def test_unknown_tool_error():
    raw = handle_tool("market_nonexistent", {})
    data = json.loads(raw)
    assert "Unknown tool" in data["error"]


def test_get_tool_meta_market_basket():
    meta = get_tool_meta("market_basket")
    assert meta is not None
    assert meta["bundle"] == "shop"
    assert "market_search" in meta["pairs_with"]


def test_market_discover_composes_three_apis():
    with patch("market_core.market_mcp.api", side_effect=[{"lines": 1}, {"stores": 2}, {"countries": 3}]):
        raw = handle_tool("market_discover", {})
    data = json.loads(raw)
    assert data["lines"] == {"lines": 1}
    assert data["stores"] == {"stores": 2}
    assert data["countries"] == {"countries": 3}


def test_legacy_lines_returns_lines_slice():
    with patch("market_core.market_mcp.api", side_effect=[{"lines": "L"}, {"stores": "S"}, {"countries": "C"}]):
        raw = handle_tool("market_lines", {})
    data = json.loads(raw)
    assert data["lines"] == "L"
    assert data["_deprecation"]["use"] == "market_discover"


def test_cart_remove_uses_cart_update_with_zero_qty():
    with patch("market_core.market_mcp.api", return_value={"updated": True}) as mock_api:
        handle_tool("market_cart_remove", {"product_id": "sku-1"})
    mock_api.assert_called_once_with("PUT", "/cart/update", {"product_id": "sku-1", "quantity": 0})


def test_reorder_uses_orders_reorder_last():
    with patch("market_core.market_mcp.api", return_value={"reordered": True}) as mock_api:
        handle_tool("market_reorder", {})
    mock_api.assert_called_once_with("POST", "/orders/reorder", {})


def test_orders_reorder_last_param():
    with patch("market_core.market_mcp.api", return_value={"reordered": True}) as mock_api:
        handle_tool("market_orders", {"reorder_last": True})
    mock_api.assert_called_once_with("POST", "/orders/reorder", {})


def test_alerts_and_notify_route_to_price_alerts():
    with patch("market_core.market_mcp.api", return_value={"alerts": []}) as mock_api:
        handle_tool("market_alerts", {"product": "leche", "store": "metro"})
    assert "/v1/intel/alerts" in mock_api.call_args[0][1]
    with patch("market_core.market_mcp.api", return_value={"alerts": []}) as mock_api:
        handle_tool("market_notify", {"product": "leche"})
    assert "/v1/intel/alerts" in mock_api.call_args[0][1]


def test_deprecation_notice_on_direct_deprecated_tool():
    notice = get_deprecation("market_lines")
    assert notice == {"deprecated": "market_lines", "use": "market_discover"}
    assert get_deprecation("market_preferences") == {
        "deprecated": "market_preferences",
        "use": "market_household_get",
    }


def test_preferences_alias_routes_to_household():
    with patch("market_core.market_mcp.api", return_value={"profile": {}}) as mock_api:
        raw = handle_tool("market_preferences", {})
    assert mock_api.call_args[0] == ("GET", "/v1/household")
    data = json.loads(raw)
    assert data["_deprecation"]["use"] == "market_household_get"


@pytest.mark.parametrize(
    "alias,slice_key",
    [
        ("market_indicators", "catalog"),
        ("market_analytics_indicators", "analytics"),
        ("market_enrichment", "enrichment"),
        ("market_enrichment_subcategories", "subcategories"),
    ],
)
def test_pr3_intel_aliases_resolve(alias: str, slice_key: str):
    assert resolve_tool_name(alias) == "market_intel_brief"


def test_market_intel_brief_handler():
    mock_brief = {
        "headline": "test",
        "catalog": [{"key": "promo_intensity"}],
        "analytics": {"indicators": [{"key": "promo_intensity"}], "total": 1},
        "enrichment": {"indicators": [{"key": "off_match_rate"}], "total": 1},
        "subcategories": {"subcategories": [{"key": "subcat_x"}], "total": 1},
        "country": "PE",
    }
    with patch("market_core.market_mcp.api", return_value=mock_brief):
        raw_indicators = handle_tool("market_indicators", {})
        raw_analytics = handle_tool("market_analytics_indicators", {"country": "PE"})
    data_ind = json.loads(raw_indicators)
    data_an = json.loads(raw_analytics)
    assert data_ind["total"] == 1
    assert data_an["total"] == 1
    assert data_ind["_deprecation"]["use"] == "market_intel_brief"