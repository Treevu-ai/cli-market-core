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

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from .data_v1_service import (
    build_coverage_matrix,
    query_dispersion,
    query_flagged,
    query_prices,
)
from .market_action_links import get_shopping_list_export
from .market_basket import build_basket_compare, build_basket_tco, build_canasta_snapshot
from .market_core import get_db
from .market_household import (
    DEFAULT_HOUSEHOLD,
    get_household,
    household_summary,
    patch_household,
    put_household,
)
from .market_ecosystem import list_ecosystem_launches
from .market_feature_flags import crowd_receipts_enabled, ecosystem_radar_enabled, household_enabled
from .market_missions import run_optimize_purchase
from .market_procurement_bulk import run_procurement_bulk
from .market_receipts import compute_moat_confidence, get_receipt, submit_receipt
from .market_intel_products import (
    compute_affordability,
    compute_inflation_report,
    compute_price_deal_alerts,
    compute_price_risk,
    compute_procurement_signal,
)
from .market_quality import build_data_quality_scores
from .market_regulatory import list_regulatory_events
from .market_substitutes import find_substitutes
from .market_slas import slas_by_retailer, slas_summary
from .market_observatory import record_affiliate_click
from .response_envelope import build_provenance, confidence_from_coverage, envelope, timing

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


def _wrap_provenance(
    data: Any,
    latency_ms: float | None,
    *,
    primary_source: str,
    methodology: str,
    confidence: str = "ok",
    sources_used: list[str] | None = None,
    stores_responded: int | None = None,
    stores_queried: int | None = None,
) -> dict:
    prov = build_provenance(
        primary_source=primary_source,
        methodology=methodology,
        sources_used=sources_used,
        stores_responded=stores_responded,
        stores_queried=stores_queried,
    )
    conf = confidence_from_coverage(prov.get("coverage_pct"), fallback=confidence)
    return _wrap(data, latency_ms=latency_ms, confidence=conf, provenance=prov)


def _feature_disabled(feature: str) -> None:
    raise HTTPException(status_code=503, detail=f"{feature} is temporarily disabled")


def _require_auth(username: str) -> str:
    if not username or username == "anonymous":
        raise HTTPException(status_code=401, detail="authentication required")
    return username


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
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="price_snapshots",
                methodology="price_risk_v1",
            )
        return result
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
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="price_snapshots",
                methodology="inflation_report_v1",
            )
        return result
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
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="price_snapshots",
                methodology="procurement_signal_v1",
            )
        return result
    finally:
        db.close()


@router.get("/intel/alerts")
def intel_price_deal_alerts(
    product: str = Query(..., min_length=1, description="Product name query"),
    store: str | None = Query(None, description="Optional store key filter"),
    threshold_pct: float = Query(5.0, ge=0.1, le=100.0),
    limit: int = Query(10, ge=1, le=50),
    enveloped: bool = Query(True),
):
    """Price deal alerts — products at or above threshold_pct discount vs list price."""
    db = get_db()
    try:
        with timing() as t:
            result = compute_price_deal_alerts(
                db,
                product=product,
                store=store,
                threshold_pct=threshold_pct,
                limit=limit,
            )
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="price_snapshots",
                methodology="price_deal_alerts_v1",
            )
        return result
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
    zipcode: str | None = Query(None),
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
                zipcode=zipcode,
            )
        if enveloped:
            sources = ["price_snapshots"]
            if include_delivery and result.get("delivery", {}).get("available"):
                sources.append("delivery")
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="price_snapshots",
                sources_used=sources,
                methodology="tco_v1",
            )
        return result
    finally:
        db.close()


# ── Household profile (wave 2) ─────────────────────────────────────────────────

@router.get("/household")
def household_get(
    username: str = Depends(_v1_auth),
    enveloped: bool = Query(True),
):
    """Persistent household budget and dietary restrictions."""
    if not household_enabled():
        _feature_disabled("household")
    user = _require_auth(username)
    db = get_db()
    try:
        with timing() as t:
            profile = get_household(db, user)
            data = profile if profile is not None else dict(DEFAULT_HOUSEHOLD)
        if enveloped:
            return _wrap_provenance(
                data,
                t.elapsed_ms,
                primary_source="household_profiles",
                methodology="household_v1",
            )
        return data
    finally:
        db.close()


