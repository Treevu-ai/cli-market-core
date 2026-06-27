"""Intel products — business-question-specific intelligence reports.

Three product functions that answer distinct business questions using the
existing data-moat indicators. Each returns a structured report with signal
interpretation suitable for API endpoints and MCP tool responses.
"""

from __future__ import annotations

from typing import Any

from .market_indicators import (
    compute_basket_stress,
    compute_internal_inflation_avg,
    compute_price_dispersion,
    compute_promo_intensity,
    compute_search_momentum,
    compute_staple_price_momentum,
    get_latest_values,
)
from .market_regulatory import regulatory_headlines

_AFFORDABILITY_DISCLAIMER_ES = (
    "Precios observados en tiendas online indexadas; no reemplaza el IPC INEI ni encuestas de hogares."
)

_MINIMUM_WAGE_LOCAL: dict[str, float] = {
    "PE": 1130.0,
    "AR": 234000.0,
    "MX": 7468.0,
    "BR": 1518.0,
    "CO": 1423500.0,
    "CL": 500000.0,
}

_CURRENCY_BY_COUNTRY: dict[str, str] = {
    "PE": "PEN",
    "AR": "ARS",
    "MX": "MXN",
    "BR": "BRL",
    "CO": "COP",
    "CL": "CLP",
}


