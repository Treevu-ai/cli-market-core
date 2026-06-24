#!/usr/bin/env bash
# deploy-world-intel-alerts-fix.sh — superseded by deploy-world-1.11.3.sh (pin + fix)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/deploy-world-1.11.3.sh"