@router.get("/household/summary")
def household_summary_v1(
    username: str = Depends(_v1_auth),
    enveloped: bool = Query(True),
):
    """Derived budget summary for the authenticated household."""
    if not household_enabled():
        _feature_disabled("household")
    user = _require_auth(username)
    db = get_db()
    try:
        with timing() as t:
            data = household_summary(db, user)
        if enveloped:
            return _wrap_provenance(
                data,
                t.elapsed_ms,
                primary_source="household_profiles",
                methodology="household_summary_v1",
            )
        return data
    finally:
        db.close()


@router.put("/household")
def household_put(
    payload: dict[str, Any] = Body(...),
    username: str = Depends(_v1_auth),
    enveloped: bool = Query(True),
):
    """Replace household profile (schema v1)."""
    if not household_enabled():
        _feature_disabled("household")
    user = _require_auth(username)
    db = get_db()
    try:
        with timing() as t:
            try:
                data = put_household(db, user, payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        if enveloped:
            return _wrap_provenance(
                data,
                t.elapsed_ms,
                primary_source="household_profiles",
                methodology="household_v1",
            )
        return data
    finally:
        db.close()


@router.patch("/household")
def household_patch(
    payload: dict[str, Any] = Body(...),
    username: str = Depends(_v1_auth),
    enveloped: bool = Query(True),
):
    """Partial update of household profile."""
    if not household_enabled():
        _feature_disabled("household")
    user = _require_auth(username)
    db = get_db()
    try:
        with timing() as t:
            try:
                data = patch_household(db, user, payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        if enveloped:
            return _wrap_provenance(
                data,
                t.elapsed_ms,
                primary_source="household_profiles",
                methodology="household_v1",
            )
        return data
    finally:
        db.close()


# ── Basket compare (wave 4) ────────────────────────────────────────────────────

@router.post("/basket/compare")
def basket_compare_v1(
    payload: dict[str, Any] = Body(...),
    enveloped: bool = Query(True),
):
    """Compare basket totals across retailers with optional TCO and action links."""
    db = get_db()
    try:
        store_filter = None
        stores = payload.get("stores")
        if stores:
            store_filter = {str(s).strip() for s in stores if str(s).strip()}
        with timing() as t:
            result = build_basket_compare(
                db,
                items=payload.get("items") or [],
                store_filter=store_filter,
                include_tco=bool(payload.get("include_tco", False)),
                payment_method=str(payload.get("payment_method") or "yape"),
                include_delivery=bool(payload.get("include_delivery", True)),
                zipcode=payload.get("zipcode"),
                include_action_links=bool(payload.get("include_action_links", False)),
                country=str(payload.get("country") or "PE"),
            )
        if enveloped:
            store_rows = result.get("stores") or []
            sources = ["price_snapshots"]
            if any((s.get("tco") or {}).get("delivery", {}).get("available") for s in store_rows):
                sources.append("delivery")
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="price_snapshots",
                sources_used=sources,
                stores_responded=len(store_rows),
                stores_queried=len(store_rows) or None,
                methodology="basket_compare_v1",
            )
        return result
    finally:
        db.close()


# ── Missions (wave 2) ──────────────────────────────────────────────────────────

@router.post("/missions/optimize-purchase")
def mission_optimize_purchase(
    payload: dict[str, Any] = Body(...),
    username: str = Depends(_v1_auth),
    enveloped: bool = Query(True),
):
    """Composite mission: basket compare + TCO + substitutes + intel + action links."""
    db = get_db()
    try:
        with timing() as t:
            result = run_optimize_purchase(
                db,
                country=str(payload.get("country") or "PE"),
                items=payload.get("items") or [],
                constraints=payload.get("constraints"),
                include_intel=bool(payload.get("include_intel", True)),
                username=username,
            )
        if enveloped:
            conf = "ok" if result.get("status") == "ok" else "warn"
            compare = (result.get("sections") or {}).get("compare") or {}
            store_rows = compare.get("stores") or []
            sources = ["price_snapshots", "golden_taxonomy"]
            if any((s.get("tco") or {}).get("delivery", {}).get("available") for s in store_rows):
                sources.append("delivery")
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="price_snapshots",
                sources_used=sources,
                stores_responded=len(store_rows),
                stores_queried=len(store_rows) or None,
                methodology="optimize_purchase_v1",
                confidence=conf,
            )
        return result
    finally:
        db.close()


@router.get("/export/shopping-list/{token}")
def export_shopping_list(
    token: str,
    enveloped: bool = Query(False),
):
    """Retrieve an exported shopping list by token (L2 action closure)."""
    db = get_db()
    try:
        with timing() as t:
            data = get_shopping_list_export(db, token)
            if data is None:
                raise HTTPException(status_code=404, detail="export not found or expired")
        return _wrap(data, latency_ms=t.elapsed_ms) if enveloped else data
    finally:
        db.close()


