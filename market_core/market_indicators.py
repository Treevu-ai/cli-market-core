"""Data moat indicators — catalog, external API fetchers, and computed scores.

Indicators are stored in ``indicator_definitions`` + ``indicator_values``.
Computed signals derive from ``price_snapshots``, ``price_history``, and
``search_queries``. External macro signals use public APIs with graceful fallback.
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .market_core import STORES, get_db
from .market_indicators_catalog import (
    COUNTRY_CURRENCY,
    ENRICHMENT_INDICATOR_KEYS,
    INDICATOR_DEFINITIONS,
    TIER2_INDICATOR_KEYS,  # noqa: F401 - re-exported for market_core.market_indicators consumers
    WB_COUNTRY,
)
from .response_envelope import compute_freshness_seconds, envelope
from .market_spread import CANASTA_ITEMS

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _since_iso(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=max(1, hours))).strftime("%Y-%m-%d %H:%M:%S")


def _stores_for_country(country: str | None) -> list[str]:
    if not country:
        return []
    cc = country.upper()
    return [k for k, v in STORES.items() if v.get("country") == cc and not v.get("disabled")]


def seed_indicator_definitions(db) -> None:
    for d in INDICATOR_DEFINITIONS:
        db.execute(
            """
            INSERT INTO indicator_definitions
                (key, name, category, source, unit, refresh_hours, description, formula)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                source=excluded.source,
                unit=excluded.unit,
                refresh_hours=excluded.refresh_hours,
                description=excluded.description,
                formula=excluded.formula
            """,
            (
                d["key"],
                d["name"],
                d["category"],
                d["source"],
                d.get("unit", ""),
                d.get("refresh_hours", 24),
                d.get("description", ""),
                d.get("formula", ""),
            ),
        )


def _upsert_indicator_value(
    db,
    *,
    indicator_key: str,
    scope: str,
    value: float | None,
    country: str | None = None,
    line: str | None = None,
    metadata: dict | None = None,
) -> None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return
    db.execute(
        """
        INSERT INTO indicator_values
            (indicator_key, scope, country, line, value, metadata_json, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            indicator_key,
            scope,
            country or "",
            line or "",
            round(float(value), 4),
            json.dumps(metadata or {}, ensure_ascii=False),
            _now_iso(),
        ),
    )


def _snapshot_filter(country: str | None, line: str | None) -> tuple[str, list]:
    q = " FROM price_snapshots WHERE price > 0"
    params: list = []
    stores = _stores_for_country(country)
    if stores:
        q += f" AND store IN ({','.join('?' * len(stores))})"
        params.extend(stores)
    if line:
        q += " AND line = ?"
        params.append(line)
    return q, params


def compute_promo_intensity(db, country: str | None = None, line: str | None = None) -> float | None:
    filt, params = _snapshot_filter(country, line)
    row = db.execute(
        f"SELECT COUNT(*) AS total, SUM(CASE WHEN discount IS NOT NULL AND discount > 0 THEN 1 ELSE 0 END) AS promos{filt}",
        params,
    ).fetchone()
    total = row["total"] or 0
    if total == 0:
        return None
    return round((row["promos"] or 0) / total * 100, 2)


def compute_price_dispersion(db, country: str | None = None, line: str | None = None) -> float | None:
    from .golden_taxonomy import canonical_price_buckets

    buckets = canonical_price_buckets(db, country, line)
    if not any(len(prices) >= 2 for prices in buckets.values()):
        filt, params = _snapshot_filter(country, line)
        rows = db.execute(
            f"SELECT LOWER(SUBSTR(name, 1, 40)) AS pname, price{filt} AND name IS NOT NULL",
            params,
        ).fetchall()
        buckets = {}
        for r in rows:
            if r["price"] and r["price"] > 0:
                buckets.setdefault(r["pname"], []).append(float(r["price"]))

    cvs: list[float] = []
    for prices in buckets.values():
        if len(prices) < 2:
            continue
        mean = sum(prices) / len(prices)
        if mean <= 0:
            continue
        var = sum((p - mean) ** 2 for p in prices) / len(prices)
        cvs.append(math.sqrt(var) / mean * 100)
    if not cvs:
        return None
    return round(sum(cvs) / len(cvs), 2)


def compute_moat_freshness(db, country: str | None = None, line: str | None = None) -> float | None:
    # Store-coverage freshness: what fraction of catalog stores have at least one
    # snapshot in the last 24h? This avoids penalising moat growth — the old
    # snapshot-count formula (fresh_rows / total_rows) decreases as the moat grows
    # even when the collector is healthy.
    since = _since_iso(24)
    stores_in_catalog = _stores_for_country(country) if country else list(STORES.keys())
    if not stores_in_catalog:
        return None
    filt, params = _snapshot_filter(country, line)
    rows = db.execute(
        f"SELECT COUNT(DISTINCT store) AS fresh_stores{filt} AND queried_at >= ?",
        [*params, since],
    ).fetchone()
    fresh = rows["fresh_stores"] or 0
    return round(fresh / len(stores_in_catalog) * 100, 2)


def compute_store_coverage(db, country: str | None = None, line: str | None = None) -> float | None:
    filt, params = _snapshot_filter(country, line)
    row = db.execute(f"SELECT COUNT(DISTINCT store) AS n{filt}", params).fetchone()
    n = row["n"] or 0
    return float(n) if n else None


