[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ServerRoot
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ServerRoot)) {
    $ServerRoot = Read-Host 'Caminho da raiz do servidor ARK (pasta que contem ArkApi)'
}

$root = [System.IO.Path]::GetFullPath($ServerRoot.Trim().Trim('"'))
$apiPlugins = Join-Path $root 'ArkApi\Plugins'
$destination = Join-Path $apiPlugins 'FazendaRecursos'
$payload = Join-Path $PSScriptRoot 'FazendaRecursos'
$backupRoot = Join-Path $apiPlugins '_FazendaRecursos-backups'

if (-not (Test-Path -LiteralPath $apiPlugins -PathType Container)) {
    throw "Não encontrei '$apiPlugins'. Informe a pasta correta do servidor (a pasta que contém ArkApi)."
}
foreach ($required in @('FazendaRecursos.dll', 'PluginInfo.json', 'config.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $payload $required) -PathType Leaf)) {
        throw "O pacote está incompleto: faltou '$required' em '$payload'."
    }
}

Write-Host ''
Write-Host 'Instalação de teste do FazendaRecursos v0.1.2-test' -ForegroundColor Cyan
Write-Host "Servidor: $root"
Write-Host "Destino:  $destination"
Write-Host 'Pré-requisito: servidor parado e cópia de segurança recente do servidor.' -ForegroundColor Yellow
Write-Host 'Diagnostic build: exports the engram catalog and opaque Soul blobs; no production, cloning or delivery.' -ForegroundColor Yellow
$confirmation = Read-Host "Digite INSTALAR para continuar"
if ($confirmation -cne 'INSTALAR') {
    Write-Host 'Instalação cancelada.'
    exit 0
}

if (Test-Path -LiteralPath $destination -PathType Container) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    $backup = Join-Path $backupRoot "FazendaRecursos-$stamp"
    Copy-Item -LiteralPath $destination -Destination $backup -Recurse
    Write-Host "Backup criado em: $backup" -ForegroundColor Green
}

New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $payload 'FazendaRecursos.dll') -Destination $destination -Force
Copy-Item -LiteralPath (Join-Path $payload 'PluginInfo.json') -Destination $destination -Force
if (-not (Test-Path -LiteralPath (Join-Path $destination 'config.json') -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $payload 'config.json') -Destination $destination
}

Write-Host ''
Write-Host 'Arquivos instalados. Inicie o servidor e confira o log do ArkServerAPI.' -ForegroundColor Green
Write-Host 'Para carregar/recarregar a DLL pelo console: plugins.load FazendaRecursos'
Write-Host 'Comandos de diagnóstico/status disponíveis nesta etapa: /fazstatus e /fazcoletar (admin).'
Write-Host 'Produção e resgate ainda não estão implementados nesta versão.' -ForegroundColor Yellow
