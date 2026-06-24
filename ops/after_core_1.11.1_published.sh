#!/usr/bin/env bash
# Run in cli-market-world AFTER cli-market-core 1.11.1 is on PyPI.
set -euo pipefail
VER=1.11.1
sed -i "s/^cli-market-core @ git+.*/cli-market-core==${VER}/" requirements-railway.txt
sed -i "s/^cli-market-core==.*/cli-market-core==${VER}/" requirements-railway.txt
python3 ops/verify_railway_core_pin.py
git add requirements-railway.txt
git commit -m "chore(release): pin cli-market-core==${VER} (product URL deeplink fix)"
git push -u origin HEAD
echo "Pushed world pin ${VER} — Railway redeploy."
