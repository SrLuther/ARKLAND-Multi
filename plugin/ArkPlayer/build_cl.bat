@echo off
setlocal EnableDelayedExpansion

set PLUGIN_DIR=%~dp0
set SRC_DIR=%PLUGIN_DIR%src
set OBJ_DIR=%PLUGIN_DIR%obj
set BIN_DIR=%PLUGIN_DIR%bin
set SDK_ROOT=%PLUGIN_DIR%..\CustomShop\ArkServerAPI

set SDK_DIR=%SDK_ROOT%\version\Core\Public
set LIB_DIR=%SDK_ROOT%\out_lib
if not exist "%LIB_DIR%\ArkApi.lib" set LIB_DIR=%SDK_ROOT%\lib

if not exist "%SDK_DIR%\API\ARK\Ark.h" (
    if exist "%SDK_ROOT%\API\ARK\Ark.h" (
        set SDK_DIR=%SDK_ROOT%
    ) else (
        echo ERROR: ArkServerAPI SDK nao encontrado em %SDK_ROOT%
        exit /b 1
    )
)

if not exist "%LIB_DIR%\ArkApi.lib" (
    echo ERROR: ArkApi.lib nao encontrado.
    exit /b 1
)

set VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe
if not exist "%VSWHERE%" (
    echo ERROR: vswhere.exe nao encontrado.
    exit /b 1
)

for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS_DIR=%%i
if not defined VS_DIR (
    echo ERROR: Visual Studio com C++ nao encontrado.
    exit /b 1
)

set MSVC_DIR=
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "%VS_DIR%\VC\Tools\MSVC" 2^>nul`) do (
    if not defined MSVC_DIR set MSVC_DIR=%VS_DIR%\VC\Tools\MSVC\%%i
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

if not exist "%OBJ_DIR%" mkdir "%OBJ_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

for /f "usebackq delims=" %%v in ("%PLUGIN_DIR%plugin_version.txt") do set PLUGIN_VER=%%v

echo === Compiling ArkPlayer (v%PLUGIN_VER%) ===
"%CL_EXE%" /c /O2 /MT /nologo /W3 /std:c++20 /EHsc /d2FH4- ^
  /I"%WIN_INCLUDE%" /I"%WIN_SDK_INCLUDE%\ucrt" /I"%WIN_SDK_INCLUDE%\um" /I"%WIN_SDK_INCLUDE%\shared" ^
  /I"%SDK_DIR%" /I"%SDK_ROOT%" /I"%SRC_DIR%" ^
  /DWIN32 /D_WINDOWS /D_USRDLL /DNDEBUG /DARK_GAME ^
  /DUNICODE /D_UNICODE ^
  /D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS /D_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR ^
  /Fo"%OBJ_DIR%\\" ^
  "%SRC_DIR%\Main.cpp" ^
  "%SRC_DIR%\PlayerConfig.cpp" ^
  "%SRC_DIR%\PlayerPerms.cpp" ^
  "%SRC_DIR%\PlayerPoints.cpp" ^
  "%SRC_DIR%\PlayerCommands.cpp"
if %ERRORLEVEL% neq 0 goto :error

echo === Linking DLL ===
"%LINK_EXE%" /DLL /NOLOGO ^
  /OUT:"%BIN_DIR%\ArkPlayer.dll" ^
  /LIBPATH:"%LIB_DIR%" ^
  /LIBPATH:"%WIN_LIB%" ^
  /LIBPATH:"%WIN_SDK_LIB%\ucrt\x64" ^
  /LIBPATH:"%WIN_SDK_LIB%\um\x64" ^
  ArkApi.lib ^
  kernel32.lib user32.lib advapi32.lib ole32.lib oleaut32.lib ^
  "%OBJ_DIR%\Main.obj" ^
  "%OBJ_DIR%\PlayerConfig.obj" ^
  "%OBJ_DIR%\PlayerPerms.obj" ^
  "%OBJ_DIR%\PlayerPoints.obj" ^
  "%OBJ_DIR%\PlayerCommands.obj"
if %ERRORLEVEL% neq 0 goto :error

copy /Y "%PLUGIN_DIR%configs\config.json" "%BIN_DIR%\config.json" >nul
copy /Y "%PLUGIN_DIR%configs\PluginInfo.json" "%BIN_DIR%\PluginInfo.json" >nul

echo.
echo === BUILD SUCCEEDED (v%PLUGIN_VER%) ===
echo Output: %BIN_DIR%\ArkPlayer.dll
goto :end

:error
echo.
echo === BUILD FAILED ===
exit /b 1

:end
endlocal
