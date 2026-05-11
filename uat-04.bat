@echo off
REM Phase 04 manual UAT helper.
REM
REM Sobe backend :8765 + vite :5173 em janelas separadas, seeda um projeto
REM UAT (iberia_868 com 14 artefatos), imprime o project_id e abre o
REM checklist 04-06-HUMAN-UAT.md ao lado do browser.
REM
REM Os 12 testes manuais ficam em:
REM   .planning/phases/04-parameter-studio-live-re-render/04-06-HUMAN-UAT.md
REM
REM Pre-requisitos: setup.bat ja rodado.

setlocal
set REPO=%~dp0
set UAT_FILE=%REPO%.planning\phases\04-parameter-studio-live-re-render\04-06-HUMAN-UAT.md

echo === Medieval Forge - UAT Phase 04 (parameter studio) ===
echo Backend (FastAPI):  http://127.0.0.1:8765
echo Frontend (Vite):    http://127.0.0.1:5173
echo Checklist:          %UAT_FILE%
echo.

echo [1/3] Seed UAT project (iberia_868 + 14 artefatos)...
cd /d "%REPO%backend"
python -c "from tests.fixtures.uat_setup import main; import sys; sys.exit(main(['uat_setup.py']))"
set SEED_EC=%ERRORLEVEL%
cd /d "%REPO%"
if %SEED_EC% NEQ 0 (
    echo ERRO: seed UAT falhou (exit %SEED_EC%^).
    pause
    exit /b %SEED_EC%
)

echo.
echo [2/3] Subindo backend + frontend em janelas separadas...
start "MF backend (uvicorn :8765)" cmd /k "cd /d "%REPO%backend" && python -m uvicorn medieval_forge.main:app --host 127.0.0.1 --port 8765 --reload"
start "MF frontend (vite :5173)" cmd /k "cd /d "%REPO%frontend" && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

echo.
echo [3/3] Abrindo checklist + browser...
REM Pequena espera para Vite ficar pronto antes de abrir o browser.
timeout /t 8 /nobreak >nul
start "" "%UAT_FILE%"
start "" "http://127.0.0.1:5173/projects"

echo.
echo === Pronto ===
echo Use o project_id impresso acima (linha JSON do seed) para abrir o projeto.
echo URL direta: http://127.0.0.1:5173/projects/^<project_id^>
echo.
echo Rode os 12 testes em ordem. Reporte cada resultado para o Claude transcrever no UAT.md.
echo Para parar: feche as duas janelas (backend + frontend).
endlocal
