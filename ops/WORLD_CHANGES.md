# WORLD_CHANGES — Cost-of-Living OS post Wave 4

Cambios sugeridos en **cli-market-world** tras bump core `@8469854`.

## MCP marketing sync

Actualizar copy que cite conteo de tools:

| Antes | Ahora |
|-------|-------|
| "24 MCP tools" | **32 tools** en perfil default (`public_tool_count("default")`) |
| "57 total" | 57 registrados, 54 en perfil `full` |

Verificar en: `landing/lib/marketStats.ts`, `mcp.json`, README, docs site.

```bash
# Desde cli-market-core
python3 -c "from market_core.market_mcp_registry import public_tool_count; print(public_tool_count('default'))"
```

## P0 — Compound job como default

El flujo agente/humano debe priorizar **una llamada compuesta**:

```
market_optimize_purchase(country, items, constraints)
```

En lugar de: `market_search` → `market_compare` → `market_affordability` → `market_procurement_signal`.

### CLI sugerido

```bash
market optimize leche arroz --country PE --budget 80
# internamente: POST /v1/missions/optimize-purchase
# muestra: recommendation.action, tco_total, action_links, rationale_es
```

Patch listo: `ops/ecosystem-patches/cli-market-world-optimize.patch` — ver `APPLY-WORLD-OPTIMIZE.md`.

**Production API (Railway):** montar `market_core.api_routes` en `market_server.py` — patch `cli-market-world-mount-api-routes.patch`, ver `APPLY-WORLD-MOUNT-API-ROUTES.md`.

Parámetros MCP útiles:
- `constraints.include_tco: true`
- `constraints.include_action_links: true` (o leer `action_links` de la respuesta mission)
- `constraints.max_budget` / household profile si hay sesión

## P1 — Basket compare con TCO

```bash
market basket leche:2 arroz:1 --tco
# POST /v1/basket/compare { include_tco: true, include_delivery: true }
```

Mostrar `cheapest_tco_store` vs `cheapest_shelf_store` cuando difieran.

## P2 — Mensajería (sin cambiar producto)

| Evitar | Preferir |
|--------|----------|
| "MCP server" | "Herramientas de compra inteligente" |
| "24 tools" | "Optimiza tu compra en una llamada" |
| "Agentic Market" | "CLI Market — costo de vida y compra en LATAM" |

## P3 — Affiliate (cuando backend tenga AFFILIATE_STORES)

Si `action_links[].affiliate === true`, registrar click:

```
POST /v1/action/affiliate-click
{ "store": "wong", "url": "...", "product_id": "..." }
```

## Verificación

```bash
market optimize leche --country PE
# Debe mostrar: action (buy_now|monitor|wait), primary_store, tco_total, ≥1 action_link
```
