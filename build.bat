@echo off
setlocal
echo ============================================
echo  [ARKLAND]-Multi  -  Build Script
echo ============================================
echo.

:: Instala dependencias
echo [1/3] Instalando dependencias...
pip install -r requirements.txt
pip install pyinstaller
echo.

:: Cria o executavel
echo [2/3] Gerando executavel com PyInstaller...
pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "ARKLAND-Multi" ^
  main.py

echo.
echo [3/3] Concluido!
echo O executavel esta em: dist\ARKLAND-Multi.exe
echo.
pause
