#Requires -Version 5.1
<#
.SYNOPSIS
  Corrige preços VIP placeholder (99.999.999) no catálogo de produção e alinha settings.json da Web Store.

.DESCRIPTION
  1. Aplica apply_catalog_sync no arquivo mestre config.json
  2. Atualiza config_path em arkshop_web/settings.json para o caminho persistente
  3. (Opcional) Copia o mestre para configs CustomShop em cada mapa
  4. Imprime preços de verificação (vip_bronze, diamante, etc.)

  Corrigir só config_path NÃO altera preços — o JSON em disco precisa ser reescrito.

.PARAMETER MasterPath
  Caminho do config.json mestre. Se omitido, usa o primeiro existente entre candidatos.

.PARAMETER WebSettingsPath
  settings.json da Web Store (padrão: %APPDATA%\ARKLAND-ServerManager\arkshop_web\settings.json)

.PARAMETER SyncMaps
  Copia o mestre corrigido para MAPAS\*\...\CustomShop\config.json

.PARAMETER MapsRoot
  Raiz dos mapas (padrão: C:\ARKLAND SERVER\MAPAS)

.EXAMPLE
  .\tools\fix_production_catalog.ps1

.EXAMPLE
  .\tools\fix_production_catalog.ps1 -MasterPath "C:\Program Files\ARKLAND-ServerManager\plugin\CustomShop\configs\config.json" -SyncMaps
