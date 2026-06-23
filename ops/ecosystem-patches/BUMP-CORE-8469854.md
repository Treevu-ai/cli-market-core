# Bump cli-market-core → 8469854 (Wave 4 — action closure + delivery TCO)

Aplica en **cli-market-backend** para exponer Waves 1–4 en Railway/local.

## Cambio

`requirements.txt`:

```text
cli-market-core @ git+https://github.com/Treevu-ai/cli-market-core.git@8469854
```

`Dockerfile` y `Dockerfile.collector` (si aplica):

```text
CACHE_BUST=2026-06-23-core-8469854
```

## Smoke post-deploy

```bash
API=https://cli-market-production.up.railway.app

# Wave 1 — affordability
curl -s "$API/v1/intel/affordability?country=PE" | jq '.data.affordability_score,.meta.provenance'

# Wave 2 — household (401 sin auth)
curl -s -o /dev/null -w "%{http_code}\n" "$API/v1/household"

# Wave 4 — basket compare + TCO delivery
curl -s "$API/v1/basket/compare" -X POST -H "Content-Type: application/json" \
  -d '{"country":"PE","items":[{"name":"leche","qty":2}],"include_tco":true,"include_action_links":true}' \
  | jq '.data.stores[0].tco.delivery,.data.action_links'

# Wave 4 — affiliate telemetry
curl -s "$API/v1/action/affiliate-click" -X POST -H "Content-Type: application/json" \
  -d '{"store":"wong","url":"https://www.wong.pe/test/p","country":"PE"}' | jq '.data.recorded'
```

## Env vars opcionales (Railway)

| Variable | Default | Uso |
|----------|---------|-----|
| `AFFILIATE_STORES` | — | `wong,metro` para UTMs L3 |
| `AFFILIATE_ENABLED` | `0` | Toggle global afiliación |
| `EXTERNAL_CART_HANDOFF_ENABLED` | `0` | Stub L4 partner handoff |
| `HOUSEHOLD_ENABLED` | `1` | Apagar household → 503 |
| `CROWD_RECEIPTS_ENABLED` | `1` | Apagar receipts → 503 |
| `ECOSYSTEM_RADAR_ENABLED` | `1` | Apagar radar → 503 |

## Local (PowerShell)

```powershell
pip install "cli-market-core @ git+https://github.com/Treevu-ai/cli-market-core.git@8469854"
# reiniciar market_server.py
```

## Historial

| SHA | Contenido |
|-----|-----------|
| `7dfe4b6` | Pre Cost-of-Living |
| `1ed299e` | Waves 1–3 + market_matcher |
| `8469854` | Wave 4: L3 affiliate, L4 stub, delivery TCO, provenance rollout, feature flags |

Relacionado: cli-market-core PR #70–#75.
