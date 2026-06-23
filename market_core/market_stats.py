"""Canonical marketing stats — single source of truth for README, PyPI, landing.

Always phrase retailers as: "60 retailers, 30 verified active" (defined vs live).
Auto-derived from .market_stores.py, market_mcp.py, store_credentials.py.
Run: python3 ops/sync_market_stats.py
"""

from __future__ import annotations

# ── Derived from codebase (never stale) ──────────────────────────────────────

def _stores():
    from .market_stores import STORES
    return STORES

def _default_store_keys():
    from .store_credentials import get_default_stores
    return get_default_stores()

def _mcp_tools_count():
    from .market_mcp_registry import public_tool_count
    return public_tool_count("default")

def _indicators_count():
    from .market_indicators import INDICATOR_DEFINITIONS
    return len(INDICATOR_DEFINITIONS)


# ── Canonical figures (computed at import time) ─────────────────────────────

_stores = _stores()
_defaults = frozenset(_default_store_keys())

RETAILERS_DEFINED = len(_stores)
RETAILERS_VERIFIED = len(_defaults)  # active = stores with credentials configured
PLATFORMS = 4
PLATFORM_VTEX = sum(1 for s in _stores.values() if s.get("platform") == "vtex")
PLATFORM_SHOPIFY = sum(1 for s in _stores.values() if s.get("platform") == "shopify")
PLATFORM_MAGENTO = sum(1 for s in _stores.values() if s.get("platform") == "magento")
PLATFORM_WOOCOMMERCE = sum(1 for s in _stores.values() if s.get("platform") == "woocommerce")
COUNTRIES = len({s["country"] for s in _stores.values() if not s.get("disabled")})
COUNTRY_CODES = tuple(sorted({s["country"] for s in _stores.values() if not s.get("disabled")}))
COUNTRIES_CATALOG = len({s["country"] for s in _stores.values()})
MCP_TOOLS = _mcp_tools_count()
INDICATORS_COUNT = _indicators_count()
ENRICHMENT_SOURCES_LABEL = "OFF · Wikimedia · Open-Meteo · World Bank · IMF · Eurostat · BCB"
PRICES_REFRESH_HOURS = 4
CANONICAL_OPTIMIZE_TOOL = "market_optimize_purchase"  # Cost-of-Living OS one-call entry point

def _live_price_label(fallback: str = "63,000+") -> str:
    """Fetch total snapshots from health/db endpoint and round to nearest thousand."""
    try:
        import httpx
        from .market_core import API as api
        r = httpx.get(f"{api}/health/db", timeout=10)
        r.raise_for_status()
        n = r.json().get("snapshots", 0)
        if n and n > 0:
            return f"{round(n / 1000) * 1000:,}+"
    except Exception:
        pass
    return fallback

PRICES_VERIFIED_LABEL = _live_price_label()


def _live_golden_linkage_pct(fallback: float = 0.0) -> float:
    """Fetch golden linkage % from GET /health/stats (public, aggregated)."""
    try:
        import httpx
        from .market_core import API as api
        r = httpx.get(f"{api}/health/stats", timeout=10)
        r.raise_for_status()
        body = r.json()
        pct = body.get("golden_linkage_pct", body.get("linkage_pct"))
        if pct is not None:
            return float(pct)
    except Exception:
        pass
    return fallback


GOLDEN_LINKAGE_PCT = _live_golden_linkage_pct()
PYPI_PACKAGE_NAME = "cli-market-world"
PACKAGE_VERSION = "1.11.0"
LICENSE = "MIT"
PYPI_URL = f"https://pypi.org/project/{PYPI_PACKAGE_NAME}/"
PEPY_PROJECT_URL = f"https://pepy.tech/projects/{PYPI_PACKAGE_NAME}"
# static.pepy.tech personalized-badge 404s until Pepy indexes a new PyPI name;
# shields.io/pepy/dt uses the same Pepy download data and works immediately.
# Pepy indexes legacy `cli-market` until cli-market-world accumulates stats.
PEPY_STATS_PROJECT = "cli-market"
PEPY_BADGE_URL = (
    f"https://img.shields.io/pepy/dt/{PEPY_STATS_PROJECT}"
    "?label=downloads&color=00d75f&logo=pypi"
)
PIP_INSTALL_CMD = f"pip install {PYPI_PACKAGE_NAME}"
PAYMENTS_LABEL = "PayPal (USD) · Yape · Plin · Mercado Pago (soles)"
BUSINESS_LINES = 6
PLATFORM_LIST_EN = "VTEX · Shopify · Magento · WooCommerce"
PLATFORM_LIST_ES = "VTEX · Shopify · Magento · WooCommerce"

SHOPIFY_BRANDS = tuple(
    _stores[k]["name"] for k in sorted(_stores)
    if _stores[k].get("platform") == "shopify"
)
WOOCOMMERCE_STORES = tuple(
    _stores[k]["name"] for k in sorted(_stores)
    if _stores[k].get("platform") == "woocommerce"
)

RETAILERS_PHRASE_EN = f"{RETAILERS_DEFINED} retailers, {RETAILERS_VERIFIED} verified active"
RETAILERS_PHRASE_ES = f"{RETAILERS_DEFINED} retailers, {RETAILERS_VERIFIED} verificados activos"
PLATFORMS_PHRASE_EN = f"{PLATFORMS} platforms ({PLATFORM_LIST_EN})"
PLATFORMS_PHRASE_ES = f"{PLATFORMS} plataformas ({PLATFORM_LIST_ES})"


