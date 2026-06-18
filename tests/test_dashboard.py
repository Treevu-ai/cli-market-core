"""Tests for dashboard modules (view model, renderer, glossary, quality)."""

from __future__ import annotations

from market_core import get_db
from market_core.dashboard_glossary import (
    build_metric_glossary,
    metric_description,
    metric_label,
    section_title,
)
from market_core.dashboard_quality import build_quality_funnel, count_flagged_discounts
from market_core.dashboard_renderer import _esc, render_dashboard_html
from market_core.dashboard_view_model import (
    CANASTA_PARTIAL_THRESHOLD,
    SPEC_VERSION,
    build_dashboard_view_model,
)


def _minimal_dashboard_payload(**overrides) -> dict:
    base = {
        "generated_at": "2026-06-17T12:00:00+00:00",
        "kpis": {
            "total_indexed": 1200,
            "stores_indexed": 4,
            "fresh_24h_pct": 85.5,
            "moat_age_hours": 2.5,
            "snapshots_24h": 300,
        },
        "collector": {"status": "ok", "interval_hours": 8},
        "by_country": [{"country": "PE"}, {"country": "CL"}],
        "moat_guide": {
            "layers": [{"id": "freshness", "metrics": {"status": "fresh"}}],
        },
        "quality_funnel": {
            "captured": 100,
            "clean": 90,
            "flagged": 10,
            "citable": 85,
        },
        "canasta_basica": [
            {"store_name": "Wong", "currency": "PEN", "total": 45.5, "items": 8},
            {"store_name": "Metro", "currency": "PEN", "total": 12.0, "items": 3},
        ],
        "marketing_spreads": [
            {
                "seed": "arroz_1kg",
                "sample_name": "Arroz Costeño 1kg",
                "spread_ratio": 2.8,
                "stores": 3,
                "currency": "PEN",
            }
        ],
        "inflation": [],
        "top_risers": [],
        "top_fallers": [],
        "indicators": {"latest": [], "enrichment": []},
        "store_health": [
            {"store": "wong_pe", "success_pct": 95, "consecutive_failures": 0, "coverage_7d_pct": 88},
            {"store": "dead_pe", "success_pct": 10, "consecutive_failures": 5, "coverage_7d_pct": 5},
        ],
        "suspect_discounts": [
            {"name": "Leche promo", "store_name": "Wong", "discount_pct": 95},
        ],
        "outliers": [],
        "line_country_matrix": [
            {"line": "supermercados", "country": "PE", "stores": 2},
            {"line": "supermercados", "country": "CL", "stores": 0},
        ],
        "by_line_currency": [
            {
                "line": "supermercados",
                "line_name": "Supermercados",
                "currency": "PEN",
                "count": 50,
                "p25": 3.0,
                "p50": 5.0,
                "p75": 8.0,
                "min_price": 1.0,
                "max_price": 20.0,
                "normalizable_pct": 80.0,
            }
        ],
        "dispersion": [{"status": "crit", "line": "supermercados", "spread_ratio": 12}],
        "analytics_meta": {"marketing_canasta_min_spread": 2.5},
    }
    base.update(overrides)
    return base


def test_build_quality_funnel():
    funnel = build_quality_funnel(
        captured=100,
        flagged_discounts=5,
        flagged_outliers=3,
        citable=80,
    )
    assert funnel["captured"] == 100
    assert funnel["flagged"] == 8
    assert funnel["clean"] == 92
    assert funnel["citable"] == 80
    assert "discount>=90%" in funnel["filters"]


def test_build_quality_funnel_never_negative_clean():
    funnel = build_quality_funnel(
        captured=5,
        flagged_discounts=10,
        flagged_outliers=10,
        citable=0,
    )
    assert funnel["clean"] == 0


