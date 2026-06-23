# HANDOFF — cli-market-core

> **Cost-of-Living OS (Waves 1–4):** ver **[ops/HANDOFF-COST-OF-LIVING.md](ops/HANDOFF-COST-OF-LIVING.md)** — documento canónico post PR #75 (`8469854`).

## Quick links

| Doc | Para quién |
|-----|------------|
| [HANDOFF-COST-OF-LIVING.md](ops/HANDOFF-COST-OF-LIVING.md) | Backend, agents, integradores |
| [BUMP-CORE-8469854.md](ops/ecosystem-patches/BUMP-CORE-8469854.md) | Railway / requirements pin |
| [WORLD_CHANGES.md](ops/WORLD_CHANGES.md) | cli-market-world (CLI + marketing) |
| [PRD-COST-OF-LIVING-OS.md](ops/PRD-COST-OF-LIVING-OS.md) | Producto / oleadas 1–4 |

## Legacy (Sprint 1-3, v1.10.0 pre–Cost-of-Living)

El contenido histórico de envelope + intel products (`price-risk`, `inflation-report`, `procurement-signal`) sigue vigente y está **incluido** en el handoff Cost-of-Living. Los endpoints v1 del sprint 1-3 viven en `market_core/api_routes.py` junto con las rutas wave 1–4.

### Mount mínimo (backend)

```python
from market_core.api_routes import router as v1_router
from market_core import api_routes

api_routes._auth_fn = require_api_key  # opcional
app.include_router(v1_router, prefix="/v1")
```

### Tests

```bash
CI=true MARKET_SKIP_LIVE=1 python3 -m pytest -q -m "not integration"
```
