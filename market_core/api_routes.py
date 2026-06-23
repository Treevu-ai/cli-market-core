"""API v1 routes — shared between backend and CLI.

Mount in backend with::

    from market_core.api_routes import router
    app.include_router(router, prefix="/v1")

Auth is pluggable: set ``_auth_fn`` to your auth callable before the app starts.
Set ``_enveloped_default`` to False if you don't want response envelopes.

All endpoints default to ``enveloped=True`` — responses wrapped in
canonical ``{data, meta, trace}``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query

from .data_v1_service import (
    build_coverage_matrix,
    query_dispersion,
    query_flagged,
    query_prices,
)
from .market_basket import build_basket_tco, build_canasta_snapshot
from .market_core import get_db
from .market_intel_products import (
    compute_affordability,
    compute_inflation_report,
    compute_price_risk,
    compute_procurement_signal,
)
from .market_quality import build_data_quality_scores
from .market_regulatory import list_regulatory_events
from .market_substitutes import find_substitutes
from .market_slas import slas_by_retailer, slas_summary
from .response_envelope import build_provenance, envelope, timing

router = APIRouter(tags=["intel", "quality", "health"])

# ── Pluggable auth ────────────────────────────────────────────────────────────

# Set before app startup if you need auth.
# Signature: (authorization: str | None) -> str (username)
_auth_fn = None

# Set to False to disable response envelopes by default.
_enveloped_default = True


def _v1_auth(authorization: str | None = Header(None)) -> str:
    """Auth dependency — pluggable via _auth_fn."""
    if _auth_fn is not None:
        return _auth_fn(authorization)
    return "anonymous"


def _wrap(data: Any, latency_ms: float | None = None, **extra_meta) -> dict:
    return envelope(
        data=data,
        freshness_seconds=None,
        confidence=extra_meta.pop("confidence", "ok"),
        latency_ms=latency_ms,
        extra_meta=extra_meta or None,
    )


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


@router.get("/intel/affordability")
def intel_affordability(
    country: str = Query(..., description="PE, AR, MX, BR, CO, CL"),
    line: str = Query("supermercados"),
    days: int = Query(30, ge=1, le=365),
    enveloped: bool = Query(True),
):
    """Affordability OS — cost-of-living composite from shelf + macro signals."""
    db = get_db()
    try:
        with timing() as t:
            result = compute_affordability(db, country=country, line=line, days=days)
        confidence = "ok" if result.get("components", {}).get("canasta_min") else "low"
        prov = build_provenance(primary_source="price_snapshots", methodology="affordability_os_v1")
        if enveloped:
            return _wrap(result, latency_ms=t.elapsed_ms, confidence=confidence, provenance=prov)
        return result
    finally:
        db.close()


@router.get("/intel/regulatory")
def intel_regulatory(
    country: str = Query(..., description="PE, AR, MX, BR, CO, CL"),
    days: int = Query(90, ge=1, le=365),
    category: str | None = Query(None, description="food, energy, fx, pharma, transport"),
    enveloped: bool = Query(True),
):
    """Regulatory context events that may explain shelf price moves."""
    db = get_db()
    try:
        with timing() as t:
            events = list_regulatory_events(db, country=country, days=days, category=category)
            result = {"country": country.upper(), "days": days, "events": events}
        if enveloped:
            return _wrap(
                result,
                latency_ms=t.elapsed_ms,
                provenance=build_provenance(primary_source="regulatory_events", methodology="curated_v1"),
            )
        return result
    finally:
        db.close()


@router.get("/products/substitutes")
def products_substitutes(
    query: str = Query(..., description="Product search term"),
    country: str = Query("PE"),
    store: str | None = Query(None),
    limit: int = Query(3, ge=1, le=10),
    enveloped: bool = Query(True),
):
    """Substitute products with unit-normalized price comparison."""
    db = get_db()
    try:
        with timing() as t:
            result = find_substitutes(db, query=query, country=country, store=store, limit=limit)
        if enveloped:
            return _wrap(
                result,
                latency_ms=t.elapsed_ms,
                confidence="warn" if result.get("method", "").startswith("fuzzy") else "ok",
                provenance=build_provenance(
                    primary_source="price_snapshots",
                    sources_used=["price_snapshots", "golden_taxonomy"],
                    methodology=result.get("method", "substitutes_v1"),
                ),
            )
        return result
    finally:
        db.close()


@router.get("/basket/tco")
def basket_tco_v1(
    country: str = Query("PE"),
    store: str = Query(..., description="Store key from market_discover"),
    items: str = Query(..., description='JSON array [{"name":"leche","qty":2}]'),
    payment_method: str = Query("yape"),
    include_delivery: bool = Query(True),
    enveloped: bool = Query(True),
):
    """Total cost of ownership for a basket at one store."""
    import json

    db = get_db()
    try:
        parsed = json.loads(items)
        if not isinstance(parsed, list):
            parsed = []
        with timing() as t:
            result = build_basket_tco(
                db,
                country=country,
                store=store,
                items=parsed,
                payment_method=payment_method,
                include_delivery=include_delivery,
            )
        if enveloped:
            return _wrap(
                result,
                latency_ms=t.elapsed_ms,
                provenance=build_provenance(primary_source="price_snapshots", methodology="tco_v1"),
            )
        return result
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


# ── Data v1 ────────────────────────────────────────────────────────────────────

@router.get("/quality/flagged")
def quality_flagged(
    reason: str | None = Query(None, description="discount | outlier | spread"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    username: str = Depends(_v1_auth),
):
    """Paginated quality anomalies."""
    db = get_db()
    try:
        return query_flagged(db, reason=reason, limit=limit, offset=offset)
    finally:
        db.close()


@router.get("/prices")
def prices_v1(
    clean: bool = Query(True, alias="clean"),
    country: str | None = None,
    line: str | None = None,
    currency: str | None = None,
    store: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    username: str = Depends(_v1_auth),
):
    """Paginated price snapshots (?clean=1 filters suspect)."""
    db = get_db()
    try:
        return query_prices(
            db,
            clean=clean,
            country=country,
            line=line,
            currency=currency,
            store=store,
            limit=limit,
            offset=offset,
        )
    finally:
        db.close()


@router.get("/dispersion")
def dispersion_v1(
    clean: bool = Query(True, alias="clean"),
    line: str | None = None,
    currency: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    username: str = Depends(_v1_auth),
):
    """Spread groups by subcategory."""
    db = get_db()
    try:
        return query_dispersion(
            db,
            clean=clean,
            line=line,
            currency=currency,
            limit=limit,
            offset=offset,
        )
    finally:
        db.close()


@router.get("/basket")
def basket_snapshot_v1(
    stores: str | None = Query(None, description="Comma-separated store keys"),
    min_items: int = Query(3, ge=1, le=10),
    username: str = Depends(_v1_auth),
):
    """Canasta snapshot from DB."""
    store_filter = None
    if stores:
        store_filter = {s.strip() for s in stores.split(",") if s.strip()}
    db = get_db()
    try:
        return build_canasta_snapshot(db, min_items=min_items, store_filter=store_filter)
    finally:
        db.close()


@router.get("/coverage/matrix")
def coverage_matrix_v1(
    line: str | None = None,
    username: str = Depends(_v1_auth),
):
    """Country × line coverage map."""
    db = get_db()
    try:
        return build_coverage_matrix(db, line=line)
    finally:
        db.close()
