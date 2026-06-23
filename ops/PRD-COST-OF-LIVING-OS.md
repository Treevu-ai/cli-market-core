# PRD — Cost-of-Living OS & Agent Commerce (Oleadas 1–3)

| Campo | Valor |
|-------|-------|
| **Estado** | Draft para revisión |
| **Versión** | 0.1 |
| **Paquete** | cli-market-core (+ backend mount, world MCP exposure) |
| **Base** | main @ v1.10.x |
| **Autores** | Product / Intelligence |

---

## 1. Resumen ejecutivo

CLI MARKET evoluciona de **inteligencia de precios retail** a **sistema operativo de costo de vida y compra** para humanos y agentes en LATAM. Este PRD concreta nueve capacidades en tres oleadas, con endpoints REST `/v1/*`, herramientas MCP, esquemas JSON, gating por tier y criterios de aceptación.

**Posicionamiento objetivo**

> *“La API que responde cuánto cuesta vivir, qué comprar, por qué confiar en el número, y qué hacer ahora — en LATAM.”*

**Principios de diseño**

1. Reutilizar moat existente (`price_snapshots`, `golden_taxonomy`, `market_units`, indicadores, envelope).
2. Toda respuesta pública v1 usa `{data, meta, trace}` (`response_envelope.envelope`).
3. Extender herramientas MCP existentes antes de crear nuevas; promover a perfil `default` solo lo que cierra tareas de agente.
4. Etiquetar siempre inflación/precios como **observados online**, no IPC oficial.
5. `confidence` y `provenance` son first-class en `meta` (no campos opcionales).

---

## 2. Objetivos y no-objetivos

### Objetivos (P0)

| ID | Objetivo | Oleada |
|----|----------|--------|
| O1 | Unificar canasta + salario + macro + contexto en **Affordability OS** | 1 |
| O2 | Exponer **precio real** (TCO) en compare/basket | 1 |
| O3 | Ofrecer **sustitutos** con trade-offs (precio, unidad, Nutri-Score) | 1 |
| O4 | Registrar y surfear **eventos regulatorios** en intel brief | 1 |
| O5 | Persistir **perfil de hogar** para agentes multi-sesión | 2 |
| O6 | Promover **misiones** como tool MCP default | 2 |
| O7 | Estandarizar **provenance** en envelope | 2 |
| O8 | **Cierre de acción** L1–L2 (deep link + lista exportable) | 2 |
| O9 | Flywheel **boleta/crowd** → confianza del moat | 3 |
| O10 | **Ecosystem radar** para builders | 3 |
| O11 | **Procurement B2B** bulk | 3 |
| O12 | **Action closure** L3+ (afiliación/partners) | 3 |

### No-objetivos (explícito)

- Fulfillment real en sitios de retailers (sin acuerdo comercial).
- Listings de alquiler, educación, turismo, trading financiero.
- Scraping agresivo de apps cerradas (Rappi/PedidosYa) sin API partner.
- Product Hunt u otras fuentes como producto consumer-facing en oleada 1.
- Reemplazar IPC oficial ni SUNAT como autoridad fiscal.

---

## 3. Personas

| Persona | Necesidad | Tools principales |
|---------|-----------|-------------------|
| **Agente MCP (builder)** | JSON estable, cierre de tarea, poca ambigüedad | `market_optimize_purchase`, `market_affordability`, TCO en compare |
| **Humano LATAM** | Ahorro en moneda local, tranquilidad mensual | Affordability brief, alertas presupuesto |
| **Analista fintech/research** | Inflación alternativa auditable | `market_affordability`, regulatory context, export |
| **Comprador B2B (trade)** | Lista 50+ SKUs, señal buy/wait | `market_procurement_bulk` |
| **Ops CLI MARKET** | Priorizar connectors | `market_ecosystem_radar` (admin) |

---

## 4. Matriz de tiers

