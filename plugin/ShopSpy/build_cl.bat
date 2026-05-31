@echo off
setlocal

set VS_DIR=C:\Program Files\Microsoft Visual Studio\18\Community
set MSVC_DIR=%VS_DIR%\VC\Tools\MSVC\14.51.36231

set CL_EXE=%MSVC_DIR%\bin\Hostx64\x64\cl.exe
set LINK_EXE=%MSVC_DIR%\bin\Hostx64\x64\link.exe

set PLUGIN_DIR=%~dp0
rem Reutiliza o SDK do CustomShop (pasta irmã)
set SDK_DIR=%PLUGIN_DIR%..\CustomShop\ArkServerAPI\version\Core\Public
set LIB_DIR=%PLUGIN_DIR%..\CustomShop\ArkServerAPI\out_lib
set SRC_DIR=%PLUGIN_DIR%src

pushd "%~dp0"
set OBJ_DIR=%CD%\obj
set BIN_DIR=%CD%\bin
popd

set WIN_INCLUDE=%MSVC_DIR%\include
set WIN_SDK_INCLUDE=C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0
set WIN_LIB=%MSVC_DIR%\lib\x64
set WIN_SDK_LIB=C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0

if not exist "%OBJ_DIR%" mkdir "%OBJ_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

echo === Verificando SDK ===
if not exist "%SDK_DIR%\API\ARK\Ark.h" (
    echo ERRO: SDK nao encontrado em: %SDK_DIR%
    echo Certifique-se de que CustomShop\ArkServerAPI esta instalado.
    exit /b 1
)
echo SDK OK: %SDK_DIR%

echo === Compilando ShopSpy.cpp ===
"%CL_EXE%" /c /O2 /MD /nologo /W3 /std:c++20 /EHsc ^
  /I"%WIN_INCLUDE%" /I"%WIN_SDK_INCLUDE%\ucrt" /I"%WIN_SDK_INCLUDE%\um" /I"%WIN_SDK_INCLUDE%\shared" ^
  /I"%SDK_DIR%" /I"%SRC_DIR%" ^
  /DWIN32 /D_WINDOWS /D_USRDLL /DNDEBUG /DARK_GAME ^
  /DUNICODE /D_UNICODE ^
  /D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS /D_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR ^
  /Fo"%OBJ_DIR%\Main.obj" ^
  "%SRC_DIR%\Main.cpp"
if %ERRORLEVEL% neq 0 goto :error

echo === Linkando ShopSpy.dll ===
"%LINK_EXE%" /DLL /NOLOGO ^
  /OUT:"%BIN_DIR%\ShopSpy.dll" ^
  /LIBPATH:"%LIB_DIR%" ^
  /LIBPATH:"%WIN_LIB%" ^
  /LIBPATH:"%WIN_SDK_LIB%\ucrt\x64" ^
  /LIBPATH:"%WIN_SDK_LIB%\um\x64" ^
  ArkApi.lib ^
  kernel32.lib user32.lib advapi32.lib ^
  "%OBJ_DIR%\Main.obj"
if %ERRORLEVEL% neq 0 goto :error

echo.
echo === BUILD OK ===
echo Output: %BIN_DIR%\ShopSpy.dll
echo.
echo === DEPLOY ===
echo 1. Copiar %BIN_DIR%\ShopSpy.dll  ->  ArkApi/Plugins/ShopSpy/ShopSpy.dll
echo 2. Copiar %PLUGIN_DIR%configs\config.json  ->  ArkApi/Plugins/ShopSpy/config.json
goto :end

:error
echo.
echo === BUILD FALHOU (erro %ERRORLEVEL%) ===
exit /b 1

:end
endlocal
