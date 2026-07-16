@echo off
setlocal

rem Sempre executar a partir da raiz deste arquivo, mesmo quando aberto por um atalho.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv\Scripts\python.exe
    echo Crie o ambiente e instale requirements.txt antes de iniciar o servico.
    pause
    exit /b 1
)

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Docker nao foi encontrado no PATH.
    echo Inicie o Docker Desktop e tente novamente.
    pause
    exit /b 1
)

echo Verificando o Docker Desktop e iniciando o Kokoro, se necessario...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERRO] O Docker Desktop nao esta ativo ou nao respondeu.
    echo Inicie o Docker Desktop e tente novamente.
    pause
    exit /b 1
)

docker compose up -d --wait tts
if errorlevel 1 (
    echo [ERRO] Nao foi possivel iniciar ou aguardar o servico Kokoro.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%CD%"

echo Iniciando Leitura Ligeira em http://localhost:8000
echo Para encerrar, pressione Ctrl+C nesta janela.
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERRO] Uvicorn terminou com codigo %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
