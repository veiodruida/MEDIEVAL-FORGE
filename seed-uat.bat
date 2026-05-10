@echo off
REM Cria um projeto UAT com os 14 arquivos do contrato (10 Phase 01 + 4
REM canvas-sidecars) ja seeded no output dir. Imprime o UUID e a URL para
REM voce abrir no browser apos rodar dev.bat.
REM
REM Pipeline cacheado em ~/.medieval-forge/uat_cache/iberia_868/ — primeira
REM execucao demora ~45s, subsequentes sao instantaneas.

setlocal
set REPO=%~dp0

echo === Medieval Forge - Seed UAT project ===
echo Gera/reutiliza pipeline iberia_868 + cria Project DB + seed artifacts.
echo.

cd /d "%REPO%backend"
python -c "from tests.fixtures.uat_setup import main; import sys; sys.exit(main(['uat_setup.py']))"
set EC=%ERRORLEVEL%
cd /d "%REPO%"

if %EC% NEQ 0 (
    echo.
    echo === Seed FALHOU (exit %EC%^) ===
    pause
    exit /b %EC%
)

echo.
echo === Seed concluido ===
echo Linha JSON acima contem project_id. Abra:
echo   http://127.0.0.1:5173/projects/^<project_id^>   (com dev.bat^)
echo   http://127.0.0.1:8765/projects/^<project_id^>   (com start.bat^)
endlocal
