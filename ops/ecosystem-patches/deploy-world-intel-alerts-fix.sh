#!/usr/bin/env bash
# deploy-world-intel-alerts-fix.sh — alias for router-only fix (core pin assumed done)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/deploy-world-intel-router-fix.sh"
