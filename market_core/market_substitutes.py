"""Product substitution — golden taxonomy + unit normalization + OFF tradeoffs."""

from __future__ import annotations

from typing import Any

from .golden_taxonomy import equivalent_products, resolve_canonical_id
from .market_enrich_sources import resolve_off_for_product
from .market_units import price_per_base_unit


def _off_tradeoff(original: dict | None, candidate: dict | None) -> dict[str, Any]:
    _grade_rank = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
    orig_ns = (original or {}).get("nutriscore", "").upper()
    cand_ns = (candidate or {}).get("nutriscore", "").upper()
    ns_delta = _grade_rank.get(cand_ns, 0) - _grade_rank.get(orig_ns, 0)
    orig_nova = (original or {}).get("nova_group")
    cand_nova = (candidate or {}).get("nova_group")
    nova_delta = 0
    if isinstance(orig_nova, int) and isinstance(cand_nova, int):
        nova_delta = cand_nova - orig_nova
    return {
        "nutriscore_delta": ns_delta,
        "nova_delta": nova_delta,
        "brand_change": True,
    }


def _search_candidates(db, query: str, country: str, store: str | None, limit: int = 20) -> list[dict]:
    from .market_core import STORES

    cc = country.upper()
    stores = [
        k
        for k, v in STORES.items()
        if v.get("country") == cc and not v.get("disabled")
    ]
    if store:
        stores = [store] if store in stores else stores[:1]

    if not stores:
        return []

    placeholders = ",".join("?" * len(stores))
    q = f"%{query.strip()}%"
    try:
        rows = db.execute(
            f"""
            SELECT product_id, name, store, store_name, price, currency, line,
                   canonical_product_id
            FROM price_snapshots
            WHERE store IN ({placeholders})
              AND price > 0 AND price < 999999
              AND LOWER(name) LIKE LOWER(?)
            ORDER BY price ASC
            LIMIT ?
            """,
            [*stores, q, limit],
        ).fetchall()
    except Exception:
        rows = db.execute(
            f"""
            SELECT product_id, name, store, store_name, price, currency, line
            FROM price_snapshots
            WHERE store IN ({placeholders})
              AND price > 0 AND price < 999999
              AND LOWER(name) LIKE LOWER(?)
            ORDER BY price ASC
            LIMIT ?
            """,
            [*stores, q, limit],
        ).fetchall()
    return [dict(r) for r in rows]


def _passes_constraints(candidate: dict, constraints: dict | None, off: dict | None) -> bool:
    if not constraints:
        return True
    max_nova = constraints.get("max_nova")
    if max_nova is not None and off:
        nova = off.get("nova_group")
        if isinstance(nova, int) and nova > int(max_nova):
            return False
    min_ns = constraints.get("min_nutriscore")
    if min_ns and off:
        rank = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
        grade = (off.get("nutriscore") or "").upper()
        if rank.get(grade, 0) < rank.get(str(min_ns).upper(), 0):
            return False
    max_delta = constraints.get("max_price_delta_pct")
    if max_delta is not None and candidate.get("save_pct") is not None:
        if float(candidate["save_pct"]) > float(max_delta):
            return False
    return True


def find_substitutes(
    db,
    *,
    query: str,
    country: str,
    store: str | None = None,
    limit: int = 3,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Find substitute products with unit-normalized price comparison."""
    query = (query or "").strip()
    country = (country or "PE").strip().upper()
    if not query:
        return {
            "query": query,
            "country": country,
            "original": None,
            "substitutes": [],
            "method": "empty_query",
        }

    candidates = _search_candidates(db, query, country, store, limit=30)
    if not candidates:
        return {
            "query": query,
            "country": country,
            "original": None,
            "substitutes": [],
            "method": "no_candidates",
        }

    original_raw = candidates[0]
    canonical_id = resolve_canonical_id(
        db,
        str(original_raw.get("product_id") or ""),
        str(original_raw.get("name") or ""),
    )
    orig_unit = price_per_base_unit(float(original_raw["price"]), str(original_raw.get("name") or ""))

    original = {
        "product_id": original_raw["product_id"],
        "name": original_raw["name"],
        "store": original_raw["store"],
        "price": float(original_raw["price"]),
        "price_per_unit": orig_unit,
        "canonical_product_id": canonical_id,
        "in_stock": True,
    }

    pool: list[dict] = []
    if canonical_id:
        pool = equivalent_products(
            db,
            canonical_id,
            country,
            exclude_product_id=str(original_raw["product_id"]),
        )
    if not pool:
        pool = [c for c in candidates[1:] if c["product_id"] != original_raw["product_id"]]
        method = "fuzzy_name+unit_norm"
    else:
        method = "golden_taxonomy+unit_norm"

    orig_off = resolve_off_for_product(
        db, str(original_raw["product_id"]), str(original_raw.get("name") or "")
    )

    substitutes: list[dict] = []
    orig_ppu = None
    if orig_unit:
        orig_ppu = orig_unit.get("price_per_base") or orig_unit.get("price_per_l") or orig_unit.get("price_per_kg")

    for cand in pool:
        if len(substitutes) >= limit:
            break
        price = float(cand.get("price") or 0)
        if price <= 0:
            continue
        unit = price_per_base_unit(price, str(cand.get("name") or ""))
        save_pct = None
        if orig_ppu and unit:
            cand_ppu = unit.get("price_per_base") or unit.get("price_per_l") or unit.get("price_per_kg")
            if cand_ppu and orig_ppu > 0:
                save_pct = round((orig_ppu - cand_ppu) / orig_ppu * 100, 1)

        off = resolve_off_for_product(db, str(cand.get("product_id") or ""), str(cand.get("name") or ""))
        entry = {
            "product_id": cand.get("product_id"),
            "name": cand.get("name"),
            "store": cand.get("store"),
            "price": price,
            "price_per_unit": unit,
            "save_pct": save_pct,
            "match_reason": "same_canasta_item+unit_equivalent" if canonical_id else "fuzzy_name",
            "canonical_product_id": cand.get("canonical_product_id") or canonical_id,
            "off": off,
            "tradeoffs": _off_tradeoff(orig_off, off),
            "confidence": "ok" if canonical_id else "warn",
        }
        if not _passes_constraints(entry, constraints, off):
            continue
        substitutes.append(entry)

    return {
        "query": query,
        "country": country,
        "original": original,
        "substitutes": substitutes,
        "method": method,
    }
