"""B2B procurement bulk — per-line buy/wait/monitor signals for SKU lists."""

from __future__ import annotations

from typing import Any

from .market_intel_products import compute_procurement_signal
from .market_substitutes import find_substitutes


def _line_signal(db, *, country: str, sku_query: str, include_substitutes: bool) -> dict[str, Any]:
    query = (sku_query or "").strip()
    if not query:
        return {"sku_query": query, "signal": "monitor", "reason": "empty query"}

    row = db.execute(
        """
        SELECT product_id, store, store_name, name, price, currency
        FROM price_snapshots
        WHERE price > 0 AND LOWER(name) LIKE LOWER(?)
        ORDER BY price ASC LIMIT 1
        """,
        (f"%{query}%",),
    ).fetchone()

    substitute = None
    if include_substitutes:
        sub = find_substitutes(db, query=query, country=country, limit=1)
        subs = sub.get("substitutes") or []
        if subs:
            substitute = subs[0]

    procurement = compute_procurement_signal(db, country=country)
    base_signal = procurement.get("signal") or "monitor"
    reason = procurement.get("signal_reason") or "market conditions"

    spread_pct = None
    if row and substitute and substitute.get("price"):
        moat_price = float(row["price"])
        sub_price = float(substitute["price"])
        if moat_price > 0:
            spread_pct = round((moat_price - sub_price) / moat_price * 100, 1)

    return {
        "sku_query": query,
        "signal": base_signal,
        "reason": reason,
        "best_match": dict(row) if row else None,
        "substitute": substitute,
        "spread_pct": spread_pct,
    }


def run_procurement_bulk(
    db,
    *,
    country: str = "PE",
    lines: list[dict[str, Any]],
    organization_id: str | None = None,
    include_substitutes: bool = True,
    output: str = "json",
) -> dict[str, Any]:
    """Aggregate procurement signals for a list of SKU queries."""
    country = (country or "PE").strip().upper()
    if not lines:
        return {
            "status": "error",
            "error": "lines required",
            "country": country,
            "organization_id": organization_id,
        }

    per_line = [
        _line_signal(
            db,
            country=country,
            sku_query=str(line.get("sku_query") or line.get("name") or ""),
            include_substitutes=include_substitutes,
        )
        for line in lines
    ]

    counts = {"buy_now": 0, "wait": 0, "monitor": 0}
    for entry in per_line:
        sig = entry.get("signal") or "monitor"
        counts[sig] = counts.get(sig, 0) + 1

    if counts["wait"] > counts["buy_now"]:
        aggregate = "wait"
    elif counts["buy_now"] >= max(1, len(per_line) // 2):
        aggregate = "buy_now"
    else:
        aggregate = "monitor"

    result: dict[str, Any] = {
        "status": "ok",
        "country": country,
        "organization_id": organization_id,
        "aggregate_signal": aggregate,
        "lines": per_line,
        "summary": counts,
        "output": output,
    }
    if output == "csv_url":
        result["csv_url"] = None
        result["note"] = "CSV export requires backend storage hook; use output=json for v1."
    return result
