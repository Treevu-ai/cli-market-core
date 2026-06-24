#!/usr/bin/env bash
# deploy-world-intel-router-fix.sh — fix GET /v1/intel/alerts 500 (routers/intel.py only)
# Requires: cli-market-world already on cli-market-core==1.11.3 (world #367+).
# Requires push access to Treevu-ai/cli-market-world (cursor[bot] cannot push).
set -euo pipefail
BRANCH="cursor/fix-intel-alerts-router-d0e9"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARENT="$(cd "$CORE_ROOT/.." && pwd)"
REPO="${CLI_MARKET_WORLD:-$PARENT/cli-market-world}"
PATCH="$SCRIPT_DIR/cli-market-world-intel-alerts-fix.patch"

[[ -f "$PATCH" ]] || { echo "Missing patch: $PATCH"; exit 1; }
[[ -d "$REPO" ]] || { echo "Missing repo: $REPO (set CLI_MARKET_WORLD=)"; exit 1; }

echo "Repo: $REPO"
echo "Branch: $BRANCH"
echo "Patch: routers/intel.py → compute_price_deal_alerts (core 1.11.3+)"

(
  cd "$REPO"
  git fetch origin
  git checkout main
  git pull origin main
  if ! grep -q 'cli-market-core==1.11.3' requirements-railway.txt; then
    echo "warn: requirements-railway.txt is not pinned to 1.11.3 — apply PyPI pin first" >&2
  fi
  git branch -D "$BRANCH" 2>/dev/null || true
  git checkout -b "$BRANCH"
  git am --abort 2>/dev/null || true
  git am "$PATCH"
  git push -u origin "$BRANCH" --force
)

if curl -sfL "https://raw.githubusercontent.com/Treevu-ai/cli-market-world/$BRANCH/routers/intel.py" | grep -q 'compute_price_deal_alerts'; then
  echo "Remote OK — open PR:"
  echo "https://github.com/Treevu-ai/cli-market-world/compare/main...${BRANCH}?expand=1"
else
  echo "FAIL: branch not visible on GitHub yet"
  exit 1
fi
