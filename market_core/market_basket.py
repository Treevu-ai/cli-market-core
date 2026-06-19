"""Canasta básica snapshot from DB — shared by dashboard and GET /v1/basket."""

from __future__ import annotations
from typing import Any

from .response_envelope import envelope, freshness_from_string
from .market_spread import CANASTA_ITEMS, CANASTA_SQL_LIKE, matches_canasta_item
from .market_units import is_standard_canasta_pack

CANASTA_TOTAL_ITEMS = 10
CANASTA_PARTIAL_THRESHOLD = 6


def _canasta_name_sql(prod: str) -> tuple[str, tuple]:
    patterns = CANASTA_SQL_LIKE.get(prod, (f"%{prod}%",))
    if len(patterns) == 1:
        return "LOWER(name) LIKE LOWER(?)", (patterns[0],)
    clause = " OR ".join("LOWER(name) LIKE LOWER(?)" for _ in patterns)
    return f"({clause})", patterns


def _aggregate_canasta(db, *, store_filter: set[str] | None = None) -> dict[str, dict]:
    canasta: dict[str, dict] = {}
    for prod in CANASTA_ITEMS:
        name_sql, name_params = _canasta_name_sql(prod)
        rows = db.execute(
            f"""SELECT store_name, store, name, price, currency
               FROM price_snapshots
               WHERE line='supermercados' AND price>0 AND price<999999 AND {name_sql}""",
            name_params,
        ).fetchall()
        store_best: dict[tuple[str, str], float] = {}
        store_fallback: dict[tuple[str, str], float] = {}
        for r in rows:
            row = {"line": "supermercados", "name": r["name"]}
            if not matches_canasta_item(row, prod):
                continue
            if store_filter and r["store"] not in store_filter:
                continue
            key = (r["store_name"], r["currency"])
            price = float(r["price"])
            if is_standard_canasta_pack(r["name"], prod):
                if key not in store_best or price < store_best[key]:
                    store_best[key] = price
            elif key not in store_best:
                if key not in store_fallback or price < store_fallback[key]:
                    store_fallback[key] = price
        for key, price in store_fallback.items():
            if key not in store_best:
                store_best[key] = price
        for (s, cur), best_price in store_best.items():
            canasta.setdefault(s, {"store_name": s, "items": 0, "total": 0, "currency": cur})
            canasta[s]["items"] += 1
            canasta[s]["total"] = round(canasta[s]["total"] + best_price, 2)
    return canasta


def build_canasta_basica(db, *, min_items: int = 3, enveloped: bool = False) -> list[dict] | dict:
    """Dashboard-compatible canasta_basica rows."""
    canasta = _aggregate_canasta(db)
    rows = sorted(
        [v for v in canasta.values() if v["items"] >= min_items],
        key=lambda x: x["total"],
    )[:10]
    if not enveloped:
        return rows
    return envelope(
        data=rows,
        freshness_seconds=None,
        confidence="ok",
        extra_meta={"items_total": CANASTA_TOTAL_ITEMS, "min_items": min_items},
    )


def build_canasta_snapshot(
    db,
    *,
    min_items: int = 3,
    store_filter: set[str] | None = None,
    enveloped: bool = False,
) -> dict:
    """Build canasta snapshot for GET /v1/basket."""
    canasta = _aggregate_canasta(db, store_filter=store_filter)
    stores = sorted(
        [v for v in canasta.values() if v["items"] >= min_items],
        key=lambda x: x["total"],
    )[:10]

    snapshot_row = db.execute(
        "SELECT MAX(queried_at) as ts FROM price_snapshots WHERE price > 0"
    ).fetchone()
    snapshot_at = snapshot_row["ts"] if snapshot_row else None

    result = {
        "source": "snapshot",
        "snapshot_at": snapshot_at,
        "items_total": CANASTA_TOTAL_ITEMS,
        "partial_threshold": CANASTA_PARTIAL_THRESHOLD,
        "stores": [
            {
                "store_name": row["store_name"],
                "items_found": int(row["items"]),
                "completeness_pct": int(row["items"]) * 10,
                "comparable": int(row["items"]) >= CANASTA_PARTIAL_THRESHOLD,
                "total": row["total"],
                "currency": row["currency"],
            }
            for row in stores
        ],
    }
    if not enveloped:
        return result
    return envelope(
        data=result["stores"],
        freshness_seconds=freshness_from_string(snapshot_at),
        confidence="ok",
        extra_meta={
            "source": result["source"],
            "snapshot_at": snapshot_at,
            "items_total": result["items_total"],
            "partial_threshold": result["partial_threshold"],
        },
    )


def build_basket_compare(
    db,
    *,
    items: list[dict[str, Any]],
    store_filter: set[str] | None = None,
    enveloped: bool = False,
) -> dict[str, Any]:
    """Compare total basket cost across retailers for arbitrary items.

    Args:
        db: Database connection.
        items: List of dicts with ``name`` (required) and optional ``qty`` (default 1).
        store_filter: Optional set of store keys to restrict comparison.
        enveloped: When True, wrap result in canonical envelope.

    Returns:
        ``{items_searched, items_found, stores: [{store_name, items_found, total, currency, breakdown}]}``
    """
    store_totals: dict[str, dict[str, Any]] = {}
    items_found = 0

    for entry in items:
        query = str(entry.get("name", "")).strip()
        qty = max(1, int(entry.get("qty", 1) or 1))
        if not query:
            continue

        rows = db.execute(
            """SELECT store, store_name, name, price, currency
               FROM price_snapshots
               WHERE price > 0 AND price < 999999
                 AND LOWER(name) LIKE LOWER(?)
               ORDER BY price ASC""",
            (f"%{query}%",),
        ).fetchall()

        store_best: dict[str, tuple[float, str, str]] = {}
        for r in rows:
            store = r["store"]
            if store_filter and store not in store_filter:
                continue
            price = float(r["price"])
            if store not in store_best or price < store_best[store][0]:
                store_best[store] = (price, r["store_name"], r["currency"])

        if store_best:
            items_found += 1
            for store, (price, store_name, currency) in store_best.items():
                item_total = round(price * qty, 2)
                if store not in store_totals:
                    store_totals[store] = {
                        "store_name": store_name,
                        "items_found": 0,
                        "total": 0.0,
                        "currency": currency,
                        "breakdown": [],
                    }
                store_totals[store]["items_found"] += 1
                store_totals[store]["total"] = round(store_totals[store]["total"] + item_total, 2)
                store_totals[store]["breakdown"].append({
                    "item": query,
                    "qty": qty,
                    "unit_price": price,
                    "item_total": item_total,
                })

    stores = sorted(store_totals.values(), key=lambda x: x["total"])

    result = {
        "items_searched": len(items),
        "items_found": items_found,
        "stores": stores[:10],
    }
    if not enveloped:
        return result
    return envelope(
        data=stores[:10],
        freshness_seconds=None,
        confidence="ok",
        extra_meta=result,
    )
