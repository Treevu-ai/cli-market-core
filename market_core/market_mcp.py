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
    get_profile,
    is_deprecated_alias,
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


def _tool_handlers() -> dict:
    return {
        "market_login": lambda a: api("POST", "/auth/login", {"username": a["username"], "password": a["password"]}),
        "market_lines": lambda a: api("GET", "/lines"),
        "market_search": lambda a: api(
            "POST",
            "/products/search",
            {"query": a["query"], "store": a.get("store"), "line": a.get("line"), "limit": a.get("limit", 10)},
        ),
        "market_compare": lambda a: api(
            "POST",
            "/products/compare",
            {"query": a["query"], "line": a.get("line"), "limit": a.get("limit", 10)},
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
        "market_cart_remove": lambda a: api("DELETE", f"/cart/{a['product_id']}"),
        "market_checkout": lambda a: _checkout_api(a),
        "market_orders": lambda a: api("GET", "/orders"),
        "market_reorder": lambda a: api("POST", "/orders/reorder"),
        "market_ask": lambda a: api("POST", "/agent/ask", {"prompt": a["prompt"]}),
        "market_basket": lambda a: api("POST", "/v1/basket/compare", {"items": a["items"], "stores": a.get("stores")}),
        "market_inflation": lambda a: api(
            "GET", f"/v1/intel/inflation?country={a.get('country', '')}&line={a.get('line', '')}"
        ),
        "market_indicators": lambda a: api("GET", "/v1/intel/indicators"),
        "market_scores": lambda a: api("GET", f"/v1/intel/scores?country={a.get('country', '')}&line={a.get('line', '')}"),
        "market_intel_refresh": lambda a: api(
            "POST", f"/v1/intel/refresh?country={a.get('country', '')}&line={a.get('line', '')}"
        ),
        "market_enrichment": lambda a: api("GET", f"/v1/intel/enrichment?country={a.get('country', '')}"),
        "market_enrichment_refresh": lambda a: api(
            "POST", f"/v1/intel/enrichment/refresh?country={a.get('country', '')}"
        ),
        "market_enrichment_subcategories": lambda a: api(
            "GET", f"/v1/intel/enrichment/subcategories?country={a.get('country', 'PE')}"
        ),
        "market_categories": lambda a: api("GET", f"/categories/{a['store']}"),
        "market_barcode": lambda a: api("GET", f"/products/barcode/{a['code']}"),
        "market_enrich": lambda a: api("GET", f"/products/enrich?query={a['query']}&limit={a.get('limit', 5)}"),
        "market_stores": lambda a: api("GET", "/stores"),
        "market_countries": lambda a: api("GET", "/countries"),
        "market_ticket": lambda a: api("POST", "/v1/ticket/scan-url", {"url": a["url"], "country": a.get("country")}),
        "market_voice": lambda a: api("POST", "/v1/voice/transcribe-url", {"url": a["url"]}),
        "market_price_history": lambda a: api(
            "GET",
            f"/analytics/price-history?product_id={a.get('product_id', '')}&store={a.get('store', '')}"
            f"&line={a.get('line', '')}&limit={a.get('limit', 50)}",
        ),
        "market_stats": lambda a: api("GET", "/analytics/stats"),
        "market_analytics_indicators": lambda a: api(
            "GET",
            f"/analytics/indicators?country={a.get('country', '')}&line={a.get('line', '')}&limit={a.get('limit', 30)}",
        ),
        "market_alerts": lambda a: api(
            "GET",
            f"/v1/intel/alerts?product={a['product']}&store={a.get('store', '')}"
            f"&threshold_pct={a.get('threshold_pct', 5.0)}&limit={a.get('limit', 10)}",
        ),
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
        "market_notify": lambda a: api(
            "GET",
            f"/v1/intel/alerts?product={a['product']}&store={a.get('store', '')}"
            f"&threshold_pct={a.get('threshold_pct', 5.0)}",
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


def handle_tool(name: str, args: dict) -> str:
    """Dispatch MCP tool calls to the API. Resolves legacy aliases."""
    canonical = resolve_tool_name(name)
    if not canonical:
        return json.dumps({"error": f"Unknown tool: {name}"})
    handler = _TOOL_MAP.get(canonical)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = handler(args)
        if is_deprecated_alias(name):
            if isinstance(result, dict):
                result = {**result, "_deprecation": {"alias": name, "use": canonical}}
            else:
                result = {"data": result, "_deprecation": {"alias": name, "use": canonical}}
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


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

        method = request.get("method", "")
        req_id = request.get("id")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "cli-market", "version": "1.0.0"},
                },
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": list_tools(profile)},
            }
        elif method == "tools/call":
            tool_name = request["params"]["name"]
            tool_args = request["params"].get("arguments", {})
            content = handle_tool(tool_name, tool_args)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": content}]},
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()