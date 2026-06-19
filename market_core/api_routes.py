"""FastAPI router for Sprint 1-3 endpoints — importable by the backend.

Mount in backend with::

    from market_core.api_routes import router
    app.include_router(router, prefix="/v1")

All endpoints default to ``enveloped=True`` — responses wrapped in
canonical ``{data, meta, trace}``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from .market_core import get_db
from .market_intel_products import (
    compute_inflation_report,
    compute_price_risk,
    compute_procurement_signal,
)
from .market_quality import build_data_quality_scores
from .market_slas import slas_by_retailer, slas_summary
from .response_envelope import envelope, timing

router = APIRouter(tags=["intel", "quality", "health"])


def _wrap(data: Any, latency_ms: float | None = None) -> dict:
    return envelope(data=data, freshness_seconds=None, confidence="ok", latency_ms=latency_ms)


# ── Intel products ─────────────────────────────────────────────────────────────

@router.get("/intel/price-risk")
def intel_price_risk(
    country: str | None = Query(None, description="PE, AR, MX, BR, CO, CL"),
    line: str | None = Query(None, description="supermercados, farmacias, electro"),
    days: int = Query(7, ge=1, le=90),
    enveloped: bool = Query(True),
):
    """Price Risk Intelligence — which categories are becoming volatile?"""
    db = get_db()
    try:
        with timing() as t:
            result = compute_price_risk(db, country=country, line=line, days=days)
        return _wrap(result, latency_ms=t.elapsed_ms) if enveloped else result
    finally:
        db.close()


@router.get("/intel/inflation-report")
def intel_inflation_report(
    country: str | None = Query(None, description="PE, AR, MX, BR, CO, CL"),
    line: str | None = Query(None, description="supermercados, farmacias, electro"),
    days: int = Query(30, ge=1, le=365),
    enveloped: bool = Query(True),
):
    """Inflation Intelligence — where is price pressure increasing?"""
    db = get_db()
    try:
        with timing() as t:
            result = compute_inflation_report(db, country=country, line=line, days=days)
        return _wrap(result, latency_ms=t.elapsed_ms) if enveloped else result
    finally:
        db.close()


@router.get("/intel/procurement-signal")
def intel_procurement_signal(
    country: str | None = Query(None, description="PE, AR, MX, BR, CO, CL"),
    line: str | None = Query(None, description="supermercados, farmacias, electro"),
    enveloped: bool = Query(True),
):
    """Procurement Intelligence — when should I buy? Returns buy_now/monitor/wait."""
    db = get_db()
    try:
        with timing() as t:
            result = compute_procurement_signal(db, country=country, line=line)
        return _wrap(result, latency_ms=t.elapsed_ms) if enveloped else result
    finally:
        db.close()


# ── Data quality ───────────────────────────────────────────────────────────────

@router.get("/quality/scores")
def quality_scores(
    days: int = Query(7, ge=1, le=30),
    enveloped: bool = Query(True),
):
    """Composite data-quality scores: freshness, unit normalization, match confidence."""
    db = get_db()
    try:
        with timing() as t:
            result = build_data_quality_scores(db, days=days)
        return _wrap(result, latency_ms=t.elapsed_ms) if enveloped else result
    finally:
        db.close()


# ── Health / SLAs ──────────────────────────────────────────────────────────────

@router.get("/health/slas")
def health_slas(
    line: str | None = Query(None),
    enveloped: bool = Query(True),
):
    """Per-retailer SLA metrics: p50/p95 freshness, alive/dead status, error rate."""
    db = get_db()
    try:
        with timing() as t:
            result = slas_by_retailer(db, line=line)
        return _wrap(result, latency_ms=t.elapsed_ms) if enveloped else result
    finally:
        db.close()


@router.get("/health/slas-summary")
def health_slas_summary(
    line: str | None = Query(None),
    enveloped: bool = Query(True),
):
    """Compact SLA summary."""
    db = get_db()
    try:
        with timing() as t:
            result = slas_summary(db, line=line)
        return _wrap(result, latency_ms=t.elapsed_ms) if enveloped else result
    finally:
        db.close()
