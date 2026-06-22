#!/usr/bin/env bash
# deploy-collector-world.sh — P0 collector fix para cli-market-world
set -euo pipefail
BRANCH="cursor/collector-index-rotate-p0-e95e"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARENT="$(cd "$CORE_ROOT/.." && pwd)"
REPO="$PARENT/cli-market-world"
PATCH="$SCRIPT_DIR/cli-market-world-collector-p0.patch"

[[ -f "$PATCH" ]] || { echo "No encuentro $PATCH"; exit 1; }
[[ -d "$REPO" ]] || { echo "No encuentro $REPO"; exit 1; }

echo "Repo: $REPO"
echo "Rama: $BRANCH"

(
  cd "$REPO"
  git fetch origin
  git checkout main
  git pull origin main
  git branch -D "$BRANCH" 2>/dev/null || true
  git checkout -b "$BRANCH"
  git am --abort 2>/dev/null || true
  git am "$PATCH"
  grep -q _run_index_cycle collect_prices.py
  grep -q run_rotating_catalog_pg collect_prices.py
  grep -q 90fefe1 requirements-railway.txt
  git push -u origin "$BRANCH" --force
)

if curl -sfL "https://raw.githubusercontent.com/Treevu-ai/cli-market-world/$BRANCH/collect_prices.py" | grep -q _run_index_cycle; then
  echo "Remote OK — abre PR:"
  echo "https://github.com/Treevu-ai/cli-market-world/compare/main...${BRANCH//\//%2F}?expand=1"
else
  echo "FAIL: push no visible en GitHub"
  exit 1
fi
