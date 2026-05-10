@echo off
REM Roda o UAT Playwright da Phase 03 (Plan 03-08).
REM
REM playwright.config.ts tem webServer + globalSetup, entao este script
REM nao precisa subir backend/frontend manualmente — o Playwright faz isso.
REM
REM Pre-requisitos (rode setup.bat se ainda nao fez):
REM   - Python deps instaladas (pip install -e ".[dev]")
REM   - npm install no frontend
REM   - npx playwright install chromium

setlocal
set REPO=%~dp0

echo === Medieval Forge - UAT Phase 03 ===
echo Sobe backend :8765 + vite :5173, seed projeto, roda spec.
echo.

cd /d "%REPO%frontend"
call npx playwright test 03-canvas-workspace.spec.ts --reporter=line %*
set EC=%ERRORLEVEL%
cd /d "%REPO%"

if %EC% NEQ 0 (
    echo.
    echo === UAT FALHOU (exit %EC%^) ===
    echo Para investigar: cd frontend ^&^& npx playwright show-report
    pause
    exit /b %EC%
)

echo.
echo === UAT PASSOU ===
endlocal
