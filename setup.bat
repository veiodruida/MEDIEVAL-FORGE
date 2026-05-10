@echo off
echo === Medieval Forge - Setup (primeira vez) ===

echo.
echo [1/5] Instalando dependencias Python...
python -m pip install -e ".[dev]"
if errorlevel 1 (
    echo ERRO: falhou ao instalar dependencias Python
    pause
    exit /b 1
)

echo.
echo [2/5] Rodando migracoes do banco de dados...
python -m alembic upgrade head
if errorlevel 1 (
    echo ERRO: falhou ao rodar migracoes
    pause
    exit /b 1
)

echo.
echo [3/5] Instalando dependencias do frontend...
cd frontend
call npm install
if errorlevel 1 (
    echo ERRO: falhou ao instalar dependencias npm
    cd ..
    pause
    exit /b 1
)

echo.
echo [4/5] Instalando navegador Chromium do Playwright (para test-uat.bat)...
call npx playwright install chromium
if errorlevel 1 (
    echo AVISO: instalacao do Chromium do Playwright falhou. test-uat.bat nao funcionara ate corrigir.
)

echo.
echo [5/5] Buildando o frontend...
call npm run build
cd ..
if errorlevel 1 (
    echo ERRO: falhou ao buildar o frontend
    pause
    exit /b 1
)

echo.
echo === Setup concluido! ===
echo   start.bat     - servidor producao (porta 8765, abre browser)
echo   dev.bat       - dev mode (backend :8765 + vite :5173 com HMR)
echo   test-uat.bat  - roda UAT Playwright Phase 03 (sobe servidores sozinho)
echo   seed-uat.bat  - cria projeto seed com artefatos Phase 01 ja gerados
pause
