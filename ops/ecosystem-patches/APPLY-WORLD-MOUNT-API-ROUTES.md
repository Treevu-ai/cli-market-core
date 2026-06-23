# Mount `market_core.api_routes` — cli-market-world (production Wave 4)

Patch: `cli-market-world-mount-api-routes.patch` (commit `e60b9ab`)

## Problem

World `market_server.py` served legacy routers only. Production returned **404** for:

- `POST /v1/missions/optimize-purchase`
- `GET /v1/intel/affordability`
- `POST /v1/action/affiliate-click`

CLI `market optimize` and MCP `market_optimize_purchase` depend on these routes.

## What the patch does

| Change | Detail |
|--------|--------|
| **`market_server.py`** | Mount `market_core.api_routes` with `prefix="/v1"` after world routers |
| **Auth** | `api_routes._auth_fn = require_api_key` |
| **`Dockerfile`** | `CACHE_BUST=2026-06-23-core-8469854` to force Railway rebuild |

World handlers keep precedence on duplicate paths (e.g. `POST /v1/basket/compare` in `routers/search.py`). New Wave 1–4 routes from core are added without breaking existing behavior.

## Apply

```bash
cd cli-market-world
git checkout main && git pull origin main
git checkout -b cursor/mount-api-routes-9eee
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-mount-api-routes.patch
# or if git am fails:
git apply --3way ../cli-market-core/ops/ecosystem-patches/cli-market-world-mount-api-routes.patch
git add -A && git commit -m "feat(server): mount core api_routes for Wave 4 production"
git push -u origin cursor/mount-api-routes-9eee
```

PR: https://github.com/Treevu-ai/cli-market-world/compare/main...cursor/mount-api-routes-9eee

## Post-deploy smoke

```bash
API=https://cli-market-production.up.railway.app

# Was 404 — should be 401 without token or 200 with Bearer sk-...
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/v1/missions/optimize-purchase" \
  -H "Content-Type: application/json" \
  -d '{"country":"PE","items":[{"name":"leche","qty":1}]}'

curl -s -o /dev/null -w "%{http_code}\n" "$API/v1/intel/affordability?country=PE"

# With API key:
curl -s "$API/v1/missions/optimize-purchase" -X POST \
  -H "Authorization: Bearer $MARKET_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"country":"PE","items":[{"name":"leche","qty":2}],"constraints":{"include_tco":true}}' \
  | jq '.meta.provenance.methodology,.data.status'
```

## Tests

```bash
python3 -m pytest -q tests/test_market_optimize_cli.py
```
