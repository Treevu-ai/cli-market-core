# Apply Phase 0 — marketing source of truth

Patch: `cli-market-world-phase0-marketing.patch`

## Apply

```bash
cd cli-market-world
git checkout main && git pull
git checkout -b cursor/phase0-marketing-source-9eee
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-phase0-marketing.patch
git push -u origin cursor/phase0-marketing-source-9eee
```

Regenerate locally (optional, needs prod API for 63k prices):

```bash
MARKET_API_URL=https://cli-market-production.up.railway.app python3 ops/sync_market_stats.py
```

## Verify

```bash
python3 -m pytest -q tests/test_sync_market_stats_phase0.py
grep 'market_optimize_purchase.*canonical.: true' landing/lib/marketStats.ts
grep 'Canonical: market_optimize_purchase' landing/public/llms-full.txt
```
