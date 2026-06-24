# Bump cli-market-core → 1.11.3

**Scope:** PG-safe `GET /v1/intel/alerts` (`market_price_alerts` MCP tool).

## Core (this repo)

1. Merge PR #97
2. `pyproject.toml` → `1.11.3` (included in PR)
3. Publish via `.github/workflows/publish-pypi.yml` (tag `v1.11.3` or workflow_dispatch)

## World

```bash
bash ops/ecosystem-patches/deploy-world-1.11.3.sh
```

See `ops/ecosystem-patches/APPLY-WORLD-PYPI-1.11.3.md`.
