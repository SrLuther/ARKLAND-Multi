@echo off
setlocal EnableDelayedExpansion

set "PLUGIN_DIR=%~dp0"
set "SRC_DIR=%PLUGIN_DIR%src"
set "SDK_ROOT=%PLUGIN_DIR%..\CustomShop\ArkServerAPI"
if defined STRUCTURELIMITS_SDK_ROOT set "SDK_ROOT=%STRUCTURELIMITS_SDK_ROOT%"
set "SDK_DIR=%SDK_ROOT%\version\Core\Public"
set "LIB_DIR=%SDK_ROOT%\out_lib"
if not exist "%LIB_DIR%\ArkApi.lib" set "LIB_DIR=%SDK_ROOT%\lib"
if not exist "%SDK_DIR%\API\ARK\Ark.h" (
  echo ERROR: ArkServerAPI headers not found.
  exit /b 1
)
if not exist "%LIB_DIR%\ArkApi.lib" (
  echo ERROR: ArkApi.lib not found.
  exit /b 1
)

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VS_DIR=%%i"
if not defined VS_DIR exit /b 1
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "%VS_DIR%\VC\Tools\MSVC" 2^>nul`) do if not defined MSVC_DIR set "MSVC_DIR=%VS_DIR%\VC\Tools\MSVC\%%i"
set "CL_EXE=%MSVC_DIR%\bin\Hostx64\x64\cl.exe"
set "LINK_EXE=%MSVC_DIR%\bin\Hostx64\x64\link.exe"
set "WIN_KIT=C:\Program Files (x86)\Windows Kits\10"
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "%WIN_KIT%\Include" 2^>nul`) do if not defined WIN_SDK_INCLUDE set "WIN_SDK_INCLUDE=%WIN_KIT%\Include\%%i"
for /f "usebackq delims=" %%i in (`dir /b /ad /o-n "%WIN_KIT%\Lib" 2^>nul`) do if not defined WIN_SDK_LIB set "WIN_SDK_LIB=%WIN_KIT%\Lib\%%i"

set "BUILD_DIR=%TEMP%\ARKLAND-StructureLimits-plugin-probe"
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
call "%VS_DIR%\VC\Auxiliary\Build\vcvarsall.bat" x64
if errorlevel 1 exit /b 1
pushd "%BUILD_DIR%"
cl /c /O2 /MT /nologo /W3 /std:c++20 /EHsc /d2FH4- /I"%WIN_SDK_INCLUDE%\ucrt" /I"%WIN_SDK_INCLUDE%\um" /I"%WIN_SDK_INCLUDE%\shared" /I"%SDK_DIR%" /I"%SDK_ROOT%" /I"%SRC_DIR%" /DWIN32 /D_WINDOWS /D_USRDLL /DNDEBUG /DARK_GAME /DUNICODE /D_UNICODE /D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS /D_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR "%SRC_DIR%\Main.cpp" "%SRC_DIR%\StructureLimitsCore.cpp" "%SRC_DIR%\StructureLimitsConfig.cpp" "%SRC_DIR%\DurableOutbox.cpp" "%SRC_DIR%\LocalSnapshotStore.cpp" "%SRC_DIR%\OutboxSynchronizer.cpp" "%SRC_DIR%\ObservedInventory.cpp" "%SRC_DIR%\InventoryJournal.cpp" "%SRC_DIR%\OwnerDirectory.cpp" "%SRC_DIR%\LiveInventoryRuntime.cpp"
if errorlevel 1 exit /b 1
link /DLL /NOLOGO /OUT:"%BUILD_DIR%\StructureLimits.dll" /LIBPATH:"%LIB_DIR%" /LIBPATH:"%WIN_SDK_LIB%\ucrt\x64" /LIBPATH:"%WIN_SDK_LIB%\um\x64" ArkApi.lib kernel32.lib user32.lib advapi32.lib bcrypt.lib ole32.lib oleaut32.lib "%BUILD_DIR%\Main.obj" "%BUILD_DIR%\StructureLimitsCore.obj" "%BUILD_DIR%\StructureLimitsConfig.obj" "%BUILD_DIR%\DurableOutbox.obj" "%BUILD_DIR%\LocalSnapshotStore.obj" "%BUILD_DIR%\OutboxSynchronizer.obj" "%BUILD_DIR%\ObservedInventory.obj" "%BUILD_DIR%\InventoryJournal.obj" "%BUILD_DIR%\OwnerDirectory.obj" "%BUILD_DIR%\LiveInventoryRuntime.obj"
if errorlevel 1 exit /b 1
echo BUILD SUCCEEDED: %BUILD_DIR%\StructureLimits.dll
echo This artifact wires configuration, core engine, local snapshot and outbox startup plus diagnostic hooks.
echo Enforcement is still fail-open and unavailable without a complete validated live inventory and a proven safe placement hook.
popd
exit /b 0