def compute_search_momentum(db, country: str | None = None) -> float | None:
    now = datetime.now(timezone.utc)
    w7 = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    w14 = (now - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
    q_base = "SELECT COUNT(*) AS n FROM search_queries WHERE created_at >= ? AND created_at < ?"
    params_recent: list = [w7, _now_iso()]
    params_prev: list = [w14, w7]
    if country:
        q_base += " AND country = ?"
        params_recent.append(country.upper())
        params_prev.append(country.upper())
    recent = db.execute(q_base, params_recent).fetchone()["n"] or 0
    prev = db.execute(q_base, params_prev).fetchone()["n"] or 0
    if recent == 0 and prev == 0:
        return None
    return round(recent / max(prev, 1), 3)


def compute_basket_stress(db, country: str | None = None) -> float | None:
    """Minimum sum of cheapest canasta item per staple; index vs 30d ago if history exists."""
    from .golden_taxonomy import min_canasta_prices_golden

    stores = _stores_for_country(country)
    if not stores:
        return None

    golden = min_canasta_prices_golden(db, country)
    totals: list[float] = list(golden.values()) if len(golden) >= 3 else []

    if len(totals) < 3:
        placeholders = ",".join("?" * len(stores))
        totals = []
        for item in CANASTA_ITEMS:
            row = db.execute(
                f"""
                SELECT MIN(price) AS p FROM price_snapshots
                WHERE store IN ({placeholders}) AND price > 0
                  AND LOWER(name) LIKE ?
                """,
                [*stores, f"%{item}%"],
            ).fetchone()
            if row and row["p"]:
                totals.append(float(row["p"]))
    if len(totals) < 3:
        return None
    placeholders = ",".join("?" * len(stores))
    current = sum(totals)
    baseline = current
    try:
        since = _since_iso(24 * 30)
        hist_rows = db.execute(
            f"""
            SELECT SUM(min_p) AS total FROM (
                SELECT product_id, MIN(price) AS min_p
                FROM price_history
                WHERE store IN ({placeholders}) AND recorded_at >= ? AND price > 0
                GROUP BY product_id
            )
            """,
            [*stores, since],
        ).fetchone()
        if hist_rows and hist_rows["total"] and hist_rows["total"] > 0:
            baseline = float(hist_rows["total"])
    except Exception:
        pass
    return round(current / baseline * 100, 2) if baseline > 0 else None


def compute_internal_inflation_avg(db, country: str | None, line: str | None, days: int = 30) -> float | None:
    """Lightweight avg delta_pct from price_history pairs."""
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).strftime("%Y-%m-%d %H:%M:%S")
    stores = _stores_for_country(country)
    q = """
        SELECT product_id, store, price, recorded_at
        FROM price_history
        WHERE price > 0 AND recorded_at >= ?
    """
    params: list = [since]
    if stores:
        q += f" AND store IN ({','.join('?' * len(stores))})"
        params.extend(stores)
    if line:
        q += " AND store IN (SELECT store FROM price_snapshots WHERE line = ? LIMIT 1)"
        params.append(line)
    rows = db.execute(q, params).fetchall()
    series: dict[str, list[tuple[str, float]]] = {}
    for r in rows:
        k = f"{r['store']}|{r['product_id']}"
        series.setdefault(k, []).append((r["recorded_at"], float(r["price"])))
    deltas: list[float] = []
    for pts in series.values():
        if len(pts) < 2:
            continue
        pts.sort(key=lambda x: x[0])
        first, last = pts[0][1], pts[-1][1]
        if first > 0:
            deltas.append((last - first) / first * 100)
    if not deltas:
        return None
    return round(sum(deltas) / len(deltas), 2)


def compute_staple_price_momentum(db, country: str | None, days: int = 7) -> float | None:
    """Average % price change for canasta staples over the last N days."""
    from .golden_taxonomy import staple_price_deltas_golden

    golden_deltas = staple_price_deltas_golden(db, country, days=days)
    if golden_deltas:
        return round(sum(golden_deltas) / len(golden_deltas), 2)

    stores = _stores_for_country(country)
    if not stores:
        return None
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).strftime("%Y-%m-%d %H:%M:%S")
    ph = ",".join("?" * len(stores))
    like_clauses = " OR ".join(["LOWER(ps.name) LIKE ?"] * len(CANASTA_ITEMS))
    rows = db.execute(
        f"""
        SELECT ph.product_id, ph.store, ph.price, ph.recorded_at
        FROM price_history ph
        INNER JOIN price_snapshots ps ON ps.product_id = ph.product_id AND ps.store = ph.store
        WHERE ph.store IN ({ph}) AND ph.price > 0 AND ph.recorded_at >= ?
          AND ({like_clauses})
        """,
        [*stores, since, *[f"%{item}%" for item in CANASTA_ITEMS]],
    ).fetchall()
    series: dict[str, list[tuple[str, float]]] = {}
    for r in rows:
        k = f"{r['store']}|{r['product_id']}"
        series.setdefault(k, []).append((r["recorded_at"], float(r["price"])))
    deltas: list[float] = []
    for pts in series.values():
        if len(pts) < 2:
            continue
        pts.sort(key=lambda x: x[0])
        first, last = pts[0][1], pts[-1][1]
        if first > 0:
            deltas.append((last - first) / first * 100)
    if not deltas:
        return None
    return round(sum(deltas) / len(deltas), 2)


def fetch_fx_rates() -> dict[str, float]:
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get("https://open.er-api.com/v6/latest/USD")
            r.raise_for_status()
            data = r.json()
            if data.get("result") != "success":
                return {}
            rates = data.get("rates") or {}
            return {k: float(v) for k, v in rates.items() if v}
    except Exception as e:
        logger.warning("FX fetch failed: %s", e)
        return {}


def fetch_worldbank_indicator(country_code: str, indicator: str) -> float | None:
    wb = WB_COUNTRY.get(country_code.upper())
    if not wb:
        return None
    url = (
        f"https://api.worldbank.org/v2/country/{wb}/indicator/{indicator}"
        f"?format=json&per_page=5&date={(datetime.now().year - 5)}:{datetime.now().year}"
    )
    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.get(url)
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, list) or len(payload) < 2:
                return None
            for entry in payload[1]:
                val = entry.get("value")
                if val is not None:
                    return round(float(val), 3)
    except Exception as e:
        logger.warning("World Bank fetch failed (%s/%s): %s", country_code, indicator, e)
    return None


def refresh_internal_indicators(db, country: str | None = None, line: str | None = None) -> int:
    scope = f"{country or 'global'}:{line or 'all'}"
    writers = [
        ("promo_intensity", compute_promo_intensity(db, country, line)),
        ("price_dispersion", compute_price_dispersion(db, country, line)),
        ("moat_freshness", compute_moat_freshness(db, country, line)),
        ("store_coverage", compute_store_coverage(db, country, line)),
        ("search_momentum", compute_search_momentum(db, country)),
        ("basket_stress_index", compute_basket_stress(db, country)),
    ]
    n = 0
    for key, val in writers:
        if val is not None:
            _upsert_indicator_value(db, indicator_key=key, scope=scope, value=val, country=country, line=line)
            n += 1
    return n


