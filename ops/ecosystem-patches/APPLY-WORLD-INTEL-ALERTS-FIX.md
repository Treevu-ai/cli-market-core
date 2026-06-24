# Fix GET /v1/intel/alerts HTTP 500 (PostgreSQL ROUND)

**Root cause:** `routers/intel.py` used `ROUND(double precision, 1)` which PostgreSQL rejects
(`function round(double precision, integer) does not exist`). SQLite accepts it, so CI passed.

**Fix:** delegate to `market_core.market_intel_products.compute_price_deal_alerts` (uses `::numeric` cast).

## Apply in cli-market-world

Requires **cli-market-core==1.11.3** on PyPI (merge PR #97 + publish first).

**Recommended:** use the combined patch (pin + intel fix):

```bash
bash ~/cli-market-core/ops/ecosystem-patches/deploy-world-1.11.3.sh
```

See `APPLY-WORLD-PYPI-1.11.3.md`.

Intel-only patch (legacy, superseded by `cli-market-world-1.11.3.patch`):

```bash
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-intel-alerts-fix.patch
```

## Verify

```bash
curl -H "Authorization: Bearer $CLI_MARKET_API_KEY" \
  "https://cli-market-production.up.railway.app/v1/intel/alerts?product=aceite%20vegetal&store=metro&threshold_pct=5"
```

Expect HTTP 200 with `{product, store, threshold_pct, total, results}`.
