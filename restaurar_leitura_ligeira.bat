@echo off
setlocal

rem A restauracao padrao usa restored-data e nunca sobrescreve data sem --replace.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv\Scripts\python.exe
    exit /b 1
)

if "%~1"=="" (
    echo Uso: restaurar_leitura_ligeira.bat CAMINHO-DO-BACKUP [opcoes]
    echo Destino seguro padrao: restored-data
    echo Para substituir dados reais: --target-data-dir data --replace
    exit /b 2
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
".venv\Scripts\python.exe" scripts\backup_restore.py restore %*
exit /b %ERRORLEVEL%