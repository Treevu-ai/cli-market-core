"""Ecosystem radar — curated launches cache with optional Product Hunt fetch."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

CACHE_TTL_HOURS = 24

CURATED_LAUNCHES: list[dict[str, Any]] = [
    {
        "name": "Fudo",
        "tagline": "POS and inventory for restaurants in LATAM",
        "votes": 0,
        "url": "https://www.producthunt.com/search?q=fudo",
        "relevance": "grocery_latam",
        "suggested_integration": "connector_candidate",
        "topic": "food",
        "source": "manual_curated",
    },
    {
        "name": "Tiendanube",
        "tagline": "E-commerce platform for SMB retailers",
        "votes": 0,
        "url": "https://www.tiendanube.com",
        "relevance": "retail_latam",
        "suggested_integration": "shopify_like_connector",
        "topic": "retail",
        "source": "manual_curated",
    },
    {
        "name": "Cornershop API",
        "tagline": "Quick-commerce delivery integrations",
        "votes": 0,
        "url": "https://cornershopapp.com",
        "relevance": "delivery_latam",
        "suggested_integration": "delivery_handoff",
        "topic": "food",
        "source": "manual_curated",
    },
]


def _cache_key(topic: str, days: int) -> str:
    return f"ecosystem:{topic.lower()}:{days}"


def _read_cache(db, cache_key: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT payload_json, recorded_at FROM ecosystem_launches_cache WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if not row:
        return None
    try:
        recorded = datetime.fromisoformat(str(row["recorded_at"]).replace("Z", "+00:00"))
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - recorded > timedelta(hours=CACHE_TTL_HOURS):
            return None
        return json.loads(row["payload_json"] or "{}")
    except Exception:
        return None


def _write_cache(db, cache_key: str, payload: dict[str, Any], source: str) -> None:
    db.execute(
        """
        INSERT INTO ecosystem_launches_cache (cache_key, source, payload_json, recorded_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(cache_key) DO UPDATE SET
            source = excluded.source,
            payload_json = excluded.payload_json,
            recorded_at = datetime('now')
        """,
        (cache_key, source, json.dumps(payload, ensure_ascii=False)),
    )
    db.commit()


def _fetch_product_hunt(topic: str, *, limit: int = 20) -> list[dict[str, Any]]:
    token = (os.getenv("PRODUCT_HUNT_TOKEN") or "").strip()
    if not token:
        return []
    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        query = """
        query($topic: String!, $first: Int!) {
          posts(order: VOTES, topic: $topic, first: $first) {
            edges { node { name tagline votesCount url } }
          }
        }
        """
        with httpx.Client(timeout=15) as client:
            r = client.post(
                "https://api.producthunt.com/v2/api/graphql",
                headers=headers,
                json={"query": query, "variables": {"topic": topic, "first": limit}},
            )
            if r.status_code != 200:
                return []
            data = r.json()
            edges = (((data.get("data") or {}).get("posts") or {}).get("edges")) or []
            out: list[dict[str, Any]] = []
            for edge in edges:
                node = edge.get("node") or {}
                out.append(
                    {
                        "name": node.get("name"),
                        "tagline": node.get("tagline"),
                        "votes": node.get("votesCount") or 0,
                        "url": node.get("url"),
                        "relevance": f"{topic}_global",
                        "suggested_integration": "watchlist",
                        "topic": topic,
                        "source": "producthunt",
                    }
                )
            return out
    except Exception:
        return []


def list_ecosystem_launches(
    db,
    *,
    topic: str = "food",
    days: int = 7,
    limit: int = 20,
) -> dict[str, Any]:
    """Return ecosystem launches from cache, Product Hunt, and curated seed."""
    topic = (topic or "food").strip().lower()
    limit = max(1, min(50, int(limit or 20)))
    cache_key = _cache_key(topic, days)

    cached = _read_cache(db, cache_key)
    if cached:
        return cached

    sources: list[str] = []
    launches: list[dict[str, Any]] = []

    curated = [item for item in CURATED_LAUNCHES if topic in (item.get("topic") or "food")]
    launches.extend(curated[:limit])
    if curated:
        sources.append("manual_curated")

    ph = _fetch_product_hunt(topic, limit=limit)
    if ph:
        launches.extend(ph)
        sources.append("producthunt")

    launches = launches[:limit]
    payload = {
        "topic": topic,
        "days": days,
        "launches": launches,
        "sources": sources or ["manual_curated"],
        "disclaimer": "Ecosystem signal only; not price data.",
    }
    _write_cache(db, cache_key, payload, ",".join(sources) or "manual_curated")
    return payload