def header_en() -> str:
    return (
        "CLI Market — Commerce infrastructure for AI agents.\n"
        f"{RETAILERS_DEFINED} retailers across {PLATFORMS} platforms "
        f"({PLATFORM_LIST_EN}), {RETAILERS_VERIFIED} verified live.\n"
        f"{COUNTRIES} countries. {MCP_TOOLS} MCP tools. {PRICES_VERIFIED_LABEL} verified shelf prices, "
        f"normalized per kg/L, refreshed every {PRICES_REFRESH_HOURS}h.\n"
        "One pip install. One API. Zero scraping. MIT."
    )


def header_es() -> str:
    return (
        "CLI Market — Infraestructura de comercio para agentes de IA.\n"
        f"{RETAILERS_DEFINED} retailers en {PLATFORMS} plataformas "
        f"({PLATFORM_LIST_ES}), {RETAILERS_VERIFIED} verificados y activos.\n"
        f"{COUNTRIES} países. {MCP_TOOLS} herramientas MCP. {PRICES_VERIFIED_LABEL} precios reales de góndola, "
        f"normalizados por kg/L, actualizados cada {PRICES_REFRESH_HOURS}h.\n"
        "Un pip install. Una API. Cero scraping. MIT."
    )


def pypi_summary() -> str:
    return (
        "mcp-name: io.github.Treevu-ai/cli-market-world - "
        "CLI Market: commerce API for AI agents. "
        f"{MCP_TOOLS} MCP tools, {INDICATORS_COUNT} indicators, "
        f"{RETAILERS_VERIFIED} verified retailers in {COUNTRIES} countries. MIT."
    )


def readme_tagline_html() -> str:
    return (
        f"<b>Commerce infrastructure for AI agents.</b><br>"
        f"{RETAILERS_DEFINED} retailers ({RETAILERS_VERIFIED} verified). {COUNTRIES} countries. "
        f"{PLATFORMS} platforms. {MCP_TOOLS} MCP tools. {PAYMENTS_LABEL}.<br>"
        f"{PRICES_VERIFIED_LABEL} verified shelf prices, normalized per kg/L, refreshed every {PRICES_REFRESH_HOURS} hours.<br>"
        f"One <code>pip install</code>. One API. Zero scraping."
    )


def server_json_description() -> str:
    return (
        f"Commerce for AI agents. {MCP_TOOLS} MCP tools. "
        f"{RETAILERS_DEFINED} retailers ({RETAILERS_VERIFIED} verified), {COUNTRIES} countries, {PLATFORMS} platforms."
    )


# ── Percentile helpers (issue #7–9: MAA segmentation, WAA) ──────────────────


def compute_usage_percentiles(
    counts: list[int],
    *,
    percentiles: tuple[float, ...] = (50.0, 90.0, 99.0),
) -> dict[str, float]:
    """Return P50/P90/P99 (or custom) from a list of per-agent usage counts.

    >>> compute_usage_percentiles([1, 1, 1, 2, 5, 100], percentiles=(50, 90))
    {'P50': 1.5, 'P90': 52.5, 'n': 6, 'total': 110, 'mean': 18.33}
    """
    if not counts:
        return {"P50": 0.0, "P90": 0.0, "P99": 0.0, "n": 0, "total": 0, "mean": 0.0}
    n = len(counts)
    total = sum(counts)
    sorted_counts = sorted(counts)

    def _pctile(p: float) -> float:
        k = (p / 100.0) * (n - 1)
        lo = int(k)
        hi = min(lo + 1, n - 1)
        frac = k - lo
        return round(sorted_counts[lo] * (1 - frac) + sorted_counts[hi] * frac, 2)

    result: dict[str, float] = {"n": n, "total": total, "mean": round(total / n, 2)}
    for p in percentiles:
        result[f"P{int(p)}"] = _pctile(p)
    return result


def usage_segments(
    counts: list[int],
    *,
    active_threshold: int = 3,
) -> dict:
    """Segment agents into power / active / dormant / one-hit.

    ``active_threshold``: minimum weekly tool calls to count as active (WAA).

    Returns segment counts and the percentile breakdown.
    """
    if not counts:
        return {
            "total_agents": 0,
            "power": 0,        # top 5% by volume
            "active": 0,       # >= active_threshold calls
            "dormant": 0,      # < active_threshold but > 1
            "one_hit": 0,      # exactly 1 call
            "zero": 0,         # 0 calls
            "percentiles": compute_usage_percentiles(counts),
        }

    n = len(counts)
    total_calls = sum(counts)
    # Power = top agents whose cumulative share reaches 80% of total calls,
    # or top 5% by count, whichever is smaller. Prevents "everyone is power"
    # when most agents have identical low counts.
    sorted_desc = sorted(counts, reverse=True)
    cum = 0
    power_n = 0
    for c in sorted_desc:
        cum += c
        power_n += 1
        if cum >= total_calls * 0.8 or power_n >= max(1, n // 20):
            break
    # Floor: at most 5% of agents, at least 1 if any calls exist
    power_n = min(power_n, max(1, n // 20)) if total_calls > 0 else 0

    segments = {
        "total_agents": n,
        "power": power_n,
        "active": sum(1 for c in counts if c >= active_threshold),
        "dormant": sum(1 for c in counts if 1 < c < active_threshold),
        "one_hit": sum(1 for c in counts if c == 1),
        "zero": sum(1 for c in counts if c == 0),
        "percentiles": compute_usage_percentiles(counts),
    }
    return segments


def seo_description() -> str:
    return (
        f"Commerce API for AI agents. {MCP_TOOLS} MCP tools, {RETAILERS_PHRASE_EN}. "
        f"{COUNTRIES} countries. {PRICES_VERIFIED_LABEL} verified shelf prices refreshed every {PRICES_REFRESH_HOURS} hours. "
        f"Normalized per kg/L, quality-filtered. {PIP_INSTALL_CMD}."
    )
