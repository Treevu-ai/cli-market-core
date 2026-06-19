"""MCP tool registry — canonical definitions, metadata, aliases, and profiles.

PR1+PR2+PR5: canonical tool registry with metadata, aliases, and profiles.
``tools/list`` defaults to the ``default`` profile (24 curated Shop/Intel/Account tools).
Set ``MCP_TOOL_PROFILE=legacy`` for all 46 registered tools (includes deprecated aliases).
Also: ``full`` (43) and ``admin`` (46 + scan/refresh).
"""

from __future__ import annotations

import os
from typing import Any

BUNDLES = ("shop", "intel", "account", "advanced", "admin")

# Profiles: legacy = all registered tools (default, no breaking change).
PROFILES = ("legacy", "default", "full", "admin")

def _coverage_stats() -> tuple[int, int, int]:
    """Same derivation as market_stats — avoids circular import at load time."""
    from .market_stores import STORES
    from .store_credentials import get_default_stores

    defaults = frozenset(get_default_stores())
    verified = len(defaults)
    countries = len({s["country"] for s in STORES.values() if not s.get("disabled")})
    defined = len(STORES)
    return verified, countries, defined

# Tools hidden from ``default`` profile (advanced / admin / soon-deprecated).
_ADVANCED_NAMES = frozenset(
    {
        "market_voice",
        "market_categories",
        "market_enrich",
        "market_stock",
        "market_delivery",
        "market_exchange",
        "market_brands",
        "market_price_history",
    }
)
_ADMIN_NAMES = frozenset(
    {
        "market_scan",
        "market_intel_refresh",
        "market_enrichment_refresh",
    }
)
# Consolidation targets (PR2/PR3) — hidden in ``default`` but kept as legacy aliases.
_DEFAULT_HIDDEN = frozenset(
    {
        "market_lines",
        "market_stores",
        "market_countries",
        "market_cart_remove",
        "market_reorder",
        "market_indicators",
        "market_analytics_indicators",
        "market_enrichment",
        "market_enrichment_subcategories",
        "market_notify",
        "market_alerts",
    }
)

# Legacy tool names → canonical handler (PR2 consolidations).
ALIASES: dict[str, str] = {
    "market_lines": "market_discover",
    "market_stores": "market_discover",
    "market_countries": "market_discover",
    "market_cart_remove": "market_cart_update",
    "market_reorder": "market_orders",
    "market_alerts": "market_price_alerts",
    "market_notify": "market_price_alerts",
    # PR3 — intel narrative consolidates fragmented reads
    "market_indicators": "market_intel_brief",
    "market_analytics_indicators": "market_intel_brief",
    "market_enrichment": "market_intel_brief",
    "market_enrichment_subcategories": "market_intel_brief",
}


def _schema_object(props: dict[str, Any] | None = None, *, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props or {}, "required": required or []}


def _meta(
    *,
    bundle: str,
    order: int,
    min_tier: str = "free",
    requires_auth: bool | str = False,
    icp: list[str] | None = None,
    pairs_with: list[str] | None = None,
    replaces: str | None = None,
) -> dict[str, Any]:
    return {
        "bundle": bundle,
        "order": order,
        "requires_auth": requires_auth,
        "min_tier": min_tier,
        "icp": icp or ["builder", "agent"],
        "pairs_with": pairs_with or [],
        "replaces": replaces,
    }


def _tool(
    name: str,
    description: str,
    input_schema: dict,
    *,
    meta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
        "_meta": meta,
    }


