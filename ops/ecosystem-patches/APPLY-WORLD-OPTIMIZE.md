# Apply `market optimize` — cli-market-world

Patch: `cli-market-world-optimize.patch` (commit `633a8d2` equivalent)

## Qué incluye

| Cambio | Detalle |
|--------|---------|
| **`market optimize`** | `POST /v1/missions/optimize-purchase` — TCO + sustitutos + intel + action links |
| **`market basket`** | Compatible con envelope v1 + flags `--tco`, `--action-links`, `--no-delivery` |
| **Core pin** | `cli-market-core @ …8469854` en `requirements-railway.txt` + CI |
| **Marketing** | MCP default **32** tools (`sync_market_stats`) |

## Aplicar (desde tu máquina)

```bash
cd cli-market-world
git checkout main && git pull origin main
git checkout -b cursor/market-optimize-9eee
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-optimize.patch
# o si git am falla:
git apply --3way ../cli-market-core/ops/ecosystem-patches/cli-market-world-optimize.patch
git add -A && git commit -m "feat(cli): market optimize + basket v1 envelope"
git push -u origin cursor/market-optimize-9eee
```

PR: https://github.com/Treevu-ai/cli-market-world/compare/main...cursor/market-optimize-9eee

## Smoke local

```bash
pip install "cli-market-core @ git+https://github.com/Treevu-ai/cli-market-core.git@8469854"
pip install -e .

market optimize leche:2 --country PE --budget 80
market basket leche:2 arroz:1 --country PE --tco
market basket leche:1 --country PE --tco --action-links --json
```

Esperado:
- `optimize` → `BUY_NOW|MONITOR|WAIT`, `primary_store`, `tco_total`, `action_links`
- `basket --tco` → tabla con columna TCO, sin error `comparison` vacío

## Tests

```bash
python3 -m pytest -q tests/test_market_optimize_cli.py
```

## Backend requisito

Railway/backend debe estar en core **`@8469854`** (Wave 4). Sin eso, `/v1/missions/optimize-purchase` y `/v1/basket/compare` enveloped fallan o 404.
