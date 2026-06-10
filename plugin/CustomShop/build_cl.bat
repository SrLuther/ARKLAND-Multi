@echo off
setlocal EnableDelayedExpansion

set PLUGIN_DIR=%~dp0
set SRC_DIR=%PLUGIN_DIR%src
set OBJ_DIR=%PLUGIN_DIR%obj
set BIN_DIR=%PLUGIN_DIR%bin
set MYSQL_DIR=%PLUGIN_DIR%mariadb

set SDK_DIR=%PLUGIN_DIR%ArkServerAPI\version\Core\Public
set LIB_DIR=%PLUGIN_DIR%ArkServerAPI\out_lib
if not exist "%LIB_DIR%\ArkApi.lib" set LIB_DIR=%PLUGIN_DIR%ArkServerAPI\lib

if not exist "%SDK_DIR%\API\ARK\Ark.h" (
    if exist "%PLUGIN_DIR%ArkServerAPI\API\ARK\Ark.h" (
        set SDK_DIR=%PLUGIN_DIR%ArkServerAPI
    ) else (
        echo ERROR: ArkServerAPI SDK nao encontrado.
        echo Coloque o SDK em: %PLUGIN_DIR%ArkServerAPI
        echo Esperado: version\Core\Public\API\ARK\Ark.h  ou  API\ARK\Ark.h
        exit /b 1
    )
)

if not exist "%LIB_DIR%\ArkApi.lib" (
    echo ERROR: ArkApi.lib nao encontrado em out_lib nem lib.
    exit /b 1
)

if not exist "%MYSQL_DIR%\lib\libmariadb.lib" (
    echo ERROR: libmariadb.lib nao encontrado em %MYSQL_DIR%\lib
    echo Baixe o MariaDB Connector/C e copie libmariadb.lib para mariadb\lib\
    exit /b 1
)

set VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe
if not exist "%VSWHERE%" (
    echo ERROR: vswhere.exe nao encontrado. Instale o Visual Studio 2022 com C++.
    exit /b 1
)

for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS_DIR=%%i
if not defined VS_DIR (
    echo ERROR: Visual Studio com ferramentas C++ nao encontrado.
    exit /b 1
)

set MSVC_DIR=
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "%VS_DIR%\VC\Tools\MSVC" 2^>nul`) do (
    if not defined MSVC_DIR set MSVC_DIR=%VS_DIR%\VC\Tools\MSVC\%%i
)
if not defined MSVC_DIR (
    echo ERROR: MSVC toolset nao encontrado em %VS_DIR%\VC\Tools\MSVC
    exit /b 1
)

set CL_EXE=%MSVC_DIR%\bin\Hostx64\x64\cl.exe
set LINK_EXE=%MSVC_DIR%\bin\Hostx64\x64\link.exe

set WIN_INCLUDE=%MSVC_DIR%\include
set WIN_LIB=%MSVC_DIR%\lib\x64

set "WIN_KIT=C:\Program Files (x86)\Windows Kits\10"
set WIN_SDK_INCLUDE=
set WIN_SDK_LIB=
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "!WIN_KIT!\Include" 2^>nul`) do (
    if not defined WIN_SDK_INCLUDE set "WIN_SDK_INCLUDE=!WIN_KIT!\Include\%%i"
)
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "!WIN_KIT!\Lib" 2^>nul`) do (
    if not defined WIN_SDK_LIB set "WIN_SDK_LIB=!WIN_KIT!\Lib\%%i"
)
if not defined WIN_SDK_INCLUDE (
    echo ERROR: Windows SDK nao encontrado.
    exit /b 1
)

if not exist "%OBJ_DIR%" mkdir "%OBJ_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

echo === SDK: %SDK_DIR% ===
echo === MSVC: %MSVC_DIR% ===

echo === Compiling C++ sources ===
"%CL_EXE%" /c /O2 /MT /nologo /W3 /std:c++20 /EHsc /d2FH4- ^
  /I"%WIN_INCLUDE%" /I"%WIN_SDK_INCLUDE%\ucrt" /I"%WIN_SDK_INCLUDE%\um" /I"%WIN_SDK_INCLUDE%\shared" ^
  /I"%SDK_DIR%" /I"%SRC_DIR%" /I"%MYSQL_DIR%\include" ^
  /DWIN32 /D_WINDOWS /D_USRDLL /DNDEBUG /DARK_GAME ^
  /DUNICODE /D_UNICODE ^
  /D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS /D_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR ^
  /Fo"%OBJ_DIR%\\" ^
  "%SRC_DIR%\Main.cpp" ^
  "%SRC_DIR%\ShopBridge.cpp" ^
  "%SRC_DIR%\ShopConfig.cpp" ^
  "%SRC_DIR%\ShopData.cpp" ^
  "%SRC_DIR%\ShopPerms.cpp" ^
  "%SRC_DIR%\ShopPoints.cpp" ^
  "%SRC_DIR%\ShopStore.cpp" ^
  "%SRC_DIR%\ShopVip.cpp" ^
  "%SRC_DIR%\TimedPoints.cpp" ^
  "%SRC_DIR%\Commands.cpp" ^
  "%SRC_DIR%\HttpClient.cpp"
if %ERRORLEVEL% neq 0 goto :error

echo === Linking DLL ===
"%LINK_EXE%" /DLL /NOLOGO ^
  /OUT:"%BIN_DIR%\CustomShop.dll" ^
  /LIBPATH:"%LIB_DIR%" ^
  /LIBPATH:"%MYSQL_DIR%\lib" ^
  /LIBPATH:"%WIN_LIB%" ^
  /LIBPATH:"%WIN_SDK_LIB%\ucrt\x64" ^
  /LIBPATH:"%WIN_SDK_LIB%\um\x64" ^
  ArkApi.lib libmariadb.lib winhttp.lib ^
  kernel32.lib user32.lib advapi32.lib ole32.lib oleaut32.lib ^
  "%OBJ_DIR%\Main.obj" ^
  "%OBJ_DIR%\ShopBridge.obj" ^
  "%OBJ_DIR%\ShopConfig.obj" ^
  "%OBJ_DIR%\ShopData.obj" ^
  "%OBJ_DIR%\ShopPerms.obj" ^
  "%OBJ_DIR%\ShopPoints.obj" ^
  "%OBJ_DIR%\ShopStore.obj" ^
  "%OBJ_DIR%\ShopVip.obj" ^
  "%OBJ_DIR%\TimedPoints.obj" ^
  "%OBJ_DIR%\Commands.obj" ^
  "%OBJ_DIR%\HttpClient.obj"
if %ERRORLEVEL% neq 0 goto :error

copy /Y "%PLUGIN_DIR%configs\config.json" "%BIN_DIR%\config.json" >nul

echo.
echo === BUILD SUCCEEDED ===
echo Output: %BIN_DIR%\CustomShop.dll
goto :end

:error
echo.
echo === BUILD FAILED (error %ERRORLEVEL%) ===
exit /b 1

:end
endlocal
