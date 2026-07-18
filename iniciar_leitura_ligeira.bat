@echo off
setlocal

rem Sempre executar a partir da raiz deste arquivo, mesmo quando aberto por um atalho.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv\Scripts\python.exe
    echo Crie-o com Python 3.13.11 e instale requirements.lock.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%CD%"

".venv\Scripts\python.exe" scripts\check_environment.py --runtime
if errorlevel 1 (
    pause
    exit /b 1
)

".venv\Scripts\python.exe" scripts\check_environment.py --kokoro-ready >nul 2>&1
if not errorlevel 1 (
    echo Kokoro ja esta ativo e saudavel.
    goto start_app
)

where docker >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Docker nao encontrado. O leitor iniciara sem narrador.
    echo Instale Docker Desktop para habilitar o TTS local.
    goto start_app
)

".venv\Scripts\python.exe" scripts\check_environment.py --docker-ready >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Docker Desktop nao esta ativo. O leitor iniciara sem narrador.
    echo Abra o Docker Desktop antes de ligar o narrador.
    goto start_app
)

echo Kokoro esta parado; iniciando a dependencia local em segundo plano...
docker compose up -d tts
if errorlevel 1 (
    echo [AVISO] Nao foi possivel solicitar a inicializacao do Kokoro.
    echo O leitor iniciara normalmente sem narrador.
    goto start_app
)

echo Kokoro solicitado. A inicializacao do modelo continuara em segundo plano.
echo Se ainda estiver carregando, o Narrador permitira tentar novamente.

:start_app
".venv\Scripts\python.exe" scripts\run_server.py %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERRO] Inicializador terminou com codigo %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%