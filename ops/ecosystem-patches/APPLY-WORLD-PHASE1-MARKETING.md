# Apply Phase 1 — README + llms + agents.json

Patch: `cli-market-world-phase1-marketing.patch`

Depends on Phase 0 (`cli-market-world-phase0-marketing.patch`) if not already on main.

## Apply

```bash
cd cli-market-world
git checkout main && git pull
git checkout -b cursor/phase1-public-copy-9eee
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-phase1-marketing.patch
git push -u origin cursor/phase1-public-copy-9eee
```

Regenerate locally (optional, needs prod API for 63k prices):

```bash
MARKET_API_URL=https://cli-market-production.up.railway.app python3 ops/sync_market_stats.py
```

## Verify

```bash
CI=true MARKET_SKIP_LIVE=1 python3 -m pytest -q tests/test_sync_market_stats_phase0.py
grep -n 'market optimize' README.md
grep -n '32 curated MCP' README.md landing/public/llms.txt
grep -n '63,000+' README.md landing/public/llms.txt landing/public/agents.json
grep '"version": "1.11.0"' landing/public/agents.json
grep -n 'default agent flow' landing/public/llms.txt
```

## What changes

- **README**: Cost-of-Living OS (Wave 4), `market optimize` quick start, 32 MCP, Starter 5k req/day, 63k prices
- **llms.txt / llms-full.txt**: 32 tools, 63k, optimize-first quick start, default agent flow
- **agents.json**: version 1.11.0, Wave 4 capabilities, no stock_check overclaim
- **sync_market_stats.py**: `sync_llms_txt`, `sync_agents_json`, README MCP footer, 61k→63k normalization
