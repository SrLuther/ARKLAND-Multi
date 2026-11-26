@echo off
setlocal

set "PLUGIN_DIR=%~dp0"
if not defined STRUCTURELIMITS_SDK_ROOT set "STRUCTURELIMITS_SDK_ROOT=%PLUGIN_DIR%..\CustomShop\ArkServerAPI"
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
  echo ERROR: vswhere.exe nao encontrado.
  exit /b 1
)

for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VS_DIR=%%i"
if not defined VS_DIR (
  echo ERROR: Visual Studio C++ nao encontrado.
  exit /b 1
)

set "VCVARS=%VS_DIR%\VC\Auxiliary\Build\vcvarsall.bat"
set "BUILD_DIR=%TEMP%\ARKLAND-StructureLimits-tests"
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
if errorlevel 1 exit /b 1

call "%VCVARS%" x64
if errorlevel 1 exit /b 1

pushd "%BUILD_DIR%"
cl /nologo /std:c++20 /EHsc /W4 /I"%PLUGIN_DIR%src" ^
  /I"%STRUCTURELIMITS_SDK_ROOT%\version\Core\Public" ^
  "%PLUGIN_DIR%src\StructureLimitsCore.cpp" ^
  "%PLUGIN_DIR%src\DurableOutbox.cpp" ^
  "%PLUGIN_DIR%src\LocalSnapshotStore.cpp" ^
  "%PLUGIN_DIR%src\OutboxSynchronizer.cpp" ^
  "%PLUGIN_DIR%src\StructureLimitsConfig.cpp" ^
  "%PLUGIN_DIR%src\ObservedInventory.cpp" ^
  "%PLUGIN_DIR%src\InventoryJournal.cpp" ^
  "%PLUGIN_DIR%tests\core_tests.cpp" ^
  /Fe:StructureLimitsCoreTests.exe /link ole32.lib
if errorlevel 1 goto :error

StructureLimitsCoreTests.exe
if errorlevel 1 goto :error
popd
exit /b 0

:error
popd
exit /b 1