#>
[CmdletBinding()]
param(
    [string]$MasterPath = "",
    [string]$WebSettingsPath = "",
    [switch]$SyncMaps,
    [string]$MapsRoot = "C:\ARKLAND SERVER\MAPAS"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-RepoRoot {
    $here = $PSScriptRoot
    if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
    return (Resolve-Path (Join-Path $here "..")).Path
}

function Get-DefaultWebSettingsPath {
    if ($env:APPDATA) {
        return Join-Path $env:APPDATA "ARKLAND-ServerManager\arkshop_web\settings.json"
    }
    return ""
}

function Get-MasterCandidates {
  @(
        (Join-Path $env:APPDATA "ARKLAND-ServerManager\CustomShop\configs\config.json"),
        "C:\Program Files\ARKLAND-ServerManager\plugin\CustomShop\configs\config.json",
        "C:\ARKLAND SERVER\MAPAS\*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json",
        "C:\ARKLAND SERVER\WEBSTORE\config.json"
    ) | Where-Object { $_ -and ($_ -ne "") }
}

function Find-RichestMapConfig {
    param([string]$MapsRoot = "C:\ARKLAND SERVER\MAPAS")
    $pattern = Join-Path $MapsRoot "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
    $best = $null
    $bestScore = -1
    foreach ($f in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
        try {
            $d = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            $n = (@($d.Items.PSObject.Properties) + @($d.ShopItems.PSObject.Properties) + @($d.Kits.PSObject.Properties)).Count
            if ($n -gt $bestScore) { $bestScore = $n; $best = $f.FullName }
        } catch {}
    }
    return $best
}

function Resolve-MasterPath([string]$Requested) {
    if ($Requested -and (Test-Path -LiteralPath $Requested)) {
        return (Resolve-Path -LiteralPath $Requested).Path
    }
    if ($Requested) {
        throw "MasterPath não encontrado: $Requested"
    }
    $richest = Find-RichestMapConfig -MapsRoot $MapsRoot
    if ($richest) {
        Write-Host "MasterPath: mapa com mais itens: $richest" -ForegroundColor Yellow
        return $richest
    }
    foreach ($candidate in (Get-MasterCandidates)) {
        if ($candidate -like '*`**') { continue }
        if (Test-Path -LiteralPath $candidate) {
            Write-Host "MasterPath auto-detectado: $candidate" -ForegroundColor Yellow
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "Nenhum config.json mestre encontrado. Use -MasterPath ou restaure de backup."
}

function Find-Python {
    $candidates = @(
        "python",
        "py",
        "python3"
    )
    foreach ($cmd in $candidates) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($exe) { return $exe.Source }
    }
    throw "Python não encontrado no PATH. Instale Python ou execute a partir do Server Manager."
}

function Invoke-ApplyCatalogSync {
    param(
        [string]$RepoRoot,
        [string]$CatalogPath
    )
    $py = Find-Python
    $script = @"
import json
import sys
from pathlib import Path

repo = Path(r'''$RepoRoot''')
sys.path.insert(0, str(repo))

from src.catalog_sync import apply_catalog_sync, catalog_has_placeholder_kit_prices

path = Path(r'''$CatalogPath''')
data = json.loads(path.read_text(encoding='utf-8'))
had_placeholders = catalog_has_placeholder_kit_prices(data)
cleared, kit_updates = apply_catalog_sync(data)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

kits = data.get('Kits') or {}
items = data.get('Items') or {}

def kit_price(kid):
    k = kits.get(kid) or {}
    return k.get('Price')

def item_price(iid):
    i = items.get(iid) or {}
    return i.get('Price')

print('HAD_PLACEHOLDERS=' + str(had_placeholders))
print('CLEARED=' + ','.join(cleared[:20]))
print('KIT_UPDATES=' + ','.join(kit_updates[:20]))
print('ITEMS=' + str(len(items)))
print('KITS=' + str(len(kits)))
"@
    $output = & $py -c $script 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao aplicar catalog sync:`n$output"
    }
    return $output
}

function Update-WebSettings {
    param(
        [string]$SettingsPath,
        [string]$CatalogPath
    )
    if (-not (Test-Path -LiteralPath $SettingsPath)) {
        Write-Host "AVISO: settings.json não existe — criando: $SettingsPath" -ForegroundColor Yellow
        $dir = Split-Path -Parent $SettingsPath
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $obj = @{ config_path = $CatalogPath }
        $obj | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $SettingsPath -Encoding UTF8
        return
    }
    $raw = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8
    $settings = $raw | ConvertFrom-Json
    $old = [string]$settings.config_path
    $settings.config_path = $CatalogPath
    $settings | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $SettingsPath -Encoding UTF8
    if ($old -and ($old -ne $CatalogPath)) {
        Write-Host "config_path atualizado: $old -> $CatalogPath" -ForegroundColor Green
    } else {
        Write-Host "config_path confirmado: $CatalogPath" -ForegroundColor Green
    }
    if ($old -match '_MEI') {
        Write-Host "OK: removido caminho temporário PyInstaller (_MEI*)" -ForegroundColor Green
    }
}

function Sync-MapConfigs {
    param(
        [string]$Master,
        [string]$Root
    )
    if (-not (Test-Path -LiteralPath $Root)) {
        Write-Host "AVISO: MapsRoot não encontrado ($Root) — sync de mapas ignorado." -ForegroundColor Yellow
        return
    }
    $pattern = Join-Path $Root "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
    $targets = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue
    if (-not $targets) {
        Write-Host "AVISO: nenhum config.json de mapa em $pattern" -ForegroundColor Yellow
        return
    }
    foreach ($target in $targets) {
        Copy-Item -LiteralPath $Master -Destination $target.FullName -Force
        Write-Host "Mapa sincronizado: $($target.FullName)" -ForegroundColor Green
    }
}

# ── Main ──────────────────────────────────────────────────────────────────────

Write-Step "ARKLAND — correção de catálogo VIP em produção"
$repoRoot = Resolve-RepoRoot
Write-Host "Repo/script root: $repoRoot"

if (-not $WebSettingsPath) {
    $WebSettingsPath = Get-DefaultWebSettingsPath
}
if (-not $WebSettingsPath) {
    throw "Defina -WebSettingsPath (APPDATA indisponível)."
}

$master = Resolve-MasterPath -Requested $MasterPath
Write-Step "Aplicando manutenção de catálogo em $master"
$pricingOutput = Invoke-ApplyCatalogSync -RepoRoot $repoRoot -CatalogPath $master
$pricingOutput | ForEach-Object { Write-Host $_ }

Write-Step "Atualizando Web Store settings: $WebSettingsPath"
Update-WebSettings -SettingsPath $WebSettingsPath -CatalogPath $master

$webstoreConfig = "C:\ARKLAND SERVER\WEBSTORE\config.json"
if (Test-Path -LiteralPath (Split-Path $webstoreConfig -Parent)) {
    Copy-Item -LiteralPath $master -Destination $webstoreConfig -Force
    Write-Host "WEBSTORE\config.json restaurado a partir do mestre." -ForegroundColor Green
}

if ($SyncMaps) {
    Write-Step "Sincronizando configs dos mapas em $MapsRoot"
    Sync-MapConfigs -Master $master -Root $MapsRoot
}

Write-Step "Verificação local (arquivo mestre)"
$verifyPy = @"
import json
from pathlib import Path
p = Path(r'''$master''')
d = json.loads(p.read_text(encoding='utf-8'))
kits = d.get('Kits') or {}
items = d.get('Items') or {}
print(f'  itens: {len(items)}  kits: {len(kits)}')
print(f'  placeholder_kits: {any(int((k or {}).get("Price") or 0) >= 1000000 for k in kits.values() if isinstance(k, dict))}')
"@
& (Find-Python) -c $verifyPy

Write-Host ""
Write-Step "Próximos passos no servidor"
Write-Host @"
1. Reinicie a Web Store (ARKLAND-WebStore.exe ou serviço) para recarregar settings.json.
2. Verifique a API:
   curl -s https://arkland.com.br/api/catalog | python -c "import sys,json; d=json.load(sys.stdin); m=d.get('catalog_meta',{}); print('config_path:', m.get('config_path')); print('placeholder_kits:', m.get('placeholder_kits_detected'))"
3. Esperado: placeholder_kits_detected = false
4. Se ainda errado, confira qual arquivo a web lê:
   type "$WebSettingsPath" | findstr config_path
   (deve ser o mesmo path em catalog_meta.config_path)
5. No ASM: Loja > Sync + Reload RCON propaga o mestre para todos os mapas (alternativa a -SyncMaps).
"@ -ForegroundColor White
