"""Tests for MCP tool registry (PR1): metadata, aliases, profiles, legacy compat."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from market_core.market_mcp import handle_tool
from market_core.market_mcp_registry import (
    CANONICAL_NAMES,
    TOOLS,
    get_tool_meta,
    list_tools,
    public_tool_count,
    resolve_tool_name,
)


LEGACY_NAMES = sorted(CANONICAL_NAMES)

BUNDLE_PREFIXES = ("[Shop]", "[Intel]", "[Account]", "[Advanced]", "[Admin]")


def test_registry_has_43_tools():
    assert len(TOOLS) == 43
    names = [t["name"] for t in TOOLS]
    assert len(names) == len(set(names))


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


def test_legacy_profile_lists_all_43():
    assert len(list_tools("legacy")) == 43


def test_default_profile_is_smaller():
    default_count = public_tool_count("default")
    assert 18 <= default_count <= 24


def test_admin_profile_includes_scan():
    names = {t["name"] for t in list_tools("admin")}
    assert "market_scan" in names


def test_default_profile_hides_admin_and_advanced():
    names = {t["name"] for t in list_tools("default")}
    assert "market_scan" not in names
    assert "market_ticket" not in names
    assert "market_intel_refresh" not in names


def test_list_tools_strips_meta():
    for tool in list_tools("legacy"):
        assert "_meta" not in tool
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool


@pytest.mark.parametrize("name", LEGACY_NAMES)
def test_resolve_legacy_name(name: str):
    assert resolve_tool_name(name) == name


@pytest.mark.parametrize("name", LEGACY_NAMES)
def test_handle_tool_accepts_legacy_name(name: str):
    """All 43 legacy tool names must dispatch without 'Unknown tool'."""
    with patch("market_core.market_mcp.api", return_value={"ok": True}):
        if name == "market_login":
            raw = handle_tool(name, {"username": "u", "password": "p"})
        elif name in ("market_search", "market_compare"):
            raw = handle_tool(name, {"query": "arroz"})
        elif name == "market_add":
            raw = handle_tool(
                name,
                {"product_id": "1", "name": "x", "price": 1.0, "store": "metro"},
            )
        elif name in ("market_cart_update",):
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
        elif name == "market_alerts":
            raw = handle_tool(name, {"product": "leche"})
        elif name == "market_notify":
            raw = handle_tool(name, {"product": "leche"})
        elif name == "market_stock":
            raw = handle_tool(name, {"product_id": "1", "store": "metro"})
        elif name == "market_exchange":
            raw = handle_tool(name, {"amount": 10, "from_currency": "PEN", "to_currency": "USD"})
        elif name == "market_delivery":
            raw = handle_tool(name, {"product_id": "1", "store": "metro"})
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