def test_count_flagged_discounts(isolated_db):
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO price_snapshots (product_id, store, name, price, list_price)
            VALUES ('ok', 's1', 'Normal', 10.0, 12.0),
                   ('flag', 's2', 'Sospechoso', 1.0, 100.0),
                   ('edge', 's3', 'Casi', 10.0, 100.0)
            """
        )
        db.commit()
        assert count_flagged_discounts(db) == 2
    finally:
        db.close()


def test_build_metric_glossary_structure():
    glossary = build_metric_glossary()
    assert glossary["audience"]
    assert "header" in glossary["sections"]
    assert "inventory" in glossary["layer_metrics"]
    assert "fresh" in glossary["status_legend"]


def test_metric_label_and_description():
    assert metric_label("header", "total_indexed", "fallback") != "fallback"
    assert metric_description("header", "total_indexed")
    assert section_title("header") == "Resumen rápido"


def test_metric_label_layer_fallback():
    label = metric_label("nonexistent", "total_indexed")
    assert "Precios" in label or "Total" in label or "precios" in label.lower()


def test_build_dashboard_view_model_blocks():
    vm = build_dashboard_view_model(_minimal_dashboard_payload())
    assert vm["spec_version"] == SPEC_VERSION
    assert vm["locale"] == "es"
    blocks = vm["blocks"]
    assert blocks["hero"]["state"] == "ok"
    assert blocks["canasta"]["state"] == "ok"
    assert blocks["price_spreads"]["state"] == "ok"
    assert blocks["inflation"]["state"] == "measuring"
    assert len(blocks["portada"]["cards"]) == 3


def test_canasta_partial_warning():
    vm = build_dashboard_view_model(_minimal_dashboard_payload())
    stores = vm["blocks"]["canasta"]["stores"]
    partial = [s for s in stores if s["items_found"] < CANASTA_PARTIAL_THRESHOLD]
    assert partial
    assert all(s["warning"] for s in partial)
    assert all(not s["comparable"] for s in partial)


def test_system_status_stale_when_no_snapshots():
    payload = _minimal_dashboard_payload(
        kpis={
            "total_indexed": 50,
            "stores_indexed": 2,
            "fresh_24h_pct": 10,
            "moat_age_hours": 30,
            "snapshots_24h": 0,
        },
        moat_guide={"layers": [{"id": "freshness", "metrics": {"status": "stale"}}]},
    )
    vm = build_dashboard_view_model(payload)
    assert vm["blocks"]["hero"]["state"] == "stale"


def test_inflation_rows_when_data_present():
    payload = _minimal_dashboard_payload(
        inflation=[
            {"line": "Supermercados", "currency": "PEN", "delta_pct": 1.5, "avg_before": 10},
        ],
        top_risers=[{"name": "Arroz"}],
    )
    vm = build_dashboard_view_model(payload)
    block = vm["blocks"]["inflation"]
    assert block["state"] == "ok"
    assert block["rows"][0]["direction"] == "up"


def test_reading_order():
    vm = build_dashboard_view_model(_minimal_dashboard_payload())
    assert vm["reading_order"][0] == "global_bar"
    assert "ops" in vm["reading_order"]


def test_escapes_html():
    assert "&lt;script&gt;" in _esc("<script>")
    assert _esc(None) == ""


def test_render_dashboard_html_document():
    raw = _minimal_dashboard_payload()
    view = build_dashboard_view_model(raw)
    glossary = build_metric_glossary()
    html = render_dashboard_html(
        {
            "generated_at": raw["generated_at"],
            "dashboard_view": view,
            "metric_glossary": glossary,
        }
    )
    assert html.startswith("<!DOCTYPE html>")
    assert 'lang="es"' in html
    assert "CLI Market // Data Moat" in html
    assert "global-bar" in html
    assert "portada" in html
    assert "quality-layer" in html
    assert view["footer_stamp"][:10] in html or "Actualizado" in html


def test_render_dashboard_html_escapes_user_content():
    raw = _minimal_dashboard_payload(
        suspect_discounts=[
            {"name": "<img onerror=alert(1)>", "store_name": "Wong", "discount_pct": 95},
        ]
    )
    view = build_dashboard_view_model(raw)
    html = render_dashboard_html(
        {"dashboard_view": view, "metric_glossary": build_metric_glossary()}
    )
    assert "<img onerror" not in html
    assert "&lt;img onerror" in html


def test_render_dashboard_html_glossary_panel():
    view = build_dashboard_view_model(_minimal_dashboard_payload())
    glossary = build_metric_glossary()
    html = render_dashboard_html({"dashboard_view": view, "metric_glossary": glossary})
    assert "glossary-panel" in html
    assert section_title("header") in html