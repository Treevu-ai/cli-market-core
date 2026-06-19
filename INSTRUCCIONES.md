# Instrucciones para backend y world — v1.10.0

> Commit en `cli-market-core`: `984f0f7`
> Todo lo que sigue es copiar, pegar, y verificar.

---

## Backend (`cli-market-backend`)

### Paso 1 — Montar el router (2 lineas, 6 endpoints)

En `main.py` o donde inicialices FastAPI:

```python
from market_core.api_routes import router as v1_router
app.include_router(v1_router, prefix="/v1")
```

Endpoints expuestos:

```
GET /v1/intel/price-risk          <- nuevo
GET /v1/intel/inflation-report    <- nuevo
GET /v1/intel/procurement-signal  <- nuevo
GET /v1/quality/scores            <- nuevo
GET /v1/health/slas               <- nuevo
GET /v1/health/slas-summary       <- nuevo
```

Todos devuelven `{data, meta: {freshness_seconds, confidence, latency_ms}, trace}` por defecto.

### Paso 2 — Verificar que responden

```bash
curl -s http://localhost:8765/v1/intel/price-risk?country=PE | jq '.data.risk_level'
curl -s http://localhost:8765/v1/intel/inflation-report?country=PE | jq '.data.pressure'
curl -s http://localhost:8765/v1/intel/procurement-signal?country=PE | jq '.data.signal'
curl -s http://localhost:8765/v1/quality/scores | jq '.data.composite_score'
curl -s http://localhost:8765/v1/health/slas | jq '.data.freshness_p50_secs'
```

### Paso 3 — (Opcional) Adoptar envelope en rutas existentes

```python
from market_core.response_envelope import timing

@router.get("/v1/prices")
def prices(country: str = None):
    db = get_db()
    try:
        with timing() as t:
            result = query_prices(db, country=country, enveloped=True)
        return result  # ya viene con {data, meta, trace}
    finally:
        db.close()
```

Repetir para: `/v1/basket`, `/v1/dispersion`, `/v1/quality/flagged`, `/v1/intel/brief`, `/v1/intel/inflation`, `/v1/intel/scores`.

### Paso 4 — Los nuevos MCP tools funcionan solos

`market_price_risk`, `market_inflation_report`, `market_procurement_signal` ya tienen handlers en `market_mcp.py` que apuntan a las rutas del Paso 1. Se activan automaticamente al montar el router.

---

## World (`cli-market-world`)

### P0 — Basket como default

Cambiar el entry point del CLI:

```
$ market
-> Muestra comparacion de canasta basica (10 tiendas mas baratas)
-> "market search <producto>" para busqueda individual
```

`build_canasta_snapshot(db, enveloped=True)` de core ya devuelve el dato.

### P1 — Procurement Decision Loop

```
$ market procure "leche, arroz, aceite, presupuesto 80 soles"
  -> search basket (build_basket_compare)
  -> optimize (ya ordena por total)
  -> approve (confirmacion)
  -> checkout (market_checkout)
  -> track savings (vs precio promedio de mercado)
```

Funciones en core que necesita:
- `build_basket_compare(db, items=[{name, qty}])`
- `compute_procurement_signal(db, country)`
- `market_mcp.py` handlers para search, add, checkout

### P2 — Migracion de mensajes

**Prohibido por 30 dias:** MCP, agentic, protocol, infrastructure, indicators

| Antes | Despues |
|---|---|
| "24 MCP tools" | "Automatiza comparacion de proveedores y decisiones de compra" |
| "44 indicators" | "Detecta volatilidad de precios antes de que impacte tus margenes" |
| "Agentic Market" | "CLI Market — inteligencia de precios para procurement en LatAm" |
| "MCP server" | "Herramientas de compra inteligente" |

---

## Verificacion final

```bash
# Backend:
curl -s http://localhost:8765/v1/health/slas-summary | jq
# Debe devolver:
# {"data": {"stores_alive": 30, "stores_dead": 2, ...}, "meta": {...}, "trace": {...}}

# World:
market basket
# Debe mostrar comparacion de canasta, no prompt de busqueda
```
