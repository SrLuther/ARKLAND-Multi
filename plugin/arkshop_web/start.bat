@echo off
echo ArkShop Web Manager — ARKLAND
echo ================================
cd /d "%~dp0"

:: Python embarcado do ARKLAND (ajuste o caminho se necessário)
set PYTHON=%~dp0..\..\python-full\python.exe
if not exist "%PYTHON%" set PYTHON=%~dp0..\..\.python-full\python.exe
if not exist "%PYTHON%" set PYTHON=python

:: Instala dependências se necessário
"%PYTHON%" -m pip show flask >nul 2>&1 || "%PYTHON%" -m pip install -r "%~dp0requirements.txt" -q

:: Define porta padrão
set PORT=5177

echo Iniciando servidor em http://127.0.0.1:%PORT%
echo Pressione Ctrl+C para parar.
echo.

start "" "http://127.0.0.1:%PORT%"
"%PYTHON%" "%~dp0app.py"
pause
