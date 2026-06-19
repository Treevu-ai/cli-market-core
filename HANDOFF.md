# HANDOFF — Sprint 1-3 Deliverables

> What changed in cli-market-core v1.10.0 and what the backend/world teams need to do.

## New modules

| Module | Purpose | Coverage |
|---|---|---|
| `market_core/response_envelope.py` | Canonical `{data, meta, trace}` envelope builder, freshness/confidence helpers, timing | 99% |
| `market_core/market_slas.py` | p50/p95 freshness per retailer, alive/dead, error rate | 100% |
| `market_core/market_quality.py` | Coverage freshness, unit normalization, match confidence, composite score | 100% |
| `market_core/market_intel_products.py` | Price risk, inflation report, procurement signal | 69% |

## Changed modules

| Module | Change |
|---|---|
| `data_v1_service.py` | `enveloped=False` on all data functions; `build_coverage_matrix` now includes `freshness_pct` per cell |
| `market_basket.py` | `enveloped=False` on existing functions; NEW: `build_basket_compare(items=[{name, qty}])` |
| `market_indicators.py` | `enveloped=False` on `get_latest_values` |
| `market_intel_agent.py` | Tier-based model (paid->Sonnet), max_tokens 4096, iterations 8, 3 new tools |
| `market_mcp_registry.py` | 3 new MCP tools: `market_price_risk`, `market_inflation_report`, `market_procurement_signal` |
| `market_mcp.py` | Handlers for 3 new MCP tools |
| `pyproject.toml` | Version 1.9.44 -> 1.10.0 |

## Backward compatibility

All data functions default to `enveloped=False`. Existing callers get exactly the same dicts.

## What the backend team needs to do

### 1. Adopt the response envelope

```python
from market_core.response_envelope import timing

# Before:
result = query_prices(db, country="PE")
# After:
with timing() as t:
    result = query_prices(db, country="PE", enveloped=True)
# result -> {data: [...], meta: {freshness_seconds, confidence, latency_ms}, trace: {...}}
```

Apply to: `/v1/prices`, `/v1/basket`, `/v1/dispersion`, `/v1/quality/flagged`, `/v1/intel/brief`, `/v1/intel/inflation`, `/v1/intel/scores`.

### 2. Add three new intel endpoints

```python
# GET /v1/intel/price-risk?country=PE&line=supermercados&days=7
from market_core.market_intel_products import compute_price_risk
result = compute_price_risk(db, country="PE", line="supermercados", days=7)

# GET /v1/intel/inflation-report?country=PE&days=30
from market_core.market_intel_products import compute_inflation_report
result = compute_inflation_report(db, country="PE", days=30)

# GET /v1/intel/procurement-signal?country=PE
from market_core.market_intel_products import compute_procurement_signal
result = compute_procurement_signal(db, country="PE")
```

MCP handlers in `market_mcp.py` already point at these paths.

### 3. Add data quality endpoint

```python
# GET /v1/quality/scores
from market_core.market_quality import build_data_quality_scores
scores = build_data_quality_scores(db, days=7)
```

### 4. Add SLA health endpoint

```python
# GET /health/slas
from market_core.market_slas import slas_by_retailer
result = slas_by_retailer(db)
```

### 5. Wire new MCP tools

The three new intel MCP tools are registered and have handlers. Once the backend exposes the endpoints from step 2, the tools work immediately.

## What the world team needs to do

- Make basket the default landing experience
- Ship the Procurement Decision Loop: search -> compare -> approve -> checkout -> track savings

## Test status

346 passed, 3 skipped, 0 failures. Coverage 59.46%.
