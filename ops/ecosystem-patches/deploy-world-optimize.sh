#!/usr/bin/env bash
# deploy-world-optimize.sh — apply market optimize patch to cli-market-world
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO="$PARENT/cli-market-world"
PATCH="$SCRIPT_DIR/cli-market-world-optimize.patch"
BRANCH="cursor/market-optimize-9eee"

if [[ ! -d "$REPO/.git" ]]; then
  echo "error: expected sibling repo at $REPO" >&2
  exit 1
fi
if [[ ! -f "$PATCH" ]]; then
  echo "error: patch not found: $PATCH" >&2
  exit 1
fi

cd "$REPO"
git fetch origin main
git checkout main
git pull origin main
git branch -D "$BRANCH" 2>/dev/null || true
git checkout -b "$BRANCH"

if git am "$PATCH"; then
  echo "Applied via git am"
else
  git am --abort 2>/dev/null || true
  git apply --3way "$PATCH"
  git add -A
  git commit -m "feat(cli): market optimize + basket v1 envelope (patch from cli-market-core)"
fi

git push -u origin "$BRANCH"
echo "Open PR: https://github.com/Treevu-ai/cli-market-world/compare/main...${BRANCH//\//%2F}"
