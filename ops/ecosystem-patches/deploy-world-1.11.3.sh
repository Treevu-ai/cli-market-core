#!/usr/bin/env bash
# deploy-world-1.11.3.sh — pin cli-market-world → cli-market-core==1.11.3 + intel alerts fix
# Requires push access to Treevu-ai/cli-market-world (cursor[bot] cannot push).
# Layout: sibling repos under the same parent (~/cli-market-core, ~/cli-market-world).
set -euo pipefail
BRANCH="cursor/release-core-1.11.3-d0e9"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARENT="$(cd "$CORE_ROOT/.." && pwd)"
REPO="${CLI_MARKET_WORLD:-$PARENT/cli-market-world}"
PATCH="$SCRIPT_DIR/cli-market-world-1.11.3.patch"
VER="1.11.3"

[[ -f "$PATCH" ]] || { echo "Missing patch: $PATCH"; exit 1; }
[[ -d "$REPO" ]] || { echo "Missing repo: $REPO (set CLI_MARKET_WORLD=)"; exit 1; }

if ! python3 - <<PY
import json, urllib.request, sys
ver = "${VER}"
data = json.load(urllib.request.urlopen("https://pypi.org/pypi/cli-market-core/json", timeout=20))
sys.exit(0 if ver in data.get("releases", {}) else 1)
PY
then
  echo "error: cli-market-core $VER not on PyPI yet — merge core PR and publish first" >&2
  exit 1
fi

echo "Repo: $REPO"
echo "Branch: $BRANCH"

(
  cd "$REPO"
  git fetch origin
  git checkout main
  git pull origin main
  git branch -D "$BRANCH" 2>/dev/null || true
  git checkout -b "$BRANCH"
  git am --abort 2>/dev/null || true
  git am "$PATCH"
  python3 ops/verify_railway_core_pin.py
  git push -u origin "$BRANCH" --force
)

if curl -sfL "https://raw.githubusercontent.com/Treevu-ai/cli-market-world/$BRANCH/requirements-railway.txt" | grep -q "cli-market-core==1.11.3"; then
  echo "Remote OK — open PR:"
  echo "https://github.com/Treevu-ai/cli-market-world/compare/main...${BRANCH}?expand=1"
else
  echo "FAIL: branch not visible on GitHub yet"
  exit 1
fi
