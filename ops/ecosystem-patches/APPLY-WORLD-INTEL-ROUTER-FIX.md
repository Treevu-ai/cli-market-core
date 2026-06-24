# Fix GET /v1/intel/alerts HTTP 500 — router only

**Prerequisite:** `cli-market-world` already pinned to `cli-market-core==1.11.3` (world #367).

Pinning core alone does **not** fix alerts: world mounts `routers/intel.py` **before** core `api_routes`, so the broken PostgreSQL `ROUND(double precision, 1)` query still runs until this patch is applied.

## Apply

```bash
bash ~/cli-market-core/ops/ecosystem-patches/deploy-world-intel-router-fix.sh
```

Manual:

```bash
cd cli-market-world
git checkout main && git pull
git checkout -b cursor/fix-intel-alerts-router-d0e9
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-intel-alerts-fix.patch
git push -u origin cursor/fix-intel-alerts-router-d0e9
```

PR: https://github.com/Treevu-ai/cli-market-world/compare/main...cursor/fix-intel-alerts-router-d0e9

## Verify (post-merge + Railway redeploy)

```bash
curl -H "Authorization: Bearer $CLI_MARKET_API_KEY" \
  "https://cli-market-production.up.railway.app/v1/intel/alerts?product=aceite%20vegetal&store=metro&threshold_pct=5"
```

Expect HTTP 200 with `{product, store, threshold_pct, total, results}`.
