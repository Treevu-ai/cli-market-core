"""Data moat quality scores — coverage freshness, unit normalization, match confidence.

Three pillar scores that feed the composite data-quality dashboard. All operate
on ``price_snapshots`` and are importable by the backend for ``/v1/quality/scores``.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from .market_core import STORES
from .market_units import parse_pack_size


def compute_coverage_freshness(db, *, days: int = 7) -> dict[str, Any]:
    """Coverage freshness score: fresh SKUs in the last *days* / total SKUs.

    Returns per-cell (line x country) freshness plus a global aggregate.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()

    rows = db.execute(
        """
        SELECT line, store, COUNT(*) as total,
               SUM(CASE WHEN queried_at >= ? THEN 1 ELSE 0 END) as fresh
        FROM price_snapshots WHERE price > 0
        GROUP BY line, store
        """,
        (cutoff,),
    ).fetchall()

    cells: dict[str, dict[str, Any]] = {}
    global_total = 0
    global_fresh = 0

    for r in rows:
        line = r["line"] or "unknown"
        store = r["store"]
        country = STORES.get(store, {}).get("country", "??")
        key = f"{line}|{country}"
        total = int(r["total"] or 0)
        fresh = int(r["fresh"] or 0)

        if key not in cells:
            cells[key] = {"line": line, "country": country, "total": 0, "fresh": 0}
        cells[key]["total"] += total
        cells[key]["fresh"] += fresh

        global_total += total
        global_fresh += fresh

    cell_list = sorted(cells.values(), key=lambda c: (c["country"], c["line"]))
    for c in cell_list:
        c["freshness_pct"] = round(c["fresh"] / c["total"] * 100, 1) if c["total"] > 0 else 0.0

    global_pct = round(global_fresh / global_total * 100, 1) if global_total > 0 else 0.0

    return {
        "global": {
            "total_snapshots": global_total,
            "fresh_snapshots": global_fresh,
            "freshness_pct": global_pct,
            "window_days": days,
        },
        "cells": cell_list,
    }


def compute_unit_normalization_rate(db) -> dict[str, Any]:
    """Unit normalization score: % of products with parsable base_unit + unit_price.

    Samples product names from ``price_snapshots`` and attempts to parse
    pack sizes via :func:`market_units.parse_pack_size`.
    """
    rows = db.execute(
        """
        SELECT DISTINCT name, price FROM price_snapshots
        WHERE price > 0 AND name IS NOT NULL AND name != ''
        """
    ).fetchall()

    total = 0
    normalized = 0

    for r in rows:
        name = r["name"]
        price = float(r["price"]) if r["price"] else 0.0
        total += 1
        parsed = parse_pack_size(name) if price > 0 else None
        if parsed is not None:
            normalized += 1

    rate = round(normalized / total * 100, 1) if total > 0 else 0.0

    return {
        "total_products_sampled": total,
        "normalized_products": normalized,
        "normalization_pct": rate,
    }


def compute_match_confidence_rate(db) -> dict[str, Any]:
    """Match confidence score: % of snapshots with confidence='ok'.

    Uses the ``confidence`` column in ``price_snapshots``.
    """
    row = db.execute(
        """
        SELECT COUNT(*) as total,
               SUM(CASE WHEN confidence = 'ok' THEN 1 ELSE 0 END) as ok_count
        FROM price_snapshots WHERE price > 0
        """
    ).fetchone()

    total = int(row["total"] or 0)
    ok_count = int(row["ok_count"] or 0)
    pct = round(ok_count / total * 100, 1) if total > 0 else 0.0

    return {
        "total_snapshots": total,
        "ok_snapshots": ok_count,
        "suspect_snapshots": total - ok_count,
        "confidence_pct": pct,
    }


def build_data_quality_scores(db, *, days: int = 7) -> dict[str, Any]:
    """Composite data-quality report combining freshness, normalization, and confidence.

    Returns a single dict suitable for ``/v1/quality/scores`` and dashboard rendering.
    """
    freshness = compute_coverage_freshness(db, days=days)
    normalization = compute_unit_normalization_rate(db)
    confidence = compute_match_confidence_rate(db)

    f = float(freshness["global"]["freshness_pct"])
    n = float(normalization["normalization_pct"])
    c = float(confidence["confidence_pct"])
    composite = round(f * 0.4 + n * 0.3 + c * 0.3, 1)

    return {
        "composite_score": composite,
        "freshness": freshness,
        "unit_normalization": normalization,
        "match_confidence": confidence,
    }
