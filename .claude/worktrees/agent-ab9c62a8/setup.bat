@echo off
echo === Medieval Forge - Setup (primeira vez) ===

echo.
echo [1/4] Instalando dependencias Python...
python -m pip install -e ".[dev]"
if errorlevel 1 (
    echo ERRO: falhou ao instalar dependencias Python
    pause
    exit /b 1
)

echo.
echo [2/4] Rodando migracoes do banco de dados...
python -m alembic upgrade head
if errorlevel 1 (
    echo ERRO: falhou ao rodar migracoes
    pause
    exit /b 1
)

echo.
echo [3/4] Instalando dependencias do frontend...
cd frontend
call npm install
if errorlevel 1 (
    echo ERRO: falhou ao instalar dependencias npm
    cd ..
    pause
    exit /b 1
)

echo.
echo [4/4] Buildando o frontend...
call npm run build
cd ..
if errorlevel 1 (
    echo ERRO: falhou ao buildar o frontend
    pause
    exit /b 1
)

echo.
echo === Setup concluido! ===
echo Rode start.bat para iniciar o servidor.
pause
