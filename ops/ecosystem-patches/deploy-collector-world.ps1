# deploy-collector-world.ps1 — P0 collector fix para cli-market-world
# Uso (desde carpeta padre de repos, ej. C:\Users\acuba\Treevu-ai):
#   powershell -ExecutionPolicy Bypass -File cli-market-core\ops\ecosystem-patches\deploy-collector-world.ps1

$ErrorActionPreference = "Stop"
$Branch = "cursor/collector-index-rotate-p0-e95e"
$PatchDir = $PSScriptRoot
$CoreRoot = (Resolve-Path (Join-Path $PatchDir "..\..")).Path
$ReposParent = Split-Path $CoreRoot -Parent
$RepoName = "cli-market-world"
$RepoPath = Join-Path $ReposParent $RepoName
$PatchFile = Join-Path $PatchDir "cli-market-world-collector-p0.patch"

if (-not (Test-Path $PatchFile)) {
    throw "No encuentro $PatchFile — actualiza cli-market-core (git pull)"
}
if (-not (Test-Path $RepoPath)) {
    throw "No encuentro $RepoPath — clona cli-market-world junto a cli-market-core"
}

Write-Host "Repo: $RepoPath" -ForegroundColor Cyan
Write-Host "Rama: $Branch" -ForegroundColor Cyan
Write-Host "Patch: $PatchFile" -ForegroundColor Cyan

Push-Location $RepoPath
try {
    git fetch origin
    git checkout main
    git pull origin main
    git branch -D $Branch 2>$null
    git checkout -b $Branch
    git am --abort 2>$null
    git am $PatchFile

    if (-not (Select-String -Path "collect_prices.py" -Pattern "_run_index_cycle" -Quiet)) {
        throw "Verificacion fallo: falta _run_index_cycle en collect_prices.py"
    }
    if (-not (Select-String -Path "collect_prices.py" -Pattern "run_rotating_catalog_pg" -Quiet)) {
        throw "Verificacion fallo: falta run_rotating_catalog_pg en collect_prices.py"
    }
    if (-not (Select-String -Path "requirements-railway.txt" -Pattern "90fefe1" -Quiet)) {
        throw "Verificacion fallo: requirements-railway.txt no pinnea core 90fefe1"
    }

    Write-Host "Push $Branch ..." -ForegroundColor Green
    git push -u origin $Branch --force

    Write-Host "`nVerificacion remota ..." -ForegroundColor Cyan
    $url = "https://raw.githubusercontent.com/Treevu-ai/cli-market-world/$Branch/collect_prices.py"
    $remote = (Invoke-WebRequest -Uri $url -UseBasicParsing).Content
    if ($remote -match "_run_index_cycle") {
        Write-Host "Remote OK — abre PR en GitHub:" -ForegroundColor Green
        Write-Host "https://github.com/Treevu-ai/cli-market-world/compare/main...$($Branch -replace '/','%2F')?expand=1"
    } else {
        throw "Push parece OK pero GitHub no muestra los cambios aun. Espera 10s y revisa la URL."
    }
}
catch {
    Write-Host "FAIL: $_" -ForegroundColor Red
    git am --abort 2>$null
    exit 1
}
finally {
    Pop-Location
}
