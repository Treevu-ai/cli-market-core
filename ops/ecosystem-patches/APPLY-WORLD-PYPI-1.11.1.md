# Pin cli-market-world → cli-market-core==1.11.1 (PyPI)

**Merge after** `cli-market-core==1.11.1` is on PyPI (deeplink fix: canonical VTEX URLs per retailer).

## Verify core on PyPI

```bash
python3 -m pip index versions cli-market-core | grep 1.11.1
```

## Apply world pin (local machine with push access)

```bash
cd cli-market-world
git checkout main && git pull
git checkout -b cursor/core-pin-1.11.1-d0e9
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-pypi-1.11.1.patch
# o:
git apply --3way ../cli-market-core/ops/ecosystem-patches/cli-market-world-pypi-1.11.1.patch
git add -A && git commit -m "chore(release): pin cli-market-core==1.11.1 (product URL deeplink fix)"
git push -u origin cursor/core-pin-1.11.1-d0e9
```

O ejecutar en world (post-PyPI): `bash ops/after_core_1.11.1_published.sh`

PR: https://github.com/Treevu-ai/cli-market-world/compare/main...cursor/core-pin-1.11.1-d0e9

## Files changed

| File | Change |
|------|--------|
| `requirements-railway.txt` | `cli-market-core==1.11.1` |
| `.github/workflows/ci.yml` | `pip install "cli-market-core==1.11.1"` (×2) |
| `.github/workflows/morning-ops-chain.yml` | `cli-market-core==1.11.1` (×6) |
| `Dockerfile` | `CACHE_BUST=2026-06-24-core-1.11.1` |
| `ops/after_core_1.11.1_published.sh` | one-shot pin script for future bumps |

## Post-merge

Railway redeploys automatically. Re-run `market_optimize_purchase` — `product_links` should use canonical store URLs (no Metro/Wong/Plaza Vea 404s).