def _build_tool_specs() -> list[dict[str, Any]]:
    """Return canonical tool definitions (43 tools)."""
    verified, countries, defined = _coverage_stats()
    cov = f"{verified} verified retailers across {countries} countries"
    catalog = f"{defined} retailers ({verified} verified active)"
    return [
        _tool(
            "market_login",
            f"[Shop] Authenticate in CLI Market. Call before cart, checkout, or orders. "
            "Returns access + refresh tokens (access default 90d, refresh 365d) persisted locally. "
            "On 401 with expired access, CLI auto-calls POST /auth/refresh; agents may re-login or refresh.",
            _schema_object({"username": {"type": "string"}, "password": {"type": "string"}}),
            meta=_meta(bundle="shop", order=1, requires_auth="setup"),
        ),
        _tool(
            "market_discover",
            f"[Shop] Retail coverage in one call: business lines, retailers, and countries. "
            f"Replaces market_lines + market_stores + market_countries. {cov}.",
            _schema_object(
                {
                    "country": {"type": "string", "description": "Optional country filter for stores"},
                    "line": {"type": "string", "description": "Optional business line filter for stores"},
                }
            ),
            meta=_meta(
                bundle="shop",
                order=2,
                pairs_with=["market_search", "market_compare", "market_intel_brief"],
            ),
        ),
        _tool(
            "market_lines",
            f"[Shop] Deprecated — use market_discover. Lists business lines with VTEX retailers. {cov}.",
            _schema_object(),
            meta=_meta(bundle="shop", order=99, replaces="market_discover"),
        ),
        _tool(
            "market_search",
            f"[Shop] Search products across {cov}. Returns JSON with product_id, name, price, "
            "store_key (required for market_add), store, and line. Filter by line or store ID. "
            "Prefer this over scraping.",
            _schema_object(
                {
                    "query": {"type": "string", "description": "Search term"},
                    "store": {"type": "string", "description": "Store ID (empty = all in country). Use market_discover for valid IDs."},
                    "country": {"type": "string", "description": "Country code: PE, AR, MX, BR, CO, CL, ES, US. Prefer setting this to avoid timeouts."},
                    "line": {"type": "string", "description": "Business line: supermercados, farmacias, electro, moda, deportes, hogar"},
                    "limit": {"type": "integer", "default": 10},
                },
                required=["query"],
            ),
            meta=_meta(bundle="shop", order=3, pairs_with=["market_compare", "market_add", "market_discover", "market_intel_brief", "market_login"]),
        ),
        _tool(
            "market_compare",
            f"[Shop] Compare prices for one query across retailers side-by-side. Use when the user "
            "asks for cheapest option or cross-store comparison. Set country (e.g. PE) or store to avoid timeouts.",
            _schema_object(
                {
                    "query": {"type": "string", "description": "Product to compare"},
                    "store": {"type": "string", "description": "Optional single store ID from market_discover"},
                    "country": {"type": "string", "description": "Country code: PE, AR, MX, BR, CO, CL, ES, US"},
                    "line": {"type": "string", "description": "Business line filter"},
                    "limit": {"type": "integer", "default": 10},
                },
                required=["query"],
            ),
            meta=_meta(bundle="shop", order=4, pairs_with=["market_search", "market_basket", "market_intel_brief"]),
        ),
        _tool(
            "market_add",
            "[Shop] Add to cart. Copy ALL four fields from market_search: product_id, name, price, "
            "store (use store_key value as store). Missing fields cause 422 — re-run market_search if needed.",
            _schema_object(
                {
                    "product_id": {"type": "string", "description": "From market_search product_id"},
                    "name": {"type": "string", "description": "From market_search name"},
                    "price": {"type": "number", "description": "From market_search price"},
                    "store": {"type": "string", "description": "From market_search store_key"},
                    "quantity": {"type": "integer", "default": 1},
                },
                required=["product_id", "name", "price", "store"],
            ),
            meta=_meta(bundle="shop", order=5, requires_auth=True, pairs_with=["market_search", "market_cart"]),
        ),
        _tool(
            "market_cart",
            "[Shop] View current cart with products, quantities, prices, and total.",
            _schema_object(),
            meta=_meta(bundle="shop", order=6, requires_auth=True, pairs_with=["market_add", "market_checkout"]),
        ),
        _tool(
            "market_cart_update",
            "[Shop] Change item quantity in cart. Use quantity=0 to remove (replaces market_cart_remove in PR2).",
            _schema_object(
                {
                    "product_id": {"type": "string", "description": "Cart product_id"},
                    "quantity": {"type": "integer", "description": "New quantity (0 = remove)"},
                },
                required=["product_id", "quantity"],
            ),
            meta=_meta(bundle="shop", order=7, requires_auth=True),
        ),
        _tool(
            "market_cart_remove",
            "[Shop] Deprecated — use market_cart_update with quantity=0.",
            _schema_object(
                {"product_id": {"type": "string", "description": "Product ID to remove"}},
                required=["product_id"],
            ),
            meta=_meta(bundle="shop", order=99, requires_auth=True, replaces="market_cart_update"),
        ),
        _tool(
            "market_checkout",
            "[Shop] Pay for cart via CLI Market (Yape/Plin/PayPal) — creates internal order, "
            "not checkout on retailer sites. Requires Pro tier for live charge. "
            "payment_method: yape, plin, paypal, tarjeta. See GET /v1/capabilities.",
            _schema_object(
                {"payment_method": {"type": "string", "default": "yape", "description": "yape | plin | paypal | tarjeta"}},
            ),
            meta=_meta(bundle="shop", order=9, requires_auth=True, min_tier="pro", pairs_with=["market_cart"]),
        ),
        _tool(
            "market_orders",
            "[Shop] Order history. Set reorder_last=true to repeat the last order.",
            _schema_object(
                {"reorder_last": {"type": "boolean", "default": False, "description": "Repeat last order"}},
            ),
            meta=_meta(bundle="shop", order=10, requires_auth=True),
        ),
        _tool(
            "market_reorder",
            "[Shop] Deprecated — use market_orders with reorder_last=true.",
            _schema_object(),
            meta=_meta(bundle="shop", order=99, requires_auth=True, replaces="market_orders"),
        ),
        _tool(
            "market_ask",
            "[Shop] Natural-language shopping. Examples: 'buy milk', 'repeat last purchase', 'compare rice'.",
            _schema_object(
                {"prompt": {"type": "string", "description": "Natural-language instruction"}},
                required=["prompt"],
            ),
            meta=_meta(bundle="shop", order=12, pairs_with=["market_search"]),
        ),
        _tool(
            "market_basket",
            f"[Shop] Compare total basket cost across retailers. Pass items with name and qty. "
            f"Returns per-store totals and cheapest retailer. LATAM differentiator — {cov}.",
            _schema_object(
                {
                    "items": {
                        "type": "array",
                        "description": 'Items, e.g. [{"name":"milk","qty":2},{"name":"rice","qty":1}]',
                    },
                    "stores": {"type": "array", "description": "Optional store filter. Empty = all retailers."},
                },
                required=["items"],
            ),
            meta=_meta(bundle="shop", order=13, pairs_with=["market_search", "market_compare"]),
        ),
        _tool(
            "market_intel_brief",
            "[Intel] One-call intelligence narrative: shelf signals, macro gap vs official CPI, "
            "composite scores, and moat confidence. Replaces indicators + analytics + enrichment reads.",
            _schema_object(
                {
                    "country": {"type": "string", "description": "PE, AR, MX, BR, CO, CL"},
                    "line": {"type": "string", "description": "supermercados, farmacias, electro"},
                    "days": {"type": "integer", "default": 7, "description": "Analysis window in days"},
                    "include_catalog": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include full indicator catalog (replaces market_indicators)",
                    },
                }
            ),
            meta=_meta(
                bundle="intel",
                order=0,
                icp=["research", "fintech", "trade", "builder"],
                pairs_with=["market_inflation", "market_scores"],
            ),
        ),
        _tool(
            "market_inflation",
            "[Intel] Shelf inflation from the data moat: price deltas and average inflation. Filter by country or line.",
            _schema_object(
                {
                    "country": {"type": "string", "description": "Country code: AR, BR, MX, CO, PE, CL, IT, FR"},
                    "line": {"type": "string", "description": "Business line: supermercados, farmacias, electro, hogar"},
                    "days": {"type": "integer", "description": "Analysis window in days (default 30)"},
                }
            ),
            meta=_meta(bundle="intel", order=1, icp=["research", "fintech", "trade"]),
        ),
        _tool(
            "market_indicators",
            "[Intel] Deprecated — use market_intel_brief(include_catalog=true).",
            _schema_object(),
            meta=_meta(bundle="intel", order=99, replaces="market_intel_brief"),
        ),
        _tool(
            "market_scores",
            "[Intel] Composite moat scores: retail_aggression, price_fairness, basket_stress, "
            "data_confidence, macro_alignment.",
            _schema_object(
                {
                    "country": {"type": "string", "description": "PE, AR, MX, BR, CO, CL"},
                    "line": {"type": "string", "description": "supermercados, farmacias, electro"},
                }
            ),
            meta=_meta(bundle="intel", order=3, icp=["research", "trade"]),
        ),
        _tool(
            "market_intel_refresh",
            "[Admin] Recalculate internal indicators and fetch public APIs (FX, World Bank CPI, OFF, Wikimedia, weather). "
            "Not for public MCP — cron/admin only.",
            _schema_object({"country": {"type": "string"}, "line": {"type": "string"}}),
            meta=_meta(bundle="admin", order=1, min_tier="enterprise"),
        ),
        _tool(
            "market_enrichment",
            "[Intel] Deprecated — use market_intel_brief (enrichment section).",
            _schema_object({"country": {"type": "string", "description": "PE, AR, MX, BR, CO, CL"}}),
            meta=_meta(bundle="intel", order=99, replaces="market_intel_brief"),
        ),
        _tool(
            "market_enrichment_subcategories",
            "[Intel] Deprecated — use market_intel_brief (subcategories section).",
            _schema_object({"country": {"type": "string", "description": "PE, AR, MX, BR, CO, CL"}}),
            meta=_meta(bundle="intel", order=99, replaces="market_intel_brief"),
        ),
        _tool(
            "market_enrichment_refresh",
            "[Admin] Refresh enrichment indicators only (OFF, Wiki, weather, food CPI) without full moat recalc.",
            _schema_object({"country": {"type": "string", "description": "PE, AR, MX, BR, CO, CL"}}),
            meta=_meta(bundle="admin", order=2, min_tier="enterprise"),
        ),
        _tool(
            "market_categories",
            f"[Advanced] Explore VTEX category tree for a retailer. Deep catalog discovery — {catalog}.",
            _schema_object(
                {"store": {"type": "string", "description": "Store ID (use market_lines for valid IDs)"}},
                required=["store"],
            ),
            meta=_meta(bundle="advanced", order=1),
        ),
        _tool(
            "market_barcode",
            "[Advanced] Look up product by EAN/UPC barcode.",
            _schema_object(
                {"code": {"type": "string", "description": "EAN/UPC barcode"}},
                required=["code"],
            ),
            meta=_meta(bundle="advanced", order=2, pairs_with=["market_search"]),
        ),
        _tool(
            "market_enrich",
            "[Advanced] Search Open Food Facts for nutritional enrichment data.",
            _schema_object(
                {
                    "query": {"type": "string", "description": "Product to search"},
                    "limit": {"type": "integer", "default": 5},
                },
                required=["query"],
            ),
            meta=_meta(bundle="advanced", order=3, icp=["research"]),
        ),
        _tool(
            "market_stores",
            f"[Shop] Deprecated — use market_discover. Lists verified retailers. {cov}.",
            _schema_object(),
            meta=_meta(bundle="shop", order=99, replaces="market_discover"),
        ),
        _tool(
            "market_countries",
            f"[Shop] Deprecated — use market_discover. Lists {countries} countries with store counts.",
            _schema_object(),
            meta=_meta(bundle="shop", order=99, replaces="market_discover"),
        ),
        _tool(
            "market_ticket",
            "[Advanced] Scan purchase receipt via OCR and compare prices against the data moat. "
            "Pass a public image URL.",
            _schema_object(
                {
                    "url": {"type": "string", "description": "Receipt image URL (.jpg, .png)"},
                    "country": {"type": "string", "description": "Optional: PE, AR, BR, MX, CO, CL"},
                },
                required=["url"],
            ),
            meta=_meta(bundle="advanced", order=4),
        ),
        _tool(
            "market_voice",
            "[Advanced] Transcribe voice audio to text. Pass a public audio file URL (.ogg, .mp3, .wav).",
            _schema_object(
                {"url": {"type": "string", "description": "Audio file URL"}},
                required=["url"],
            ),
            meta=_meta(bundle="advanced", order=5),
        ),
        _tool(
            "market_price_history",
            "[Advanced] Price history for a product in the data moat. May merge into market_inflation (PR3).",
            _schema_object(
                {
                    "product_id": {"type": "string"},
                    "store": {"type": "string"},
                    "line": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                }
            ),
            meta=_meta(bundle="advanced", order=6),
        ),
        _tool(
            "market_stats",
            "[Intel] Data moat health: total prices, active stores, tracked products, last refresh.",
            _schema_object(),
            meta=_meta(bundle="intel", order=6),
        ),
        _tool(
            "market_analytics_indicators",
            "[Intel] Deprecated — use market_intel_brief (analytics section).",
            _schema_object(
                {
                    "country": {"type": "string"},
                    "line": {"type": "string"},
                    "limit": {"type": "integer", "default": 30},
                }
            ),
            meta=_meta(bundle="intel", order=99, replaces="market_intel_brief"),
        ),
        _tool(
            "market_price_alerts",
            "[Account] Price alerts: query drops or configure threshold notifications for a product.",
            _schema_object(
                {
                    "product": {"type": "string", "description": "Product to monitor"},
                    "store": {"type": "string"},
                    "threshold_pct": {"type": "number", "default": 5.0},
                    "limit": {"type": "integer", "default": 10},
                },
                required=["product"],
            ),
            meta=_meta(bundle="account", order=4, requires_auth=True),
        ),
        _tool(
            "market_alerts",
            "[Account] Deprecated — use market_price_alerts.",
            _schema_object(
                {
                    "product": {"type": "string", "description": "Product to monitor"},
                    "store": {"type": "string"},
                    "threshold_pct": {"type": "number", "default": 5.0},
                    "limit": {"type": "integer", "default": 10},
                },
                required=["product"],
            ),
            meta=_meta(bundle="account", order=99, requires_auth=True, replaces="market_price_alerts"),
        ),
        _tool(
            "market_whoami",
            "[Account] Verify identity: username and subscription tier for the authenticated user.",
            _schema_object(),
            meta=_meta(bundle="account", order=1, requires_auth=True),
        ),
        _tool(
            "market_preferences",
            "[Account] User preferences from purchase history: favorite stores, total spent.",
            _schema_object(),
            meta=_meta(bundle="account", order=5, requires_auth=True),
        ),
        _tool(
            "market_subscription",
            "[Account] Current subscription plan: tier, rate limits, available API keys.",
            _schema_object(),
            meta=_meta(bundle="account", order=2, requires_auth=True),
        ),
        _tool(
            "market_export",
            "[Intel] Export data moat as CSV or JSON. Requires starter tier or above.",
            _schema_object(
                {
                    "country": {"type": "string"},
                    "line": {"type": "string"},
                    "format": {"type": "string", "default": "json"},
                    "limit": {"type": "integer", "default": 100},
                }
            ),
            meta=_meta(bundle="intel", order=8, min_tier="starter", icp=["research"]),
        ),
        _tool(
            "market_trending",
            "[Intel] Products with largest price movement in the last 7 days.",
            _schema_object(
                {
                    "country": {"type": "string"},
                    "line": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                }
            ),
            meta=_meta(bundle="intel", order=9),
        ),
        _tool(
            "market_scan",
            "[Admin] Scan for new VTEX stores. Admin-only — not exposed in public MCP profiles.",
            _schema_object({"line": {"type": "string", "description": "Optional business line filter"}}),
            meta=_meta(bundle="admin", order=3, min_tier="enterprise"),
        ),
        _tool(
            "market_stock",
            "[Advanced] Check product stock availability at a specific store.",
            _schema_object(
                {"product_id": {"type": "string"}, "store": {"type": "string"}},
                required=["product_id", "store"],
            ),
            meta=_meta(bundle="advanced", order=7),
        ),
        _tool(
            "market_brands",
            "[Advanced] Most frequent brands in the data moat. Filter by line or country.",
            _schema_object(
                {
                    "line": {"type": "string"},
                    "country": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                }
            ),
            meta=_meta(bundle="advanced", order=8),
        ),
        _tool(
            "market_favorites",
            "[Account] Manage favorite products: list, add, or remove. Omit action for list.",
            _schema_object(
                {
                    "action": {"type": "string", "description": "list, add, remove"},
                    "product_id": {"type": "string"},
                    "name": {"type": "string"},
                    "store": {"type": "string"},
                }
            ),
            meta=_meta(bundle="account", order=3, requires_auth=True),
        ),
        _tool(
            "market_notify",
            "[Account] Deprecated — use market_price_alerts.",
            _schema_object(
                {
                    "product": {"type": "string"},
                    "store": {"type": "string"},
                    "threshold_pct": {"type": "number", "default": 5.0},
                },
                required=["product"],
            ),
            meta=_meta(bundle="account", order=99, requires_auth=True, replaces="market_price_alerts"),
        ),
        _tool(
            "market_exchange",
            "[Advanced] Convert amounts between operating currencies (PEN, ARS, BRL, MXN, COP, CLP, EUR).",
            _schema_object(
                {
                    "amount": {"type": "number"},
                    "from_currency": {"type": "string"},
                    "to_currency": {"type": "string"},
                },
                required=["amount", "from_currency", "to_currency"],
            ),
            meta=_meta(bundle="advanced", order=9),
        ),
        _tool(
            "market_delivery",
            "[Advanced] Delivery options for a product and postal code.",
            _schema_object(
                {
                    "product_id": {"type": "string"},
                    "store": {"type": "string"},
                    "zipcode": {"type": "string"},
                },
                required=["product_id", "store"],
            ),
            meta=_meta(bundle="advanced", order=10),
        ),
    ]


