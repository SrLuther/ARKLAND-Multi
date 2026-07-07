@echo off
setlocal EnableDelayedExpansion
echo ============================================================
echo  ARKLAND - Server Manager  -  Build Script
echo ============================================================
echo.

:: -- Localiza Python ----------------------------------------------------------
set PYTHON=

:: 0) Python port?til local com tkinter (python-build-standalone)
if exist "%~dp0.python-full\python.exe" (
    set "PYTHON=%~dp0.python-full\python.exe"
    goto :found_python
)

:: 1) venv local
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
    goto :found_python
)

:: 2) python no PATH
where python >nul 2>&1
if !errorlevel! == 0 (
    for /f "tokens=*" %%P in ('where python') do (
        "%%P" --version >nul 2>&1
        if !errorlevel! == 0 (
            set "PYTHON=%%P"
            goto :found_python
        )
    )
)

:: 3) Locais t?picos de instala??o
for %%V in (313 312 311 310 39) do (
    for %%D in (
        "%LocalAppData%\Programs\Python\Python%%V\python.exe"
        "C:\Python%%V\python.exe"
        "C:\Program Files\Python%%V\python.exe"
    ) do (
        if exist %%D (
            set "PYTHON=%%~D"
            goto :found_python
        )
    )
)

:: 4) Conda / Miniconda
for %%D in (
    "%UserProfile%\miniconda3\python.exe"
    "%UserProfile%\anaconda3\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
) do (
    if exist %%D (
        set "PYTHON=%%~D"
        goto :found_python
    )
)

echo [ERRO] Python nao encontrado!
echo Instale Python 3.9+ em https://www.python.org/downloads/
echo Marque "Add Python to PATH" durante a instalacao.
pause
exit /b 1

:found_python
echo Usando Python: %PYTHON%
echo.

:: -- Cria/atualiza venv (apenas se nao for .python-full ou .venv ja existente) 
set USE_VENV=1
if not "x%PYTHON:.python-full=%"=="x%PYTHON%" set USE_VENV=0
if not "x%PYTHON:.venv=%"=="x%PYTHON%" set USE_VENV=0

if %USE_VENV%==1 (
    if not exist "%~dp0.venv\Scripts\python.exe" (
        echo [0/4] Criando ambiente virtual...
        "%PYTHON%" -m venv "%~dp0.venv"
        echo.
    )
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
)

:: -- Instala depend?ncias -----------------------------------------------------
echo [1/4] Instalando dependencias...
"%PYTHON%" -m pip install --upgrade pip --quiet
"%PYTHON%" -m pip install -r "%~dp0requirements.txt" --quiet
"%PYTHON%" -m pip install -r "%~dp0plugin\arkshop_web\requirements.txt" --quiet
"%PYTHON%" -m pip install pyinstaller --quiet
echo       Concluido.
echo.

echo [1a/4] Sincronizando versoes dos plugins com APP_VERSION...
"%PYTHON%" "%~dp0scripts\sync_plugin_versions.py" --from-app
if errorlevel 1 (
    echo [AVISO] sync_plugin_versions.py falhou — continuando com versoes existentes.
)
echo.

echo [1b/4] Compilando CustomShop.dll...
if exist "%~dp0plugin\CustomShop\build_cl.bat" (
    pushd "%~dp0plugin\CustomShop"
    call build_cl.bat
    set CS_BUILD=!errorlevel!
    popd
    if !CS_BUILD! neq 0 (
        echo [AVISO] build CustomShop falhou — usando DLL existente em plugin\CustomShop\bin\
    ) else (
        echo       CustomShop.dll atualizado em plugin\CustomShop\bin\
    )
) else (
    echo [AVISO] plugin\CustomShop\build_cl.bat nao encontrado — pulando compile do plugin.
)
echo.

echo [1c/4] Compilando CustomDinoDeliver.dll...
if exist "%~dp0plugin\CustomDinoDeliver\build_cl.bat" (
    pushd "%~dp0plugin\CustomDinoDeliver"
    call build_cl.bat
    set CD_BUILD=!errorlevel!
    popd
    if !CD_BUILD! neq 0 (
        echo [AVISO] build CustomDinoDeliver falhou — usando DLL existente em plugin\CustomDinoDeliver\bin\
    ) else (
        echo       CustomDinoDeliver.dll atualizado em plugin\CustomDinoDeliver\bin\
    )
) else (
    echo [AVISO] plugin\CustomDinoDeliver\build_cl.bat nao encontrado — pulando compile do plugin.
)
echo.

:: -- Gera o execut?vel --------------------------------------------------------
echo [2/4] Gerando executavel com PyInstaller (modo onefile)...
"%PYTHON%" -m PyInstaller --noconfirm "%~dp0ARKLAND-Multi.spec"
if !errorlevel! neq 0 (
    echo [ERRO] PyInstaller falhou. Verifique os erros acima.
    pause
    exit /b 1
)
echo       Executavel: dist\ARKLAND-ServerManager.exe
echo.

echo [2b/4] Gerando ARKLAND-Updater.exe...
"%PYTHON%" -m PyInstaller --noconfirm "%~dp0ARKLAND-Updater.spec"
if !errorlevel! neq 0 (
    echo [ERRO] PyInstaller falhou ao gerar ARKLAND-Updater.exe.
    pause
    exit /b 1
)
echo       Executavel: dist\ARKLAND-Updater.exe
echo.

echo [2c/4] Gerando HTML do regulamento (Web Store)...
"%PYTHON%" "%~dp0scripts\build_regulamento_html.py"
if !errorlevel! neq 0 (
    echo [ERRO] build_regulamento_html.py falhou.
    pause
    exit /b 1
)
echo.

echo [2d/4] Gerando ARKLAND-WebStore.exe...
"%PYTHON%" -m PyInstaller --noconfirm "%~dp0ARKLAND-WebStore.spec"
if !errorlevel! neq 0 (
    echo [ERRO] PyInstaller falhou ao gerar ARKLAND-WebStore.exe.
    pause
    exit /b 1
)
echo       Executavel: dist\ARKLAND-WebStore.exe
echo.

:: -- Gera o installer com Inno Setup (se dispon?vel) --------------------------
echo [3/4] Procurando Inno Setup...
set ISCC=

for %%D in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    "C:\Program Files\Inno Setup 5\ISCC.exe"
) do (
    if exist %%D (
        set "ISCC=%%~D"
        goto :found_iscc
    )
)

echo       Inno Setup nao encontrado - pulando geracao do installer.
echo       Instale em: https://jrsoftware.org/isinfo.php
goto :build_done

:found_iscc
echo       Inno Setup: %ISCC%
"%ISCC%" /Q "%~dp0setup.iss"
if !errorlevel! neq 0 (
    echo [AVISO] Inno Setup retornou erro. Verifique setup.iss.
) else (
    echo       Installer gerado em: installer\
)

:: -- Sincroniza CHANGELOG.md com src/version.py -------------------------------
echo [3b/4] Sincronizando CHANGELOG.md...
"%PYTHON%" "%~dp0scripts\sync_changelog_md.py"
if !errorlevel! neq 0 (
    echo [AVISO] sync_changelog_md.py falhou — CHANGELOG.md pode estar desatualizado.
)
echo.

:build_done
echo.
echo [4/4] Build concluido!
echo.
echo   EXE standalone : dist\ARKLAND-ServerManager.exe
if exist "%~dp0installer\" (
    echo   Installer       : installer\ARKLAND-ServerManager-Setup-*.exe
)
echo.
