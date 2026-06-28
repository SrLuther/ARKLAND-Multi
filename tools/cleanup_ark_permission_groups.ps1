#Requires -Version 5.1
<#
.SYNOPSIS
  Limpa grupos legados (VIP*, Moderacao corrompida) em ark_permission.

.DESCRIPTION
  1. Remove VIP* e variantes de Moderacao dos jogadores (PermissionGroups / TimedPermissionGroups)
  2. Converte Moderacao -> Mod
  3. Apaga linhas obsoletas em permissiongroups

  Nao use "Provisionar grupos (RCON)" depois sem revisar - pode recriar grupos do catalogo.

.EXAMPLE
  .\tools\cleanup_ark_permission_groups.ps1

.EXAMPLE
  .\tools\cleanup_ark_permission_groups.ps1 -MySqlPassword "sua_senha"
#>
[CmdletBinding()]
param(
    [string]$MapsRoot = "C:\ARKLAND SERVER\MAPAS",
    [string]$Host_ = "127.0.0.1",
    [int]$Port = 3306,
    [string]$User = "arkland",
    [string]$MySqlPassword = "",
    [string]$Database = "ark_permission",
    [switch]$PreviewOnly
)

$ErrorActionPreference = "Stop"

function Find-Python {
    foreach ($cmd in @("python", "py", "python3")) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($exe) { return $exe.Source }
    }
    throw "Python nao encontrado. Instale Python ou use a aba SQL do TEK com cleanup_ark_permission_groups.sql"
}

function Read-PermissionsConfig {
    param([string]$Root)
    $pattern = Join-Path $Root "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\Permissions\config.json"
    foreach ($f in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
        try {
            $cfg = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            return @{
                Host = [string]$cfg.MysqlHost
                Port = [int]$cfg.MysqlPort
                User = [string]$cfg.MysqlUser
                Password = [string]$cfg.MysqlPass
                Database = [string]$cfg.MysqlDB
                Source = $f.FullName
            }
        } catch {}
    }
    return $null
}

function Ensure-Pymysql([string]$PyExe) {
    & $PyExe -c "import pymysql" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Instalando pymysql..." -ForegroundColor Yellow
        & $PyExe -m pip install pymysql -q
    }
}

$cfg = Read-PermissionsConfig -Root $MapsRoot
if ($cfg) {
    Write-Host "Credenciais de: $($cfg.Source)" -ForegroundColor DarkGray
    if ($cfg.Host) { $Host_ = $cfg.Host }
    if ($cfg.Port) { $Port = $cfg.Port }
    if ($cfg.User) { $User = $cfg.User }
    if ($cfg.Database) { $Database = $cfg.Database }
    if (-not $MySqlPassword -and $cfg.Password -and $cfg.Password -notmatch '^(SUA_SENHA|changeme)$') {
        $MySqlPassword = $cfg.Password
    }
}

if (-not $MySqlPassword) {
    $sec = Read-Host ('Senha MySQL ({0}@{1})' -f $User, $Host_) -AsSecureString
    $MySqlPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    )
}

$pyExe = Find-Python
Ensure-Pymysql -PyExe $pyExe

$tmpPy = Join-Path $env:TEMP "arkland_cleanup_perm_$([Guid]::NewGuid().ToString('N')).py"
$previewFlag = if ($PreviewOnly) { "True" } else { "False" }

$pyContent = @'
import re
import sys
import pymysql

HOST = sys.argv[1]
PORT = int(sys.argv[2])
USER = sys.argv[3]
PASSWORD = sys.argv[4]
DATABASE = sys.argv[5]
PREVIEW = sys.argv[6].lower() == "true"

VIP_RE = re.compile(r"^VIP", re.I)
MOD_ALIASES = {
    "moderacao", "moderação", "modera????o", "moderaã§ã£o", "moderaÃ§Ã£o",
}

DELETE_IDS = {6, 7, 10, 11, 12, 13, 29, 70}  # Moderacao* + VIP* (print TEK)


