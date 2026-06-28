#Requires -Version 5.1
<#
.SYNOPSIS
  Limpeza completa de produção: catálogo + ark_permission + arkland_shop (uma execução).

.DESCRIPTION
  1. apply_catalog_sync no config mestre (remove licenças/kits obsoletos, placeholders)
  2. Propaga config para todos os mapas, WEBSTORE e settings.json
  3. Apaga os 8 grupos obsoletos em ark_permission (ids 6,7,10-13,29,70)
  4. Normaliza jogadores (VIP fora, Moderacao* -> Mod)
  5. Remove entitlements VIP em arkland_shop

.PARAMETER BackupDir
  Pasta de backup antes da limpeza (padrão: C:\ARKLAND SERVER\BACKUP\database).

.EXAMPLE
  .\tools\arkland_production_cleanup.ps1

.EXAMPLE
  .\tools\arkland_production_cleanup.ps1 -BackupDir "C:\ARKLAND SERVER\BACKUP\database"
#>
[CmdletBinding()]
param(
    [string]$MapsRoot = "C:\ARKLAND SERVER\MAPAS",
    [string]$MasterPath = "",
    [string]$RepoRoot = "",
    [string]$MySqlPassword = "",
    [string]$MySqlUser = "",
    [string]$MySqlHost = "127.0.0.1",
    [int]$MySqlPort = 3306,
    [string]$PermDatabase = "ark_permission",
    [string]$ShopDatabase = "arkland_shop",
    [string]$BackupDir = "C:\ARKLAND SERVER\BACKUP\database",
    [switch]$SkipBackup,
    [switch]$PreviewOnly
)

$ErrorActionPreference = "Stop"

$WebStore = "C:\ARKLAND SERVER\WEBSTORE\config.json"
$Settings = Join-Path $env:APPDATA "ARKLAND-ServerManager\arkshop_web\settings.json"

function Write-Step([string]$Msg) { Write-Host "`n==> $Msg" -ForegroundColor Cyan }

function Find-Python {
    foreach ($cmd in @("python", "py", "python3")) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($exe) { return $exe.Source }
    }
    throw "Python nao encontrado no PATH."
}

function Resolve-RepoRoot([string]$Requested) {
    if ($Requested -and (Test-Path -LiteralPath $Requested)) {
        return (Resolve-Path -LiteralPath $Requested).Path
    }
    $candidates = @(
        (Join-Path $PSScriptRoot ".."),
        "C:\Users\Ciano\Documents\arkland-multi",
        "C:\Program Files\ARKLAND-ServerManager"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path (Join-Path $c "src\catalog_sync.py"))) {
            return (Resolve-Path -LiteralPath $c).Path
        }
    }
    return ""
}

function Read-PermissionsConfig([string]$Root) {
    $pattern = Join-Path $Root "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\Permissions\config.json"
    foreach ($f in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
        try {
            $cfg = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            return @{
                Host     = [string]$cfg.MysqlHost
                Port     = [int]$cfg.MysqlPort
                User     = [string]$cfg.MysqlUser
                Password = [string]$cfg.MysqlPass
                Database = [string]$cfg.MysqlDB
                Source   = $f.FullName
            }
        } catch {}
    }
    return $null
}

function Resolve-MasterCatalog([string]$Requested, [string]$Root) {
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
    if (-not $best) { throw "Nenhum config.json em $pattern" }
    return (Resolve-Path -LiteralPath $best).Path
}

