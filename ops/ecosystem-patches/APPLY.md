# Aplicar fixes P0–P2 en tu máquina local

Los patches viven en **cli-market-core** (`ops/ecosystem-patches/`), rama `cursor/ecosystem-fixes-p0-p2-e95e` o `main` tras merge PR #38.

## Por qué no aparece el PR en GitHub

`cursor[bot]` **no tiene permisos de push** en `cli-market-world`, `cli-market-content` ni `procure-copilot`. Los commits existen solo en el agente local hasta que **tú** ejecutes el script de deploy desde tu máquina (con tu cuenta GitHub).

Además, la rama remota `cursor/collector-p0-world-e95e` en world es **vieja** (23 commits detrás de `main`, sin cambios del collector). Usa la rama nueva `cursor/collector-index-rotate-p0-e95e`.

### P0 collector (world) — un solo comando

No hace falta una carpeta `Treevu-ai`. Basta con que los repos estén **al mismo nivel**, por ejemplo:

```
C:\Users\acuba\cli-market-core\
C:\Users\acuba\cli-market-world\
```

Puedes ejecutar el script **desde cualquier carpeta** (usa rutas absolutas):

```powershell
# 1) Actualizar core (trae el patch)
cd C:\Users\acuba\cli-market-core
git pull origin cursor/ecosystem-fixes-p0-p2-e95e

# 2) Deploy collector → push rama nueva en world
powershell -ExecutionPolicy Bypass -File C:\Users\acuba\cli-market-core\ops\ecosystem-patches\deploy-collector-world.ps1
```

```bash
# Linux/macOS (mismo layout: ~/cli-market-core y ~/cli-market-world)
bash ~/cli-market-core/ops/ecosystem-patches/deploy-collector-world.sh
```

Luego abre el PR: https://github.com/Treevu-ai/cli-market-world/compare/main...cursor/collector-index-rotate-p0-e95e

## ⚠️ No mezclar patches entre repos

Cada `.patch` es **solo para un repo**. Si aplicas el patch equivocado (ej. backend en world), verás archivos que no corresponden.

| Patch | Repo | Archivos que toca |
|-------|------|-------------------|
| `cli-market-backend.patch` | **cli-market-backend** | `collect_prices.py`, `Dockerfile.collector`, `railway.collector.toml`, `requirements.txt` |
| `cli-market-backend-core-1ed299e.patch` | **cli-market-backend** | Bump Wave 1–3 (superseded by 8469854) |
| `BUMP-CORE-8469854.md` | **cli-market-backend** | Bump Wave 4 — pin + smoke (doc only) |
| `BUMP-CORE-1ed299e.md` | — | Historial Wave 1–3 |
| `cli-market-world.patch` | **cli-market-world** | `ci.yml`, `mcp.json`, `marketStats.ts`, … (stats sync) |
| `cli-market-world-optimize.patch` | **cli-market-world** | `market optimize`, basket v1 envelope, core @8469854 |
| `cli-market-world-mount-api-routes.patch` | **cli-market-world** | Mount `api_routes` on `market_server.py` for production Wave 4 |
| `cli-market-world-pypi-1.11.0.patch` | **cli-market-world** | Pin `cli-market-core==1.11.0` after PyPI publish |
| `cli-market-world-1.11.3.patch` | **cli-market-world** | Pin `cli-market-core==1.11.3` + intel alerts PG fix |
| `BUMP-CORE-1.11.3.md` | — | Release checklist for 1.11.3 |
| `cli-market-content.patch` | **cli-market-content** | `outbound/procure-sequences.md`, `commercial/procure-copilot-feature-matrix.md`, … |
| `procure-copilot.patch` | **procure-copilot** | `app/checkout/success`, `app/checkout/cancel`, `lib/market-stats.ts` |

### Verificación rápida después de aplicar

**Backend** — debe contener `run_rotating_catalog` en `collect_prices.py`:

```bash
grep run_rotating_catalog collect_prices.py   # backend: sí
```

**World** — NO debe ganar `run_rotating_catalog` por este patch; actualizar `mcpTools` a **32** (default profile post Wave 4):

```bash
grep run_rotating_catalog collect_prices.py   # world: no (0 matches)
grep mcpTools landing/lib/marketStats.ts      # world: mcpTools: 32 (o public_tool_count)
```

### Si la rama remota quedó vieja (push devuelve OK pero GitHub sigue en False)

Usa una **rama nueva** `cursor/ecosystem-p0-p2-v2-e95e` y push con `--force`:

```powershell
# Windows — desde carpeta padre de los repos:
powershell -ExecutionPolicy Bypass -File cli-market-core\ops\ecosystem-patches\deploy-v2.ps1
```

```bash
# Linux/macOS:
bash cli-market-core/ops/ecosystem-patches/deploy-v2.sh
```

Diagnóstico manual si `git push` falla:

```powershell
git remote -v                    # debe ser Treevu-ai/<repo>
git status
git log -1 --oneline
git push -u origin <rama> --force 2>&1
```

Si `git am` falla, copia el error completo — el patch aplica limpio sobre `main` actual (verificado 2026-06-22).

---

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

- Repos clonados como **hermanos** en la misma carpeta (ej. `C:\Users\acuba\cli-market-core` y `C:\Users\acuba\cli-market-world`). No se requiere carpeta `Treevu-ai`.
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