| Capacidad | free | starter | pro | enterprise |
|-----------|------|---------|-----|------------|
| Affordability OS (resumen) | ✓ país | ✓ | ✓ + línea | ✓ + bulk |
| TCO en compare/basket | preview (sin delivery) | ✓ | ✓ completo | ✓ |
| Sustitución (3 alternativas) | 1 alternativa | ✓ | ✓ + OFF | ✓ |
| Regulatory context | headline | ✓ | ✓ | ✓ + webhook |
| Household profile | — | lectura | ✓ CRUD | ✓ org |
| `market_optimize_purchase` | — | ✓ | ✓ | ✓ |
| Deep links / export lista | — | ✓ | ✓ | ✓ |
| Receipt crowd submit | — | ✓ | ✓ | ✓ |
| Ecosystem radar | — | — | ✓ | ✓ |
| B2B bulk procurement | — | — | — | ✓ |

---

## 5. Extensiones transversales

### 5.1 `meta.provenance` (oleada 2, adoptar en oleada 1 donde aplique)

Extensión de `response_envelope.envelope(..., extra_meta=)`:

```json
{
  "meta": {
    "freshness_seconds": 28800,
    "confidence": "ok",
    "latency_ms": 142.3,
    "provenance": {
      "primary_source": "price_snapshots",
      "sources_used": ["price_snapshots", "open.er-api.com", "worldbank"],
      "stores_responded": 8,
      "stores_queried": 12,
      "coverage_pct": 66.7,
      "staleness_warning": false,
      "methodology": "shelf_observed_online_v1"
    }
  }
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `primary_source` | string | Fuente dominante del payload |
| `sources_used` | string[] | Todas las fuentes |
| `stores_responded` | int? | Retailers con precio válido |
| `stores_queried` | int? | Retailers intentados |
| `coverage_pct` | float? | responded/queried × 100 |
| `staleness_warning` | bool | true si freshness > SLA de línea |
| `methodology` | string | Slug de metodología auditable |

### 5.2 Nuevas tablas (todas las oleadas)

```sql
-- Oleada 1
CREATE TABLE regulatory_events (
  id TEXT PRIMARY KEY,
  country TEXT NOT NULL,
  category TEXT NOT NULL,        -- food, energy, fx, pharma, transport
  title TEXT NOT NULL,
  summary TEXT,
  effective_at TEXT,
  source_url TEXT,
  created_at TEXT NOT NULL
);

-- Oleada 2
CREATE TABLE household_profiles (
  username TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL,    -- schema household v1
  updated_at TEXT NOT NULL
);

-- Oleada 3
CREATE TABLE receipt_submissions (
  id TEXT PRIMARY KEY,
  username TEXT,
  country TEXT,
  store TEXT,
  image_url TEXT,
  ocr_json TEXT,
  moat_diff_json TEXT,
  status TEXT NOT NULL,          -- pending, confirmed, rejected
  created_at TEXT NOT NULL
);

CREATE TABLE ecosystem_launches_cache (
  cache_key TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);
