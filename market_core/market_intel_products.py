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
    staple_mom = compute_staple_price_momentum(db, country, days)

    latest = get_latest_values(db, country=country, line=line, limit=50)
    latest_map = {v["key"]: v for v in latest}
    gap = latest_map.get("collector_vs_official_gap", {}).get("value")
    food_spread = latest_map.get("food_inflation_spread", {}).get("value")

    pressure = _interpret_inflation_pressure(inflation, staple_mom, gap)

    return {
        "question": "Where is price pressure increasing?",
        "country": country,
        "line": line,
        "days": days,
        "pressure": pressure,
        "signals": {
            "internal_inflation_pct": inflation,
            "staple_momentum_pct": staple_mom,
            "vs_official_cpi_gap_pp": gap,
            "food_inflation_spread": food_spread,
        },
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
