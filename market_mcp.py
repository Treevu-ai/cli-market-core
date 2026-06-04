#!/usr/bin/env python3
"""market-mcp — MCP server para Agentic Market (JSON-RPC sobre stdio)."""

import json
import sys

from market_core import API, SESSION_FILE, api, get_token  # noqa: F401

TOOLS = [
    {"name": "market_login", "description": "Authenticate in CLI Market.", "inputSchema": {"type": "object", "properties": {"username": {"type": "string"}, "password": {"type": "string"}}}},
    {"name": "market_lines", "description": "List business lines.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_search", "description": "Search products across 30+ retailers.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "store": {"type": "string"}, "line": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": ["query"]}},
    {"name": "market_compare", "description": "Compare prices across all retailers.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "line": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": ["query"]}},
    {"name": "market_add", "description": "Add to cart.", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "name": {"type": "string"}, "price": {"type": "number"}, "store": {"type": "string"}, "quantity": {"type": "integer", "default": 1}}, "required": ["product_id", "name", "price", "store"]}},
    {"name": "market_cart", "description": "View current cart.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_cart_update", "description": "Update cart item quantity.", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "quantity": {"type": "integer"}}, "required": ["product_id", "quantity"]}},
    {"name": "market_cart_remove", "description": "Remove item from cart.", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},
    {"name": "market_checkout", "description": "Complete purchase.", "inputSchema": {"type": "object", "properties": {"payment_method": {"type": "string", "default": "yape"}}}},
    {"name": "market_orders", "description": "View order history.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_reorder", "description": "Repeat last order.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_ask", "description": "Natural language purchase.", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "market_basket", "description": "Compare basket cost across retailers.", "inputSchema": {"type": "object", "properties": {"items": {"type": "array"}, "stores": {"type": "array"}}, "required": ["items"]}},
    {"name": "market_inflation", "description": "Price variation from data moat.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}, "line": {"type": "string"}, "days": {"type": "integer"}}}},
    {"name": "market_indicators", "description": "Data moat indicators catalog.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_scores", "description": "Composite moat scores.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}, "line": {"type": "string"}}}},
    {"name": "market_intel_refresh", "description": "Recalculate internal indicators.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}, "line": {"type": "string"}}}},
    {"name": "market_enrichment", "description": "Enrichment indicators.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}}}},
    {"name": "market_enrichment_subcategories", "description": "Per-subcategory enrichment.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}}}},
    {"name": "market_enrichment_refresh", "description": "Refresh enrichment indicators.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}}}},
    {"name": "market_categories", "description": "Explore retailer category tree.", "inputSchema": {"type": "object", "properties": {"store": {"type": "string"}}, "required": ["store"]}},
    {"name": "market_barcode", "description": "Search by EAN/UPC barcode.", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "market_enrich", "description": "Open Food Facts enrichment.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}}, "required": ["query"]}},
    {"name": "market_stores", "description": "List verified retailers.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_countries", "description": "List available countries.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_ticket", "description": "Scan purchase ticket via OCR.", "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "country": {"type": "string"}}, "required": ["url"]}},
    {"name": "market_voice", "description": "Transcribe audio to text.", "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "market_price_history", "description": "Product price history.", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "store": {"type": "string"}, "line": {"type": "string"}, "limit": {"type": "integer", "default": 50}}}},
    {"name": "market_stats", "description": "Data moat statistics.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_analytics_indicators", "description": "Latest moat indicator values.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}, "line": {"type": "string"}, "limit": {"type": "integer", "default": 30}}}},
    {"name": "market_alerts", "description": "Price alerts.", "inputSchema": {"type": "object", "properties": {"product": {"type": "string"}, "store": {"type": "string"}, "threshold_pct": {"type": "number", "default": 5.0}, "limit": {"type": "integer", "default": 10}}, "required": ["product"]}},
    {"name": "market_whoami", "description": "Verify identity.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_preferences", "description": "User preferences.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_subscription", "description": "Current subscription plan.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "market_export", "description": "Export data moat.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}, "line": {"type": "string"}, "format": {"type": "string", "default": "json"}, "limit": {"type": "integer", "default": 100}}}},
    {"name": "market_trending", "description": "Trending products.", "inputSchema": {"type": "object", "properties": {"country": {"type": "string"}, "line": {"type": "string"}, "limit": {"type": "integer", "default": 10}}}},
    {"name": "market_scan", "description": "Scan new VTEX stores.", "inputSchema": {"type": "object", "properties": {"line": {"type": "string"}}}},
    {"name": "market_stock", "description": "Check product stock.", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "store": {"type": "string"}}, "required": ["product_id", "store"]}},
    {"name": "market_brands", "description": "Top brands in moat.", "inputSchema": {"type": "object", "properties": {"line": {"type": "string"}, "country": {"type": "string"}, "limit": {"type": "integer", "default": 20}}}},
    {"name": "market_favorites", "description": "Manage favorites.", "inputSchema": {"type": "object", "properties": {"action": {"type": "string"}, "product_id": {"type": "string"}, "name": {"type": "string"}, "store": {"type": "string"}}}},
    {"name": "market_notify", "description": "Set price alerts.", "inputSchema": {"type": "object", "properties": {"product": {"type": "string"}, "store": {"type": "string"}, "threshold_pct": {"type": "number", "default": 5.0}}, "required": ["product"]}},
    {"name": "market_exchange", "description": "Currency conversion.", "inputSchema": {"type": "object", "properties": {"amount": {"type": "number"}, "from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": ["amount", "from_currency", "to_currency"]}},
    {"name": "market_delivery", "description": "Delivery options.", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "store": {"type": "string"}, "zipcode": {"type": "string"}}, "required": ["product_id", "store"]}},
]


def _checkout_api(args: dict) -> dict:
    pm = (args.get("payment_method") or "yape").lower()
    routes = {"yape": "/checkout/yape", "plin": "/checkout/yape", "paypal": "/checkout/paypal", "tarjeta": "/checkout/paypal"}
    return api("POST", routes.get(pm, "/checkout/yape"), {})


def handle_tool(name: str, args: dict) -> str:
    tool_map = {
        "market_login":      lambda a: api("POST", "/auth/login", {"username": a["username"], "password": a["password"]}),
        "market_lines":      lambda a: api("GET", "/lines"),
        "market_search":     lambda a: api("POST", "/products/search", {"query": a["query"], "store": a.get("store"), "line": a.get("line"), "limit": a.get("limit", 10)}),
        "market_compare":    lambda a: api("POST", "/products/compare", {"query": a["query"], "line": a.get("line"), "limit": a.get("limit", 10)}),
        "market_add":        lambda a: api("POST", "/cart/add", {"product_id": a["product_id"], "name": a["name"], "price": a["price"], "store": a["store"], "quantity": a.get("quantity", 1)}),
        "market_cart":       lambda a: api("GET", "/cart"),
        "market_cart_update": lambda a: api("PUT", "/cart/update", {"product_id": a["product_id"], "quantity": a["quantity"]}),
        "market_cart_remove": lambda a: api("DELETE", f"/cart/{a['product_id']}"),
        "market_checkout":   lambda a: _checkout_api(a),
        "market_orders":     lambda a: api("GET", "/orders"),
        "market_reorder":    lambda a: api("POST", "/orders/reorder"),
        "market_ask":        lambda a: api("POST", "/agent/ask", {"prompt": a["prompt"]}),
        "market_basket":     lambda a: api("POST", "/v1/basket/compare", {"items": a["items"], "stores": a.get("stores")}),
        "market_inflation":  lambda a: api("GET", f"/v1/intel/inflation?country={a.get('country', '')}&line={a.get('line', '')}"),
        "market_indicators": lambda a: api("GET", "/v1/intel/indicators"),
        "market_scores":     lambda a: api("GET", f"/v1/intel/scores?country={a.get('country', '')}&line={a.get('line', '')}"),
        "market_intel_refresh": lambda a: api("POST", f"/v1/intel/refresh?country={a.get('country', '')}&line={a.get('line', '')}"),
        "market_enrichment": lambda a: api("GET", f"/v1/intel/enrichment?country={a.get('country', '')}"),
        "market_enrichment_refresh": lambda a: api("POST", f"/v1/intel/enrichment/refresh?country={a.get('country', '')}"),
        "market_enrichment_subcategories": lambda a: api("GET", f"/v1/intel/enrichment/subcategories?country={a.get('country', 'PE')}"),
        "market_categories": lambda a: api("GET", f"/categories/{a['store']}"),
        "market_barcode":    lambda a: api("GET", f"/products/barcode/{a['code']}"),
        "market_enrich":     lambda a: api("GET", f"/products/enrich?query={a['query']}&limit={a.get('limit', 5)}"),
        "market_stores":     lambda a: api("GET", "/stores"),
        "market_countries":  lambda a: api("GET", "/countries"),
        "market_ticket":     lambda a: api("POST", "/v1/ticket/scan-url", {"url": a["url"], "country": a.get("country")}),
        "market_voice":      lambda a: api("POST", "/v1/voice/transcribe-url", {"url": a["url"]}),
        "market_price_history": lambda a: api("GET", f"/analytics/price-history?product_id={a.get('product_id','')}&store={a.get('store','')}&line={a.get('line','')}&limit={a.get('limit',50)}"),
        "market_stats":      lambda a: api("GET", "/analytics/stats"),
        "market_analytics_indicators": lambda a: api("GET", f"/analytics/indicators?country={a.get('country', '')}&line={a.get('line', '')}&limit={a.get('limit', 30)}"),
        "market_alerts":     lambda a: api("GET", f"/v1/intel/alerts?product={a['product']}&store={a.get('store','')}&threshold_pct={a.get('threshold_pct',5.0)}&limit={a.get('limit',10)}"),
        "market_whoami":     lambda a: api("GET", "/auth/whoami"),
        "market_preferences": lambda a: api("GET", "/agent/preferences"),
        "market_subscription": lambda a: api("GET", "/auth/subscription"),
        "market_export":     lambda a: api("POST", "/v1/data/export", {"country": a.get("country"), "line": a.get("line"), "format": a.get("format", "json"), "limit": a.get("limit", 100)}),
        "market_trending":   lambda a: api("GET", f"/analytics/trending?country={a.get('country','')}&line={a.get('line','')}&limit={a.get('limit',10)}"),
        "market_scan":       lambda a: api("POST", "/v1/admin/scan-stores", {"line": a.get("line")}),
        "market_stock":      lambda a: api("GET", f"/products/stock/{a['product_id']}?store={a['store']}"),
        "market_brands":     lambda a: api("GET", f"/analytics/brands?line={a.get('line','')}&country={a.get('country','')}&limit={a.get('limit',20)}"),
        "market_favorites":  lambda a: api("POST", "/favorites", {"action": a.get("action","list"), "product_id": a.get("product_id",""), "name": a.get("name",""), "store": a.get("store","")}),
        "market_notify":     lambda a: api("GET", f"/v1/intel/alerts?product={a['product']}&store={a.get('store','')}&threshold_pct={a.get('threshold_pct',5.0)}"),
        "market_exchange":   lambda a: api("POST", "/v1/utils/exchange", {"amount": a["amount"], "from": a["from_currency"], "to": a["to_currency"]}),
        "market_delivery":   lambda a: api("GET", f"/products/delivery/{a['product_id']}?store={a['store']}&zipcode={a.get('zipcode','')}"),
    }
    handler = tool_map.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = handler(args)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def main():
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
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "cli-market", "version": "1.0.0"}}}
        elif method == "tools/list":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            tool_name = request["params"]["name"]
            tool_args = request["params"].get("arguments", {})
            content = handle_tool(tool_name, tool_args)
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": content}]}}
        else:
            response = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
