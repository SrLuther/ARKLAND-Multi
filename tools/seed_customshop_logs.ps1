# Seed CustomShop/logs on all MAPAS\* so Explorer shows the folder before/after DLL deploy.
param([string]$MapsRoot = "C:\ARKLAND SERVER\MAPAS")
if (-not (Test-Path $MapsRoot)) { $MapsRoot = "C:\ARKLANDSERVER\MAPAS" }
if (-not (Test-Path $MapsRoot)) { Write-Error "MAPAS not found: $MapsRoot"; exit 1 }
Get-ChildItem "$MapsRoot\*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $logs = Join-Path $_.FullName "logs"
  New-Item -ItemType Directory -Force -Path $logs | Out-Null
  $readme = Join-Path $logs "README.txt"
  if (-not (Test-Path $readme)) {
    @"
ARKLAND CustomShop — pasta de debug
Como ligar TRACE: Debug.Enabled=true + Shop.Reload (ou Shop.DebugLevel trace)
Docs: docs/ARKLAND_PLUGIN_DEBUG.md
"@ | Set-Content $readme -Encoding UTF8
  }
  $log = Join-Path $logs "arkland_debug.log"
  if (-not (Test-Path $log)) {
    '{"category":"Boot","message":"folder ready — deploy CustomShop >=1.10.15 for auto boot marker"}' | Set-Content $log -Encoding UTF8
  }
  "ready" | Set-Content (Join-Path $logs ".arkland_debug_ready") -Encoding UTF8
  Write-Host "OK $logs"
}
