# Pin cli-market-world → cli-market-core==1.11.0 (PyPI)

**Merge only after** `cli-market-core==1.11.0` is on PyPI.

## Publish core first

1. Merge **cli-market-core** PR `cursor/release-core-1.11.0-9eee` (bumps `pyproject.toml` + `PACKAGE_VERSION`)
2. GitHub Actions:
   - **Opción A (recomendada):** `cli-market-core` → **Publish PyPI** → Run workflow
   - **Opción B:** `cli-market-world` → **Publish cli-market-core (patch)** → `version: 1.11.0`
3. Verificar: `pip index versions cli-market-core | grep 1.11.0`

## Apply world pin

```bash
cd cli-market-world
git checkout main && git pull
git checkout -b cursor/core-pypi-1.11.0-9eee
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world-pypi-1.11.0.patch
# o:
git apply --3way ../cli-market-core/ops/ecosystem-patches/cli-market-world-pypi-1.11.0.patch
git add -A && git commit -m "chore(release): pin cli-market-core==1.11.0"
git push -u origin cursor/core-pypi-1.11.0-9eee
```

O ejecutar en world (post-PyPI): `bash ops/after_core_1.11.0_published.sh`

PR: https://github.com/Treevu-ai/cli-market-world/compare/main...cursor/core-pypi-1.11.0-9eee

## Files changed

| File | Change |
|------|--------|
| `requirements-railway.txt` | `cli-market-core==1.11.0` |
| `.github/workflows/ci.yml` | `pip install "cli-market-core==1.11.0"` (×2) |
| `Dockerfile` | `CACHE_BUST=2026-06-23-core-1.11.0` |
| `ops/patches/cli-market-core-1.11.0.patch` | version bump for publish workflow |
| `ops/verify_railway_core_pin.py` | fail on git pin (no more SKIP) |
