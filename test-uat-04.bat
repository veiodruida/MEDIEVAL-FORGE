@echo off
REM Roda os Playwright e2e da Phase 04:
REM   - parameter-studio-sc3.spec.ts    (sigma change -> pixel diff visivel)
REM   - parameter-studio-cancel.spec.ts (cancel restora canvas + sidebar state)
REM
REM playwright.config.ts tem webServer + globalSetup, entao este script
REM nao precisa subir backend/frontend manualmente — o Playwright faz isso.
REM
REM Pre-requisitos (setup.bat ja rodado):
REM   - Python deps + alembic upgrade head
REM   - npm install no frontend
REM   - npx playwright install chromium
REM
REM SC-3 wall-clock budget foi relaxado para 30s nesta phase (Phase 05
REM otimiza). Tempo total esperado: ~60-90s.

setlocal
set REPO=%~dp0

echo === Medieval Forge - Playwright UAT Phase 04 ===
echo Sobe backend :8765 + vite :5173, seeda projeto, roda 2 specs.
echo.

cd /d "%REPO%frontend"
call npx playwright test parameter-studio-sc3.spec.ts parameter-studio-cancel.spec.ts --reporter=line %*
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
