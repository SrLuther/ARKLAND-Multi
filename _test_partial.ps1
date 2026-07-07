<#
.SYNOPSIS
    Script de release ARKLAND - Server Manager

.DESCRIPTION
    Ponto de entrada ÚNICO para publicar uma nova versão.
    
    WORKFLOW:
      1. Adicione a entrada do novo changelog em src/version.py (CHANGELOG list)
      2. Execute:  .\_release.ps1 -Version "X.Y.Z"
      3. O script cuida do resto: atualiza todos os arquivos, builda e publica.

    Arquivos atualizados automaticamente:
      - src/version.py  → APP_VERSION
      - version.json    → version, date, download_url, changelog
      - setup.iss       → AppVersion, OutputBaseFilename
      - plugin/*/plugin_version.txt + PluginInfo.json  → VersionLabel = APP_VERSION

.PARAMETER Version
    Versão a publicar no formato X.Y.Z (ex: "1.2.2")

.EXAMPLE
    .\_release.ps1 -Version "1.2.2"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".python-full\python.exe"
$utf8NoBOM = New-Object System.Text.UTF8Encoding $false

function Write-Step($n, $total, $text) {
    Write-Host ""
    Write-Host "[$n/$total] $text" -ForegroundColor Cyan
}
function Write-Ok($text)   { Write-Host "      OK  $text" -ForegroundColor Green }
function Write-Fail($text) {
    Write-Host ""
    Write-Host "  ERRO: $text" -ForegroundColor Red
    exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "  ARKLAND Release Script  —  v$Version" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow

# ── 0) Formato da versão ──────────────────────────────────────────────────────
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    Write-Fail "Formato inválido: '$Version'. Use X.Y.Z (ex: 1.2.2)"
}

