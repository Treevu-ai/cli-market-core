"""Golden Record taxonomy bridge — reads index export from enrichment_cache."""

from __future__ import annotations

from .market_enrich_sources import cache_get, cache_set
from .market_spread import CANASTA_ITEMS

REGISTRY_CACHE_KEY = "taxonomy:registry"
REGISTRY_SOURCE = "cli-market-index"


def get_taxonomy_registry(db) -> dict[str, dict]:
    """prod_id → {canasta_item, category, fao_commodity, tags, name}."""
    payload = cache_get(db, REGISTRY_CACHE_KEY, max_age_hours=24 * 7)
    if not payload:
        return {}
    products = payload.get("products")
    return products if isinstance(products, dict) else {}


def set_taxonomy_registry(db, products: dict[str, dict], *, registry_size: int = 0) -> None:
    cache_set(
        db,
        REGISTRY_CACHE_KEY,
        REGISTRY_SOURCE,
        {"products": products, "registry_size": registry_size},
    )


def min_canasta_prices_golden(db, country: str | None) -> dict[str, float]:
    """
    Minimum shelf price per canasta staple via canonical_product_id + taxonomy registry.
    Returns {} when registry or linkage is insufficient.
    """
    from .market_core import STORES

    registry = get_taxonomy_registry(db)
    if not registry:
        return {}

    cc = (country or "").upper()
    stores = [k for k, v in STORES.items() if v.get("country") == cc and not v.get("disabled")]
    if not stores:
        return {}

    prod_to_item: dict[str, str] = {}
    for prod_id, meta in registry.items():
        item = meta.get("canasta_item")
        if item in CANASTA_ITEMS:
            prod_to_item[prod_id] = item

    if not prod_to_item:
        return {}

    placeholders = ",".join("?" * len(stores))
    prod_placeholders = ",".join("?" * len(prod_to_item))
    rows = db.execute(
        f"""
        SELECT canonical_product_id, MIN(price) AS p
        FROM price_snapshots
        WHERE store IN ({placeholders})
          AND price > 0
          AND canonical_product_id IN ({prod_placeholders})
        GROUP BY canonical_product_id
        """,
        [*stores, *prod_to_item.keys()],
    ).fetchall()

    by_item: dict[str, float] = {}
    for row in rows:
        prod_id = str(row["canonical_product_id"] or "")
        item = prod_to_item.get(prod_id)
        price = float(row["p"] or 0)
        if item and price > 0:
            prev = by_item.get(item)
            if prev is None or price < prev:
                by_item[item] = price
    return by_item


def canonical_price_buckets(db, country: str | None, line: str | None = None) -> dict[str, list[float]]:
    """Group shelf prices by canonical_product_id for cross-store dispersion."""
    from .market_core import STORES

    cc = (country or "").upper()
    stores = [k for k, v in STORES.items() if v.get("country") == cc and not v.get("disabled")]
    if not stores:
        return {}

    ph = ",".join("?" * len(stores))
    q = f"""
        SELECT canonical_product_id, price
        FROM price_snapshots
        WHERE store IN ({ph}) AND price > 0
          AND canonical_product_id IS NOT NULL AND canonical_product_id != ''
    """
    params: list = list(stores)
    if line:
        q += " AND line = ?"
        params.append(line)

    buckets: dict[str, list[float]] = {}
    for row in db.execute(q, params).fetchall():
        cid = str(row["canonical_product_id"] or "")
        price = float(row["price"] or 0)
        if cid and price > 0:
            buckets.setdefault(cid, []).append(price)
    return buckets


def staple_price_deltas_golden(db, country: str | None, days: int = 7) -> list[float]:
    """% price changes for canasta staples linked via Golden Record IDs."""
    from datetime import datetime, timedelta, timezone

    from .market_core import STORES

    registry = get_taxonomy_registry(db)
    if not registry:
        return []

    cc = (country or "").upper()
    stores = [k for k, v in STORES.items() if v.get("country") == cc and not v.get("disabled")]
    prod_ids = [pid for pid, meta in registry.items() if meta.get("canasta_item")]
    if not stores or not prod_ids:
        return []

    since = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).strftime("%Y-%m-%d %H:%M:%S")
    store_ph = ",".join("?" * len(stores))
    prod_ph = ",".join("?" * len(prod_ids))
    rows = db.execute(
        f"""
        SELECT ph.product_id, ph.store, ph.price, ph.recorded_at
        FROM price_history ph
        INNER JOIN price_snapshots ps
          ON ps.product_id = ph.product_id AND ps.store = ph.store
        WHERE ph.store IN ({store_ph})
          AND ph.price > 0 AND ph.recorded_at >= ?
          AND ps.canonical_product_id IN ({prod_ph})
        """,
        [*stores, since, *prod_ids],
    ).fetchall()

    series: dict[str, list[tuple[str, float]]] = {}
    for row in rows:
        key = f"{row['store']}|{row['product_id']}"
        series.setdefault(key, []).append((row["recorded_at"], float(row["price"])))

    deltas: list[float] = []
    for pts in series.values():
        if len(pts) < 2:
            continue
        pts.sort(key=lambda x: x[0])
        first, last = pts[0][1], pts[-1][1]
        if first > 0:
            deltas.append((last - first) / first * 100)
    return deltas
