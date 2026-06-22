#!/usr/bin/env bash
# deploy-v2.sh — misma lógica que deploy-v2.ps1 (Linux/macOS)
set -euo pipefail
BRANCH="cursor/ecosystem-p0-p2-v2-e95e"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARENT="$(cd "$CORE_ROOT/.." && pwd)"
PATCH_DIR="$SCRIPT_DIR"

deploy_repo() {
  local repo="$1" patch="$2" verify_cmd="$3"
  local path="$PARENT/$repo"
  [[ -d "$path" ]] || { echo "SKIP $repo"; return 0; }
  echo "=== $repo ==="
  (
    cd "$path"
    git fetch origin
    git checkout main
    git pull origin main
    git branch -D "$BRANCH" 2>/dev/null || true
    git checkout -b "$BRANCH"
    git am --abort 2>/dev/null || true
    git am "$PATCH_DIR/$patch"
    eval "$verify_cmd"
    git push -u origin "$BRANCH" --force
  )
  echo "OK $repo"
}

echo "Rama: $BRANCH | Patches: $PATCH_DIR"
deploy_repo cli-market-backend cli-market-backend.patch 'grep -q run_rotating_catalog collect_prices.py && grep -q d4b8061 requirements.txt'
deploy_repo cli-market-world cli-market-world.patch 'grep -q d4b8061 requirements-railway.txt && grep -q "mcpTools: 27" landing/lib/marketStats.ts && ! grep -q run_rotating_catalog collect_prices.py'
deploy_repo cli-market-content cli-market-content.patch 'grep -q "Ops.*79" outbound/procure-sequences.md'
deploy_repo procure-copilot procure-copilot.patch 'test -f app/checkout/success/page.tsx'

echo "=== Verificacion remota ==="
curl -sfL "https://raw.githubusercontent.com/Treevu-ai/cli-market-backend/$BRANCH/collect_prices.py" | grep -q run_rotating_catalog && echo "backend remote: OK" || echo "backend remote: FAIL"
curl -sfL "https://raw.githubusercontent.com/Treevu-ai/cli-market-world/$BRANCH/requirements-railway.txt" | grep -q d4b8061 && echo "world remote: OK" || echo "world remote: FAIL"
echo "Listo — rama $BRANCH"