# Canonical tools sorted by bundle order for stable tools/list.
_TOOL_SPECS: list[dict[str, Any]] = sorted(
    _build_tool_specs(),
    key=lambda t: (t["_meta"]["bundle"], t["_meta"]["order"], t["name"]),
)

TOOLS: list[dict[str, Any]] = _TOOL_SPECS

CANONICAL_NAMES: frozenset[str] = frozenset(t["name"] for t in TOOLS)

# Reverse alias map: legacy name → canonical handler name.
_ALIAS_TO_CANONICAL: dict[str, str] = {**{n: n for n in CANONICAL_NAMES}, **ALIASES}


def resolve_tool_name(name: str) -> str | None:
    """Resolve a tool name (legacy alias or canonical) to the handler key."""
    return _ALIAS_TO_CANONICAL.get(name)


def is_deprecated_alias(name: str) -> bool:
    """True when ``name`` is a legacy alias pointing at a different canonical tool."""
    canonical = resolve_tool_name(name)
    return canonical is not None and name != canonical


def get_deprecation(name: str) -> dict[str, str] | None:
    """Deprecation notice for a tool call (alias redirect or replaces metadata)."""
    if is_deprecated_alias(name):
        return {"deprecated": name, "use": resolve_tool_name(name) or name}
    meta = get_tool_meta(name)
    if meta and meta.get("replaces"):
        return {"deprecated": name, "use": meta["replaces"]}
    return None


