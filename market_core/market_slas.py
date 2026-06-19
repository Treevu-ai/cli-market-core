"""SLA aggregation — p50/p95 freshness, error rates, and health scoring.

Importable by the backend to expose ``GET /health/slas``.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from .market_core import STORES
from .response_envelope import _parse_timestamp


def slas_by_retailer(db, *, line: str | None = None) -> dict[str, Any]:
    """Compute per-retailer SLA metrics from ``price_snapshots.queried_at``.

    Returns p50/p95 freshness age in seconds, store count with 24h data,
    and a dead/alive classification per retailer.

    The freshness age is the age of the *newest* snapshot per store (how recently
    did this retailer produce data), since the stalest is less actionable.
    """
    now = datetime.now(timezone.utc)

    clauses = ["price > 0"]
    params: list = []
    if line:
        clauses.append("line = ?")
        params.append(line)

    where = " AND ".join(clauses)
    rows = db.execute(
        f"""
        SELECT store, store_name, MAX(queried_at) as last_seen, COUNT(*) as snapshots
        FROM price_snapshots
        WHERE {where}
        GROUP BY store, store_name
        """,
        tuple(params),
    ).fetchall()

    ages: list[float] = []
    per_store: list[dict[str, Any]] = []
    alive_24h = 0
    dead_24h = 0

    for r in rows:
        store_key = r["store"]
        store_name = r["store_name"] or store_key
        snapshots = int(r["snapshots"] or 0)
        last_seen = r["last_seen"]
        dt = _parse_timestamp(last_seen)
        age_secs: float | None = None
        if dt:
            age_secs = (now - dt).total_seconds()
            ages.append(max(0.0, age_secs))

        alive = dt is not None and age_secs is not None and age_secs < 86400
        entry: dict[str, Any] = {
            "store": store_key,
            "store_name": store_name,
            "last_seen_seconds": max(0, int(age_secs)) if age_secs is not None else None,
            "snapshots": snapshots,
            "status": "alive" if alive else "dead",
            "country": STORES.get(store_key, {}).get("country", "??"),
        }
        per_store.append(entry)
        if alive:
            alive_24h += 1
        else:
            dead_24h += 1

    per_store.sort(key=lambda x: x["last_seen_seconds"] or 999999)

    p50 = statistics.median(ages) if ages else None
    p95 = _percentile(ages, 95) if ages else None

    defined = len(STORES)
    missing = max(0, defined - len(per_store))

    return {
        "measured_stores": len(per_store),
        "defined_stores": defined,
        "missing_stores": missing,
        "alive_24h": alive_24h,
        "dead_24h": dead_24h,
        "freshness_p50_secs": round(p50, 1) if p50 is not None else None,
        "freshness_p95_secs": round(p95, 1) if p95 is not None else None,
        "error_rate_pct": round(dead_24h / max(len(per_store), 1) * 100, 1),
        "line": line,
        "retailers": per_store,
    }


def slas_summary(db, *, line: str | None = None) -> dict[str, Any]:
    """Compact SLA summary — suitable for health check endpoints."""
    full = slas_by_retailer(db, line=line)
    return {
        "stores_alive": full["alive_24h"],
        "stores_dead": full["dead_24h"],
        "stores_total": full["measured_stores"],
        "freshness_p50_secs": full["freshness_p50_secs"],
        "freshness_p95_secs": full["freshness_p95_secs"],
        "error_rate_pct": full["error_rate_pct"],
        "line": line,
    }


# ── Internal ────────────────────────────────────────────────────────────────────

def _percentile(values: list[float], pct: float) -> float:
    """Compute the *pct*-th percentile of *values* using linear interpolation."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    k = (pct / 100.0) * (n - 1)
    f = int(k)
    c = k - f
    if f + 1 < n:
        return sorted_vals[f] + c * (sorted_vals[f + 1] - sorted_vals[f])
    return sorted_vals[f]
