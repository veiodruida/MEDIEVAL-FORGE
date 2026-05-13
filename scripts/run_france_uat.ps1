# Phase 05 Plan 12 — France 1066 UAT live runner (PowerShell mirror of run_france_uat.sh).
# Closes VERIFICATION Gap 2: live browser session against the live stack.
#
# Usage:   pwsh scripts/run_france_uat.ps1   (or PowerShell 5.1: powershell -ExecutionPolicy Bypass -File scripts/run_france_uat.ps1)
# Expects: .\backend\pyproject.toml + .\frontend\package.json present (repo root).

$ErrorActionPreference = "Stop"

$ROOT = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $ROOT

Write-Host "[1/5] Killing any lingering dev servers..."
Get-Process | Where-Object { $_.ProcessName -match "medieval-forge|uvicorn|node" -and $_.MainWindowTitle -match "vite|forge" } | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {}
}
Start-Sleep -Seconds 1

Write-Host "[2/5] Frontend build (catches type errors before Playwright)..."
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "frontend build failed (exit=$LASTEXITCODE)" }
Pop-Location

Write-Host "[3/5] Starting backend (medieval-forge start) in background..."
$BackendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location $root
    medieval-forge start *>&1 | Out-File -FilePath "$env:TEMP\medieval_forge_backend.log"
} -ArgumentList $ROOT
Write-Host "    backend job id=$($BackendJob.Id)  log=$env:TEMP\medieval_forge_backend.log"

Write-Host "[4/5] Starting frontend dev server in background..."
$FrontendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location "$root\frontend"
    npm run dev *>&1 | Out-File -FilePath "$env:TEMP\medieval_forge_frontend.log"
} -ArgumentList $ROOT
Write-Host "    frontend job id=$($FrontendJob.Id) log=$env:TEMP\medieval_forge_frontend.log"

Write-Host "    Waiting for backend (http://localhost:8000/api/v3/regions)..."
for ($i = 1; $i -le 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/api/v3/regions" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { Write-Host "    backend ready"; break }
    } catch { }
    Start-Sleep -Seconds 1
}

Write-Host "    Waiting for frontend (http://localhost:5173)..."
for ($i = 1; $i -le 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -in 200,304) { Write-Host "    frontend ready"; break }
    } catch { }
    Start-Sleep -Seconds 1
}

try {
    Write-Host "[5/5] Running Playwright spec: france_1066_create_project"
    Set-Location frontend
    npx playwright test france_1066_create_project --reporter=line
    $EXITCODE = $LASTEXITCODE
} finally {
    Write-Host "[cleanup] Shutting down servers..."
    Stop-Job   -Job $BackendJob,$FrontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $BackendJob,$FrontendJob -Force -ErrorAction SilentlyContinue
    Set-Location $ROOT
}

Write-Host ""
Write-Host "===================="
Write-Host "Playwright exit code: $EXITCODE"
Write-Host "===================="
exit $EXITCODE