def _indicator_is_stale(db, indicator_key: str, scope: str, refresh_hours: int) -> bool:
    row = db.execute(
        """
        SELECT recorded_at FROM indicator_values
        WHERE indicator_key = ? AND scope = ?
        ORDER BY recorded_at DESC LIMIT 1
        """,
        (indicator_key, scope),
    ).fetchone()
    if not row or not row["recorded_at"]:
        return True
    try:
        raw = str(row["recorded_at"]).replace("T", " ")[:19]
        recorded = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    age = datetime.now(timezone.utc) - recorded
    return age >= timedelta(hours=max(1, refresh_hours))


def _latest_indicator_value(db, indicator_key: str, scope: str) -> float | None:
    row = db.execute(
        """
        SELECT value FROM indicator_values
        WHERE indicator_key = ? AND scope = ?
        ORDER BY recorded_at DESC LIMIT 1
        """,
        (indicator_key, scope),
    ).fetchone()
    if row and row["value"] is not None:
        return float(row["value"])
    return None


def refresh_phase2_indicators(db, country: str | None = None) -> int:
    """FAO/CEPAL/DANE/Trends fetchers + PE/CO composites."""
    from .market_enrich_sources import (
        fetch_commodity_input_pressure,
        fetch_gtrends_search_momentum,
        fetch_ipp_food_co,
        fetch_real_wage_cepal_index,
    )

    cc = (country or "PE").upper()
    scope = f"{cc}:macro"
    enrich_scope = f"{cc}:enrichment"
    defs = {d["key"]: d for d in INDICATOR_DEFINITIONS}
    n = 0

    global_scope = "global:macro"
    comm_hours = defs.get("commodity_input_pressure", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "commodity_input_pressure", global_scope, comm_hours):
        pressure = fetch_commodity_input_pressure()
        if pressure is not None:
            _upsert_indicator_value(
                db,
                indicator_key="commodity_input_pressure",
                scope=global_scope,
                value=pressure,
                metadata={"source": "worldbank:AG.PRD.FOOD.XD"},
            )
            n += 1

    wage_hours = defs.get("real_wage_basket_ratio", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "real_wage_basket_ratio", scope, wage_hours):
        cepal_wage = fetch_real_wage_cepal_index(cc)
        basket = _latest_indicator_value(db, "basket_stress_index", f"{cc}:all") or compute_basket_stress(db, cc)
        if cepal_wage is not None and basket and basket > 0:
            ratio = round(cepal_wage / basket * 100, 2)
            _upsert_indicator_value(
                db,
                indicator_key="real_wage_basket_ratio",
                scope=scope,
                value=ratio,
                country=cc,
                metadata={"cepal_wage_index": cepal_wage, "basket_stress_index": basket},
            )
            n += 1

    if cc == "CO":
        ipp_hours = defs.get("ipp_food_co", {}).get("refresh_hours", 168)
        if _indicator_is_stale(db, "ipp_food_co", scope, ipp_hours):
            ipp = fetch_ipp_food_co()
            if ipp is not None:
                _upsert_indicator_value(
                    db,
                    indicator_key="ipp_food_co",
                    scope=scope,
                    value=ipp,
                    country="CO",
                    metadata={"proxy": "worldbank:FP.CPI.FOOD.ZG"},
                )
                n += 1

    gt_hours = defs.get("gtrends_search_momentum", {}).get("refresh_hours", 24)
    if _indicator_is_stale(db, "gtrends_search_momentum", enrich_scope, gt_hours):
        gt = fetch_gtrends_search_momentum(db, cc)
        if gt is not None:
            _upsert_indicator_value(
                db,
                indicator_key="gtrends_search_momentum",
                scope=enrich_scope,
                value=gt,
                country=cc,
                metadata={"source": "google-trends-rss"},
            )
            n += 1

    if cc == "PE":
        gap_hours = defs.get("bcrp_shelf_gap", {}).get("refresh_hours", 168)
        if _indicator_is_stale(db, "bcrp_shelf_gap", scope, gap_hours):
            bcrp = _latest_indicator_value(db, "bcrp_inflation_expectation_12m", scope)
            shelf = _latest_indicator_value(db, "staple_price_momentum", enrich_scope)
            if bcrp is not None and shelf is not None:
                _upsert_indicator_value(
                    db,
                    indicator_key="bcrp_shelf_gap",
                    scope=scope,
                    value=round(bcrp - shelf, 2),
                    country="PE",
                    metadata={"bcrp_inflation_expectation_12m": bcrp, "staple_price_momentum": shelf},
                )
                n += 1

    lag_hours = defs.get("commodity_transmission_lag", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "commodity_transmission_lag", enrich_scope, lag_hours):
        comm = _latest_indicator_value(db, "commodity_input_pressure", global_scope)
        shelf = _latest_indicator_value(db, "staple_price_momentum", enrich_scope)
        if comm is not None and shelf is not None:
            _upsert_indicator_value(
                db,
                indicator_key="commodity_transmission_lag",
                scope=enrich_scope,
                value=round(comm - shelf, 2),
                country=cc,
                metadata={"commodity_input_pressure": comm, "staple_price_momentum": shelf},
            )
            n += 1

    return n


