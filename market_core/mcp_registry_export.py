"""Canonical MCP registry export — CSV rows for docs, landing sync, and agent onboarding."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .market_mcp_registry import (
    ALIASES,
    TOOLS,
    get_deprecation,
    is_deprecated_alias,
    list_tools,
    tool_in_profile,
)

REGISTRY_CSV_HEADERS = (
    "tool",
    "estado_codigo",
    "bundle",
    "reemplazo_codigo",
    "alternativa_docs",
    "default_visible",
)

# Operational guidance for advanced/admin tools (not formal code aliases).
DOCS_ALTERNATIVES: dict[str, str] = {
    "market_scan": "Admin-only VTEX discovery — use market_discover for retail coverage",
    "market_intel_refresh": "Admin/cron refresh — use market_intel_brief for agent reads",
    "market_enrichment_refresh": "Admin/cron enrichment — use market_intel_brief",
    "market_categories": "Advanced VTEX tree — prefer market_discover + market_search",
    "market_enrich": "Advanced Open Food Facts lookup — optional enrichment",
    "market_voice": "Advanced audio transcription — use market_ask for text NL shopping",
    "market_price_history": "Advanced SKU history — use market_trending or market_inflation",
    "market_moat_confidence": "Advanced receipt confidence — use market_price_risk for volatility",
    "market_stock": "Advanced per-SKU stock — use market_search or market_optimize_purchase",
    "market_brands": "Advanced brand frequency — use market_scores for composite signals",
    "market_exchange": "Advanced FX conversion — market_intel_brief includes macro context",
    "market_delivery": "Advanced delivery quote — use market_basket/checkout with include_tco",
    "market_ecosystem_radar": "Intel/Pro ecosystem radar — signal only, not shelf prices",
    "market_procurement_bulk": "Intel/Enterprise bulk signals — prefer market_optimize_purchase or Procure API",
}


def _estado_codigo(name: str) -> str:
    if is_deprecated_alias(name):
        return "legacy-alias"
    if get_deprecation(name):
        return "legacy-alias"
    return "recommended"


def _reemplazo_codigo(name: str) -> str:
    if name in ALIASES:
        return ALIASES[name]
    for tool in TOOLS:
        if tool["name"] == name:
            rep = tool.get("_meta", {}).get("replaces")
            return rep or ""
    return ""


def registry_export_rows(profile: str = "default") -> list[dict[str, Any]]:
    """One row per registered tool, sorted by bundle then name."""
    default_names = {t["name"] for t in list_tools(profile)}
    rows: list[dict[str, Any]] = []
    for tool in TOOLS:
        name = tool["name"]
        meta = tool["_meta"]
        rows.append(
            {
                "tool": name,
                "estado_codigo": _estado_codigo(name),
                "bundle": meta["bundle"],
                "reemplazo_codigo": _reemplazo_codigo(name),
                "alternativa_docs": DOCS_ALTERNATIVES.get(name, ""),
                "default_visible": name in default_names,
            }
        )
    rows.sort(key=lambda r: (r["bundle"], r["tool"]))
    return rows


def registry_csv_text(profile: str = "default") -> str:
    """Return CSV document as a string."""
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=REGISTRY_CSV_HEADERS, lineterminator="\n")
    writer.writeheader()
    for row in registry_export_rows(profile):
        out = dict(row)
        out["default_visible"] = "true" if row["default_visible"] else "false"
        writer.writerow(out)
    return buf.getvalue()


def write_registry_csv(path: Path | str, *, profile: str = "default") -> Path:
    """Write canonical registry CSV to ``path``."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(registry_csv_text(profile), encoding="utf-8")
    return dest