def _is_mod_alias(part: str) -> bool:
    low = part.lower()
    if low in MOD_ALIASES or part == "Moderacao":
        return True
    # Modera????o, ModeraÃ§Ã£o, etc.
    return low.startswith("modera") and part != "Mod"


def clean_groups(value: str) -> str:
    if not value:
        return value
    parts = [p.strip() for p in value.split(",") if p.strip()]
    out = []
    has_mod = False
    for part in parts:
        if VIP_RE.match(part):
            continue
        if _is_mod_alias(part):
            if not has_mod:
                out.append("Mod")
                has_mod = True
            continue
        if part == "Mod":
            if not has_mod:
                out.append("Mod")
                has_mod = True
            continue
        out.append(part)
    if not out:
        out = ["Default"]
    if "Default" not in out:
        out.insert(0, "Default")
    return ",".join(out) + ","


def main() -> int:
    conn = pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD,
        database=DATABASE, charset="utf8mb4", autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            print("==> Grupos ANTES:")
            cur.execute("SELECT Id, GroupName FROM permissiongroups ORDER BY Id")
            for row in cur.fetchall():
                print(f"  {row[0]:>3}  {row[1]}")

            cur.execute("SELECT Id, SteamId, PermissionGroups, TimedPermissionGroups FROM players")
            players = cur.fetchall()
            player_updates = 0
            for pid, steam, pg, tpg in players:
                new_pg = clean_groups(pg or "")
                new_tpg = clean_groups(tpg or "")
                if new_pg != (pg or "") or new_tpg != (tpg or ""):
                    player_updates += 1
                    if PREVIEW:
                        print(f"  jogador {steam}: PG {pg!r} -> {new_pg!r}")
                    else:
                        cur.execute(
                            "UPDATE players SET PermissionGroups=%s, TimedPermissionGroups=%s WHERE Id=%s",
                            (new_pg, new_tpg, pid),
                        )

            delete_sql = (
                "DELETE FROM permissiongroups WHERE Id IN (%s)"
                % ",".join(str(i) for i in sorted(DELETE_IDS))
            )
            if PREVIEW:
                cur.execute(
                    "SELECT Id, GroupName FROM permissiongroups "
                    "WHERE Id IN (%s)"
                    % ",".join(str(i) for i in sorted(DELETE_IDS))
                )
                to_delete = cur.fetchall()
                print(f"==> PREVIEW: {player_updates} jogador(es) seriam atualizados")
                print(f"==> PREVIEW: {len(to_delete)} grupo(s) seriam apagados:")
                for row in to_delete:
                    print(f"  DELETE id={row[0]} {row[1]!r}")
                conn.rollback()
            else:
                print(f"==> Atualizando {player_updates} jogador(es)...")
                cur.execute(delete_sql)
                deleted = cur.rowcount
                if deleted != len(DELETE_IDS):
                    print(f"AVISO: esperados {len(DELETE_IDS)} grupos, apagados {deleted}", file=sys.stderr)
                conn.commit()
                print(f"==> Apagados {deleted} grupo(s) obsoletos")

                print("==> Grupos DEPOIS:")
                cur.execute("SELECT Id, GroupName FROM permissiongroups ORDER BY Id")
                for row in cur.fetchall():
                    print(f"  {row[0]:>3}  {row[1]}")
        return 0
    except Exception as exc:
        conn.rollback()
        print("ERRO:", exc, file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
'@

try {
    Write-Host "==> ARKLAND - limpar ark_permission.permissiongroups" -ForegroundColor Cyan
    Set-Content -LiteralPath $tmpPy -Value $pyContent -Encoding UTF8
    & $pyExe $tmpPy $Host_ $Port $User $MySqlPassword $Database $previewFlag
    if ($LASTEXITCODE -ne 0) { throw "Script Python falhou" }
    if ($PreviewOnly) {
        Write-Host "`nPreview only. Rode de novo sem -PreviewOnly para aplicar." -ForegroundColor Yellow
    } else {
        Write-Host "`nPronto. Permissions recarrega em ~60s (ClusterSyncTime). Sem restart." -ForegroundColor Green
    }
} finally {
    Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
}
