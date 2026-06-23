# Apply Phase 1 — README + llms + agents.json

Patch: `cli-market-world-phase1-marketing.patch`

Depends on Phase 0 (`cli-market-world-phase0-marketing.patch`) if not already on main.

## Apply

### Bash (Linux / macOS / Git Bash)

```bash
cd cli-market-world
git checkout main && git pull
git checkout -b cursor/phase1-public-copy-9eee
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-phase1-marketing.patch
git push -u origin cursor/phase1-public-copy-9eee
```

### PowerShell (Windows)

Use `;` instead of `&&` on PowerShell 5.x. Fetch the patch from **core** first (it lives on branch `cursor/phase1-public-copy-9eee` until PR #82 merges):

```powershell
cd C:\Users\acuba\cli-market-core
git fetch origin cursor/phase1-public-copy-9eee
git checkout cursor/phase1-public-copy-9eee

cd C:\Users\acuba\cli-market-world
git checkout main
git pull
git branch -D cursor/phase1-public-copy-9eee
git checkout -b cursor/phase1-public-copy-9eee
git am ..\cli-market-core\ops\ecosystem-patches\cli-market-world-phase1-marketing.patch
git push -u origin cursor/phase1-public-copy-9eee --force-with-lease
```

`--force-with-lease` is needed if you already pushed an empty branch (as in the failed `git am` attempt).

**Patch missing?** Merge [cli-market-core PR #82](https://github.com/Treevu-ai/cli-market-core/pull/82) on GitHub, then `git pull` in `cli-market-core` on `main`.

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
