@echo off
setlocal
echo ============================================
echo  [ARKLAND]-Multi  -  Build Script
echo ============================================
echo.

:: Detecta o Python: usa o venv local se existir, senão cai para o Python do PATH
if exist "%~dp0.venv\Scripts\python.exe" (
    set PYTHON=%~dp0.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo Usando Python: %PYTHON%
echo.

:: Instala dependencias
echo [1/3] Instalando dependencias...
"%PYTHON%" -m pip install -r requirements.txt
"%PYTHON%" -m pip install pyinstaller
echo.

:: Cria o executavel
echo [2/3] Gerando executavel com PyInstaller...
"%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "ARKLAND-Multi" ^
  --icon "ig\ArkLandBR.ico" ^
  --add-data "ig;ig" ^
  main.py

echo.
echo [3/3] Concluido!
echo O executavel esta em: dist\ARKLAND-Multi.exe
echo.
pause
