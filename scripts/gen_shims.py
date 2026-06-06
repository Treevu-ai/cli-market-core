#!/usr/bin/env python3
"""Generate top-level compatibility shims for market_core submodules."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = [
    "market_alerts",
    "market_basket",
    "market_spread",
    "market_units",
    "market_db",
    "market_indicators",
    "market_enrich_subcategory",
    "market_billing",
    "market_mcp",
    "market_intel_agent",
    "market_health_alert",
    "market_enrich_sources",
    "data_v1_service",
    "dashboard_glossary",
    "dashboard_quality",
    "dashboard_renderer",
    "dashboard_view_model",
    "source_health",
    "price_confidence",
]

TEMPLATE = '''"""Compatibility shim — prefer ``market_core.{name}`` in new code."""

from market_core.{name} import *  # noqa: F403
'''

for name in MODULES:
    path = ROOT / f"{name}.py"
    path.write_text(TEMPLATE.format(name=name), encoding="utf-8")
    print("wrote", path.name)