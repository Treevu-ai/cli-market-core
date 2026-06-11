#!/usr/bin/env python3
"""
market-mcp — MCP server para Agentic Market.

Expone búsqueda, carrito y checkout como tools MCP (JSON-RPC sobre stdio)
para que cualquier agente IA (DeepSeek TUI, Claude, etc.) pueda operar
el supermercado.

Uso:
    python market_mcp.py
    → se conecta vía stdio, listo para MCP
"""

import json
import sys

# Re-exports kept for backwards compat — tests/test_server.py verifies these
# are reachable through market_mcp. Ruff would otherwise drop the unused ones.
from .market_core import API, SESSION_FILE, api, get_token  # noqa: F401
from .market_mcp_registry import (
    TOOLS,
    get_deprecation,
    get_profile,
    list_tools,
    resolve_tool_name,
)

__all__ = [
    "API",
    "SESSION_FILE",
    "TOOLS",
    "api",
    "get_token",
    "handle_tool",
    "list_tools",
    "main",
    "resolve_tool_name",
]

def _checkout_api(args: dict) -> dict:
    pm = (args.get("payment_method") or "yape").lower()
    routes = {"yape": "/checkout/yape", "plin": "/checkout/yape", "paypal": "/checkout/paypal", "tarjeta": "/checkout/paypal"}
    return api("POST", routes.get(pm, "/checkout/yape"), {})


def _discover_api(args: dict) -> dict:
    """Compose lines + stores + countries; optional legacy slice for alias callers."""
    lines = api("GET", "/lines")
    store_qs = []
    if args.get("country"):
        store_qs.append(f"country={args['country']}")
    if args.get("line"):
        store_qs.append(f"line={args['line']}")
    stores_path = "/stores" + (f"?{'&'.join(store_qs)}" if store_qs else "")
    stores = api("GET", stores_path)
    countries = api("GET", "/countries")
    slice_key = args.get("_slice")
    if slice_key == "lines":
        return lines
    if slice_key == "stores":
        return stores
    if slice_key == "countries":
        return countries
    return {"lines": lines, "stores": stores, "countries": countries}


def _price_alerts_api(args: dict) -> dict:
    return api(
        "GET",
        f"/v1/intel/alerts?product={args['product']}&store={args.get('store', '')}"
        f"&threshold_pct={args.get('threshold_pct', 5.0)}&limit={args.get('limit', 10)}",
    )


def _intel_brief_path(args: dict) -> str:
    qs: list[str] = []
    if args.get("country"):
        qs.append(f"country={args['country']}")
    if args.get("line"):
        qs.append(f"line={args['line']}")
    days = args.get("days", 7)
    qs.append(f"days={days}")
    if args.get("include_catalog"):
        qs.append("include_catalog=true")
    return "/v1/intel/brief" + ("?" + "&".join(qs) if qs else "")


def _slice_intel_brief(brief: dict, slice_key: str | None) -> dict:
    if slice_key == "catalog":
        catalog = brief.get("catalog", [])
        return {"indicators": catalog, "total": len(catalog)}
    if slice_key == "analytics":
        return brief.get("analytics", {"indicators": [], "total": 0})
    if slice_key == "enrichment":
        block = brief.get("enrichment", {"indicators": [], "total": 0})
        return {
            "indicators": block.get("indicators", []),
            "total": block.get("total", 0),
            "country": brief.get("country"),
            "sources": "Open Food Facts · Wikimedia Pageviews · Open-Meteo · World Bank",
        }
    if slice_key == "subcategories":
        block = brief.get("subcategories", {"subcategories": [], "total": 0})
        return {
            "subcategories": block.get("subcategories", []),
            "total": block.get("total", 0),
            "country": brief.get("country"),
        }
    return brief


def _intel_brief_api(args: dict) -> dict:
    brief = api("GET", _intel_brief_path(args))
    return _slice_intel_brief(brief, args.get("_slice"))


def _normalize_args(requested: str, canonical: str, args: dict) -> dict:
    """Map legacy tool args to canonical handler shape."""
    out = dict(args)
    if requested in ("market_lines", "market_stores", "market_countries"):
        out["_slice"] = requested.removeprefix("market_")
    elif requested == "market_cart_remove":
        out.setdefault("quantity", 0)
    elif requested == "market_reorder":
        out["reorder_last"] = True
    elif requested == "market_indicators":
        out["include_catalog"] = True
        out["_slice"] = "catalog"
    elif requested == "market_analytics_indicators":
        out["_slice"] = "analytics"
    elif requested == "market_enrichment":
        out["_slice"] = "enrichment"
    elif requested == "market_enrichment_subcategories":
        out["_slice"] = "subcategories"
    return out


