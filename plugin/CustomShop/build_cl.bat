@echo off
setlocal

set VS_DIR=C:\Program Files\Microsoft Visual Studio\18\Community
set MSVC_DIR=%VS_DIR%\VC\Tools\MSVC\14.51.36231

set CL_EXE=%MSVC_DIR%\bin\Hostx64\x64\cl.exe
set LINK_EXE=%MSVC_DIR%\bin\Hostx64\x64\link.exe

set PLUGIN_DIR=%~dp0
set SDK_DIR=%PLUGIN_DIR%ArkServerAPI\version\Core\Public
set LIB_DIR=%PLUGIN_DIR%ArkServerAPI\out_lib
set SRC_DIR=%PLUGIN_DIR%src
set OBJ_DIR=%PLUGIN_DIR%obj
set BIN_DIR=%PLUGIN_DIR%bin

set WIN_INCLUDE=%MSVC_DIR%\include
set WIN_SDK_INCLUDE=C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0
set WIN_LIB=%MSVC_DIR%\lib\x64
set WIN_SDK_LIB=C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0

if not exist "%OBJ_DIR%" mkdir "%OBJ_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

echo === Compiling sqlite3.c ===
"%CL_EXE%" /c /O2 /MT /nologo /W0 ^
  /I"%WIN_INCLUDE%" /I"%WIN_SDK_INCLUDE%\ucrt" /I"%WIN_SDK_INCLUDE%\um" /I"%WIN_SDK_INCLUDE%\shared" ^
  /I"%SRC_DIR%" ^
  /Fo"%OBJ_DIR%\sqlite3.obj" ^
  "%SRC_DIR%\sqlite3.c"
if %ERRORLEVEL% neq 0 goto :error

echo === Compiling C++ sources ===
"%CL_EXE%" /c /O2 /MT /nologo /W3 /std:c++17 /EHsc ^
  /I"%WIN_INCLUDE%" /I"%WIN_SDK_INCLUDE%\ucrt" /I"%WIN_SDK_INCLUDE%\um" /I"%WIN_SDK_INCLUDE%\shared" ^
  /I"%SDK_DIR%" /I"%SRC_DIR%" ^
  /DWIN32 /D_WINDOWS /D_USRDLL /DNDEBUG /DARK_GAME ^
  /DUNICODE /D_UNICODE ^
  /D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS /D_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR ^
  /Fo"%OBJ_DIR%\\" ^
  "%SRC_DIR%\Main.cpp" ^
  "%SRC_DIR%\ShopBridge.cpp" ^
  "%SRC_DIR%\ShopConfig.cpp" ^
  "%SRC_DIR%\ShopData.cpp" ^
  "%SRC_DIR%\ShopPoints.cpp" ^
  "%SRC_DIR%\ShopStore.cpp" ^
  "%SRC_DIR%\Commands.cpp"
if %ERRORLEVEL% neq 0 goto :error

echo === Linking DLL ===
"%LINK_EXE%" /DLL /NOLOGO ^
  /OUT:"%BIN_DIR%\CustomShop.dll" ^
  /LIBPATH:"%LIB_DIR%" ^
  /LIBPATH:"%WIN_LIB%" ^
  /LIBPATH:"%WIN_SDK_LIB%\ucrt\x64" ^
  /LIBPATH:"%WIN_SDK_LIB%\um\x64" ^
  ArkApi.lib ^
  kernel32.lib user32.lib advapi32.lib ole32.lib oleaut32.lib ^
  "%OBJ_DIR%\Main.obj" ^
  "%OBJ_DIR%\ShopBridge.obj" ^
  "%OBJ_DIR%\ShopConfig.obj" ^
  "%OBJ_DIR%\ShopData.obj" ^
  "%OBJ_DIR%\ShopPoints.obj" ^
  "%OBJ_DIR%\ShopStore.obj" ^
  "%OBJ_DIR%\Commands.obj" ^
  "%OBJ_DIR%\sqlite3.obj"
if %ERRORLEVEL% neq 0 goto :error

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
