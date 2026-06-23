"""Regulatory context events — curated policy signals that explain shelf price moves."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

REGULATORY_CATEGORIES = frozenset({"food", "energy", "fx", "pharma", "transport"})
IMPACT_HINTS = frozenset({"upward_cost_pressure", "downward_cost_pressure", "neutral", "volatility"})


def list_regulatory_events(
    db,
    *,
    country: str,
    days: int = 90,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Return regulatory events for *country* within the last *days*."""
    cc = (country or "").strip().upper()
    if not cc:
        return []

    since = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
    params: list[Any] = [cc, since]
    sql = """
        SELECT id, country, category, title, summary, effective_at, source_url,
               impact_hint, lines_affected_json
        FROM regulatory_events
        WHERE country = ? AND effective_at >= ?
    """
    if category:
        sql += " AND category = ?"
        params.append(category.strip().lower())

    sql += " ORDER BY effective_at DESC"
    try:
        rows = db.execute(sql, params).fetchall()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        lines_raw = r.get("lines_affected_json") or "[]"
        try:
            import json

            lines_affected = json.loads(lines_raw) if isinstance(lines_raw, str) else lines_raw
        except Exception:
            lines_affected = []
        out.append(
            {
                "id": r["id"],
                "country": r["country"],
                "category": r["category"],
                "title": r["title"],
                "summary": r.get("summary") or "",
                "effective_at": r.get("effective_at"),
                "source_url": r.get("source_url") or "",
                "impact_hint": r.get("impact_hint") or "neutral",
                "lines_affected": lines_affected if isinstance(lines_affected, list) else [],
            }
        )
    return out


def regulatory_headlines(db, country: str | None, *, limit: int = 3) -> list[dict[str, Any]]:
    """Compact headlines for intel briefs."""
    if not country:
        return []
    events = list_regulatory_events(db, country=country, days=90)[:limit]
    return [
        {
            "id": e["id"],
            "category": e["category"],
            "title": e["title"],
            "summary": e.get("summary", ""),
            "effective_at": e.get("effective_at"),
            "impact_hint": e.get("impact_hint"),
        }
        for e in events
    ]


def upsert_regulatory_event(db, event: dict[str, Any]) -> dict[str, Any]:
    """Insert or replace a curated regulatory event (admin)."""
    import json

    category = (event.get("category") or "food").strip().lower()
    if category not in REGULATORY_CATEGORIES:
        raise ValueError(f"invalid category: {category}")

    impact = (event.get("impact_hint") or "neutral").strip().lower()
    if impact not in IMPACT_HINTS:
        impact = "neutral"

    event_id = event.get("id") or f"reg-{uuid.uuid4().hex[:8]}"
    lines = event.get("lines_affected") or []
    db.execute(
        """
        INSERT INTO regulatory_events
            (id, country, category, title, summary, effective_at, source_url,
             impact_hint, lines_affected_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            country=excluded.country,
            category=excluded.category,
            title=excluded.title,
            summary=excluded.summary,
            effective_at=excluded.effective_at,
            source_url=excluded.source_url,
            impact_hint=excluded.impact_hint,
            lines_affected_json=excluded.lines_affected_json
        """,
        (
            event_id,
            (event.get("country") or "").upper(),
            category,
            event.get("title") or "",
            event.get("summary") or "",
            event.get("effective_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            event.get("source_url") or "",
            impact,
            json.dumps(lines, ensure_ascii=False),
        ),
    )
    db.commit()
    return {"id": event_id, "status": "upserted"}


def seed_default_regulatory_events(db) -> int:
    """Idempotent seed for demo / empty deployments."""
    try:
        row = db.execute("SELECT COUNT(*) AS n FROM regulatory_events").fetchone()
        n = int(row["n"]) if row else 0
        if n > 0:
            return 0
    except Exception:
        return 0

    seeds = [
        {
            "id": "reg-pe-2026-001",
            "country": "PE",
            "category": "energy",
            "title": "Ajuste tarifario eléctrico segmento B",
            "summary": "Incremento promedio 4.2% en tarifa residencial desde marzo 2026.",
            "effective_at": "2026-03-01",
            "impact_hint": "upward_cost_pressure",
            "lines_affected": ["hogar"],
            "source_url": "https://www.osinergmin.gob.pe/",
        },
        {
            "id": "reg-pe-2026-002",
            "country": "PE",
            "category": "food",
            "title": "Vigilancia de precios en canasta básica",
            "summary": "INDECOPI refuerza monitoreo de precios de arroz, aceite y leche en Lima.",
            "effective_at": "2026-01-15",
            "impact_hint": "volatility",
            "lines_affected": ["supermercados"],
            "source_url": "https://www.indecopi.gob.pe/",
        },
        {
            "id": "reg-pe-2026-003",
            "country": "PE",
            "category": "fx",
            "title": "Tipo de cambio interbancario en rango estrecho",
            "summary": "Presión cambiaria moderada; importados sensibles al USD en góndola.",
            "effective_at": "2026-02-01",
            "impact_hint": "neutral",
            "lines_affected": ["supermercados", "electro"],
            "source_url": "https://www.bcrp.gob.pe/",
        },
        {
            "id": "reg-ar-2026-001",
            "country": "AR",
            "category": "fx",
            "title": "Brecha blue vs oficial en alimentos importados",
            "summary": "Precios de góndola con componente importado siguen brecha cambiaria.",
            "effective_at": "2026-01-20",
            "impact_hint": "upward_cost_pressure",
            "lines_affected": ["supermercados"],
            "source_url": "",
        },
        {
            "id": "reg-ar-2026-002",
            "country": "AR",
            "category": "food",
            "title": "Acuerdo de precios en aceite y harina",
            "summary": "Programa de referencia de precios en categorías básicas.",
            "effective_at": "2026-02-10",
            "impact_hint": "downward_cost_pressure",
            "lines_affected": ["supermercados"],
            "source_url": "",
        },
    ]
    for ev in seeds:
        upsert_regulatory_event(db, ev)
    return len(seeds)