def refresh_external_indicators(db, country: str | None = None) -> int:
    n = 0
    cc = (country or "PE").upper()
    scope = f"{cc}:macro"

    defs = {d["key"]: d for d in INDICATOR_DEFINITIONS}

    ccy = COUNTRY_CURRENCY.get(cc)
    fx_hours = defs.get("fx_usd_local", {}).get("refresh_hours", 24)
    if ccy and _indicator_is_stale(db, "fx_usd_local", scope, fx_hours):
        rates = fetch_fx_rates()
        if ccy in rates:
            _upsert_indicator_value(
                db,
                indicator_key="fx_usd_local",
                scope=scope,
                value=rates[ccy],
                country=cc,
                metadata={"currency": ccy, "base": "USD"},
            )
            n += 1

    cpi = None
    cpi_hours = defs.get("cpi_official_yoy", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "cpi_official_yoy", scope, cpi_hours):
        cpi = fetch_worldbank_indicator(cc, "FP.CPI.TOTL.ZG")
        if cpi is not None:
            _upsert_indicator_value(db, indicator_key="cpi_official_yoy", scope=scope, value=cpi, country=cc)
            n += 1
    else:
        row = db.execute(
            "SELECT value FROM indicator_values WHERE indicator_key = ? AND scope = ? ORDER BY recorded_at DESC LIMIT 1",
            ("cpi_official_yoy", scope),
        ).fetchone()
        if row and row["value"] is not None:
            cpi = float(row["value"])

    food_hours = defs.get("food_price_index", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "food_price_index", scope, food_hours):
        food = fetch_worldbank_indicator(cc, "AG.PRD.FOOD.XD")
        if food is not None:
            _upsert_indicator_value(db, indicator_key="food_price_index", scope=scope, value=food, country=cc)
            n += 1

    internal_inf = compute_internal_inflation_avg(db, cc, None, days=30)
    if internal_inf is not None and cpi is not None:
        _upsert_indicator_value(
            db,
            indicator_key="collector_vs_official_gap",
            scope=scope,
            value=round(internal_inf - cpi, 2),
            country=cc,
            metadata={"internal_inflation_pct": internal_inf, "official_cpi_pct": cpi},
        )
        n += 1

    from .market_enrich_sources import (
        fetch_bcrp_inflation_expectation_12m,
        fetch_bcrp_reference_rate,
        fetch_fuel_price_index_pe,
        fetch_fx_ars_blue_gap,
    )

    if cc == "AR":
        ar_scope = "AR:macro"
        gap_hours = defs.get("fx_ars_blue_gap", {}).get("refresh_hours", 12)
        if _indicator_is_stale(db, "fx_ars_blue_gap", ar_scope, gap_hours):
            gap = fetch_fx_ars_blue_gap()
            if gap is not None:
                _upsert_indicator_value(
                    db,
                    indicator_key="fx_ars_blue_gap",
                    scope=ar_scope,
                    value=gap,
                    country="AR",
                    metadata={"source": "bluelytics.com.ar"},
                )
                n += 1

    if cc == "PE":
        pe_scope = "PE:macro"
        bcrp_exp_hours = defs.get("bcrp_inflation_expectation_12m", {}).get("refresh_hours", 168)
        if _indicator_is_stale(db, "bcrp_inflation_expectation_12m", pe_scope, bcrp_exp_hours):
            exp = fetch_bcrp_inflation_expectation_12m()
            if exp is not None:
                _upsert_indicator_value(
                    db,
                    indicator_key="bcrp_inflation_expectation_12m",
                    scope=pe_scope,
                    value=exp,
                    country="PE",
                    metadata={"series": "PD12912AM"},
                )
                n += 1
        bcrp_rate_hours = defs.get("bcrp_reference_rate", {}).get("refresh_hours", 168)
        if _indicator_is_stale(db, "bcrp_reference_rate", pe_scope, bcrp_rate_hours):
            rate = fetch_bcrp_reference_rate()
            if rate is not None:
                _upsert_indicator_value(
                    db,
                    indicator_key="bcrp_reference_rate",
                    scope=pe_scope,
                    value=rate,
                    country="PE",
                    metadata={"series": "PD04722MM"},
                )
                n += 1
        fuel_scope = "PE:logistics"
        fuel_hours = defs.get("fuel_price_index_pe", {}).get("refresh_hours", 168)
        if _indicator_is_stale(db, "fuel_price_index_pe", fuel_scope, fuel_hours):
            fuel = fetch_fuel_price_index_pe()
            if fuel is not None:
                _upsert_indicator_value(
                    db,
                    indicator_key="fuel_price_index_pe",
                    scope=fuel_scope,
                    value=fuel,
                    country="PE",
                    metadata={"unit": "PEN/L proxy"},
                )
                n += 1

    return n


