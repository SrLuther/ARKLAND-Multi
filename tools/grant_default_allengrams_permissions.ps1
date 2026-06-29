#Requires -Version 5.1
<#
.SYNOPSIS
  Concede AllEngrams.GiveEngrams e AllEngrams.AutoGiveEngrams ao grupo Default em ark_permission.

.DESCRIPTION
  Alternativa ao SQL manual — usa mysql.exe ou Python+pymysql.
  Também pode aplicar via RCON em todos os mapas (Permissions.Grant).

.EXAMPLE
  .\tools\grant_default_allengrams_permissions.ps1

.EXAMPLE
  .\tools\grant_default_allengrams_permissions.ps1 -ViaRcon
#>
[CmdletBinding()]
param(
    [string]$MapsRoot = "C:\ARKLAND SERVER\MAPAS",
    [string]$Host_ = "127.0.0.1",
    [int]$Port = 3306,
    [string]$MySqlUser = "",
    [string]$MySqlPassword = "",
    [string]$Database = "ark_permission",
    [switch]$ViaRcon,
    [switch]$PreviewOnly
)

$ErrorActionPreference = "Stop"

$PERMS = @(
    "AllEngrams.GiveEngrams",
    "AllEngrams.AutoGiveEngrams"
)

function Find-MysqlClient {
    $candidates = @(
        "C:\ARKLAND SERVER\MARIADB\bin\mysql.exe",
        "C:\Program Files\MariaDB 10.11\bin\mysql.exe",
        "C:\Program Files\MariaDB 11.4\bin\mysql.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    $cmd = Get-Command mysql.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "mysql.exe nao encontrado"
}

function Get-PermCredentials {
    param([string]$Root)
    $permCfg = Get-ChildItem "$Root\*\ShooterGame\Binaries\Win64\ArkApi\Plugins\Permissions\config.json" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $permCfg) { throw "Permissions/config.json nao encontrado em $Root" }
    $c = Get-Content $permCfg.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $user = if ($MySqlUser) { $MySqlUser } else { $c.MysqlUser }
    $pass = if ($MySqlPassword) { $MySqlPassword } else { $c.MysqlPass }
    $host_ = if ($Host_) { $Host_ } else { $c.MysqlHost }
    $port = if ($Port) { $Port } else { [int]$c.MysqlPort }
    $db = if ($Database) { $Database } else { $c.MysqlDB }
    if ($pass -match '^(SUA_SENHA|changeme)$' -or -not $pass) {
        $sec = Read-Host "Senha MySQL ($user)" -AsSecureString
        $pass = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    }
    return @{ Host = $host_; Port = $port; User = $user; Pass = $pass; Db = $db }
}

function Grant-ViaMysql {
    param($Cred)
    $mysql = Find-MysqlClient
    Write-Host "mysql.exe: $mysql" -ForegroundColor DarkGray

    $py = @"
import pymysql
host = '$($Cred.Host)'
port = $($Cred.Port)
user = '$($Cred.User)'
password = '''$($Cred.Pass.replace("'", "''"))'''
db = '$($Cred.Db)'
perms = $($PERMS | ConvertTo-Json -Compress)
preview = $($PreviewOnly.IsPresent.ToString().ToLower())

conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db, charset='utf8mb4')
try:
    with conn.cursor() as cur:
        cur.execute("SELECT Id, GroupName, Permissions FROM permissiongroups WHERE GroupName='Default' LIMIT 1")
        row = cur.fetchone()
        if not row:
            raise SystemExit('Grupo Default nao existe em permissiongroups')
        gid, gname, old = row[0], row[1], row[2] or ''
        parts = [p.strip() for p in old.split(',') if p.strip()]
        added = []
        for p in perms:
            if p not in parts:
                parts.append(p)
                added.append(p)
        new_val = ','.join(parts) + (',' if parts else '')
        print(f'ANTES: {old!r}')
        print(f'DEPOIS: {new_val!r}')
        if added:
            print('ADICIONADOS:', ', '.join(added))
        else:
            print('Nada a adicionar — permissoes ja presentes.')
        if not preview and added:
            cur.execute("UPDATE permissiongroups SET Permissions=%s WHERE Id=%s", (new_val, gid))
            conn.commit()
            print('OK — gravado.')
        elif preview:
            conn.rollback()
            print('PREVIEW — nenhuma alteracao gravada.')
finally:
    conn.close()
"@
    $tmp = Join-Path $env:TEMP "grant_default_perms_$([Guid]::NewGuid().ToString('N')).py"
    Set-Content -LiteralPath $tmp -Value $py -Encoding UTF8
    try {
        python $tmp
        if ($LASTEXITCODE -ne 0) { throw "Script Python falhou" }
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

function Grant-ViaRcon {
    param([string]$Root)
    Write-Host "RCON: Permissions.Grant Default <perm> em cada mapa..." -ForegroundColor Cyan
    Write-Host "Use o TEK com servidores online, ou rode manualmente no console admin:" -ForegroundColor Yellow
    foreach ($p in $PERMS) {
        Write-Host "  cheat Permissions.Grant Default $p"
    }
    Write-Host "`nOu via painel RCON de cada mapa (um comando por linha)." -ForegroundColor DarkGray
}

$cred = Get-PermCredentials -Root $MapsRoot
if ($ViaRcon) {
    Grant-ViaRcon -Root $MapsRoot
} else {
    Grant-ViaMysql -Cred $cred
    Write-Host "`nPermissions recarrega em ~60s. Teste: /GiveEngrams in-game." -ForegroundColor Green
}
