#!/usr/bin/env bash
# deploy-world-intel-alerts-fix.sh — fix GET /v1/intel/alerts 500 on PostgreSQL
set -euo pipefail
BRANCH="cursor/fix-intel-alerts-500-d0e9"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARENT="$(cd "$CORE_ROOT/.." && pwd)"
REPO="${CLI_MARKET_WORLD:-$PARENT/cli-market-world}"
PATCH="$SCRIPT_DIR/cli-market-world-intel-alerts-fix.patch"

[[ -f "$PATCH" ]] || { echo "Missing patch: $PATCH"; exit 1; }
[[ -d "$REPO" ]] || { echo "Missing repo: $REPO"; exit 1; }

(
  cd "$REPO"
  git fetch origin
  git checkout main
  git pull origin main
  git branch -D "$BRANCH" 2>/dev/null || true
  git checkout -b "$BRANCH"
  git am --abort 2>/dev/null || true
  git am "$PATCH"
  git push -u origin "$BRANCH" --force
)

echo "Open PR: https://github.com/Treevu-ai/cli-market-world/compare/main...${BRANCH}?expand=1"