def _tool_handlers() -> dict:
    return {
        "market_login": lambda a: api("POST", "/auth/login", {"username": a["username"], "password": a["password"]}),
        "market_discover": _discover_api,
        "market_search": lambda a: api(
            "POST",
            "/products/search",
            {
                "query": a["query"],
                "store": a.get("store"),
                "line": a.get("line"),
                "country": a.get("country"),
                "limit": a.get("limit", 10),
            },
        ),
        "market_compare": lambda a: api(
            "POST",
            "/products/compare",
            {
                "query": a["query"],
                "store": a.get("store"),
                "line": a.get("line"),
                "country": a.get("country"),
                "limit": a.get("limit", 10),
            },
        ),
        "market_add": lambda a: api(
            "POST",
            "/cart/add",
            {
                "product_id": a["product_id"],
                "name": a["name"],
                "price": a["price"],
                "store": a["store"],
                "quantity": a.get("quantity", 1),
            },
        ),
        "market_cart": lambda a: api("GET", "/cart"),
        "market_cart_update": lambda a: api("PUT", "/cart/update", {"product_id": a["product_id"], "quantity": a["quantity"]}),
        "market_checkout": lambda a: _checkout_api(a),
        "market_orders": lambda a: (
            api("POST", "/orders/reorder", {})
            if a.get("reorder_last")
            else api("GET", "/orders")
        ),
        "market_ask": lambda a: api("POST", "/agent/ask", {"prompt": a["prompt"]}),
        "market_basket": lambda a: api("POST", "/v1/basket/compare", {"items": a["items"], "stores": a.get("stores")}),
        "market_intel_brief": _intel_brief_api,
        "market_inflation": lambda a: api(
            "GET", f"/v1/intel/inflation?country={a.get('country', '')}&line={a.get('line', '')}"
        ),
        "market_scores": lambda a: api("GET", f"/v1/intel/scores?country={a.get('country', '')}&line={a.get('line', '')}"),
        "market_intel_refresh": lambda a: api(
            "POST", f"/v1/intel/refresh?country={a.get('country', '')}&line={a.get('line', '')}"
        ),
        "market_enrichment_refresh": lambda a: api(
            "POST", f"/v1/intel/enrichment/refresh?country={a.get('country', '')}"
        ),
        "market_categories": lambda a: api("GET", f"/categories/{a['store']}"),
        "market_barcode": lambda a: api("GET", f"/products/barcode/{a['code']}"),
        "market_enrich": lambda a: api("GET", f"/products/enrich?query={a['query']}&limit={a.get('limit', 5)}"),
        "market_ticket": lambda a: api("POST", "/v1/ticket/scan-url", {"url": a["url"], "country": a.get("country")}),
        "market_voice": lambda a: api("POST", "/v1/voice/transcribe-url", {"url": a["url"]}),
        "market_price_history": lambda a: api(
            "GET",
            f"/analytics/price-history?product_id={a.get('product_id', '')}&store={a.get('store', '')}"
            f"&line={a.get('line', '')}&limit={a.get('limit', 50)}",
        ),
        "market_stats": lambda a: api("GET", "/analytics/stats"),
        "market_price_alerts": _price_alerts_api,
        "market_whoami": lambda a: api("GET", "/auth/whoami"),
        "market_preferences": lambda a: api("GET", "/agent/preferences"),
        "market_subscription": lambda a: api("GET", "/auth/subscription"),
        "market_export": lambda a: api(
            "POST",
            "/v1/data/export",
            {
                "country": a.get("country"),
                "line": a.get("line"),
                "format": a.get("format", "json"),
                "limit": a.get("limit", 100),
            },
        ),
        "market_trending": lambda a: api(
            "GET",
            f"/analytics/trending?country={a.get('country', '')}&line={a.get('line', '')}&limit={a.get('limit', 10)}",
        ),
        "market_scan": lambda a: api("POST", "/v1/admin/scan-stores", {"line": a.get("line")}),
        "market_stock": lambda a: api("GET", f"/products/stock/{a['product_id']}?store={a['store']}"),
        "market_brands": lambda a: api(
            "GET",
            f"/analytics/brands?line={a.get('line', '')}&country={a.get('country', '')}&limit={a.get('limit', 20)}",
        ),
        "market_favorites": lambda a: api(
            "POST",
            "/favorites",
            {
                "action": a.get("action", "list"),
                "product_id": a.get("product_id", ""),
                "name": a.get("name", ""),
                "store": a.get("store", ""),
            },
        ),
        "market_exchange": lambda a: api(
            "POST",
            "/v1/utils/exchange",
            {"amount": a["amount"], "from": a["from_currency"], "to": a["to_currency"]},
        ),
        "market_delivery": lambda a: api(
            "GET",
            f"/products/delivery/{a['product_id']}?store={a['store']}&zipcode={a.get('zipcode', '')}",
        ),
    }


_TOOL_MAP = _tool_handlers()


def _attach_deprecation(result: object, notice: dict[str, str] | None) -> object:
    if not notice:
        return result
    if isinstance(result, dict):
        return {**result, "_deprecation": notice}
    return {"data": result, "_deprecation": notice}


def handle_tool(name: str, args: dict) -> str:
    """Dispatch MCP tool calls to the API. Resolves legacy aliases."""
    canonical = resolve_tool_name(name)
    if not canonical:
        return json.dumps({"error": f"Unknown tool: {name}"})
    handler = _TOOL_MAP.get(canonical)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        normalized = _normalize_args(name, canonical, args)
        result = handler(normalized)
        result = _attach_deprecation(result, get_deprecation(name))
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _is_jsonrpc_notification(request: dict) -> bool:
    """JSON-RPC notifications omit ``id``; they must not receive a response."""
    return "id" not in request


def _write_rpc(message: dict) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_rpc_request(request: dict, profile: str) -> dict | None:
    """Build one JSON-RPC response, or ``None`` when no reply is allowed (notifications)."""
    method = request.get("method", "")

    if _is_jsonrpc_notification(request):
        return None

    req_id = request["id"]
    params = request.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cli-market", "version": "1.9.31"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": list_tools(profile)},
        }
    if method == "tools/call":
        tool_name = params["name"]
        tool_args = params.get("arguments", {})
        content = handle_tool(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": content}]},
        }
    if method in ("resources/list", "resources/templates/list"):
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    """MCP JSON-RPC loop over stdio."""
    profile = get_profile()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_rpc_request(request, profile)
        if response is not None:
            _write_rpc(response)


if __name__ == "__main__":
    main()