def compute_price_risk(
    db,
    *,
    country: str | None = None,
    line: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """Price Risk Intelligence — which categories are becoming volatile?

    Combines price dispersion, promo intensity, basket stress, and staple
    momentum to produce a risk level with supporting signals.
    """
    dispersion = compute_price_dispersion(db, country, line)
    promo = compute_promo_intensity(db, country, line)
    basket_stress = compute_basket_stress(db, country)
    staple_mom = compute_staple_price_momentum(db, country, days)

    risk_level, risk_reason = _interpret_price_risk(dispersion, promo, staple_mom)

    return {
        "question": "Which categories are becoming volatile?",
        "country": country,
        "line": line,
        "days": days,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "signals": {
            "price_dispersion_pct": dispersion,
            "promo_intensity_pct": promo,
            "basket_stress_index": basket_stress,
            "staple_momentum_7d_pct": staple_mom,
        },
    }


def compute_inflation_report(
    db,
    *,
    country: str | None = None,
    line: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """Inflation Intelligence — where is price pressure increasing?

    Internal shelf-price inflation, staple momentum, and macro CPI gap.
    """
    inflation = compute_internal_inflation_avg(db, country, line, days)
    staple_mom_shelf = compute_staple_price_momentum(db, country, days, price_mode="shelf")
    staple_mom_list = compute_staple_price_momentum(db, country, days, price_mode="list")

    latest = get_latest_values(db, country=country, line=line, limit=50)
    latest_map = {v["key"]: v for v in latest}
    gap = latest_map.get("collector_vs_official_gap", {}).get("value")
    food_spread = latest_map.get("food_inflation_spread", {}).get("value")
    food_cpi = latest_map.get("food_cpi_yoy", {}).get("value")
    shelf_food_gap = latest_map.get("shelf_vs_food_cpi_gap", {}).get("value")
    if shelf_food_gap is None and staple_mom_list is not None and food_cpi is not None:
        shelf_food_gap = round(staple_mom_list - food_cpi, 2)

    pressure = _interpret_inflation_pressure(inflation, staple_mom_shelf, gap)

    return {
        "question": "Where is price pressure increasing?",
        "country": country,
        "line": line,
        "days": days,
        "pressure": pressure,
        "signals": {
            "internal_inflation_pct": inflation,
            "staple_momentum_pct": staple_mom_shelf,
            "staple_momentum_promo_adjusted_pct": staple_mom_list,
            "promo_adjustment_pp": (
                round(staple_mom_shelf - staple_mom_list, 2)
                if staple_mom_shelf is not None and staple_mom_list is not None
                else None
            ),
            "vs_official_cpi_gap_pp": gap,
            "food_inflation_spread": food_spread,
            "official_food_cpi_yoy_pct": food_cpi,
            "shelf_vs_official_food_cpi_gap_pp": shelf_food_gap,
        },
        "regulatory_headlines": regulatory_headlines(db, country, limit=3),
    }


def compute_price_deal_alerts(
    db,
    *,
    product: str,
    store: str | None = None,
    threshold_pct: float = 5.0,
    limit: int = 10,
) -> dict[str, Any]:
    """Products matching a query where shelf price is at least threshold_pct below list price."""
    product = (product or "").strip()
    if not product:
        raise ValueError("product required")

    threshold_frac = float(threshold_pct) / 100.0
    params: list[Any] = [f"%{product}%", threshold_frac]
    store_clause = ""
    if store:
        store_clause = "AND store = ?"
        params.append(store.strip())
    params.append(max(1, min(int(limit), 50)))

    rows = db.execute(
        f"""
        SELECT product_id, store, store_name, name, price, list_price, currency,
               url, queried_at,
               ROUND(((1 - price / NULLIF(list_price, 0)) * 100)::numeric, 1) AS discount_pct
        FROM price_snapshots
        WHERE name LIKE ?
          AND price > 0
          AND list_price > price
          AND list_price < 999999
          AND (1 - price / NULLIF(list_price, 0)) >= ?
          {store_clause}
        ORDER BY (1 - price / NULLIF(list_price, 0)) DESC
        LIMIT ?
        """,
        params,
    ).fetchall()

    results: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        results.append(
            {
                "product_id": row.get("product_id"),
                "store": row.get("store"),
                "store_name": row.get("store_name"),
                "name": row.get("name"),
                "price": float(row["price"]) if row.get("price") is not None else None,
                "list_price": float(row["list_price"]) if row.get("list_price") is not None else None,
                "currency": row.get("currency"),
                "url": row.get("url"),
                "queried_at": row.get("queried_at"),
                "discount_pct": float(row["discount_pct"]) if row.get("discount_pct") is not None else None,
            }
        )

    return {
        "product": product,
        "store": store,
        "threshold_pct": threshold_pct,
        "total": len(results),
        "results": results,
    }


def compute_affordability(
    db,
    *,
    country: str | None = None,
    line: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """Affordability OS — composite cost-of-living pressure from shelf + macro signals."""
    cc = (country or "PE").strip().upper()
    line = line or "supermercados"
    days = max(1, int(days or 30))

    basket_stress = compute_basket_stress(db, country=cc)
    inflation = compute_internal_inflation_avg(db, cc, line, days)
    staple_mom_shelf = compute_staple_price_momentum(db, cc, days, price_mode="shelf")
    staple_mom_list = compute_staple_price_momentum(db, cc, days, price_mode="list")
    try:
        dispersion = compute_price_dispersion(db, cc, line)
    except Exception:
        dispersion = None
    try:
        promo = compute_promo_intensity(db, cc, line)
    except Exception:
        promo = None
    search_mom = compute_search_momentum(db, cc)

    latest = get_latest_values(db, country=cc, line=line, limit=50)
    latest_map = {v["key"]: v for v in latest}
    gap = latest_map.get("collector_vs_official_gap", {}).get("value")
    food_spread = latest_map.get("food_inflation_spread", {}).get("value")
    food_cpi = latest_map.get("food_cpi_yoy", {}).get("value")
    shelf_food_gap = latest_map.get("shelf_vs_food_cpi_gap", {}).get("value")
    if shelf_food_gap is None and staple_mom_list is not None and food_cpi is not None:
        shelf_food_gap = round(staple_mom_list - food_cpi, 2)
    real_wage_ratio = latest_map.get("real_wage_basket_ratio", {}).get("value")
    gtrends = latest_map.get("gtrends_search_momentum", {}).get("value")

    canasta_min, canasta_stores, canasta_method = _canasta_min_total(db, cc)
    currency = _CURRENCY_BY_COUNTRY.get(cc, "USD")
    min_wage = _MINIMUM_WAGE_LOCAL.get(cc)

    canastas_per_wage = None
    if min_wage and canasta_min and canasta_min > 0:
        canastas_per_wage = round(min_wage / canasta_min, 2)

    score, band, band_es, data_quality = _affordability_score(
        basket_stress=basket_stress,
        real_wage_ratio=real_wage_ratio,
        gap_pp=gap,
    )
    headline = _affordability_headline(
        cc=cc,
        canasta_min=canasta_min,
        currency=currency,
        canastas_per_wage=canastas_per_wage,
        gap=gap,
        inflation=inflation,
    )

    return {
        "question": "How affordable is daily life this month?",
        "country": cc,
        "line": line,
        "days": days,
        "affordability_score": score,
        "affordability_band": band,
        "affordability_band_es": band_es,
        "score_data_quality": data_quality,
        "headline_es": headline,
        "components": {
            "canasta_min": canasta_min,
            "canasta_currency": currency,
            "canasta_stores_compared": canasta_stores,
            "canasta_method": canasta_method,
            "minimum_wage_local": min_wage,
            "canastas_per_minimum_wage": canastas_per_wage,
            "real_wage_basket_ratio": real_wage_ratio,
            "basket_stress_index": basket_stress,
            "internal_inflation_pct": inflation,
            "staple_momentum_7d_pct": staple_mom_shelf,
            "staple_momentum_promo_adjusted_7d_pct": staple_mom_list,
            "promo_adjustment_pp": (
                round(staple_mom_shelf - staple_mom_list, 2)
                if staple_mom_shelf is not None and staple_mom_list is not None
                else None
            ),
            "vs_official_cpi_gap_pp": gap,
            "food_inflation_spread": food_spread,
            "official_food_cpi_yoy_pct": food_cpi,
            "shelf_vs_official_food_cpi_gap_pp": shelf_food_gap,
        },
        "signals": {
            "price_dispersion_pct": dispersion,
            "promo_intensity_pct": promo,
            "search_momentum": search_mom,
            "gtrends_search_momentum": gtrends,
        },
        "regulatory_headlines": regulatory_headlines(db, cc, limit=3),
        "disclaimer_es": _AFFORDABILITY_DISCLAIMER_ES,
    }


def compute_procurement_signal(
    db,
    *,
    country: str | None = None,
    line: str | None = None,
) -> dict[str, Any]:
    """Procurement Intelligence — when should I buy?

    Basket stress (cost vs baseline), search momentum (demand pressure),
    and staple momentum signal whether to buy now or wait.
    """
    basket_stress = compute_basket_stress(db, country)
    search_mom = compute_search_momentum(db, country)
    staple_mom = compute_staple_price_momentum(db, country, days=7)

    signal, signal_reason = _interpret_procurement(basket_stress, search_mom, staple_mom)

    return {
        "question": "When should I buy?",
        "country": country,
        "line": line,
        "signal": signal,
        "signal_reason": signal_reason,
        "signals": {
            "basket_stress_index": basket_stress,
            "search_momentum": search_mom,
            "staple_momentum_7d_pct": staple_mom,
        },
    }


# ── Interpretation helpers ─────────────────────────────────────────────────────

def _interpret_price_risk(
    dispersion: float | None,
    promo: float | None,
    staple_mom: float | None,
) -> tuple[str, str]:
    reasons: list[str] = []
    score = 0

    if dispersion is not None:
        if dispersion > 50:
            score += 2
            reasons.append(f"high price dispersion ({dispersion:.0f}%)")
        elif dispersion > 25:
            score += 1
            reasons.append(f"elevated dispersion ({dispersion:.0f}%)")

    if promo is not None and promo > 30:
        score += 1
        reasons.append(f"high promo intensity ({promo:.0f}%)")

    if staple_mom is not None:
        if staple_mom > 5:
            score += 2
            reasons.append(f"staple prices rising fast ({staple_mom:+.1f}%)")
        elif staple_mom > 2:
            score += 1
            reasons.append(f"staple prices rising ({staple_mom:+.1f}%)")
        elif staple_mom < -3:
            score -= 1
            reasons.append(f"staple prices falling ({staple_mom:+.1f}%)")

    if score >= 3:
        return "high", ". ".join(reasons)
    if score >= 1:
        return "moderate", ". ".join(reasons) if reasons else "mixed signals"
    return "low", reasons[0] if reasons else "prices appear stable across tracked categories"


def _interpret_inflation_pressure(
    inflation: float | None,
    staple_mom: float | None,
    gap_pp: float | None,
) -> str:
    if inflation is not None and inflation > 10:
        return "rising_fast"
    if inflation is not None and inflation > 5:
        return "rising"
    if staple_mom is not None and staple_mom > 3:
        return "rising"
    if inflation is not None and inflation < -2:
        return "falling"
    if gap_pp is not None and gap_pp > 2:
        return "above_official"
    return "stable"


def _interpret_procurement(
    basket_stress: float | None,
    search_mom: float | None,
    staple_mom: float | None,
) -> tuple[str, str]:
    reasons: list[str] = []

    if basket_stress is not None:
        if basket_stress < 95:
            reasons.append(f"basket below baseline ({basket_stress:.0f})")
        elif basket_stress > 110:
            reasons.append(f"basket above baseline ({basket_stress:.0f})")

    if search_mom is not None and search_mom > 1.3:
        reasons.append("surging search demand")

    if staple_mom is not None:
        if staple_mom > 3:
            reasons.append(f"staples rising ({staple_mom:+.1f}%)")
        elif staple_mom < -2:
            reasons.append(f"staples falling ({staple_mom:+.1f}%)")

    if basket_stress is not None and basket_stress < 95 and staple_mom is not None and staple_mom < 1:
        return "buy_now", ". ".join(reasons) if reasons else "favorable conditions"
    if (basket_stress is not None and basket_stress > 110) or (staple_mom is not None and staple_mom > 5):
        return "wait", ". ".join(reasons) if reasons else "prices elevated — monitor for pullback"
    return "monitor", ". ".join(reasons) if reasons else "no strong signal either way — check back in 7 days"


def _canasta_min_total(db, country: str) -> tuple[float | None, int, str]:
    """Return (min canasta total, stores compared, method)."""
    from .golden_taxonomy import min_canasta_prices_golden
    from .market_core import STORES

    golden = min_canasta_prices_golden(db, country)
    if len(golden) >= 6:
        return round(sum(golden.values()), 2), len(golden), "golden_taxonomy"

    stores = [k for k, v in STORES.items() if v.get("country") == country and not v.get("disabled")]
    if not stores:
        return None, 0, "no_stores"

    from .market_basket import build_canasta_snapshot

    snap = build_canasta_snapshot(db, min_items=3, store_filter=set(stores))
    rows = snap.get("stores") or []
    if not rows:
        return None, 0, "snapshot_empty"
    best = min(rows, key=lambda r: float(r.get("total") or 999999))
    return float(best["total"]), len(rows), "canasta_snapshot"


def _affordability_score(
    *,
    basket_stress: float | None,
    real_wage_ratio: float | None,
    gap_pp: float | None,
) -> tuple[int, str, str, str]:
    stress = float(basket_stress or 100.0)
    # Only apply real_wage_ratio bonus when the indicator is actually populated in DB.
    # Default of 2.5 would add a spurious +12.5 upward bias and push scores to 100.
    ratio_bonus = (float(real_wage_ratio) * 5) if real_wage_ratio is not None else 0
    gap = max(0.0, float(gap_pp or 0))
    raw = 100 - stress + ratio_bonus - gap * 3
    score = int(max(0, min(100, round(raw))))
    data_quality = "low" if real_wage_ratio is None else "ok"
    if score >= 70:
        return score, "comfortable", "cómodo", data_quality
    if score >= 50:
        return score, "moderate", "moderado", data_quality
    if score >= 35:
        return score, "strained", "presionado", data_quality
    return score, "critical", "crítico", data_quality


def _affordability_headline(
    *,
    cc: str,
    canasta_min: float | None,
    currency: str,
    canastas_per_wage: float | None,
    gap: float | None,
    inflation: float | None,
) -> str:
    parts: list[str] = []
    if canasta_min is not None:
        parts.append(f"Canasta mínima observada ~{canasta_min:.0f} {currency} en {cc}")
    if canastas_per_wage is not None:
        parts.append(f"equivale a {canastas_per_wage:.1f} canastas por salario mínimo")
    if gap is not None:
        parts.append(f"gap vs IPC oficial {gap:+.1f} pp")
    elif inflation is not None:
        parts.append(f"inflación góndola {inflation:+.1f}%")
    return "; ".join(parts) if parts else f"Señales de affordability para {cc} con datos limitados en el moat."
