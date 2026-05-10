@echo off
REM Dev mode: starts FastAPI on :8765 and Vite dev server on :5173 in two
REM separate consoles. Vite proxies /api -> 127.0.0.1:8765 (vite.config.ts),
REM so open http://127.0.0.1:5173 to use the workspace with HMR.
REM
REM Close both consoles (or hit Ctrl+C in each) to stop.

setlocal
set REPO=%~dp0

echo === Medieval Forge - Dev mode ===
echo Backend (FastAPI):  http://127.0.0.1:8765
echo Frontend (Vite):    http://127.0.0.1:5173
echo Abra a URL do Vite (5173) — ele faz proxy para o backend.
echo.

start "MF backend (uvicorn :8765)" cmd /k "cd /d "%REPO%backend" && python -m uvicorn medieval_forge.main:app --host 127.0.0.1 --port 8765 --reload"

start "MF frontend (vite :5173)" cmd /k "cd /d "%REPO%frontend" && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

echo Servidores subindo em janelas separadas. Esta janela pode ser fechada.
endlocal
