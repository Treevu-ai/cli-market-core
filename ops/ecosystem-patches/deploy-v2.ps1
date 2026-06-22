# deploy-v2.ps1 — Aplica patches P0-P2 y pushea rama NUEVA (evita rama remota vieja)
# Repos hermanos bajo el usuario (ej. C:\Users\acuba\cli-market-*). No requiere carpeta Treevu-ai.
# Uso:
#   powershell -ExecutionPolicy Bypass -File C:\Users\acuba\cli-market-core\ops\ecosystem-patches\deploy-v2.ps1

$ErrorActionPreference = "Stop"
$Branch = "cursor/ecosystem-p0-p2-v2-e95e"
$PatchDir = $PSScriptRoot
$CoreRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ReposParent = Split-Path $CoreRoot -Parent

if (-not (Test-Path (Join-Path $PatchDir "cli-market-backend.patch"))) {
    throw "Ejecuta desde la carpeta padre de los repos o actualiza cli-market-core (PR #38)"
}

function Deploy-Repo {
    param(
        [string]$RepoName,
        [string]$PatchFile,
        [scriptblock]$Verify
    )
    $RepoPath = Join-Path $ReposParent $RepoName
    if (-not (Test-Path $RepoPath)) {
        Write-Host "SKIP $RepoName — no existe en $ReposParent" -ForegroundColor Yellow
        return $false
    }
    Write-Host "`n=== $RepoName ===" -ForegroundColor Cyan
    Push-Location $RepoPath
    try {
        git fetch origin
        git checkout main
        git pull origin main
        git branch -D $Branch 2>$null
        git checkout -b $Branch
        git am --abort 2>$null
        $patchPath = Join-Path $PatchDir $PatchFile
        if (-not (Test-Path $patchPath)) { throw "No encuentro patch: $patchPath" }
        git am $patchPath
        if (-not (& $Verify)) { throw "Verificacion fallo despues de git am" }
        Write-Host "Push $Branch ..." -ForegroundColor Green
        git push -u origin $Branch --force
        Write-Host "OK $RepoName" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "FAIL $RepoName : $_" -ForegroundColor Red
        git am --abort 2>$null
        return $false
    }
    finally {
        Pop-Location
    }
}

Write-Host "Core root: $CoreRoot"
Write-Host "Patch dir: $PatchDir"
Write-Host "Rama nueva: $Branch"

$results = @()
$results += Deploy-Repo "cli-market-backend" "cli-market-backend.patch" {
    (Select-String -Path "collect_prices.py" -Pattern "run_rotating_catalog" -Quiet) -and
    (Select-String -Path "requirements.txt" -Pattern "d4b8061" -Quiet)
}
$results += Deploy-Repo "cli-market-world" "cli-market-world.patch" {
    (Select-String -Path "requirements-railway.txt" -Pattern "d4b8061" -Quiet) -and
    (Select-String -Path "landing\lib\marketStats.ts" -Pattern "mcpTools: 27" -Quiet) -and
    -not (Select-String -Path "collect_prices.py" -Pattern "run_rotating_catalog" -Quiet)
}
$results += Deploy-Repo "cli-market-content" "cli-market-content.patch" {
    Select-String -Path "outbound\procure-sequences.md" -Pattern "Ops.*79" -Quiet
}
$results += Deploy-Repo "procure-copilot" "procure-copilot.patch" {
    Test-Path "app\checkout\success\page.tsx"
}

Write-Host "`n=== Verificacion remota ===" -ForegroundColor Cyan
$urls = @{
    backend = "https://raw.githubusercontent.com/Treevu-ai/cli-market-backend/$Branch/collect_prices.py"
    world   = "https://raw.githubusercontent.com/Treevu-ai/cli-market-world/$Branch/requirements-railway.txt"
}
foreach ($k in $urls.Keys) {
    try {
        $c = (Invoke-WebRequest -Uri $urls[$k] -UseBasicParsing).Content
        $ok = if ($k -eq "backend") { $c -match "run_rotating_catalog" } else { $c -match "d4b8061" }
        Write-Host "$k remote: $(if ($ok) { 'OK' } else { 'FAIL' })"
    } catch {
        Write-Host "$k remote: FAIL (404 o sin acceso)"
    }
}

if ($results -contains $false) {
    Write-Host "`nAlgun repo fallo. Copia el output completo y compartelo." -ForegroundColor Red
    exit 1
}
Write-Host "`nListo. Avanza al agente para crear PRs desde rama $Branch" -ForegroundColor Green
