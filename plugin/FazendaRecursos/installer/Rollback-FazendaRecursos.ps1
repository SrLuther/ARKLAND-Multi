[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ServerRoot,

    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath($ServerRoot.Trim().Trim('"'))
$plugins = [System.IO.Path]::GetFullPath((Join-Path $root 'ArkApi\Plugins'))
$destination = [System.IO.Path]::GetFullPath((Join-Path $plugins 'FazendaRecursos'))
$backup = [System.IO.Path]::GetFullPath($BackupPath.Trim().Trim('"'))
$expectedBackupPrefix = [System.IO.Path]::GetFullPath((Join-Path $plugins '_FazendaRecursos-backups')) + [System.IO.Path]::DirectorySeparatorChar

if (-not (Test-Path -LiteralPath $plugins -PathType Container)) { throw "Pasta de plugins não encontrada: $plugins" }
if (-not $backup.StartsWith($expectedBackupPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Por segurança, o backup deve estar dentro de '$expectedBackupPrefix'."
}
if (-not (Test-Path -LiteralPath $backup -PathType Container)) { throw "Backup não encontrado: $backup" }

Write-Host "Servidor: $root"
Write-Host "Restauração: $backup -> $destination"
Write-Host 'Confirme que o servidor está parado.' -ForegroundColor Yellow
if ((Read-Host 'Digite RESTAURAR para continuar') -cne 'RESTAURAR') { Write-Host 'Rollback cancelado.'; exit 0 }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$currentBackup = Join-Path (Join-Path $plugins '_FazendaRecursos-backups') "antes-rollback-$stamp"
if (Test-Path -LiteralPath $destination -PathType Container) {
    New-Item -ItemType Directory -Path $currentBackup -Force | Out-Null
    Copy-Item -LiteralPath $destination -Destination $currentBackup -Recurse
    Remove-Item -LiteralPath $destination -Recurse -Force
}
Copy-Item -LiteralPath $backup -Destination $destination -Recurse
Write-Host "Rollback concluído. Estado substituído preservado em: $currentBackup" -ForegroundColor Green
