"""Tests for MCP registry CSV export."""

from __future__ import annotations

from market_core.mcp_registry_export import (
    REGISTRY_CSV_HEADERS,
    registry_export_rows,
    registry_csv_text,
    write_registry_csv,
)
from market_core.market_mcp_registry import ALIASES, TOOLS, list_tools, resolve_tool_name


def test_export_row_count_matches_registry():
    assert len(registry_export_rows()) == len(TOOLS)


def test_export_csv_headers():
    text = registry_csv_text()
    header = text.splitlines()[0]
    assert header == ",".join(REGISTRY_CSV_HEADERS)


def test_intel_legacy_aliases_point_to_brief():
    rows = {r["tool"]: r for r in registry_export_rows()}
    for name in (
        "market_indicators",
        "market_analytics_indicators",
        "market_enrichment",
        "market_enrichment_subcategories",
    ):
        assert rows[name]["estado_codigo"] == "legacy-alias"
        assert rows[name]["reemplazo_codigo"] == "market_intel_brief"


def test_preferences_hidden_and_aliased():
    default = {t["name"] for t in list_tools("default")}
    assert "market_preferences" not in default
    assert "market_household_get" in default
    assert resolve_tool_name("market_preferences") == "market_household_get"
    assert "market_preferences" in ALIASES

    rows = {r["tool"]: r for r in registry_export_rows()}
    pref = rows["market_preferences"]
    assert pref["estado_codigo"] == "legacy-alias"
    assert pref["reemplazo_codigo"] == "market_household_get"
    assert pref["default_visible"] is False


def test_write_registry_csv(tmp_path):
    path = tmp_path / "out.csv"
    write_registry_csv(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(TOOLS) + 1
    assert lines[0].startswith("tool,estado_codigo")
