@echo off
setlocal EnableDelayedExpansion
set "PLUGIN_DIR=%~dp0"
if not defined CHAT_SDK_ROOT set "CHAT_SDK_ROOT=%PLUGIN_DIR%..\CustomShop\ArkServerAPI"
set "SDK_PUBLIC=%CHAT_SDK_ROOT%\version\Core\Public"
set "SDK_LIB=%CHAT_SDK_ROOT%\out_lib"
if not exist "%SDK_LIB%\ArkApi.lib" set "SDK_LIB=%CHAT_SDK_ROOT%\lib"
if not exist "%SDK_PUBLIC%\API\ARK\Ark.h" (echo SDK do ArkServerAPI ASE nao encontrado. & exit /b 1)
if not exist "%SDK_LIB%\ArkApi.lib" (echo ArkApi.lib nao encontrada. & exit /b 1)
if not defined CHAT_PYTHON (echo Defina CHAT_PYTHON com o interpretador do ambiente do projeto. & exit /b 1)
"%CHAT_PYTHON%" "%PLUGIN_DIR%generate_assets.py"
if errorlevel 1 exit /b 1
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VS_DIR=%%i"
if not defined VS_DIR (echo Ferramentas C++ do Visual Studio nao encontradas. & exit /b 1)
call "%VS_DIR%\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
if not exist "%PLUGIN_DIR%obj" mkdir "%PLUGIN_DIR%obj"
if not exist "%PLUGIN_DIR%bin" mkdir "%PLUGIN_DIR%bin"
pushd "%PLUGIN_DIR%obj"
cl /c /MP /nologo /O2 /MT /std:c++20 /utf-8 /EHsc /d2FH4- /W3 /DWIN32 /D_WINDOWS /DARK_GAME /DUNICODE /D_UNICODE /DNDEBUG /D_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR /D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS /I"%SDK_PUBLIC%" /I"%CHAT_SDK_ROOT%" /I"%PLUGIN_DIR%src" "%PLUGIN_DIR%src\ChatCore.cpp" "%PLUGIN_DIR%src\ChatTransport.cpp" "%PLUGIN_DIR%src\Main.cpp"
if errorlevel 1 (popd & exit /b 1)
link /DLL /NOLOGO /OUT:"%PLUGIN_DIR%bin\ChatArkland.dll" /LIBPATH:"%SDK_LIB%" ArkApi.lib kernel32.lib user32.lib advapi32.lib ole32.lib winhttp.lib normaliz.lib ChatCore.obj ChatTransport.obj Main.obj
if errorlevel 1 (popd & exit /b 1)
cl /nologo /O2 /MT /std:c++20 /utf-8 /EHsc /D_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR /I"%SDK_PUBLIC%" /I"%PLUGIN_DIR%src" "%PLUGIN_DIR%tests\core_tests.cpp" ChatCore.obj /link /OUT:"%PLUGIN_DIR%bin\ChatArkland-CoreTests.exe" ole32.lib normaliz.lib
if errorlevel 1 (popd & exit /b 1)
"%PLUGIN_DIR%bin\ChatArkland-CoreTests.exe"
if errorlevel 1 (popd & exit /b 1)
popd
copy /Y "%PLUGIN_DIR%configs\PluginInfo.json" "%PLUGIN_DIR%bin\PluginInfo.json" >nul
if not exist "%PLUGIN_DIR%bin\config.json" copy "%PLUGIN_DIR%configs\config.json" "%PLUGIN_DIR%bin\config.json" >nul
echo Chat Arkland compilado e testes do nucleo executados. Validacao em jogo continua obrigatoria.
exit /b 0