def refresh_enrichment_indicators(db, country: str | None = None) -> int:
    """Open Food Facts sample + Wikimedia + Open-Meteo + food CPI."""
    if os.getenv("ENRICHMENT_AUTO_REFRESH", "1").strip() in ("0", "false", "no"):
        return 0

    from .market_enrich_sources import (
        fetch_food_cpi_yoy,
        fetch_weather_logistics_stress,
        fetch_wiki_demand_momentum,
        fetch_wiki_staple_momentum,
        sample_off_coverage,
    )

    cc = (country or "PE").upper()
    scope = f"{cc}:enrichment"
    defs = {d["key"]: d for d in INDICATOR_DEFINITIONS}
    n = 0

    off_hours = defs.get("off_match_rate", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "off_match_rate", scope, off_hours):
        off = sample_off_coverage(db, cc)
        if off.get("match_rate_pct") is not None:
            _upsert_indicator_value(
                db,
                indicator_key="off_match_rate",
                scope=scope,
                value=off["match_rate_pct"],
                country=cc,
                metadata={"sampled": off["sampled"], "matched": off["matched"], "samples": off.get("samples", [])},
            )
            n += 1
        if off.get("nutriscore_ab_pct") is not None:
            _upsert_indicator_value(
                db,
                indicator_key="off_nutriscore_ab_pct",
                scope=scope,
                value=off["nutriscore_ab_pct"],
                country=cc,
            )
            n += 1
        if off.get("nova_avg") is not None:
            _upsert_indicator_value(
                db,
                indicator_key="off_nova_avg",
                scope=scope,
                value=off["nova_avg"],
                country=cc,
            )
            n += 1
        if off.get("ultra_processed_pct") is not None:
            _upsert_indicator_value(
                db,
                indicator_key="off_ultra_processed_pct",
                scope=scope,
                value=off["ultra_processed_pct"],
                country=cc,
            )
            n += 1
        if off.get("ecoscore_avg") is not None:
            _upsert_indicator_value(
                db,
                indicator_key="off_ecoscore_avg",
                scope=scope,
                value=off["ecoscore_avg"],
                country=cc,
            )
            n += 1

    wiki_hours = defs.get("wiki_demand_momentum", {}).get("refresh_hours", 24)
    if _indicator_is_stale(db, "wiki_demand_momentum", scope, wiki_hours):
        wiki = fetch_wiki_demand_momentum(cc)
        if wiki is not None:
            _upsert_indicator_value(
                db, indicator_key="wiki_demand_momentum", scope=scope, value=wiki, country=cc
            )
            n += 1

    wiki_staple_hours = defs.get("wiki_staple_momentum", {}).get("refresh_hours", 24)
    if _indicator_is_stale(db, "wiki_staple_momentum", scope, wiki_staple_hours):
        wiki_staple = fetch_wiki_staple_momentum(cc)
        if wiki_staple is not None:
            _upsert_indicator_value(
                db, indicator_key="wiki_staple_momentum", scope=scope, value=wiki_staple, country=cc
            )
            n += 1

    staple_hours = defs.get("staple_price_momentum", {}).get("refresh_hours", 8)
    if _indicator_is_stale(db, "staple_price_momentum", scope, staple_hours):
        staple_mom = compute_staple_price_momentum(db, cc)
        if staple_mom is not None:
            _upsert_indicator_value(
                db,
                indicator_key="staple_price_momentum",
                scope=scope,
                value=staple_mom,
                country=cc,
                metadata={"window_days": 7, "staples": CANASTA_ITEMS[:5]},
            )
            n += 1

    weather_hours = defs.get("weather_logistics_stress", {}).get("refresh_hours", 12)
    if _indicator_is_stale(db, "weather_logistics_stress", scope, weather_hours):
        weather = fetch_weather_logistics_stress(cc)
        if weather is not None:
            _upsert_indicator_value(
                db, indicator_key="weather_logistics_stress", scope=scope, value=weather, country=cc
            )
            n += 1

    food_cpi_hours = defs.get("food_cpi_yoy", {}).get("refresh_hours", 168)
    food_cpi_val: float | None = None
    if _indicator_is_stale(db, "food_cpi_yoy", scope, food_cpi_hours):
        food_cpi = fetch_food_cpi_yoy(cc)
        if food_cpi is not None:
            food_cpi_val = food_cpi
            _upsert_indicator_value(
                db, indicator_key="food_cpi_yoy", scope=scope, value=food_cpi, country=cc
            )
            n += 1
    else:
        row = db.execute(
            """
            SELECT value FROM indicator_values
            WHERE indicator_key = 'food_cpi_yoy' AND scope = ?
            ORDER BY recorded_at DESC LIMIT 1
            """,
            (scope,),
        ).fetchone()
        if row and row["value"] is not None:
            food_cpi_val = float(row["value"])

    spread_hours = defs.get("food_inflation_spread", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "food_inflation_spread", scope, spread_hours) and food_cpi_val is not None:
        macro_scope = f"{cc}:macro"
        cpi_row = db.execute(
            """
            SELECT value FROM indicator_values
            WHERE indicator_key = 'cpi_official_yoy' AND scope = ?
            ORDER BY recorded_at DESC LIMIT 1
            """,
            (macro_scope,),
        ).fetchone()
        if cpi_row and cpi_row["value"] is not None:
            spread = round(food_cpi_val - float(cpi_row["value"]), 3)
            _upsert_indicator_value(
                db,
                indicator_key="food_inflation_spread",
                scope=scope,
                value=spread,
                country=cc,
                metadata={"food_cpi_yoy": food_cpi_val, "cpi_official_yoy": float(cpi_row["value"])},
            )
            n += 1

    n += _refresh_tier2_indicators(db, cc, scope, defs)

    if os.getenv("SUBCATEGORY_AUTO_REFRESH", "1").strip() not in ("0", "false", "no"):
        from .market_enrich_subcategory import refresh_subcategory_enrichment

        n += refresh_subcategory_enrichment(db, cc, _upsert_indicator_value)

    return n


def _refresh_tier2_indicators(db, cc: str, scope: str, defs: dict) -> int:
    if os.getenv("TIER2_AUTO_REFRESH", "1").strip() in ("0", "false", "no"):
        return 0

    from .market_enrich_sources import (
        fetch_bcb_food_inflation_mom,
        fetch_bcb_headline_inflation_mom,
        fetch_eurostat_food_hicp_yoy,
        fetch_eurostat_headline_hicp_yoy,
        fetch_imf_epi_inflation_yoy,
        fetch_imf_gdp_growth_yoy,
        fetch_imf_inflation_yoy,
        fetch_wb_gdp_growth_yoy,
        fetch_wb_unemployment_rate,
    )

    n = 0
    imf_val: float | None = None

    imf_hours = defs.get("imf_inflation_yoy", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "imf_inflation_yoy", scope, imf_hours):
        imf = fetch_imf_inflation_yoy(cc)
        if imf is not None:
            imf_val = imf
            _upsert_indicator_value(
                db, indicator_key="imf_inflation_yoy", scope=scope, value=imf, country=cc
            )
            n += 1
    else:
        row = db.execute(
            "SELECT value FROM indicator_values WHERE indicator_key = 'imf_inflation_yoy' AND scope = ? ORDER BY recorded_at DESC LIMIT 1",
            (scope,),
        ).fetchone()
        if row and row["value"] is not None:
            imf_val = float(row["value"])

    euro_hours = defs.get("eurostat_food_hicp_yoy", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "eurostat_food_hicp_yoy", scope, euro_hours):
        euro = fetch_eurostat_food_hicp_yoy(cc)
        if euro is not None:
            _upsert_indicator_value(
                db, indicator_key="eurostat_food_hicp_yoy", scope=scope, value=euro, country=cc
            )
            n += 1

    bcb_hours = defs.get("bcb_food_inflation_mom", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "bcb_food_inflation_mom", scope, bcb_hours):
        bcb = fetch_bcb_food_inflation_mom(cc)
        if bcb is not None:
            _upsert_indicator_value(
                db, indicator_key="bcb_food_inflation_mom", scope=scope, value=bcb, country=cc
            )
            n += 1

    unemp_hours = defs.get("macro_unemployment_rate", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "macro_unemployment_rate", scope, unemp_hours):
        unemp = fetch_wb_unemployment_rate(cc)
        if unemp is not None:
            _upsert_indicator_value(
                db, indicator_key="macro_unemployment_rate", scope=scope, value=unemp, country=cc
            )
            n += 1

    gap_hours = defs.get("imf_wb_cpi_gap", {}).get("refresh_hours", 168)
    if _indicator_is_stale(db, "imf_wb_cpi_gap", scope, gap_hours) and imf_val is not None:
        macro_scope = f"{cc}:macro"
        cpi_row = db.execute(
            "SELECT value FROM indicator_values WHERE indicator_key = 'cpi_official_yoy' AND scope = ? ORDER BY recorded_at DESC LIMIT 1",
            (macro_scope,),
        ).fetchone()
        if cpi_row and cpi_row["value"] is not None:
            gap = round(imf_val - float(cpi_row["value"]), 3)
            _upsert_indicator_value(
                db,
                indicator_key="imf_wb_cpi_gap",
                scope=scope,
                value=gap,
                country=cc,
                metadata={"imf_inflation_yoy": imf_val, "cpi_official_yoy": float(cpi_row["value"])},
            )
            n += 1

    for key, fetcher in (
        ("imf_gdp_growth_yoy", fetch_imf_gdp_growth_yoy),
        ("imf_epi_inflation_yoy", fetch_imf_epi_inflation_yoy),
        ("wb_gdp_growth_yoy", fetch_wb_gdp_growth_yoy),
        ("eurostat_headline_hicp_yoy", fetch_eurostat_headline_hicp_yoy),
        ("bcb_headline_inflation_mom", fetch_bcb_headline_inflation_mom),
    ):
        hours = defs.get(key, {}).get("refresh_hours", 168)
        if _indicator_is_stale(db, key, scope, hours):
            val = fetcher(cc)
            if val is not None:
                _upsert_indicator_value(db, indicator_key=key, scope=scope, value=val, country=cc)
                n += 1

    return n


