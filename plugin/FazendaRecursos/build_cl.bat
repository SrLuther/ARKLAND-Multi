@echo off
setlocal EnableDelayedExpansion
set PLUGIN_DIR=%~dp0
set SRC_DIR=%PLUGIN_DIR%src
set OBJ_DIR=%PLUGIN_DIR%obj
set BIN_DIR=%PLUGIN_DIR%bin
set SDK_ROOT=%PLUGIN_DIR%..\CustomShop\ArkServerAPI
set SDK_DIR=%SDK_ROOT%\version\Core\Public
set LIB_DIR=%SDK_ROOT%\out_lib
set MYSQL_LIB_DIR=%PLUGIN_DIR%..\CustomShop\mysql\lib
if not exist "%LIB_DIR%\ArkApi.lib" set LIB_DIR=%SDK_ROOT%\lib
if not exist "%SDK_DIR%\API\ARK\Ark.h" if exist "%SDK_ROOT%\API\ARK\Ark.h" set SDK_DIR=%SDK_ROOT%
if not exist "%SDK_DIR%\API\ARK\Ark.h" (echo ERROR: ArkServerAPI SDK nao encontrado & exit /b 1)
if not exist "%LIB_DIR%\ArkApi.lib" (echo ERROR: ArkApi.lib nao encontrado & exit /b 1)
if not exist "%MYSQL_LIB_DIR%\libmysql.lib" (echo ERROR: libmysql.lib nao encontrado & exit /b 1)
set VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe
if not exist "%VSWHERE%" (echo ERROR: vswhere.exe nao encontrado & exit /b 1)
for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS_DIR=%%i
if not defined VS_DIR (echo ERROR: Visual Studio C++ nao encontrado & exit /b 1)
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "%VS_DIR%\VC\Tools\MSVC" 2^>nul`) do if not defined MSVC_DIR set MSVC_DIR=%VS_DIR%\VC\Tools\MSVC\%%i
set CL_EXE=%MSVC_DIR%\bin\Hostx64\x64\cl.exe
set LINK_EXE=%MSVC_DIR%\bin\Hostx64\x64\link.exe
set WIN_KIT=C:\Program Files (x86)\Windows Kits\10
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "%WIN_KIT%\Include" 2^>nul`) do if not defined WIN_SDK_INCLUDE set WIN_SDK_INCLUDE=%WIN_KIT%\Include\%%i
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "%WIN_KIT%\Lib" 2^>nul`) do if not defined WIN_SDK_LIB set WIN_SDK_LIB=%WIN_KIT%\Lib\%%i
if not exist "%OBJ_DIR%" mkdir "%OBJ_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
"%CL_EXE%" /c /O2 /MT /nologo /W3 /std:c++20 /EHsc /d2FH4- /utf-8 /I"%MSVC_DIR%\include" /I"%WIN_SDK_INCLUDE%\ucrt" /I"%WIN_SDK_INCLUDE%\um" /I"%WIN_SDK_INCLUDE%\shared" /I"%SDK_DIR%" /I"%SDK_ROOT%" /I"%SRC_DIR%" /DWIN32 /D_WINDOWS /D_USRDLL /DNDEBUG /DARK_GAME /DUNICODE /D_UNICODE /D_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR /Fo"%OBJ_DIR%\\" "%SRC_DIR%\Main.cpp" "%SRC_DIR%\FarmConfig.cpp" "%SRC_DIR%\FarmState.cpp" "%SRC_DIR%\FarmSync.cpp" "%SRC_DIR%\FarmPerms.cpp" "%SRC_DIR%\FarmCommands.cpp"
if errorlevel 1 goto error
"%LINK_EXE%" /DLL /NOLOGO /OUT:"%BIN_DIR%\FazendaRecursos.dll" /LIBPATH:"%LIB_DIR%" /LIBPATH:"%MYSQL_LIB_DIR%" /LIBPATH:"%MSVC_DIR%\lib\x64" /LIBPATH:"%WIN_SDK_LIB%\ucrt\x64" /LIBPATH:"%WIN_SDK_LIB%\um\x64" ArkApi.lib libmysql.lib kernel32.lib user32.lib advapi32.lib ole32.lib oleaut32.lib winhttp.lib "%OBJ_DIR%\Main.obj" "%OBJ_DIR%\FarmConfig.obj" "%OBJ_DIR%\FarmState.obj" "%OBJ_DIR%\FarmSync.obj" "%OBJ_DIR%\FarmPerms.obj" "%OBJ_DIR%\FarmCommands.obj"
if errorlevel 1 goto error
if exist "%PLUGIN_DIR%..\CustomShop\bin\libmariadb.dll" copy /Y "%PLUGIN_DIR%..\CustomShop\bin\libmariadb.dll" "%BIN_DIR%\libmysql.dll" >nul
if not exist "%BIN_DIR%\libmysql.dll" (echo ERROR: libmariadb.dll indisponivel para o conector MySQL & exit /b 1)
if exist "%PLUGIN_DIR%..\CustomShop\bin\z.dll" copy /Y "%PLUGIN_DIR%..\CustomShop\bin\z.dll" "%BIN_DIR%\z.dll" >nul
if not exist "%BIN_DIR%\z.dll" (echo ERROR: z.dll requerida pelo cliente MySQL indisponivel & exit /b 1)
copy /Y "%PLUGIN_DIR%configs\config.json" "%BIN_DIR%\config.json" >nul
copy /Y "%PLUGIN_DIR%configs\PluginInfo.json" "%BIN_DIR%\PluginInfo.json" >nul
echo BUILD SUCCEEDED: %BIN_DIR%\FazendaRecursos.dll
exit /b 0
:error
echo BUILD FAILED
exit /b 1
