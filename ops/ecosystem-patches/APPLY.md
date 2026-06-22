# Aplicar fixes P0–P2 en tu máquina local

Los patches viven en **cli-market-core** (`ops/ecosystem-patches/`), rama `cursor/ecosystem-fixes-p0-p2-e95e` o `main` tras merge PR #38.

## ⚠️ No mezclar patches entre repos

Cada `.patch` es **solo para un repo**. Si aplicas el patch equivocado (ej. backend en world), verás archivos que no corresponden.

| Patch | Repo | Archivos que toca |
|-------|------|-------------------|
| `cli-market-backend.patch` | **cli-market-backend** | `collect_prices.py`, `Dockerfile.collector`, `railway.collector.toml`, `requirements.txt` |
| `cli-market-world.patch` | **cli-market-world** | `ci.yml`, `mcp.json`, `marketStats.ts`, `requirements-railway.txt`, `server.json`, … (15 archivos) |
| `cli-market-content.patch` | **cli-market-content** | `outbound/procure-sequences.md`, `commercial/procure-copilot-feature-matrix.md`, … |
| `procure-copilot.patch` | **procure-copilot** | `app/checkout/success`, `app/checkout/cancel`, `lib/market-stats.ts` |

### Verificación rápida después de aplicar

**Backend** — debe contener `run_rotating_catalog` en `collect_prices.py`:

```bash
grep run_rotating_catalog collect_prices.py   # backend: sí
```

**World** — NO debe ganar `run_rotating_catalog` por este patch; sí debe tener `mcpTools: 27`:

```bash
grep run_rotating_catalog collect_prices.py   # world: no (0 matches)
grep mcpTools landing/lib/marketStats.ts      # world: mcpTools: 27
```

### Si aplicaste el patch equivocado

```bash
cd <repo-afectado>
git checkout main
git pull origin main
git branch -D cursor/ecosystem-fixes-p0-p2-e95e
git checkout -b cursor/ecosystem-fixes-p0-p2-e95e
git am ../cli-market-core/ops/ecosystem-patches/<PATCH-CORRECTO>.patch
```

---

## Prerrequisitos

- Repos clonados bajo la misma carpeta padre (ej. `~/Treevu-ai/`).
- `main` actualizado: `git pull origin main`

## cli-market-backend

```bash
cd cli-market-backend
git checkout -b cursor/ecosystem-fixes-p0-p2-e95e
git am ../cli-market-core/ops/ecosystem-patches/cli-market-backend.patch
git push -u origin cursor/ecosystem-fixes-p0-p2-e95e
```

## cli-market-world

```bash
cd cli-market-world
git checkout -b cursor/ecosystem-fixes-p0-p2-e95e
git am ../cli-market-core/ops/ecosystem-patches/cli-market-world.patch
git push -u origin cursor/ecosystem-fixes-p0-p2-e95e
```

## cli-market-content

```bash
cd cli-market-content
git checkout -b cursor/ecosystem-fixes-p0-p2-e95e
git am ../cli-market-core/ops/ecosystem-patches/cli-market-content.patch
git push -u origin cursor/ecosystem-fixes-p0-p2-e95e
```

## procure-copilot

```bash
gh repo clone Treevu-ai/procure-copilot   # si no existe
cd procure-copilot
git checkout -b cursor/ecosystem-fixes-p0-p2-e95e
git am ../cli-market-core/ops/ecosystem-patches/procure-copilot.patch
git push -u origin cursor/ecosystem-fixes-p0-p2-e95e
```

## cli-market-core (PR #38)

```bash
cd cli-market-core
git fetch origin cursor/ecosystem-fixes-p0-p2-e95e
git checkout cursor/ecosystem-fixes-p0-p2-e95e
```

## Si `git am` falla

```bash
git am --abort
git apply --3way ../cli-market-core/ops/ecosystem-patches/<repo>.patch
git add -A && git commit -m "Apply ecosystem P0-P2 patch from cli-market-core"
```

## Alternativa: dar write a cursor[bot]

GitHub → cada repo → Settings → Collaborators → invitar `cursor[bot]` con Write.
