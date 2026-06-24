# Fix GET /v1/intel/alerts HTTP 500 (PostgreSQL ROUND)

**Root cause:** `routers/intel.py` used `ROUND(double precision, 1)` which PostgreSQL rejects.

**Fix:** delegate to `market_core.market_intel_products.compute_price_deal_alerts` (in core **1.11.3+**).

## Status

| Step | Required |
|------|----------|
| Core `compute_price_deal_alerts` + PyPI **1.11.3** | ✅ merged / published |
| World pin `cli-market-core==1.11.3` | ✅ world #367 |
| World `routers/intel.py` delegation | ⏳ **this patch** |

See **`APPLY-WORLD-INTEL-ROUTER-FIX.md`** for the one-file deploy (recommended now that pin is done).

```bash
bash ~/cli-market-core/ops/ecosystem-patches/deploy-world-intel-router-fix.sh
```

Combined pin+router patch (historical): `cli-market-world-1.11.3.patch` — use only if pin is not yet applied.
