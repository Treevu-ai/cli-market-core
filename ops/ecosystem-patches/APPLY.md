# Aplicar fixes P0–P2 en tu máquina local

Los commits viven en el Cloud Agent; `cursor[bot]` no tiene write en backend/world/content/procure.
Usa estos patches desde **cli-market-core** (rama `cursor/ecosystem-fixes-p0-p2-e95e` o `main` tras merge PR #38).

## Prerrequisitos

- Tener clonados los repos bajo la misma carpeta padre (ej. `~/Treevu-ai/`).
- Estar en `main` actualizado: `git pull origin main`

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

Si no lo tienes clonado:

```bash
gh repo clone Treevu-ai/procure-copilot
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
# o merge PR https://github.com/Treevu-ai/cli-market-core/pull/38
```

## Si `git am` falla

```bash
git am --abort
git apply --3way ../cli-market-core/ops/ecosystem-patches/<repo>.patch
git add -A && git commit -m "Apply ecosystem P0-P2 patch from cli-market-core"
```

## Alternativa: dar write a cursor[bot]

GitHub → cada repo → Settings → Collaborators → invitar `cursor[bot]` con Write.
Luego el agente puede pushear las ramas directamente.