def refresh_enrichment_only(country: str | None = None) -> dict[str, Any]:
    """Refresh only enrichment indicators (OFF, Wiki, weather, food CPI)."""
    db = get_db()
    seed_indicator_definitions(db)
    written = refresh_enrichment_indicators(db, country)
    db.commit()
    db.close()
    return {"status": "ok", "enrichment_written": written, "country": country}


def refresh_indicators(country: str | None = None, line: str | None = None) -> dict[str, int]:
    db = get_db()
    seed_indicator_definitions(db)
    internal = refresh_internal_indicators(db, country, line)
    external = refresh_external_indicators(db, country)
    enrichment = refresh_enrichment_indicators(db, country)
    phase2 = refresh_phase2_indicators(db, country)
    db.commit()
    db.close()
    return {
        "internal_written": internal,
        "external_written": external,
        "enrichment_written": enrichment,
        "phase2_written": phase2,
    }


def refresh_after_collection(countries: list[str] | None = None) -> dict[str, Any]:
    """Run after each collector cycle. Enabled by default (INDICATOR_AUTO_REFRESH=1)."""
    if os.getenv("INDICATOR_AUTO_REFRESH", "1").strip() in ("0", "false", "no"):
        return {"skipped": True, "reason": "INDICATOR_AUTO_REFRESH disabled"}

    if not countries:
        countries = sorted(
            {v["country"] for v in STORES.values() if not v.get("disabled") and v.get("country")}
        )

    summary: dict[str, Any] = {
        "skipped": False,
        "countries": countries,
        "per_country": {},
        "internal_written": 0,
        "external_written": 0,
        "enrichment_written": 0,
        "phase2_written": 0,
    }
    for cc in countries:
        result = refresh_indicators(country=cc, line=None)
        summary["per_country"][cc] = result
        summary["internal_written"] += result["internal_written"]
        summary["external_written"] += result["external_written"]
        summary["enrichment_written"] += result.get("enrichment_written", 0)
        summary["phase2_written"] += result.get("phase2_written", 0)
    return summary


def get_indicator_catalog() -> list[dict]:
    return list(INDICATOR_DEFINITIONS)


def get_latest_values(
    db,
    indicator_key: str | None = None,
    country: str | None = None,
    line: str | None = None,
    limit: int = 50,
    enveloped: bool = False,
) -> list[dict]:
    q = """
        SELECT iv.indicator_key, iv.scope, iv.country, iv.line, iv.value,
               iv.metadata_json, iv.recorded_at, id.name, id.category, id.unit, id.source
        FROM indicator_values iv
        LEFT JOIN indicator_definitions id ON id.key = iv.indicator_key
        WHERE 1=1
    """
    params: list = []
    if indicator_key:
        q += " AND iv.indicator_key = ?"
        params.append(indicator_key)
    if country:
        q += " AND (iv.country = ? OR iv.country = '')"
        params.append(country.upper())
    if line:
        q += " AND (iv.line = ? OR iv.line = '')"
        params.append(line)
    q += " ORDER BY iv.recorded_at DESC LIMIT ?"
    params.append(limit)
    rows = db.execute(q, params).fetchall()
    out: list[dict] = []
    seen: set[str] = set()
    for r in rows:
        dedupe = f"{r['indicator_key']}|{r['scope']}|{r['country']}|{r['line']}"
        if dedupe in seen:
            continue
        seen.add(dedupe)
        meta = {}
        try:
            meta = json.loads(r["metadata_json"] or "{}")
        except json.JSONDecodeError:
            pass
        out.append(
            {
                "key": r["indicator_key"],
                "name": r["name"],
                "category": r["category"],
                "source": r["source"],
                "unit": r["unit"],
                "scope": r["scope"],
                "country": r["country"] or None,
                "line": r["line"] or None,
                "value": r["value"],
                "metadata": meta,
                "recorded_at": r["recorded_at"],
            }
        )
    if not enveloped:
        return out
    return envelope(
        data=out,
        freshness_seconds=compute_freshness_seconds(out, timestamp_field="recorded_at"),
        confidence="ok",
        extra_meta={"count": len(out)},
    )