def tool_in_profile(name: str, profile: str) -> bool:
    """Whether ``name`` appears in tools/list for the given profile."""
    if profile not in PROFILES:
        profile = "legacy"
    if profile == "legacy" or profile == "admin":
        return True
    if name in _ADMIN_NAMES:
        return profile == "admin"
    if profile == "full":
        return name not in _ADMIN_NAMES
    if profile == "default":
        if name in _ADVANCED_NAMES or name in _ADMIN_NAMES or name in _DEFAULT_HIDDEN:
            return False
        return True
    return True


def get_profile() -> str:
    """Active MCP tool profile from env (default: default = 24 curated tools)."""
    raw = (os.environ.get("MCP_TOOL_PROFILE") or "default").strip().lower()
    return raw if raw in PROFILES else "default"


def list_tools(profile: str | None = None) -> list[dict[str, Any]]:
    """Tools for tools/list, filtered by profile. Strips ``_meta`` from MCP payload."""
    prof = profile or get_profile()
    visible = [t for t in TOOLS if tool_in_profile(t["name"], prof)]
    return [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in visible
    ]


def public_tool_count(profile: str = "default") -> int:
    """Count of tools in a given profile (for marketing sync)."""
    return len(list_tools(profile))


def get_tool_meta(name: str) -> dict[str, Any] | None:
    """Return registry metadata for a tool name."""
    for t in TOOLS:
        if t["name"] == name:
            return dict(t["_meta"])
    return None


# Original 43 tool names — must keep resolving after PR2 additions.
ORIGINAL_TOOL_NAMES: frozenset[str] = frozenset(
    n for n in CANONICAL_NAMES if n not in {"market_discover", "market_price_alerts", "market_intel_brief"}
)