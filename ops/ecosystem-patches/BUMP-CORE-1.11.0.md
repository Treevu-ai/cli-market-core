# Bump cli-market-core → 1.11.0 (PyPI — Cost-of-Living OS Waves 1–4)

Publica **antes** de mergear el pin en world/backend.

## 1. Publicar en PyPI

**Opción A (recomendada)** — core ya en `main` con `version = 1.11.0`:

1. Merge PR de release `1.11.0` en `cli-market-core`
2. GitHub → **cli-market-core** → Actions → **Publish PyPI** → Run workflow
3. Verificar: `pip index versions cli-market-core | head -3`

**Opción B** — workflow legacy en world (`Publish cli-market-core (patch)`):

- Requiere `ops/patches/cli-market-core-1.11.0.patch` en cli-market-world
- Actions → **Publish cli-market-core (patch)** → `version: 1.11.0`

## 2. Pin world (después de PyPI)

`requirements-railway.txt`:

```text
cli-market-core==1.11.0
```

`.github/workflows/ci.yml` (ambos jobs):

```text
pip install "cli-market-core==1.11.0"
```

`Dockerfile`:

```text
ARG CACHE_BUST=2026-06-23-core-1.11.0
```

Script automatizado en world: `ops/after_core_1.11.0_published.sh`

## Smoke post-pin

```bash
python3 ops/verify_railway_core_pin.py
API=https://cli-market-production.up.railway.app
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/v1/missions/optimize-purchase" \
  -H "Content-Type: application/json" -d '{"country":"PE","items":[{"name":"leche","qty":1}]}'
```

## Contenido 1.11.0

Equivalente a git `8469854` — Wave 4: optimize-purchase, TCO delivery, affiliate L3, provenance, feature flags.
