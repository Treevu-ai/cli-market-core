# Bump cli-market-core → 1ed299e (backend + collector)

Aplica en **cli-market-backend** para exponer Wave 1–3 en Railway/local.

## Cambio

`requirements.txt` línea 4:

```text
cli-market-core @ git+https://github.com/Treevu-ai/cli-market-core.git@1ed299e
```

`Dockerfile` y `Dockerfile.collector`: `CACHE_BUST=2026-06-23-core-1ed299e`

## Opción A — patch desde cli-market-core

```bash
cd cli-market-backend
git checkout -b cursor/bump-core-cost-of-living-9eee
git am ../cli-market-core/ops/ecosystem-patches/cli-market-backend-core-1ed299e.patch
git push -u origin cursor/bump-core-cost-of-living-9eee
```

## Opción B — editar a mano

1. Edita `requirements.txt`, `Dockerfile`, `Dockerfile.collector` como arriba.
2. Commit + push + PR a `main`.

## Smoke post-deploy

```bash
curl -s "https://cli-market-production.up.railway.app/v1/intel/affordability?country=PE" | jq '.data.affordability_score'
curl -s -o /dev/null -w "%{http_code}" "https://cli-market-production.up.railway.app/v1/household"  # 401
curl -s "https://cli-market-production.up.railway.app/v1/ecosystem/launches?topic=food&limit=3" | jq '.data.launches | length'
```

## Local (Windows PowerShell)

```powershell
pip install "cli-market-core @ git+https://github.com/Treevu-ai/cli-market-core.git@1ed299e"
# reiniciar market_server.py
```

Relacionado: cli-market-core PR #71 (Wave 1–2), PR #72 (Wave 3).