function Update-WebSettingsPath([string]$SettingsPath, [string]$CatalogPath) {
    if (-not (Test-Path -LiteralPath $SettingsPath)) {
        Write-Host "AVISO: settings.json ausente: $SettingsPath" -ForegroundColor Yellow
        return
    }
    $escaped = $CatalogPath.Replace('\', '\\')
    $raw = [System.IO.File]::ReadAllText($SettingsPath)
    $raw = [regex]::Replace($raw, '("config_path"\s*:\s*"[^"]*")\s*(\r?\n\s*"central_url")', '$1,$2')
    $raw = [regex]::Replace($raw, '"config_path"\s*:\s*"[^"]*"', "`"config_path`": `"$escaped`"")
    [System.IO.File]::WriteAllText($SettingsPath, $raw, [System.Text.UTF8Encoding]::new($false))
    Write-Host "settings.json -> $CatalogPath" -ForegroundColor Green
}

function Find-Mysqldump {
    $candidates = @(
        "C:\ARKLAND SERVER\MARIADB\bin\mysqldump.exe",
        (Join-Path $env:APPDATA "ARKLAND-ServerManager\mariadb\bin\mysqldump.exe"),
        "C:\Program Files\MariaDB\bin\mysqldump.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    $cmd = Get-Command mysqldump -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Backup-BeforeCleanup {
    param(
        [string]$DestRoot,
        [string]$MasterCatalog,
        [string]$MapsRoot,
        [string]$DumpHost,
        [int]$DumpPort,
        [string]$DumpUser,
        [string]$DumpPass,
        [string[]]$Databases
    )
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $dest = Join-Path $DestRoot $ts
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Write-Host "Backup em: $dest" -ForegroundColor Green

    $catDir = Join-Path $dest "catalog"
    New-Item -ItemType Directory -Path $catDir -Force | Out-Null
    Copy-Item -LiteralPath $MasterCatalog -Destination (Join-Path $catDir "config_master.json") -Force

    $pattern = Join-Path $MapsRoot "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
    $mapDir = Join-Path $catDir "mapas"
    New-Item -ItemType Directory -Path $mapDir -Force | Out-Null
    foreach ($f in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
        $map = ($f.FullName -split '\\MAPAS\\')[1]
        $mapName = if ($map) { ($map -split '\\')[0] } else { $f.Directory.Parent.Parent.Parent.Parent.Name }
        Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $mapDir "$mapName.json") -Force
    }

    if (Test-Path -LiteralPath $Settings) {
        Copy-Item -LiteralPath $Settings -Destination (Join-Path $dest "settings_web.json") -Force
    }

    $mysqldump = Find-Mysqldump
    if (-not $mysqldump) {
        Write-Host "AVISO: mysqldump nao encontrado — backup SQL ignorado (catalogo JSON foi salvo)." -ForegroundColor Yellow
        return $dest
    }

    $sqlDir = Join-Path $dest "sql"
    New-Item -ItemType Directory -Path $sqlDir -Force | Out-Null
    foreach ($db in $Databases) {
        $out = Join-Path $sqlDir "$db.sql"
        $argList = @(
            "-h$DumpHost", "-P$DumpPort", "-u$DumpUser",
            "--single-transaction", "--routines", "--events",
            $db
        )
        $env:MYSQL_PWD = $DumpPass
        try {
            & $mysqldump @argList | Set-Content -LiteralPath $out -Encoding UTF8
            Write-Host "SQL OK: $db -> $out" -ForegroundColor DarkGreen
        } finally {
            Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
        }
    }
    return $dest
}

function Sync-CatalogToMaps([string]$Master, [string]$Root, [string]$WebStorePath) {
    $pattern = Join-Path $Root "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
    $masterFull = (Resolve-Path -LiteralPath $Master).Path
    foreach ($target in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
        $destFull = (Resolve-Path -LiteralPath $target.FullName).Path
        if ($destFull -eq $masterFull) {
            Write-Host "Mapa (mestre): $destFull" -ForegroundColor Green
            continue
        }
        Copy-Item -LiteralPath $Master -Destination $target.FullName -Force
        Write-Host "Mapa OK: $($target.FullName)" -ForegroundColor Green
    }
    if (Test-Path -LiteralPath (Split-Path $WebStorePath -Parent)) {
        Copy-Item -LiteralPath $Master -Destination $WebStorePath -Force
        Write-Host "WEBSTORE OK: $WebStorePath" -ForegroundColor Green
    }
}

Write-Step "ARKLAND — limpeza completa (catalogo + MySQL)"
$repo = Resolve-RepoRoot -Requested $RepoRoot
if ($repo) { Write-Host "Repo: $repo" -ForegroundColor DarkGray } else { Write-Host "Repo nao encontrado — purge inline no catalogo" -ForegroundColor Yellow }

$permCfg = Read-PermissionsConfig -Root $MapsRoot
if ($permCfg) {
    Write-Host "MySQL via: $($permCfg.Source)" -ForegroundColor DarkGray
    if ($permCfg.Host) { $MySqlHost = $permCfg.Host }
    if ($permCfg.Port) { $MySqlPort = $permCfg.Port }
    if ($permCfg.User -and -not $MySqlUser) { $MySqlUser = $permCfg.User }
    if ($permCfg.Database) { $PermDatabase = $permCfg.Database }
    if (-not $MySqlPassword -and $permCfg.Password -and $permCfg.Password -notmatch '^(SUA_SENHA|changeme)$') {
        $MySqlPassword = $permCfg.Password
    }
}
if (-not $MySqlUser) { $MySqlUser = "arkland" }
if (-not $MySqlPassword) {
    $sec = Read-Host "Senha MySQL ($MySqlUser@$MySqlHost)" -AsSecureString
    $MySqlPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    )
}

$master = Resolve-MasterCatalog -Requested $MasterPath -Root $MapsRoot
Write-Host "Catalogo mestre: $master" -ForegroundColor Yellow

if (-not $PreviewOnly -and -not $SkipBackup) {
    Write-Step "Backup antes da limpeza"
    if (-not (Test-Path -LiteralPath $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    }
    $backupPath = Backup-BeforeCleanup `
        -DestRoot $BackupDir `
        -MasterCatalog $master `
        -MapsRoot $MapsRoot `
        -DumpHost $MySqlHost `
        -DumpPort $MySqlPort `
        -DumpUser $MySqlUser `
        -DumpPass $MySqlPassword `
        -Databases @($PermDatabase, $ShopDatabase)
    Write-Host "Backup concluido: $backupPath" -ForegroundColor Green
}

$pyExe = Find-Python
& $pyExe -c "import pymysql" 2>$null
if ($LASTEXITCODE -ne 0) { & $pyExe -m pip install pymysql -q }

$tmpPy = Join-Path $env:TEMP "arkland_full_cleanup_$([Guid]::NewGuid().ToString('N')).py"
$preview = if ($PreviewOnly) { "1" } else { "0" }

$pyContent = @'
import json
import re
import sys
from pathlib import Path

MASTER = Path(sys.argv[1])
REPO = sys.argv[2]
HOST, PORT, USER, PASS = sys.argv[3:7]
PERM_DB, SHOP_DB = sys.argv[7:9]
PREVIEW = sys.argv[9] == "1"

DELETE_GROUP_IDS = (6, 7, 10, 11, 12, 13, 29, 70)
REMOVED_PREFIX = "VIP"
STRIP_ITEM_PERMS = (
    "struct_transmitter", "struct_generatortek", "item_soultraps_20",
    "struct_tekreplicator_vip", "stryder_rig",
)
VIP_RE = re.compile(r"^VIP", re.I)
MOD_EXACT = {"moderacao", "moderação", "modera????o", "moderaã§ã£o", "moderaÃ§Ã£o"}


def is_mod_alias(part: str) -> bool:
    low = part.lower()
    return low in MOD_EXACT or (low.startswith("modera") and part != "Mod")


def is_removed_group(name: str) -> bool:
    return bool(name) and name.upper().startswith(REMOVED_PREFIX)


def is_retired_item(item_id: str, item: dict) -> bool:
    key = item_id.lower()
    if key.startswith("licenca_vip") or "_vip" in key:
        return True
    grant = item.get("LicenseGrant") or {}
    return is_removed_group(str(grant.get("Group") or ""))


def is_retired_kit(kit_id: str, kit: dict) -> bool:
    if kit_id.lower().startswith("vip"):
        return True
    if isinstance(kit.get("VipLicense"), dict):
        return True
    perms = str(kit.get("Permissions") or "")
    return any(is_removed_group(p.strip()) for p in perms.split(",") if p.strip())


def purge_catalog_inline(data: dict) -> list[str]:
    removed = []
    items = data.setdefault("Items", {})
    kits = data.setdefault("Kits", {})
    for key in list(items.keys()):
        entry = items.get(key)
        if isinstance(entry, dict) and is_retired_item(str(key), entry):
            del items[key]
            removed.append(f"item:{key}")
    for key in list(kits.keys()):
        entry = kits.get(key)
        if isinstance(entry, dict) and is_retired_kit(str(key), entry):
            del kits[key]
            removed.append(f"kit:{key}")
    for key in STRIP_ITEM_PERMS:
        entry = items.get(key)
        if isinstance(entry, dict) and "Permissions" in entry:
            entry.pop("Permissions", None)
            removed.append(f"perms:{key}")
    return removed


def apply_catalog(master: Path) -> list[str]:
    data = json.loads(master.read_text(encoding="utf-8"))
    notes: list[str] = []
    if REPO:
        repo = Path(REPO)
        if (repo / "src" / "catalog_sync.py").is_file():
            sys.path.insert(0, str(repo))
            from src.catalog_sync import apply_catalog_sync  # noqa: WPS433

            cleared, kit_updates = apply_catalog_sync(data)
            notes.extend(cleared)
            notes.extend(kit_updates)
        else:
            notes.extend(purge_catalog_inline(data))
    else:
        notes.extend(purge_catalog_inline(data))
    if not PREVIEW:
        master.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    items_n = len(data.get("Items") or {})
    kits_n = len(data.get("Kits") or {})
    print(f"CATALOGO: itens={items_n} kits={kits_n} alteracoes={len(notes)}")
    for line in notes[:25]:
        print(f"  {line}")
    if len(notes) > 25:
        print(f"  ... +{len(notes) - 25}")
    return notes


def clean_player_groups(value: str) -> str:
    if not value:
        return value
    out, has_mod = [], False
    for part in [p.strip() for p in value.split(",") if p.strip()]:
        if VIP_RE.match(part):
            continue
        if is_mod_alias(part):
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
    if "Default" not in out:
        out.insert(0, "Default")
    return ",".join(out) + ","


def cleanup_permission_db() -> None:
    import pymysql

    conn = pymysql.connect(
        host=HOST, port=int(PORT), user=USER, password=PASS,
        database=PERM_DB, charset="utf8mb4", autocommit=False,
    )
    try:
        cur = conn.cursor()
        print(f"PERMISSOES ({PERM_DB}) ANTES:")
        cur.execute("SELECT Id, GroupName FROM permissiongroups ORDER BY Id")
        before = cur.fetchall()
        for row in before:
            print(f"  {row[0]:>3}  {row[1]}")

        cur.execute("SELECT Id, PermissionGroups, TimedPermissionGroups FROM players")
        n_players = 0
        for pid, pg, tpg in cur.fetchall():
            npg, ntpg = clean_player_groups(pg or ""), clean_player_groups(tpg or "")
            if npg != (pg or "") or ntpg != (tpg or ""):
                n_players += 1
                if not PREVIEW:
                    cur.execute(
                        "UPDATE players SET PermissionGroups=%s, TimedPermissionGroups=%s WHERE Id=%s",
                        (npg, ntpg, pid),
                    )
        ids_sql = ",".join(str(i) for i in DELETE_GROUP_IDS)
        if PREVIEW:
            cur.execute(f"SELECT Id, GroupName FROM permissiongroups WHERE Id IN ({ids_sql})")
            to_del = cur.fetchall()
            print(f"PERMISSOES PREVIEW: {n_players} jogador(es), {len(to_del)} grupo(s) a apagar")
            for row in to_del:
                print(f"  DELETE id={row[0]} {row[1]!r}")
            conn.rollback()
        else:
            cur.execute(f"DELETE FROM permissiongroups WHERE Id IN ({ids_sql})")
            deleted = cur.rowcount
            conn.commit()
            print(f"PERMISSOES: {n_players} jogador(es) atualizados, {deleted} grupos apagados")
            cur.execute("SELECT Id, GroupName FROM permissiongroups ORDER BY Id")
            print("PERMISSOES DEPOIS:")
            for row in cur.fetchall():
                print(f"  {row[0]:>3}  {row[1]}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cleanup_shop_db() -> None:
    import pymysql

    conn = pymysql.connect(
        host=HOST, port=int(PORT), user=USER, password=PASS,
        database=SHOP_DB, charset="utf8mb4", autocommit=False,
    )
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM player_entitlements WHERE group_name LIKE 'VIP%%'")
        n_ent = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name='vip_players'", (SHOP_DB,))
        has_vip = int(cur.fetchone()[0]) > 0
        n_vip = 0
        if has_vip:
            cur.execute("SELECT COUNT(*) FROM vip_players")
            n_vip = int(cur.fetchone()[0])
        if PREVIEW:
            print(f"LOJA PREVIEW: entitlements VIP={n_ent}, vip_players={n_vip}")
            conn.rollback()
            return
        cur.execute("DELETE FROM player_entitlements WHERE group_name LIKE 'VIP%%'")
        d1 = cur.rowcount
        d2 = 0
        if has_vip:
            cur.execute("DELETE FROM vip_players")
            d2 = cur.rowcount
        conn.commit()
        print(f"LOJA: removidos entitlements={d1}, vip_players={d2}")
    except Exception as exc:
        conn.rollback()
        print(f"LOJA AVISO: {exc}")
    finally:
        conn.close()


def main() -> int:
    apply_catalog(MASTER)
    cleanup_permission_db()
    cleanup_shop_db()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@

try {
    Set-Content -LiteralPath $tmpPy -Value $pyContent -Encoding UTF8
    & $pyExe $tmpPy $master $repo $MySqlHost $MySqlPort $MySqlUser $MySqlPassword $PermDatabase $ShopDatabase $preview
    if ($LASTEXITCODE -ne 0) { throw "Script Python falhou (codigo $LASTEXITCODE)" }

    if (-not $PreviewOnly) {
        Write-Step "Propagando catalogo para mapas e WEBSTORE"
        Sync-CatalogToMaps -Master $master -Root $MapsRoot -WebStorePath $WebStore
        Update-WebSettingsPath -SettingsPath $Settings -CatalogPath $master
    } else {
        Write-Host "`nPreviewOnly — catalogo/DB nao gravados; mapas nao sincronizados." -ForegroundColor Yellow
    }

    Write-Step "Pronto"
    if ($PreviewOnly) {
        Write-Host "Rode de novo sem -PreviewOnly para aplicar." -ForegroundColor Yellow
    } else {
        Write-Host @"
1. F5 no DB Manager (permissiongroups)
2. Reinicie a Web Store
3. Shop.Reload em cada mapa (ou restart)
4. NAO use «Provisionar grupos (RCON)»
"@ -ForegroundColor White
    }
} finally {
    Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
}