```

---

## 6. Oleada 1 — Profundizar moat (sin partners)

### 6.1 Affordability OS

#### User stories

- Como **humano en PE**, quiero saber cuántas canastas básicas cuesta mi salario mínimo este mes.
- Como **agente fintech**, quiero un JSON con `affordability_score`, gaps y señales en un solo GET.
- Como **analista**, quiero ver gap góndola vs IPC oficial con metodología explícita.

#### REST

```
GET /v1/intel/affordability?country=PE&line=supermercados&days=30
```

**Query params**

| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `country` | string | requerido | PE, AR, MX, BR, CO, CL |
| `line` | string | supermercados | Línea de negocio |
| `days` | int | 30 | Ventana inflación/momentum |
| `include_services` | bool | false | v1.1: índices utilities (OSINERGMIN, etc.) |

#### Response `data` schema

```json
{
  "question": "How affordable is daily life this month?",
  "country": "PE",
  "line": "supermercados",
  "days": 30,
  "affordability_score": 62,
  "affordability_band": "strained",
  "affordability_band_es": "presionado",
  "headline_es": "La canasta mínima representa 38% del salario mínimo; la góndola subió más rápido que el IPC oficial en 2.1 pp.",
  "components": {
    "canasta_min_pen": 312.4,
    "canasta_currency": "PEN",
    "canasta_stores_compared": 3,
    "minimum_wage_pen": 1130.0,
    "canastas_per_minimum_wage": 3.62,
    "real_wage_basket_ratio": 2.89,
    "basket_stress_index": 108.2,
    "internal_inflation_pct": 4.1,
    "staple_momentum_7d_pct": 1.2,
    "vs_official_cpi_gap_pp": 2.1,
    "food_inflation_spread": 0.8
  },
  "signals": {
    "price_dispersion_pct": 12.4,
    "promo_intensity_pct": 18.0,
    "search_momentum": 1.15,
    "gtrends_search_momentum": 1.08
  },
  "regulatory_headlines": [],
  "disclaimer_es": "Precios observados en tiendas online indexadas; no reemplaza el IPC INEI ni encuestas de hogares."
}
```

**`affordability_band` enum:** `comfortable` | `moderate` | `strained` | `critical`

**Lógica de score (0–100, documentada):**

```
score = clamp(100 - basket_stress_index + real_wage_basket_ratio * 5 - max(0, gap_pp) * 3, 0, 100)
```

Implementación: composición de `compute_basket_stress`, `get_latest_values`, `compute_inflation_report`, `golden_taxonomy.min_canasta_prices_golden` con fallback a `market_basket`.

#### MCP

| Acción | Tool |
|--------|------|
| **Nuevo** | `market_affordability` |
| **Extender** | `market_intel_brief` — incluir sección `affordability` (summary) por defecto |

**`market_affordability` inputSchema**

```json
{
  "type": "object",
  "properties": {
    "country": { "type": "string", "description": "PE, AR, MX, BR, CO, CL" },
    "line": { "type": "string", "default": "supermercados" },
    "days": { "type": "integer", "default": 30 }
  },
  "required": ["country"]
}
```

**Registry meta:** `bundle=intel`, `order=2`, `icp=[research,fintech,trade,builder]`, `min_tier=free`

#### Criterios de aceptación

- [ ] CA-A1: `GET /v1/intel/affordability?country=PE` retorna envelope con `data.affordability_score` ∈ [0,100].
- [ ] CA-A2: SQLite vacío retorna score con `confidence=low` y `canasta_min_pen=null`, sin 500.
- [ ] CA-A3: `market_intel_brief` incluye `data.affordability.summary` sin romper callers existentes.
- [ ] CA-A4: Tests offline con `CI=true MARKET_SKIP_LIVE=1`.
- [ ] CA-A5: Disclaimer en español siempre presente.

---

### 6.2 TCO — Total Cost of Ownership

#### User stories

- Como **agente**, al comparar leche quiero `tco_total` = precio + delivery prorrateado + fee pago.
- Como **humano**, quiero ver el retailer más barato **en la práctica**, no solo en etiqueta.

#### REST

Extender respuestas existentes (no endpoint nuevo obligatorio):

```
POST /v1/basket/compare          → añadir tco por store
POST /products/compare           → añadir tco por store (backend legacy path)
GET  /v1/basket/tco              → opcional: TCO explícito para lista dada
```

**`GET /v1/basket/tco`**

```
GET /v1/basket/tco?country=PE&store=wong&items=[{"name":"leche","qty":2}]
```

**Response `data`**

```json
{
  "country": "PE",
  "store": "wong",
  "currency": "PEN",
  "line_items": [
    {
      "name": "leche",
      "qty": 2,
      "unit_price": 4.2,
      "subtotal": 8.4,
      "product_id": "123",
      "unit_normalized": { "price_per_l": 4.2, "pack_l": 1.0 }
    }
  ],
  "subtotal_shelf": 8.4,
  "delivery": {
    "fee": 7.0,
    "min_order": 50.0,
    "min_order_gap": 41.6,
    "available": true,
    "source": "vtex_shipping_simulation"
  },
  "payment": {
    "method": "yape",
    "fee_pct": 0.0,
    "fee_amount": 0.0
  },
  "fx": null,
  "tco_total": 15.4,
  "tco_per_item": 7.7,
  "cheapest_shelf_store": "metro",
  "cheapest_tco_store": "wong",
  "tco_vs_shelf_delta_pct": 83.3
}
```

**Reglas v1**

| Componente | Fuente | Fallback |
|------------|--------|----------|
| Shelf | `price_snapshots` / search | — |
| Unit norm | `market_units.price_per_base_unit` | omitir si no parsea |
| Delivery | `market_delivery` / VTEX sim | `delivery.available=false`, TCO=shelf |
| Payment fee | `commerce_capabilities` static table | 0% Yape/Plin |
| FX | `fx_usd_local` si store currency ≠ país | null |

#### MCP

| Acción | Tool |
|--------|------|
| **Extender** | `market_basket` — param `include_tco: bool` (default false free, true pro) |
| **Extender** | `market_compare` — param `include_tco: bool` |
| **Nuevo (opcional)** | `market_tco` |

#### Criterios de aceptación

- [ ] CA-T1: Con delivery no disponible, `tco_total === subtotal_shelf`.
- [ ] CA-T2: `meta.provenance.sources_used` incluye `delivery` cuando se usa.
- [ ] CA-T3: Starter+ puede setear `payment.method`; free ignora y usa yape/0%.
- [ ] CA-T4: Documentar en `commerce_capabilities` el alcance TCO.

---

### 6.3 Sustitución y equivalencia

#### User stories

- Como **agente**, si no hay SKU exacto, quiero hasta 3 sustitutos con `save_pct` y trade-off Nutri-Score.
- Como **humano**, quiero la opción más barata **por litro/kg** comparable.

#### REST

```
GET /v1/products/substitutes?country=PE&query=leche+gloria&store=wong&limit=3
POST /v1/products/substitutes   body: { query, country, store?, constraints? }
```

**`constraints` (opcional)**

```json
{
  "max_nova": 3,
  "min_nutriscore": "C",
  "same_canasta_item": true,
  "max_price_delta_pct": 30
}
```

**Response `data`**

```json
{
  "query": "leche gloria",
  "country": "PE",
  "original": {
    "product_id": "111",
    "name": "Leche Gloria Entera Bolsa 1L",
    "store": "wong",
    "price": 4.5,
    "price_per_l": 4.5,
    "canonical_product_id": "can:leche-entera-1l",
    "in_stock": true
  },
  "substitutes": [
    {
      "product_id": "222",
      "name": "Leche Laive Entera 1L",
      "store": "metro",
      "price": 3.9,
      "price_per_l": 3.9,
      "save_pct": 13.3,
      "match_reason": "same_canasta_item+unit_equivalent",
      "canonical_product_id": "can:leche-entera-1l",
      "off": { "nutriscore": "B", "nova_group": 1 },
      "tradeoffs": {
        "nutriscore_delta": 0,
        "nova_delta": 0,
        "brand_change": true
      },
      "confidence": "ok"
    }
  ],
  "method": "golden_taxonomy+unit_norm+fuzzy_name"
}
```

**Pipeline v1**

1. Resolver query → candidatos (`market_search`).
2. Agrupar por `canonical_product_id` (`golden_taxonomy`).
3. Normalizar unidad (`market_units`); descartar packs no estándar si `same_canasta_item`.
4. Filtrar por `constraints`; enriquecer top-N con OFF (`resolve_off_for_product`).
5. Ordenar por `price_per_base_unit` ascendente.

#### MCP

| Acción | Tool |
|--------|------|
| **Nuevo** | `market_substitutes` |
| **Extender** | `market_search` — flag `include_substitutes_if_empty: bool` |

**Registry:** `bundle=shop`, `order=4.5` (entre compare y add), `min_tier=free` (1 result) / `starter` (3 results)

#### Criterios de aceptación

- [ ] CA-S1: Sin golden registry, fallback fuzzy + unit norm; `method` lo declara.
- [ ] CA-S2: Nunca retornar sustituto con `nova_delta > 1` si `constraints.max_nova=3` violado.
- [ ] CA-S3: Latencia p95 < 8s con `MARKET_SKIP_LIVE=1` fixture DB.
- [ ] CA-S4: Respuesta vacía es `substitutes: []`, no error.

---

### 6.4 Regulatory context layer

#### User stories

- Como **analista**, quiero ver eventos regulatorios que explican movimientos de precio.
- Como **agente**, quiero `regulatory_headlines` en affordability e inflation report.

#### REST

```
GET /v1/intel/regulatory?country=PE&days=90&category=food
POST /v1/admin/regulatory/events     (enterprise/admin — carga curada)
```

**Response `data`**

```json
{
  "country": "PE",
  "days": 90,
  "events": [
    {
      "id": "reg-pe-2026-001",
      "category": "energy",
      "title": "Ajuste tarifario eléctrico segmento B",
      "summary": "Incremento promedio 4.2% desde marzo 2026.",
      "effective_at": "2026-03-01",
      "impact_hint": "upward_cost_pressure",
      "source_url": "https://...",
      "lines_affected": ["hogar"]
    }
  ]
}
```

**Integración:** `compute_inflation_report` y affordability incluyen `regulatory_headlines: events[:3]`.

#### MCP

| Acción | Tool |
|--------|------|
| **Extender** | `market_inflation_report`, `market_affordability` |
| **Admin** | `market_regulatory_ingest` (perfil admin, enterprise) |

#### Criterios de aceptación

- [ ] CA-R1: País sin eventos → `events: []`.
- [ ] CA-R2: Eventos ordenados por `effective_at` desc.
- [ ] CA-R3: Seed inicial manual: ≥3 eventos PE, ≥2 AR para demo.

---

## 7. Oleada 2 — Agent OS sticky

### 7.1 Household profile

#### REST

```
GET  /v1/household
PUT  /v1/household
PATCH /v1/household
```

**`household` schema v1**

```json
{
  "version": 1,
  "size": 4,
  "country": "PE",
  "currency": "PEN",
  "budget_monthly": 2500.0,
  "budget_period_start_day": 1,
  "restrictions": {
    "celiac": false,
    "lactose_free": true,
    "vegetarian": false
  },
  "default_stores": ["wong", "metro"],
  "default_line": "supermercados",
  "staple_list": [
    { "name": "leche", "qty": 8, "unit": "L" },
    { "name": "arroz", "qty": 2, "unit": "kg" }
  ],
  "cadence_days": { "supermercado": 15 },
  "goals": ["ahorrar_10pct"]
}
```

**Derived (read-only, `GET /v1/household/summary`)**

```json
{
  "budget_remaining": 890.0,
  "budget_spent_mtd": 1610.0,
  "days_left_in_period": 12,
  "projected_overspend_pct": 0.0,
  "suggested_action": "monitor"
}
```

`budget_spent_mtd` = sum órdenes CLI MARKET + estimado canasta si no hay órdenes.

#### MCP

| Acción | Tool |
|--------|------|
| **Nuevo** | `market_household_get` |
| **Nuevo** | `market_household_update` |
| **Extender** | `market_preferences` — deprecar a favor de household; alias |

**Gating:** lectura starter+, escritura pro+.

#### Criterios de aceptación

- [ ] CA-H1: PUT valida schema; 422 si `budget_monthly < 0`.
- [ ] CA-H2: Restrictions aplican a `market_substitutes` cuando `household_id` en sesión.
- [ ] CA-H3: Sin auth → 401 en todos los endpoints household.

---

### 7.2 `market_optimize_purchase` (misión compuesta)

Reemplaza el patrón fragmentado search → compare → intel → cart para agentes.

#### REST

```
POST /v1/missions/optimize-purchase
```

**Request**

```json
{
  "country": "PE",
  "items": [{ "name": "leche", "qty": 2 }, { "name": "arroz", "qty": 1 }],
  "constraints": {
    "max_budget": 50.0,
    "preferred_stores": ["wong", "metro"],
    "include_tco": true,
    "allow_substitutes": true
  },
  "include_intel": true,
  "output_format": "agent"
}
```

**Response `data`**

```json
{
  "mission": "optimize_purchase",
  "status": "ok",
  "recommendation": {
    "action": "buy_now",
    "primary_store": "metro",
    "currency": "PEN",
    "shelf_total": 42.1,
    "tco_total": 49.1,
    "budget_headroom": 0.9,
    "rationale_es": "Metro lidera TCO; presión inflacionaria moderada en arroz."
  },
  "items_resolved": [
    {
      "requested": "leche",
      "qty": 2,
      "resolved_product_id": "222",
      "resolved_name": "Leche Laive 1L",
      "substituted": true,
      "unit_price": 3.9
    }
  ],
  "sections": {
    "compare": { },
    "tco": { },
    "procurement_signal": { },
    "affordability_context": { }
  },
  "action_links": [
    {
      "type": "retailer_deeplink",
      "store": "metro",
      "url": "https://www.metro.pe/...",
      "affiliate": false
    },
    {
      "type": "export_list",
      "url": "https://api.../v1/export/list/{token}",
      "format": "json"
    }
  ]
}
```

Implementación: evolución de `market_missions.run_investigate` + TCO + substitutes + `compute_procurement_signal` + household budget check.

#### MCP

| Acción | Tool |
|--------|------|
| **Nuevo** | `market_optimize_purchase` — **promover a perfil `default`** |
| **Mantener** | investigate interno como alias admin |

**Registry:** `bundle=shop`, `order=3`, `pairs_with=[market_basket, market_substitutes, market_affordability]`, `min_tier=starter`

#### Criterios de aceptación

- [ ] CA-O1: Un solo call MCP reemplaza ≥3 calls (search+compare+procurement) en happy path.
- [ ] CA-O2: `action_links` siempre presente (mínimo `export_list`).
- [ ] CA-O3: Si `budget_headroom < 0`, `action=wait` con rationale.

---

### 7.3 Provenance en envelope (rollout completo)

#### Alcance

Aplicar `meta.provenance` a:

- `/v1/intel/*`
- `/v1/basket/*`
- `/v1/prices`
- `/v1/products/substitutes`
- `/v1/missions/*`

#### Criterios de aceptación

- [ ] CA-P1: OpenAPI documenta `provenance` en `meta`.
- [ ] CA-P2: `confidence=low` si `coverage_pct < 40`.

---

### 7.4 Action closure L1–L2

#### L1 — Deep links

Generar URL de producto/categoría en retailer cuando el conector exponga `base` + slug o patrón VTEX:

```json
{
  "type": "retailer_deeplink",
  "store": "wong",
  "product_id": "123",
  "url": "https://www.wong.pe/...",
  "expires_at": null
}
```

Sin URL válida → omitir entry; nunca inventar.

#### L2 — Lista exportable

```
POST /v1/export/shopping-list
GET  /v1/export/shopping-list/{token}
```

Token TTL 72h, starter+.

**Payload exportado**

```json
{
  "title": "Lista optimizada CLI MARKET",
  "country": "PE",
  "store": "metro",
  "currency": "PEN",
  "items": [...],
  "totals": { "shelf": 42.1, "tco": 49.1 },
  "generated_at": "2026-06-23T12:00:00Z",
  "disclaimer": "Precios observados; verificar en tienda."
}
```

#### MCP

Extender `market_optimize_purchase` y `market_basket` con `include_action_links: bool`.

#### Criterios de aceptación

- [ ] CA-AC1: Deep link solo si `store` en `STORES` y patrón conocido.
- [ ] CA-AC2: Export token single-use opcional (enterprise).

---

## 8. Oleada 3 — Red y escala

### 8.1 Receipt / crowd truth

#### REST

```
POST /v1/receipts/submit        { "url": "...", "country": "PE" }
GET  /v1/receipts/{id}
GET  /v1/moat/confidence?product_id=&store=   → crowd confirmation score
```

**Response submit `data`**

```json
{
  "id": "RCP-ABC123",
  "status": "pending",
  "ocr": {
    "store": "Wong",
    "date": "2026-06-22",
    "total": 87.4,
    "line_items": [{ "name": "Leche Gloria 1L", "qty": 2, "unit_price": 4.8 }]
  },
  "moat_diff": [
    {
      "name": "Leche Gloria 1L",
      "receipt_price": 4.8,
      "moat_price": 4.2,
      "delta_pct": 14.3,
      "flag": "receipt_higher"
    }
  ],
  "contribution": {
    "updates_moat_confidence": true
  }
}
```

**Moat confidence extension** (`market_quality`):

```json
{
  "product_id": "111",
  "store": "wong",
  "crowd_confirmations_7d": 4,
  "crowd_conflicts_7d": 1,
  "confidence_tier": "verified"
}
```

#### MCP

| Acción | Tool |
|--------|------|
| **Extender** | `market_ticket` — añadir `submit_to_crowd: bool` |
| **Nuevo** | `market_moat_confidence` (advanced) |

#### Criterios de aceptación

- [ ] CA-C1: OCR fallido → `status=failed`, sin actualizar moat.
- [ ] CA-C2: PII en imagen — no persistir imagen raw >7d (ephemeral URL only).
- [ ] CA-C3: ≥5 receipts confirman precio → `confidence_tier=verified` en quality scores.

---

### 8.2 Ecosystem radar

#### REST

```
GET /v1/ecosystem/launches?topic=food&days=7&limit=20
```

Fuentes v1: cache curada + Product Hunt API (server-side, no exposición directa de token al cliente).

**Response `data`**

```json
{
  "topic": "food",
  "days": 7,
  "launches": [
    {
      "name": "Example Grocery AI",
      "tagline": "...",
      "votes": 120,
      "url": "https://producthunt.com/posts/...",
      "relevance": "grocery_latam",
      "suggested_integration": "connector_candidate"
    }
  ],
  "sources": ["producthunt", "manual_curated"],
  "disclaimer": "Ecosystem signal only; not price data."
}
```

#### MCP

`market_ecosystem_radar` — perfil `full`/`admin`, `min_tier=pro`.

**Requisito legal:** acuerdo PH si uso comercial en producción.

---

### 8.3 B2B procurement bulk

#### REST

```
POST /v1/intel/procurement-bulk
```

**Request**

```json
{
  "country": "PE",
  "organization_id": "org-123",
  "lines": [
    { "sku_query": "arroz costeño 50kg", "qty": 10, "unit": "kg" }
  ],
  "include_substitutes": true,
  "output": "csv_url"
}
```

**Response:** señal agregada + per-line `buy_now|monitor|wait` + spread + export URL.

#### MCP

`market_procurement_bulk` — enterprise, `requires_auth=true`.

---

### 8.4 Action closure L3+

| Nivel | Requisito | Entregable |
|-------|-----------|------------|
| L3 Afiliación | Acuerdo comercial | `affiliate: true` en deeplink + UTM |
| L4 Partner API | Contrato Rappi/PedidosYa/etc. | `external_cart_handoff` en action_links |
| L5 Fulfillment | Legal + ops | Fuera de scope v1.x |

PRD L3 mínimo: campo `action_links[].affiliate` + reporting en observatory (`query_type=affiliate_click`).

---

## 9. Mapa MCP consolidado

| Tool | Oleada | Acción | Perfil default |
|------|--------|--------|----------------|
| `market_affordability` | 1 | Nuevo | Sí |
| `market_substitutes` | 1 | Nuevo | Sí |
| `market_tco` | 1 | Nuevo (opcional) | No (advanced) |
| `market_basket` | 1 | Extender `include_tco` | Sí |
| `market_compare` | 1 | Extender `include_tco` | Sí |
| `market_intel_brief` | 1 | Extender affordability + regulatory | Sí |
| `market_inflation_report` | 1 | Extender regulatory | Sí |
| `market_household_get` | 2 | Nuevo | No (account) |
| `market_household_update` | 2 | Nuevo | No (account) |
| `market_optimize_purchase` | 2 | Nuevo | **Sí** |
| `market_ticket` | 3 | Extender crowd | Sí (ya) |
| `market_ecosystem_radar` | 3 | Nuevo | No |
| `market_procurement_bulk` | 3 | Nuevo | No |
| `market_moat_confidence` | 3 | Nuevo | No |

**Conteo perfil default:** 24 → **27** (affordability, substitutes, optimize_purchase). Actualizar copy en world (`WORLD_CHANGES.md` pattern).

---

## 10. Dependencias entre equipos

| Entregable | Owner | Depende de |
|------------|-------|------------|
| Endpoints `/v1/intel/affordability` | core + backend mount | `market_intel_products` nuevo `compute_affordability` |
| TCO shipping | core | VTEX connector shipping sim |
| Substitutes | core + index | `cli-market-index` registry freshness |
| Regulatory admin | ops/content | Seed manual eventos |
| Household DB | core + backend | Auth middleware |
| optimize-purchase | core | Oleada 1 completa |
| Deep links | connectors | URL patterns por platform |
| Receipt crowd | core + backend | Storage ephemeral imágenes |
| PH radar | core | `PRODUCT_HUNT_TOKEN`, legal OK |

---

## 11. Métricas de éxito

| Métrica | Baseline | Target oleada 1 | Target oleada 2 |
|---------|----------|-----------------|-----------------|
| MCP calls/session (agente) | ~3.2 | — | ≥2.0 (menos = más compuesto) |
| `market_optimize_purchase` adoption | 0 | — | ≥15% sesiones pro |
| p95 `optimize-purchase` latency | — | — | <12s PE |
| NPS rationale “confío en el precio” | — | +10pp | +20pp |
| Conversión free→starter | — | +5% | +8% |
| `coverage_pct` medio en responses | — | documentado | ≥55% |
| Receipts submitted / mes | 0 | — | 500 (oleada 3) |

**Observatory:** nuevos `query_type`: `affordability`, `tco`, `substitute`, `optimize`, `receipt_crowd`, `ecosystem`.

---

## 12. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Sustituto incorrecto | Alto | `confidence`, límites NOVA, disclaimer, feedback loop receipts |
| TCO delivery stale | Medio | `delivery.available`, freshness en meta |
| Affordability overclaim | Alto | disclaimer_es obligatorio, bandas no “precisión falsa” |
| PH API comercial | Legal | Cache + uso interno hasta acuerdo |
| Household PII | Alto | Encriptación at-rest, export/delete endpoint |
| Scope creep B2B | Medio | Enterprise only, catálogo separado |

---

## 13. Plan de rollout

### Fase 1a (core library)

- `compute_affordability`, TCO helpers, `find_substitutes`, `regulatory_events` CRUD
- Tests pytest offline, coverage gate 55%
- MCP registry + handlers en `market_mcp.py`

### Fase 1b (backend)

- Mount endpoints en `api_routes.py`
- `enveloped=True` en rutas nuevas
- OpenAPI publish

### Fase 2 (world)

- Bump default profile tools 24→27
- CLI `market optimize` command (opcional)
- Docs en cli-market.dev

### Fase 3 (oleada 2–3)

- Feature flags: `HOUSEHOLD_ENABLED`, `CROWD_RECEIPTS_ENABLED`, `ECOSYSTEM_RADAR_ENABLED`

---

## 14. Checklist de release (por oleada)

### Oleada 1 — Go/No-Go

- [ ] OpenAPI `/v1/intel/affordability`, `/v1/products/substitutes`
- [ ] `market_affordability`, `market_substitutes` en MCP default
- [ ] TCO en basket/compare documentado en `commerce_capabilities`
- [ ] ≥3 regulatory events seed PE
- [ ] HANDOFF actualizado para backend team
- [ ] WORLD_CHANGES si cambia default tool count

### Oleada 2 — Go/No-Go

- [ ] `market_optimize_purchase` p95 <12s en staging
- [ ] Household CRUD + auth
- [ ] `meta.provenance` en ≥80% endpoints v1 intel/shop
- [ ] Deep links ≥2 retailers PE validados manualmente

### Oleada 3 — Go/No-Go

- [ ] Legal PH o radar solo curado manual
- [ ] Receipt PII policy publicada
- [ ] Enterprise procurement bulk con 1 piloto org

---

## 15. Apéndice — OpenAPI sketch (affordability)

```yaml
/v1/intel/affordability:
  get:
    summary: Affordability OS — cost of living composite
    parameters:
      - name: country
        in: query
        required: true
        schema: { type: string, enum: [PE, AR, MX, BR, CO, CL] }
      - name: line
        in: query
        schema: { type: string, default: supermercados }
      - name: days
        in: query
        schema: { type: integer, default: 30 }
    responses:
      "200":
        description: Enveloped affordability report
        content:
          application/json:
            schema:
              type: object
              properties:
                data: { $ref: "#/components/schemas/AffordabilityReport" }
                meta: { $ref: "#/components/schemas/ResponseMeta" }
                trace: { $ref: "#/components/schemas/ResponseTrace" }
```

---

*Fin del PRD v0.1. Siguiente paso sugerido: estimación técnica por módulo core y ticket breakdown en Linear/GitHub Issues por CA-*.*
