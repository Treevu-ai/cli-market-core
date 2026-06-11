"""Shared moat KPIs for GET /health/stats — backend prod + world mirror."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .source_health import _age_hours, build_sources_health

logger = logging.getLogger(__name__)


def derive_collector_status(
    *,
    finished_at: str | datetime | None,
    prices_collected: int | None,
    moat_age_h: float | None = None,
) -> tuple[str, float | None]:
    """Map last collector run + moat freshness to ok / empty / stale / dead / running."""
    if finished_at is None:
        return "running", None
    age_h = _age_hours(finished_at)
    if age_h is None:
        return "unknown", None
    collected = int(prices_collected or 0)
    if age_h > 24 or (moat_age_h is not None and moat_age_h >= 24):
        return "dead", age_h
    if age_h > 12 or (moat_age_h is not None and moat_age_h >= 8):
        return "stale", age_h
    if collected > 0:
        return "ok", age_h
    return "empty", age_h


def compute_linkage_metrics(db) -> dict[str, float | int]:
    """Golden linkage % from price_snapshots.canonical_product_id."""
    stats: dict[str, float | int] = {
        "snapshots_linked": 0,
        "golden_records_distinct": 0,
        "unlinked_snapshots": 0,
        "linkage_pct": 0.0,
        "golden_linkage_pct": 0.0,
    }
    try:
        total = db.execute(
            "SELECT COUNT(*) as n FROM price_snapshots WHERE price > 0"
        ).fetchone()["n"]
        linked = db.execute(
            """
            SELECT COUNT(*) as n FROM price_snapshots
            WHERE price > 0
              AND canonical_product_id IS NOT NULL AND canonical_product_id != ''
            """
        ).fetchone()["n"]
        distinct = db.execute(
            """
            SELECT COUNT(DISTINCT canonical_product_id) as n FROM price_snapshots
            WHERE canonical_product_id IS NOT NULL AND canonical_product_id != ''
            """
        ).fetchone()["n"]
        pct = round(int(linked) / int(total) * 100, 1) if total else 0.0
        stats["snapshots_linked"] = int(linked)
        stats["golden_records_distinct"] = int(distinct)
        stats["unlinked_snapshots"] = int(total) - int(linked)
        stats["linkage_pct"] = pct
        stats["golden_linkage_pct"] = pct
    except Exception as exc:
        logger.debug("compute_linkage_metrics skipped: %s", exc)
    return stats


def build_health_stats(
    db,
    *,
    registry_size: int | None = None,
    include_sources_summary: bool = True,
) -> dict:
    """Live moat KPIs for landing and ops — no dashboard dependencies."""
    from .market_core import USE_PG

    interval_1d = "NOW() - INTERVAL '1 day'" if USE_PG else "datetime('now', '-1 day')"
    interval_7d = "NOW() - INTERVAL '7 days'" if USE_PG else "datetime('now', '-7 days')"

    total = db.execute(
        "SELECT COUNT(*) as n FROM price_snapshots WHERE price > 0"
    ).fetchone()["n"]
    snapshots_24h = db.execute(
        f"SELECT COUNT(*) as n FROM price_snapshots WHERE price > 0 AND queried_at >= {interval_1d}"
    ).fetchone()["n"]
    snapshots_7d = db.execute(
        f"SELECT COUNT(*) as n FROM price_snapshots WHERE price > 0 AND queried_at >= {interval_7d}"
    ).fetchone()["n"]
    stores_indexed = db.execute(
        "SELECT COUNT(DISTINCT store) as n FROM price_snapshots WHERE price > 0"
    ).fetchone()["n"]
    stores_7d = db.execute(
        f"SELECT COUNT(DISTINCT store) as n FROM price_snapshots WHERE price > 0 AND queried_at >= {interval_7d}"
    ).fetchone()["n"]
    latest = db.execute("SELECT MAX(queried_at) as t FROM price_snapshots").fetchone()["t"]

    collector_status = "unknown"
    last_run = None
    try:
        last_run = db.execute(
            "SELECT finished_at, prices_collected FROM collector_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    moat_age_hours = None
    if latest:
        try:
            if isinstance(latest, str):
                latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
            else:
                latest_dt = latest
            if latest_dt.tzinfo is None:
                latest_dt = latest_dt.replace(tzinfo=timezone.utc)
            moat_age_hours = round((now - latest_dt).total_seconds() / 3600, 1)
        except Exception:
            pass

    if last_run:
        collector_status, _ = derive_collector_status(
            finished_at=last_run["finished_at"],
            prices_collected=last_run["prices_collected"],
            moat_age_h=moat_age_hours,
        )

    linkage = compute_linkage_metrics(db)
    sources_summary = None
    if include_sources_summary:
        try:
            sources_summary = build_sources_health(db, catalog_only=True)["summary"]
        except Exception as exc:
            logger.debug("sources summary skipped: %s", exc)

    fresh_24h_pct = round(snapshots_24h / total * 100, 1) if total > 0 else 0
    coverage_7d_pct = round(stores_7d / stores_indexed * 100, 1) if stores_indexed > 0 else 0
    avg_daily_7d = round(snapshots_7d / 7) if snapshots_7d else 0

    out: dict = {
        "total_indexed": total,
        "snapshots_24h": snapshots_24h,
        "stores_indexed": stores_indexed,
        "fresh_24h_pct": fresh_24h_pct,
        "moat_age_hours": moat_age_hours,
        "coverage_7d_pct": coverage_7d_pct,
        "avg_daily_7d": avg_daily_7d,
        "generated_at": now.isoformat(),
        "collector_status": collector_status,
        "golden_linkage_pct": linkage["golden_linkage_pct"],
        "linkage_pct": linkage["linkage_pct"],
        "snapshots_linked": linkage["snapshots_linked"],
        "unlinked_snapshots": linkage["unlinked_snapshots"],
        "golden_records_distinct": linkage["golden_records_distinct"],
    }
    if registry_size is not None:
        out["registry_size"] = registry_size
    if sources_summary is not None:
        out["sources_summary"] = sources_summary
    return out
