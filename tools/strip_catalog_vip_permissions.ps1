#Requires -Version 5.1
<#
.SYNOPSIS
  Remove Permissions VIPBronze de itens avulsos no catálogo CustomShop e propaga para mapas/WEBSTORE.

.EXAMPLE
  .\tools\strip_catalog_vip_permissions.ps1
#>
[CmdletBinding()]
param(
    [string]$MasterPath = "",
    [string]$MapsRoot = "C:\ARKLAND SERVER\MAPAS"
)

$ErrorActionPreference = "Stop"

$WebStore = "C:\ARKLAND SERVER\WEBSTORE\config.json"
$Settings = Join-Path $env:APPDATA "ARKLAND-ServerManager\arkshop_web\settings.json"

function Find-Python {
    foreach ($cmd in @("python", "py", "python3")) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($exe) { return $exe.Source }
    }
    throw "Python não encontrado no PATH."
}

function Resolve-MasterPath {
    param([string]$Requested, [string]$Root)
    if ($Requested -and (Test-Path -LiteralPath $Requested)) {
        return (Resolve-Path -LiteralPath $Requested).Path
    }
    $pattern = Join-Path $Root "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
    $best = $null
    $bestScore = -1
    foreach ($f in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
        try {
            $d = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            $n = @($d.Items.PSObject.Properties).Count
            if ($n -gt $bestScore) { $bestScore = $n; $best = $f.FullName }
        } catch {}
    }
    if (-not $best) {
        throw "Nenhum config.json encontrado em $pattern"
    }
    return (Resolve-Path -LiteralPath $best).Path
}

function Fix-CatalogJson {
    param([string]$Path)
    $pyExe = Find-Python
    $tmpPy = Join-Path $env:TEMP "arkland_strip_vip_$([Guid]::NewGuid().ToString('N')).py"
    $pyContent = @'
import json
import sys
from pathlib import Path

KEYS = (
    "struct_transmitter",
    "struct_generatortek",
    "item_soultraps_20",
    "struct_tekreplicator_vip",
    "stryder_rig",
)

def main() -> int:
    p = Path(sys.argv[1])
    d = json.loads(p.read_text(encoding="utf-8"))
    items = d.get("Items") or {}
    changed = []
    for key in KEYS:
        entry = items.get(key)
        if isinstance(entry, dict) and "Permissions" in entry:
            old = entry.pop("Permissions")
            changed.append(f"{key}: removido {old!r}")
    if changed:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("OK", p)
        for line in changed:
            print(" ", line)
    else:
        print("SKIP (ja limpo)", p)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'@
    try {
        Set-Content -LiteralPath $tmpPy -Value $pyContent -Encoding UTF8
        & $pyExe $tmpPy $Path
        if ($LASTEXITCODE -ne 0) {
            throw "Python retornou codigo $LASTEXITCODE"
        }
    } finally {
        Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
    }
}

function Update-WebSettingsPath {
    param(
        [string]$SettingsPath,
        [string]$CatalogPath
    )
    if (-not (Test-Path -LiteralPath $SettingsPath)) {
        Write-Host "AVISO: settings.json nao encontrado: $SettingsPath" -ForegroundColor Yellow
        return
    }
    $escaped = $CatalogPath.Replace('\', '\\')
    $raw = [System.IO.File]::ReadAllText($SettingsPath)

    # Repara JSON quebrado: falta virgula entre config_path e central_url
    $raw = [regex]::Replace(
        $raw,
        '("config_path"\s*:\s*"[^"]*")\s*(\r?\n\s*"central_url")',
        '$1,$2'
    )

    $raw = [regex]::Replace(
        $raw,
        '"config_path"\s*:\s*"[^"]*"',
        "`"config_path`": `"$escaped`""
    )

    [System.IO.File]::WriteAllText($SettingsPath, $raw, [System.Text.UTF8Encoding]::new($false))
    Write-Host "settings.json -> $CatalogPath" -ForegroundColor Green
}

Write-Host "==> ARKLAND — remover VIPBronze de itens avulsos" -ForegroundColor Cyan

$master = Resolve-MasterPath -Requested $MasterPath -Root $MapsRoot
Write-Host "Mestre: $master" -ForegroundColor Yellow

Fix-CatalogJson -Path $master

$pattern = Join-Path $MapsRoot "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
$masterFull = (Resolve-Path -LiteralPath $master).Path
foreach ($target in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
    $destFull = (Resolve-Path -LiteralPath $target.FullName).Path
    if ($destFull -eq $masterFull) {
        Write-Host "Mapa OK (mestre): $destFull" -ForegroundColor Green
        continue
    }
    Copy-Item -LiteralPath $master -Destination $target.FullName -Force
    Write-Host "Mapa OK: $($target.FullName)" -ForegroundColor Green
}

if (Test-Path -LiteralPath (Split-Path $WebStore -Parent)) {
    Copy-Item -LiteralPath $master -Destination $WebStore -Force
    Write-Host "WEBSTORE OK: $WebStore" -ForegroundColor Green
}

Update-WebSettingsPath -SettingsPath $Settings -CatalogPath $master

Write-Host ""
Write-Host "Pronto. Reinicie a Web Store e rode Shop.Reload em cada mapa." -ForegroundColor Yellow
