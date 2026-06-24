# Pin cli-market-world → cli-market-core==1.11.3 (PyPI) + intel alerts fix

**Merge after** `cli-market-core==1.11.3` is on PyPI (PG-safe `GET /v1/intel/alerts` / `market_price_alerts`).

## 1. Publish core

```bash
cd cli-market-core
git checkout main && git pull
# merge PR #97, tag v1.11.3, run Publish PyPI workflow
python3 -m pip index versions cli-market-core | grep 1.11.3
```

## 2. Apply world patch (one shot: pin + intel fix)

```bash
bash ~/cli-market-core/ops/ecosystem-patches/deploy-world-1.11.3.sh
```

Manual apply:

```bash
cd cli-market-world
git checkout main && git pull
git checkout -b cursor/release-core-1.11.3-d0e9
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-1.11.3.patch
# o:
git apply --3way ../cli-market-core/ops/ecosystem-patches/cli-market-world-1.11.3.patch
python3 ops/verify_railway_core_pin.py
git add -A && git commit -m "chore(release): pin cli-market-core==1.11.3 + fix intel alerts PG-safe query"
git push -u origin cursor/release-core-1.11.3-d0e9
```

O ejecutar en world (post-PyPI): `bash ops/after_core_1.11.3_published.sh` (tras aplicar el fix de `routers/intel.py` si no usaste el patch combinado).

PR: https://github.com/Treevu-ai/cli-market-world/compare/main...cursor/release-core-1.11.3-d0e9

## What changes

| File | Change |
|------|--------|
| `requirements-railway.txt` | `cli-market-core==1.11.3` |
| `.github/workflows/ci.yml` | `pip install "cli-market-core==1.11.3"` (×2) |
| `.github/workflows/morning-ops-chain.yml` | `cli-market-core==1.11.3` (×6, alinea morning-ops que seguía en 1.11.0) |
| `Dockerfile` | `CACHE_BUST=2026-06-24-core-1.11.3` |
| `routers/intel.py` | delega a `compute_price_deal_alerts` (fix HTTP 500 PostgreSQL) |
| `ops/after_core_1.11.3_published.sh` | one-shot pin script for future bumps |

## 3. Verify production

```bash
curl -H "Authorization: Bearer $CLI_MARKET_API_KEY" \
  "https://cli-market-production.up.railway.app/v1/intel/alerts?product=aceite%20vegetal&store=metro&threshold_pct=5"
```

Expect HTTP 200 with `{product, store, threshold_pct, total, results}`.
