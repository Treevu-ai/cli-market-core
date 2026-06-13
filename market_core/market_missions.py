"""Deterministic investigate mission — orchestrates search, compare, and intel."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from .market_core import STORES, api

RequestFn = Callable[[str, str, dict | None], dict]

DEFAULT_SEARCH_LIMIT = 20
DEFAULT_COMPARE_LIMIT = 10


def _section(
    name: str,
    data: dict | None = None,
    *,
    error: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    if error:
        return {"name": name, "status": "unavailable", "error": error}
    return {"name": name, "status": status or "ok", "data": data}


def _store_label(store_key: str) -> tuple[str, str]:
    cfg = STORES.get(store_key, {})
    return store_key, str(cfg.get("name") or store_key)


def _compute_spread_insights(compare_data: dict) -> dict[str, Any]:
    comparison = compare_data.get("comparison") or []
    if not comparison:
        return {}

    store_prices: dict[str, list[float]] = {}
    for item in comparison:
        for store, price in (item.get("prices") or {}).items():
            if price and float(price) > 0:
                store_prices.setdefault(store, []).append(float(price))

    if not store_prices:
        return {}

    store_means = {store: sum(prices) / len(prices) for store, prices in store_prices.items()}
    leader_store = min(store_means, key=store_means.get)
    leader_key, leader_name = _store_label(leader_store)
    leader_cfg = STORES.get(leader_store, {})

    insights: dict[str, Any] = {
        "retailers_scanned": compare_data.get("stores_compared") or len(store_means),
        "skus_matched": len(comparison),
        "leader": {
            "store": leader_key,
            "store_name": leader_name,
            "price": round(store_means[leader_store], 2),
            "currency": leader_cfg.get("currency", "PEN"),
        },
    }

    if len(store_means) < 2:
        insights["spread_pct_max"] = 0.0
        return insights

    mean_all = sum(store_means.values()) / len(store_means)
    laggard_store = max(store_means, key=store_means.get)
    laggard_key, laggard_name = _store_label(laggard_store)
    laggard_cfg = STORES.get(laggard_store, {})

    spread_pct = 0.0
    laggard_pct_vs_mean = 0.0
    if mean_all > 0:
        spread_pct = round((store_means[laggard_store] - store_means[leader_store]) / mean_all * 100, 1)
        laggard_pct_vs_mean = round((store_means[laggard_store] - mean_all) / mean_all * 100, 1)

    insights["laggard"] = {
        "store": laggard_key,
        "store_name": laggard_name,
        "pct_vs_mean": laggard_pct_vs_mean,
        "price": round(store_means[laggard_store], 2),
        "currency": laggard_cfg.get("currency", "PEN"),
    }
    insights["spread_pct_max"] = spread_pct
    return insights


def _match_inflation_line(inflation_data: dict, query: str) -> dict[str, Any] | None:
    query_l = query.lower().strip()
    for item in inflation_data.get("items") or []:
        for field in ("line", "line_key", "product"):
            val = str(item.get(field) or "").lower()
            if val and (query_l in val or val in query_l):
                return {
                    "line": item.get("line") or item.get("line_key") or item.get("product"),
                    "delta_pct": float(item.get("delta_pct") or 0),
                    "days": inflation_data.get("days") or 30,
                    "currency": item.get("currency"),
                }
    return None


def _build_recommendations(insights: dict[str, Any]) -> list[dict[str, str]]:
    recs: list[dict[str, str]] = []
    spread = float(insights.get("spread_pct_max") or 0)
    laggard = insights.get("laggard") or {}
    leader = insights.get("leader") or {}

    if spread >= 25 and laggard.get("store_name"):
        recs.append(
            {
                "rule": "spread_high",
                "text": f"Monitor {laggard['store_name']} if spread stays above 25%.",
            }
        )
    if leader.get("store_name"):
        recs.append(
            {
                "rule": "baseline_leader",
                "text": f"Prefer {leader['store_name']} for basket baseline.",
            }
        )

    inflation = insights.get("inflation_line") or {}
    delta = float(inflation.get("delta_pct") or 0)
    if inflation and delta > 5:
        line = inflation.get("line") or "category"
        days = inflation.get("days") or 30
        recs.append(
            {
                "rule": "inflation_elevated",
                "text": f"Track {line} — inflation {delta:+.1f}% over {days}d.",
            }
        )
    return recs


def run_investigate(
    query: str,
    country: str = "PE",
    *,
    line: str | None = None,
    search_limit: int = DEFAULT_SEARCH_LIMIT,
    compare_limit: int = DEFAULT_COMPARE_LIMIT,
    include_intel: bool = True,
    intel_days: int = 30,
    request_fn: RequestFn | None = None,
) -> dict[str, Any]:
    """Run investigate mission: search + compare + optional intel inflation."""
    query = (query or "").strip()
    country = (country or "PE").strip().upper()
    if not query:
        return {
            "mission": "investigate",
            "query": query,
            "country": country,
            "status": "error",
            "error": "query required",
            "sections": {},
            "insights": {},
            "recommendations": [],
        }

    fn = request_fn or api
    sections: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    search_params: dict[str, Any] = {
        "query": query,
        "limit": search_limit,
        "page": 1,
        "country": country,
    }
    compare_params: dict[str, Any] = {"query": query, "limit": compare_limit, "country": country}
    if line:
        search_params["line"] = line
        compare_params["line"] = line

    tasks: dict[str, tuple[str, str, dict | None]] = {
        "search": ("POST", "/products/search", search_params),
        "compare": ("POST", "/products/compare", compare_params),
    }
    if include_intel:
        qs = f"country={country}&days={intel_days}"
        tasks["inflation"] = ("GET", f"/v1/intel/inflation?{qs}", None)

    results: dict[str, dict] = {}

    def _run_step(name: str, method: str, path: str, body: dict | None) -> tuple[str, dict]:
        try:
            return name, fn(method, path, body)
        except Exception as exc:
            return name, {"error": str(exc)}

    max_workers = max(1, min(len(tasks), int(os.getenv("MARKET_MISSION_WORKERS", "3"))))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_run_step, name, method, path, body)
            for name, (method, path, body) in tasks.items()
        ]
        for fut in as_completed(futures):
            name, out = fut.result()
            results[name] = out

    search_data = results.get("search") or {}
    if search_data.get("error"):
        sections["search"] = _section("search", error=str(search_data["error"]))
        errors.append(f"search: {search_data['error']}")
    else:
        sections["search"] = _section("search", search_data)

    compare_data = results.get("compare") or {}
    if compare_data.get("error"):
        sections["compare"] = _section("compare", error=str(compare_data["error"]))
        errors.append(f"compare: {compare_data['error']}")
    else:
        sections["compare"] = _section("compare", compare_data)

    inflation_data = results.get("inflation") or {}
    if include_intel:
        if inflation_data.get("error"):
            sections["inflation"] = _section("inflation", error=str(inflation_data["error"]))
        else:
            sections["inflation"] = _section("inflation", inflation_data)

    insights = _compute_spread_insights(compare_data if not compare_data.get("error") else {})
    if not insights.get("skus_matched") and search_data and not search_data.get("error"):
        insights["skus_matched"] = search_data.get("total") or len(search_data.get("results") or [])
    if not insights.get("retailers_scanned") and search_data and not search_data.get("error"):
        stores = {row.get("store") for row in (search_data.get("results") or []) if row.get("store")}
        insights["retailers_scanned"] = len(stores)

    if include_intel and inflation_data and not inflation_data.get("error"):
        matched = _match_inflation_line(inflation_data, query)
        if matched:
            insights["inflation_line"] = matched

    recommendations = _build_recommendations(insights)

    status = "complete"
    if errors:
        has_data = any(section.get("status") == "ok" for section in sections.values())
        status = "partial" if has_data else "error"

    payload: dict[str, Any] = {
        "mission": "investigate",
        "query": query,
        "country": country,
        "status": status,
        "sections": sections,
        "insights": insights,
        "recommendations": recommendations,
    }
    if errors:
        payload["errors"] = errors
    return payload