def _scores_from_latest(latest: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build composite scores from a latest-values map (read-only)."""
    promo = latest.get("promo_intensity", {}).get("value")
    dispersion = latest.get("price_dispersion", {}).get("value")
    freshness = latest.get("moat_freshness", {}).get("value")
    basket = latest.get("basket_stress_index", {}).get("value")
    gap = latest.get("collector_vs_official_gap", {}).get("value")
    off_match = latest.get("off_match_rate", {}).get("value")
    off_nova = latest.get("off_nova_avg", {}).get("value")
    off_nutri_ab = latest.get("off_nutriscore_ab_pct", {}).get("value")
    off_ultra = latest.get("off_ultra_processed_pct", {}).get("value")
    off_eco = latest.get("off_ecoscore_avg", {}).get("value")
    wiki = latest.get("wiki_demand_momentum", {}).get("value")
    wiki_staple = latest.get("wiki_staple_momentum", {}).get("value")
    weather = latest.get("weather_logistics_stress", {}).get("value")
    food_spread = latest.get("food_inflation_spread", {}).get("value")
    staple_mom = latest.get("staple_price_momentum", {}).get("value")
    imf_gap = latest.get("imf_wb_cpi_gap", {}).get("value")
    unemployment = latest.get("macro_unemployment_rate", {}).get("value")
    imf_gdp = latest.get("imf_gdp_growth_yoy", {}).get("value")
    commodity_pressure = latest.get("commodity_input_pressure", {}).get("value")
    wage_basket = latest.get("real_wage_basket_ratio", {}).get("value")
    ipp_food = latest.get("ipp_food_co", {}).get("value")
    gtrends = latest.get("gtrends_search_momentum", {}).get("value")
    bcrp_gap = latest.get("bcrp_shelf_gap", {}).get("value")
    transmission_lag = latest.get("commodity_transmission_lag", {}).get("value")

    scores: dict[str, Any] = {}

    if promo is not None:
        scores["retail_aggression"] = {
            "score": round(min(promo * 2, 100), 1),
            "label": "high" if promo > 25 else "moderate" if promo > 10 else "low",
            "input": {"promo_intensity_pct": promo},
        }

    if dispersion is not None:
        scores["price_fairness"] = {
            "score": round(max(0, 100 - dispersion), 1),
            "label": "competitive" if dispersion > 15 else "stable",
            "input": {"price_dispersion_pct": dispersion},
        }

    if basket is not None:
        scores["basket_stress"] = {
            "score": round(basket, 2),
            "label": "elevated" if basket > 1.05 else "normal" if basket > 0.95 else "eased",
            "input": {"basket_stress_index": basket},
        }

    if freshness is not None:
        scores["data_confidence"] = {
            "score": round(freshness, 1),
            "label": "fresh" if freshness >= 80 else "stale",
            "input": {"moat_freshness_pct": freshness},
        }

    if gap is not None:
        # Log-scale penalty so hyperinflationary economies (AR: gap≈160pp) get
        # a non-zero score that's still visually distinct from null/no-data.
        _align_score = round(max(1.0, 100 - math.log1p(abs(gap)) * 20), 1) if abs(gap) > 0 else 100.0
        scores["macro_alignment"] = {
            "score": _align_score,
            "label": "aligned" if abs(gap) < 5 else "divergent",
            "input": {"collector_vs_official_gap_pp": gap},
        }

    if off_match is not None:
        nova_penalty = max(0, (off_nova or 3) - 2) * 15 if off_nova is not None else 0
        scores["product_intelligence"] = {
            "score": round(max(0, min(100, off_match - nova_penalty)), 1),
            "label": "rich" if off_match > 50 else "sparse",
            "input": {"off_match_rate_pct": off_match, "off_nova_avg": off_nova},
        }

    if wiki is not None:
        scores["demand_outlook"] = {
            "score": round(min(wiki * 50, 100), 1),
            "label": "rising" if wiki > 1.1 else "cooling" if wiki < 0.9 else "stable",
            "input": {"wiki_demand_momentum": wiki},
        }

    if weather is not None:
        scores["logistics_risk"] = {
            "score": round(weather, 1),
            "label": "elevated" if weather > 40 else "normal",
            "input": {"weather_logistics_stress": weather},
        }

    if food_spread is not None:
        scores["food_premium"] = {
            "score": round(max(0, min(100, 50 + food_spread * 5)), 1),
            "label": "elevated" if food_spread > 2 else "normal" if food_spread > 0 else "eased",
            "input": {"food_inflation_spread_pp": food_spread},
        }

    if off_nutri_ab is not None or off_ultra is not None or off_eco is not None:
        nutri_part = off_nutri_ab or 0
        ultra_penalty = (off_ultra or 0) * 0.4
        eco_part = ((off_eco or 3) / 5) * 100 if off_eco is not None else 50
        scores["nutrition_quality"] = {
            "score": round(max(0, min(100, nutri_part * 0.5 + eco_part * 0.3 - ultra_penalty + 10)), 1),
            "label": "healthy" if (off_nutri_ab or 0) > 40 and (off_ultra or 100) < 30 else "mixed",
            "input": {
                "off_nutriscore_ab_pct": off_nutri_ab,
                "off_ultra_processed_pct": off_ultra,
                "off_ecoscore_avg": off_eco,
            },
        }

    if wiki_staple is not None:
        scores["staple_demand"] = {
            "score": round(min(wiki_staple * 50, 100), 1),
            "label": "rising" if wiki_staple > 1.1 else "cooling" if wiki_staple < 0.9 else "stable",
            "input": {"wiki_staple_momentum": wiki_staple, "staple_price_momentum_pct": staple_mom},
        }

    if imf_gap is not None:
        # Log-scale so large IMF/WB divergences (AR) produce non-zero, readable scores.
        _valid_score = round(max(1.0, 100 - math.log1p(abs(imf_gap)) * 30), 1) if abs(imf_gap) > 0 else 100.0
        scores["macro_validation"] = {
            "score": _valid_score,
            "label": "consistent" if abs(imf_gap) < 2 else "divergent",
            "input": {"imf_wb_cpi_gap_pp": imf_gap},
        }

    if unemployment is not None:
        scores["labor_stress"] = {
            "score": round(min(unemployment * 8, 100), 1),
            "label": "elevated" if unemployment > 8 else "normal",
            "input": {"macro_unemployment_rate_pct": unemployment},
        }

    if imf_gdp is not None:
        scores["growth_outlook"] = {
            "score": round(max(0, min(100, 50 + imf_gdp * 5)), 1),
            "label": "expanding" if imf_gdp > 3 else "slow" if imf_gdp > 0 else "contracting",
            "input": {"imf_gdp_growth_yoy_pct": imf_gdp},
        }

    if commodity_pressure is not None:
        scores["commodity_pressure"] = {
            "score": round(min(100, max(0, 50 + commodity_pressure * 3)), 1),
            "label": "elevated" if commodity_pressure > 5 else "normal" if commodity_pressure > 0 else "eased",
            "input": {"commodity_input_pressure_pct": commodity_pressure},
        }

    if wage_basket is not None:
        scores["wage_affordability"] = {
            "score": round(min(100, max(0, wage_basket * 25)), 1),
            "label": "stretched" if wage_basket < 1.5 else "adequate" if wage_basket < 2.5 else "comfortable",
            "input": {"real_wage_basket_ratio": wage_basket},
        }

    if ipp_food is not None:
        scores["producer_pressure"] = {
            "score": round(min(100, max(0, 50 + ipp_food * 3)), 1),
            "label": "elevated" if ipp_food > 8 else "normal" if ipp_food > 2 else "eased",
            "input": {"ipp_food_co_pct": ipp_food},
        }

    if gtrends is not None:
        scores["search_momentum"] = {
            "score": round(min(gtrends * 50, 100), 1),
            "label": "rising" if gtrends > 1.1 else "cooling" if gtrends < 0.9 else "stable",
            "input": {"gtrends_search_momentum": gtrends},
        }

    if bcrp_gap is not None:
        scores["monetary_shelf_gap"] = {
            "score": round(max(0, 100 - abs(bcrp_gap) * 4), 1),
            "label": "divergent" if abs(bcrp_gap) > 5 else "aligned",
            "input": {"bcrp_shelf_gap_pp": bcrp_gap},
        }

    if transmission_lag is not None:
        scores["commodity_transmission"] = {
            "score": round(max(0, min(100, 50 - transmission_lag * 2)), 1),
            "label": "building" if transmission_lag > 3 else "caught_up" if transmission_lag < -2 else "neutral",
            "input": {"commodity_transmission_lag_pp": transmission_lag},
        }

    return scores


def get_scores(db, country: str | None = None, line: str | None = None) -> dict[str, Any]:
    """Read-only composite scores from latest indicator values (no refresh)."""
    seed_indicator_definitions(db)
    latest_list = get_latest_values(db, country=country, line=line, limit=200)
    latest = {v["key"]: v for v in latest_list}
    return {
        "country": country,
        "line": line,
        "computed_at": _now_iso(),
        "scores": _scores_from_latest(latest),
        "disclaimer": "Composite scores combine internal moat signals with public macro APIs where available.",
    }


def _brief_headline(
    *,
    inflation_pct: float | None,
    gap_pp: float | None,
    days: int,
    country: str | None,
    line: str | None,
) -> str:
    parts: list[str] = []
    if inflation_pct is not None:
        sign = "+" if inflation_pct >= 0 else ""
        parts.append(f"Shelf inflation {sign}{inflation_pct}% over {days}d")
    if gap_pp is not None:
        direction = "above" if gap_pp > 0 else "below"
        parts.append(f"{abs(gap_pp):.1f} pp {direction} official CPI")
    if parts:
        return "; ".join(parts)
    scope = country or "LATAM"
    if line:
        scope = f"{scope} / {line}"
    return f"Intelligence brief for {scope} — moat signals from shelf prices"


def _brief_sources(latest_list: list[dict]) -> list[str]:
    found: set[str] = set()
    for v in latest_list:
        src = (v.get("source") or "").lower()
        key = (v.get("key") or "").lower()
        if "price" in src or "internal" in src:
            found.add("price_history")
        if "worldbank" in src:
            found.add("worldbank")
        if "openfoodfacts" in src or key.startswith("off_"):
            found.add("openfoodfacts")
        if "wiki" in src or key.startswith("wiki"):
            found.add("wikimedia")
        if "open-meteo" in src or "weather" in key:
            found.add("openmeteo")
    return sorted(found) or ["price_history"]


def build_intel_brief(
    db,
    *,
    country: str | None = None,
    line: str | None = None,
    days: int = 7,
    include_catalog: bool = False,
) -> dict[str, Any]:
    """One-call intelligence narrative: shelf signals, macro gap, scores, confidence."""
    seed_indicator_definitions(db)
    latest_list = get_latest_values(db, country=country, line=line, limit=200)
    latest = {v["key"]: v for v in latest_list}

    inflation_pct = compute_internal_inflation_avg(db, country, line, days=days)
    staple_mom = compute_staple_price_momentum(db, country, days=days)

    def _val(key: str) -> Any:
        entry = latest.get(key)
        return entry.get("value") if entry else None

    shelf: dict[str, Any] = {}
    for key in ("promo_intensity", "price_dispersion", "basket_stress_index"):
        v = _val(key)
        if v is not None:
            shelf[key] = v
    if staple_mom is not None:
        shelf["staple_momentum_7d_pct"] = staple_mom
    if inflation_pct is not None:
        shelf["shelf_inflation_avg_pct"] = inflation_pct

    macro_gap: dict[str, Any] = {}
    gap = _val("collector_vs_official_gap")
    food_spread = _val("food_inflation_spread")
    if gap is not None:
        macro_gap["collector_vs_official_gap_pp"] = gap
    if food_spread is not None:
        macro_gap["food_inflation_spread_pp"] = food_spread

    confidence: dict[str, Any] = {}
    freshness = _val("moat_freshness")
    stores = _val("store_coverage")
    if freshness is not None:
        confidence["moat_freshness_pct"] = freshness
    if stores is not None:
        confidence["stores_active"] = int(stores)
    else:
        from .store_credentials import get_default_stores

        confidence["stores_active"] = len(get_default_stores())

    full_scores = _scores_from_latest(latest)
    scores_summary = {
        k: {"score": v["score"], "label": v["label"]}
        for k, v in full_scores.items()
    }

    enrichment = [v for v in latest_list if v.get("key") in ENRICHMENT_INDICATOR_KEYS]
    subcategories = [v for v in latest_list if (v.get("key") or "").startswith("subcat_")]
    analytics = [
        v for v in latest_list
        if v.get("category") in ("retail", "affordability", "demand", "composite")
    ][:30]

    result: dict[str, Any] = {
        "headline": _brief_headline(
            inflation_pct=inflation_pct,
            gap_pp=gap,
            days=days,
            country=country,
            line=line,
        ),
        "country": country,
        "line": line,
        "days": days,
        "shelf": shelf,
        "macro_gap": macro_gap,
        "confidence": confidence,
        "scores": scores_summary,
        "sources": _brief_sources(latest_list),
        "staleness_hours": {"shelf": 4, "macro": 168},
        "enrichment": {"indicators": enrichment, "total": len(enrichment)},
        "subcategories": {"subcategories": subcategories, "total": len(subcategories)},
        "analytics": {"indicators": analytics, "total": len(analytics)},
        "disclaimer": "Shelf signals from online góndola prices. Does not replace official CPI (INEI, INDEC, etc.).",
    }
    if include_catalog:
        result["catalog"] = get_indicator_catalog()
    return result


def compute_composite_scores(country: str | None = None, line: str | None = None) -> dict[str, Any]:
    db = get_db()
    seed_indicator_definitions(db)
    refresh_internal_indicators(db, country, line)
    db.commit()
    result = get_scores(db, country=country, line=line)
    db.close()
    return result