@router.post("/action/affiliate-click")
def action_affiliate_click(
    payload: dict[str, Any] = Body(...),
    username: str = Depends(_v1_auth),
    enveloped: bool = Query(True),
):
    """Record L3 affiliate deeplink click for observatory reporting."""
    store = str(payload.get("store") or "").strip()
    if not store:
        raise HTTPException(status_code=422, detail="store required")
    with timing() as t:
        telemetry = record_affiliate_click(
            store=store,
            url=payload.get("url"),
            product_id=payload.get("product_id"),
            agent_id=username if username != "anonymous" else "anonymous",
            country=payload.get("country"),
            linked_username=username if username != "anonymous" else None,
        )
        data = {"recorded": bool(telemetry.get("ok")), "store": store, **telemetry}
    return _wrap(data, latency_ms=t.elapsed_ms) if enveloped else data


# ── Wave 3: crowd truth, ecosystem, procurement bulk ───────────────────────────

@router.post("/receipts/submit")
def receipts_submit(
    payload: dict[str, Any] = Body(...),
    username: str = Depends(_v1_auth),
    enveloped: bool = Query(True),
):
    """Submit a receipt image URL for crowd moat validation (OCR inline or pending)."""
    if not crowd_receipts_enabled():
        _feature_disabled("crowd_receipts")
    db = get_db()
    try:
        with timing() as t:
            result = submit_receipt(
                db,
                url=str(payload.get("url") or ""),
                country=str(payload.get("country") or "PE"),
                username=username if username != "anonymous" else None,
                ocr=payload.get("ocr"),
                line_items=payload.get("line_items"),
            )
        conf = "ok" if result.get("status") == "confirmed" else "warn"
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="receipt_submissions",
                methodology="receipt_crowd_v1",
                confidence=conf,
            )
        return result
    finally:
        db.close()


@router.get("/receipts/{receipt_id}")
def receipts_get(
    receipt_id: str,
    enveloped: bool = Query(True),
):
    """Get receipt submission status and moat diff."""
    db = get_db()
    try:
        with timing() as t:
            result = get_receipt(db, receipt_id)
            if result is None:
                raise HTTPException(status_code=404, detail="receipt not found")
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="receipt_submissions",
                methodology="receipt_crowd_v1",
            )
        return result
    finally:
        db.close()


@router.get("/moat/confidence")
def moat_confidence_v1(
    product_id: str | None = Query(None),
    store: str | None = Query(None),
    name: str | None = Query(None),
    enveloped: bool = Query(True),
):
    """Crowd-sourced confidence tier from receipt confirmations."""
    db = get_db()
    try:
        with timing() as t:
            result = compute_moat_confidence(db, product_id=product_id, store=store, name=name)
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="receipt_submissions",
                methodology="moat_confidence_v1",
            )
        return result
    finally:
        db.close()


@router.get("/ecosystem/launches")
def ecosystem_launches_v1(
    topic: str = Query("food"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=50),
    enveloped: bool = Query(True),
):
    """Ecosystem radar — curated and cached Product Hunt launches."""
    if not ecosystem_radar_enabled():
        _feature_disabled("ecosystem_radar")
    db = get_db()
    try:
        with timing() as t:
            result = list_ecosystem_launches(db, topic=topic, days=days, limit=limit)
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="ecosystem_launches_cache",
                methodology="ecosystem_radar_v1",
            )
        return result
    finally:
        db.close()


@router.post("/intel/procurement-bulk")
def intel_procurement_bulk(
    payload: dict[str, Any] = Body(...),
    username: str = Depends(_v1_auth),
    enveloped: bool = Query(True),
):
    """B2B bulk procurement signals for a SKU list."""
    _require_auth(username)
    db = get_db()
    try:
        with timing() as t:
            result = run_procurement_bulk(
                db,
                country=str(payload.get("country") or "PE"),
                lines=payload.get("lines") or [],
                organization_id=payload.get("organization_id"),
                include_substitutes=bool(payload.get("include_substitutes", True)),
                output=str(payload.get("output") or "json"),
            )
        conf = "ok" if result.get("status") == "ok" else "warn"
        if enveloped:
            return _wrap_provenance(
                result,
                t.elapsed_ms,
                primary_source="price_snapshots",
                methodology="procurement_bulk_v1",
                confidence=conf,
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
