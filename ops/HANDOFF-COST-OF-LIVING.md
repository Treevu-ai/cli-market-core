# HANDOFF — Cost-of-Living OS (Waves 1–4)

> **Core:** `main` @ `8469854` (merge PR #75)  
> **Backend:** pin `cli-market-core @ …8469854` — ver `ops/ecosystem-patches/BUMP-CORE-8469854.md`

## North star

Un solo compound job para agentes y humanos:

**`optimize_household_purchase`** = affordability + basket compare + TCO (delivery) + substitutes + provenance + action closure.

REST: `POST /v1/missions/optimize-purchase`  
MCP: `market_optimize_purchase` (default profile, tier starter+)

---

## Waves entregadas

| Wave | Módulos / endpoints | MCP destacado |
|------|---------------------|---------------|
| **1** | `market_regulatory`, `market_tco`, `market_substitutes`, affordability | `market_affordability`, `market_substitutes` |
| **2** | `market_household`, `market_action_links`, optimize mission | `market_household_*`, `market_optimize_purchase` |
| **3** | `market_receipts`, `market_ecosystem`, `market_procurement_bulk` | `market_moat_confidence`, `market_ecosystem_radar`, `market_procurement_bulk` |
| **4** | Affiliate L3, handoff L4 stub, delivery TCO, provenance, flags | `include_action_links` en `market_basket` |

---

## REST `/v1/*` (montar con `api_routes.router`)

### Intel
```
GET  /v1/intel/affordability
GET  /v1/intel/regulatory
GET  /v1/intel/price-risk
GET  /v1/intel/inflation-report
GET  /v1/intel/procurement-signal
GET  /v1/products/substitutes
POST /v1/intel/procurement-bulk          # auth, enterprise
```

### Basket / TCO
```
POST /v1/basket/compare                # include_tco, include_action_links, include_delivery
GET  /v1/basket/tco?store=&items=&zipcode=
GET  /v1/basket                        # canasta snapshot (legacy)
```

### Household (auth)
```
GET|PUT|PATCH /v1/household
GET           /v1/household/summary
```

### Missions / action closure
```
POST /v1/missions/optimize-purchase
GET  /v1/export/shopping-list/{token}
POST /v1/action/affiliate-click        # observatory query_type=affiliate_click
```

### Crowd / ecosystem (wave 3)
```
POST /v1/receipts/submit
GET  /v1/receipts/{id}
GET  /v1/moat/confidence
GET  /v1/ecosystem/launches
```

Todas las rutas nuevas devuelven envelope `{data, meta, trace}` con `enveloped=True` por defecto. Wave 4 añadió `meta.provenance` en intel, household, missions, basket y wave 3.

---

## Auth

```python
from market_core import api_routes

api_routes._auth_fn = require_api_key  # tu callable (Authorization → username)
app.include_router(v1_router, prefix="/v1")
```

Household y procurement-bulk requieren usuario no-`anonymous` → **401**.

---

## Feature flags (env, default ON)

| Flag | Apaga |
|------|-------|
| `HOUSEHOLD_ENABLED=0` | `/v1/household/*` → 503 |
| `CROWD_RECEIPTS_ENABLED=0` | `/v1/receipts/submit` → 503 |
| `ECOSYSTEM_RADAR_ENABLED=0` | `/v1/ecosystem/launches` → 503 |
| `AFFILIATE_ENABLED=1` o `AFFILIATE_STORES=wong,metro` | UTMs en deeplinks L3 |
| `EXTERNAL_CART_HANDOFF_ENABLED=1` | Stub `external_cart_handoff` en action_links |

---

## MCP

- **57** tools registrados; **32** en perfil `default` (ver `public_tool_count("default")`).
- Handlers en `market_mcp.py` llaman HTTP vía `MARKET_API_URL`.
- `market_basket` → `POST /v1/basket/compare` con `include_tco`, `include_action_links`.
- `market_optimize_purchase` → `POST /v1/missions/optimize-purchase`.

---

## DB / seeds

`ensure_db_initialized()` crea tablas wave 1–3 y siembra:
- `regulatory_events` (≥3 eventos PE en DB vacía)
- `indicator_definitions`

SQLite local: schema incompleto vs PG (`canonical_product_id` en `price_snapshots`). Tests que usan price-risk añaden `ALTER TABLE` primero.

---

## Tests (CI)

```bash
CI=true MARKET_SKIP_LIVE=1 python3 -m pytest -q -m "not integration"
# 407 passed, coverage ~62%
```

---

## Pendiente fuera de core (otros repos)

| Item | Owner | Notas |
|------|-------|-------|
| World: `market optimize` / basket default | cli-market-world | Ver `ops/WORLD_CHANGES.md` |
| Provenance en `/v1/prices`, `/v1/dispersion` legacy | backend | `enveloped=True` + `build_provenance` |
| Live VTEX shipping sim | connectors | Hoy: defaults PE + optional live API |
| L4 partner API (Rappi/PedidosYa) | partnerships | Stub listo; contrato pendiente |
| Receipt PII policy | legal/ops | PRD checklist |
| PyPI release `1.11.0` | core | Dejar de git-pin cuando publiquen |

---

## Referencias

- PRD: `ops/PRD-COST-OF-LIVING-OS.md`
- Bump backend: `ops/ecosystem-patches/BUMP-CORE-8469854.md`
- Capabilities: `GET /v1/capabilities` → `commerce_capabilities.get_commerce_capabilities()`
