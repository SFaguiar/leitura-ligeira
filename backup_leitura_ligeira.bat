@echo off
setlocal

rem Sempre executar a partir da raiz deste arquivo, mesmo quando aberto por um atalho.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv\Scripts\python.exe
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
".venv\Scripts\python.exe" scripts\backup_restore.py backup %*
exit /b %ERRORLEVEL%