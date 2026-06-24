# Fix GET /v1/intel/alerts HTTP 500 (PostgreSQL ROUND)

**Root cause:** `routers/intel.py` used `ROUND(double precision, 1)` which PostgreSQL rejects
(`function round(double precision, integer) does not exist`). SQLite accepts it, so CI passed.

**Fix:** delegate to `market_core.market_intel_products.compute_price_deal_alerts` (uses `::numeric` cast).

## Apply in cli-market-world

Requires **cli-market-core** with `compute_price_deal_alerts` (merge PR first).

```bash
cd cli-market-world
git checkout main && git pull
git checkout -b cursor/fix-intel-alerts-500-d0e9
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-intel-alerts-fix.patch
# o:
git apply --3way ../cli-market-core/ops/ecosystem-patches/cli-market-world-intel-alerts-fix.patch
git add routers/intel.py
git commit -m "fix(intel): delegate /v1/intel/alerts to core PG-safe query"
git push -u origin cursor/fix-intel-alerts-500-d0e9
```

PR: https://github.com/Treevu-ai/cli-market-world/compare/main...cursor/fix-intel-alerts-500-d0e9

## Verify

```bash
curl -H "Authorization: Bearer $CLI_MARKET_API_KEY" \
  "https://cli-market-production.up.railway.app/v1/intel/alerts?product=aceite%20vegetal&store=metro&threshold_pct=5"
```

Expect HTTP 200 with `{product, store, threshold_pct, total, results}`.
