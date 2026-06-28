#Requires -Version 5.1
<#
.SYNOPSIS
  Corrige CrossChat.ServerId duplicado nos config.json de cada mapa (chat cluster).

.EXAMPLE
  .\tools\repair_cross_chat_server_ids.ps1

.EXAMPLE
  .\tools\repair_cross_chat_server_ids.ps1 -MapsRoot "C:\ARKLAND SERVER\MAPAS"
#>
[CmdletBinding()]
param(
    [string]$MapsRoot = "C:\ARKLAND SERVER\MAPAS"
)

$ErrorActionPreference = "Stop"

function Get-MapFolderFromConfigPath {
    param([string]$ConfigPath)
    if ($ConfigPath -match '(?i)\\MAPAS\\([^\\]+)\\') {
        return $Matches[1]
    }
    return ""
}

function Set-CrossChatServerIdInFile {
    param([string]$ConfigPath, [string]$ServerId)
    $raw = [System.IO.File]::ReadAllText($ConfigPath)
    if ($raw -match '"ServerId"\s*:\s*"') {
        $raw = [regex]::Replace($raw, '("ServerId"\s*:\s*")[^"]*(")', "`${1}$ServerId`${2}", 1)
    } else {
        $raw = [regex]::Replace($raw, '("CrossChat"\s*:\s*\{)', "`${1}`n    ""ServerId"": ""$ServerId"",", 1)
    }
    [System.IO.File]::WriteAllText($ConfigPath, $raw, [System.Text.UTF8Encoding]::new($false))
}

Write-Host "==> Corrigir CrossChat.ServerId em $MapsRoot" -ForegroundColor Cyan
$pattern = Join-Path $MapsRoot "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
$used = @{}
$n = 0
foreach ($f in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
    $folder = Get-MapFolderFromConfigPath $f.FullName
    if (-not $folder) {
        Write-Host "AVISO: sem pasta MAPAS em $($f.FullName)" -ForegroundColor Yellow
        continue
    }
    $sid = $folder
    $key = $sid.ToLower()
    if ($used.ContainsKey($key)) {
        $used[$key] = [int]$used[$key] + 1
        $sid = "${folder}_$($used[$key])"
    } else {
        $used[$key] = 1
    }
    Set-CrossChatServerIdInFile -ConfigPath $f.FullName -ServerId $sid
    Write-Host "  $sid -> $($f.FullName)" -ForegroundColor Green
    $n++
}
if ($n -eq 0) {
    Write-Host "Nenhum config encontrado em $pattern" -ForegroundColor Yellow
    exit 1
}
Write-Host ""
Write-Host "Pronto ($n mapa(s)). Depois: Shop.Reload em cada mapa e reinicie a Web Store." -ForegroundColor Green
