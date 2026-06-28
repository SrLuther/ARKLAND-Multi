#Requires -Version 5.1
<#
.SYNOPSIS
  Limpeza completa de produção: catálogo + ark_permission + arkland_shop.
  Nao exige Python — usa PowerShell + mysql.exe (mesmo MariaDB do backup).

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
    [switch]$PreviewOnly,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$WebStore = "C:\ARKLAND SERVER\WEBSTORE\config.json"
$Settings = Join-Path $env:APPDATA "ARKLAND-ServerManager\arkshop_web\settings.json"

function Write-Step([string]$Msg) { Write-Host "`n==> $Msg" -ForegroundColor Cyan }

function Invoke-NativeCommand {
    param(
        [string]$Exe,
        [string[]]$ArgumentList
    )
    $prevNative = $PSNativeCommandUseErrorActionPreference
    try {
        $PSNativeCommandUseErrorActionPreference = $false
        & $Exe @ArgumentList
    } finally {
        $PSNativeCommandUseErrorActionPreference = $prevNative
    }
    return $LASTEXITCODE
}

function Find-PythonOptional {
    foreach ($cmd in @("python", "py", "python3")) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        $rc = Invoke-NativeCommand -Exe $exe.Source -ArgumentList @("-c", "import sys; print(sys.version.split()[0])")
        if ($rc -eq 0) {
            Write-Host "Python: $($exe.Source)" -ForegroundColor DarkGray
            return $exe.Source
        }
    }
    return $null
}

function Ensure-Pymysql {
    param([string]$PyExe)
    $rc = Invoke-NativeCommand -Exe $PyExe -ArgumentList @("-c", "import pymysql")
    if ($rc -eq 0) { return }
    Write-Host "Instalando pymysql (primeira vez)..." -ForegroundColor Yellow
    $rc = Invoke-NativeCommand -Exe $PyExe -ArgumentList @("-m", "pip", "install", "pymysql", "--quiet")
    if ($rc -ne 0) {
        throw "Falha ao instalar pymysql. Rode manualmente: `"$PyExe -m pip install pymysql`""
    }
}

function Show-FatalError {
    param([System.Management.Automation.ErrorRecord]$Err)
    Write-Host ""
    Write-Host "ERRO: $($Err.Exception.Message)" -ForegroundColor Red
    if ($Err.ScriptStackTrace) {
        Write-Host $Err.ScriptStackTrace -ForegroundColor DarkGray
    }
    if (-not $NoPause) {
        Read-Host "Pressione Enter para fechar"
    }
}

function Resolve-RepoRoot([string]$Requested) {
    if ($Requested -and (Test-Path -LiteralPath $Requested)) {
        return (Resolve-Path -LiteralPath $Requested).Path
    }
    $candidates = @(
        (Join-Path $PSScriptRoot ".."),
        (Join-Path $PSScriptRoot "..\.."),
        "C:\Users\Ciano\Documents\arkland-multi",
        "C:\Program Files\ARKLAND-ServerManager",
        (Join-Path $env:USERPROFILE "Documents\arkland-multi")
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

function Find-MysqlClient {
    $dump = Find-Mysqldump
    if ($dump) {
        $mysql = Join-Path (Split-Path -Parent $dump) "mysql.exe"
        if (Test-Path -LiteralPath $mysql) { return $mysql }
    }
    $candidates = @(
        "C:\ARKLAND SERVER\MARIADB\bin\mysql.exe",
        (Join-Path $env:APPDATA "ARKLAND-ServerManager\mariadb\bin\mysql.exe"),
        "C:\Program Files\MariaDB\bin\mysql.exe",
        "C:\Program Files\MariaDB 11.4\bin\mysql.exe",
        "C:\Program Files\MariaDB 11.3\bin\mysql.exe",
        "C:\Program Files\MariaDB 10.11\bin\mysql.exe",
        "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    $cmd = Get-Command mysql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "mysql.exe nao encontrado. O backup SQL funcionou; verifique se mysql.exe esta na mesma pasta do mysqldump."
}

function Invoke-MysqlScript {
    param(
        [string]$Client,
        [string]$DbHost,
        [int]$DbPort,
        [string]$DbUser,
        [string]$DbPass,
        [string]$Database,
        [string]$Sql
    )
    $args = @(
        "-h$DbHost", "-P$DbPort", "-u$DbUser",
        "--default-character-set=utf8mb4",
        $Database
    )
    $env:MYSQL_PWD = $DbPass
    try {
        $prevNative = $PSNativeCommandUseErrorActionPreference
        try {
            $PSNativeCommandUseErrorActionPreference = $false
            $out = $Sql | & $Client @args 2>&1
        } finally {
            $PSNativeCommandUseErrorActionPreference = $prevNative
        }
        if ($LASTEXITCODE -ne 0) {
            $text = ($out | Out-String).Trim()
            throw "mysql falhou (codigo $LASTEXITCODE): $text"
        }
        return $out
    } finally {
        Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
    }
}

function Test-RemovedVipGroup {
    param([string]$Name)
    return [bool]($Name -and $Name.ToUpper().StartsWith("VIP"))
}

function Test-RetiredCatalogItem {
    param([string]$ItemId, $Item)
    if (-not $Item) { return $false }
    $key = $ItemId.ToLower()
    if ($key.StartsWith("licenca_vip") -or $key.Contains("_vip")) { return $true }
    if ($Item.PSObject.Properties.Name -contains "LicenseGrant") {
        $group = [string]$Item.LicenseGrant.Group
        if (Test-RemovedVipGroup $group) { return $true }
    }
    return $false
}

function Test-RetiredCatalogKit {
    param([string]$KitId, $Kit)
    if (-not $Kit) { return $false }
    if ($KitId.ToLower().StartsWith("vip")) { return $true }
    if ($Kit.PSObject.Properties.Name -contains "VipLicense") { return $true }
    $perms = [string]$Kit.Permissions
    if ($perms) {
        foreach ($part in ($perms -split ",")) {
            if (Test-RemovedVipGroup ($part.Trim())) { return $true }
        }
    }
    return $false
}

function Skip-JsonStringEnd {
    param([string]$Text, [int]$Start)
    $j = $Start + 1
    while ($j -lt $Text.Length) {
        if ($Text[$j] -eq '\') { $j += 2; continue }
        if ($Text[$j] -eq '"') { return $j + 1 }
        $j++
    }
    return $Text.Length
}

function Find-JsonValueEnd {
    param([string]$Text, [int]$Start)
    $i = $Start
    while ($i -lt $Text.Length -and [char]::IsWhiteSpace($Text[$i])) { $i++ }
    if ($i -ge $Text.Length) { return $i }
    switch ($Text[$i]) {
        '{' {
            $depth = 0
            for ($j = $i; $j -lt $Text.Length; $j++) {
                $ch = $Text[$j]
                if ($ch -eq '"') { $j = (Skip-JsonStringEnd -Text $Text -Start $j) - 1; continue }
                if ($ch -eq '{') { $depth++ }
                elseif ($ch -eq '}') {
                    $depth--
                    if ($depth -eq 0) { return $j + 1 }
                }
            }
            return $Text.Length
        }
        '[' {
            $depth = 0
            for ($j = $i; $j -lt $Text.Length; $j++) {
                $ch = $Text[$j]
                if ($ch -eq '"') { $j = (Skip-JsonStringEnd -Text $Text -Start $j) - 1; continue }
                if ($ch -eq '[') { $depth++ }
                elseif ($ch -eq ']') {
                    $depth--
                    if ($depth -eq 0) { return $j + 1 }
                }
            }
            return $Text.Length
        }
        '"' { return Skip-JsonStringEnd -Text $Text -Start $i }
        default {
            for ($j = $i; $j -lt $Text.Length; $j++) {
                if ($Text[$j] -eq ',' -or $Text[$j] -eq '}' -or $Text[$j] -eq ']') {
                    return $j
                }
            }
            return $Text.Length
        }
    }
}

function Find-JsonSectionInnerRange {
    param([string]$Text, [string]$SectionName)
    $pat = '"' + [regex]::Escape($SectionName) + '"\s*:\s*\{'
    $m = [regex]::Match($Text, $pat)
    if (-not $m.Success) { return $null }
    $open = $m.Index + $m.Length - 1
    $close = (Find-JsonValueEnd -Text $Text -Start $open) - 1
    return @{ InnerStart = $open + 1; InnerEnd = $close }
}

function Find-JsonEntryRange {
    param(
        [string]$Text,
        [int]$InnerStart,
        [int]$InnerEnd,
        [string]$Key
    )
    $body = $Text.Substring($InnerStart, $InnerEnd - $InnerStart)
    $pat = '"' + [regex]::Escape($Key) + '"\s*:'
    $m = [regex]::Match($body, $pat)
    if (-not $m.Success) { return $null }
    $keyStart = $InnerStart + $m.Index
    $valStart = $InnerStart + $m.Index + $m.Length
    $valEnd = Find-JsonValueEnd -Text $Text -Start $valStart
    $removeStart = $keyStart
    $removeEnd = $valEnd
    $scan = $removeEnd
    while ($scan -lt $Text.Length -and [char]::IsWhiteSpace($Text[$scan])) { $scan++ }
    if ($scan -lt $Text.Length -and $Text[$scan] -eq ',') {
        $removeEnd = $scan + 1
    } else {
        $prev = $removeStart - 1
        while ($prev -ge $InnerStart -and [char]::IsWhiteSpace($Text[$prev])) { $prev-- }
        if ($prev -ge $InnerStart -and $Text[$prev] -eq ',') { $removeStart = $prev }
    }
    return @{ Start = $removeStart; End = $removeEnd }
}

function Remove-JsonEntryInSection {
    param(
        [ref]$Text,
        [string]$SectionName,
        [string]$Key
    )
    $sec = Find-JsonSectionInnerRange -Text $Text.Value -SectionName $SectionName
    if (-not $sec) { return $false }
    $entry = Find-JsonEntryRange -Text $Text.Value -InnerStart $sec.InnerStart `
        -InnerEnd $sec.InnerEnd -Key $Key
    if (-not $entry) { return $false }
    $Text.Value = $Text.Value.Remove($entry.Start, $entry.End - $entry.Start)
    return $true
}

function Remove-JsonPropertyInSectionEntry {
    param(
        [ref]$Text,
        [string]$SectionName,
        [string]$EntryKey,
        [string]$PropertyName
    )
    $sec = Find-JsonSectionInnerRange -Text $Text.Value -SectionName $SectionName
    if (-not $sec) { return $false }
    $entry = Find-JsonEntryRange -Text $Text.Value -InnerStart $sec.InnerStart `
        -InnerEnd $sec.InnerEnd -Key $EntryKey
    if (-not $entry) { return $false }
    $objStart = $Text.Value.IndexOf('{', $entry.Start)
    if ($objStart -lt 0 -or $objStart -ge $entry.End) { return $false }
    $objEnd = Find-JsonValueEnd -Text $Text.Value -Start $objStart
    $innerStart = $objStart + 1
    $innerEnd = $objEnd - 1
    $propPat = '"' + [regex]::Escape($PropertyName) + '"\s*:'
    $body = $Text.Value.Substring($innerStart, $innerEnd - $innerStart)
    $m = [regex]::Match($body, $propPat)
    if (-not $m.Success) { return $false }
    $propStart = $innerStart + $m.Index
    $valStart = $innerStart + $m.Index + $m.Length
    $valEnd = Find-JsonValueEnd -Text $Text.Value -Start $valStart
    $removeStart = $propStart
    $removeEnd = $valEnd
    $scan = $removeEnd
    while ($scan -lt $innerEnd -and [char]::IsWhiteSpace($Text.Value[$scan])) { $scan++ }
    if ($scan -lt $innerEnd -and $Text.Value[$scan] -eq ',') {
        $removeEnd = $scan + 1
    } else {
        $prev = $removeStart - 1
        while ($prev -ge $innerStart -and [char]::IsWhiteSpace($Text.Value[$prev])) { $prev-- }
        if ($prev -ge $innerStart -and $Text.Value[$prev] -eq ',') { $removeStart = $prev }
    }
    $Text.Value = $Text.Value.Remove($removeStart, $removeEnd - $removeStart)
    return $true
}

function Invoke-CatalogPurgeInline {
    param(
        [string]$CatalogPath,
        [switch]$PreviewOnly
    )
    $stripPerms = @(
        "struct_transmitter", "struct_generatortek", "item_soultraps_20",
        "struct_tekreplicator_vip", "stryder_rig"
    )
    $raw = [System.IO.File]::ReadAllText($CatalogPath)
    $data = $raw | ConvertFrom-Json
    $notes = New-Object System.Collections.Generic.List[string]
    $removeItems = New-Object System.Collections.Generic.List[string]
    $removeKits = New-Object System.Collections.Generic.List[string]
    $stripPermKeys = New-Object System.Collections.Generic.List[string]

    if ($data.Items) {
        foreach ($key in @($data.Items.PSObject.Properties.Name)) {
            if (Test-RetiredCatalogItem -ItemId $key -Item $data.Items.$key) {
                $notes.Add("item:$key")
                $removeItems.Add($key)
            }
        }
    }
    if ($data.Kits) {
        foreach ($key in @($data.Kits.PSObject.Properties.Name)) {
            if (Test-RetiredCatalogKit -KitId $key -Kit $data.Kits.$key) {
                $notes.Add("kit:$key")
                $removeKits.Add($key)
            }
        }
    }
    foreach ($key in $stripPerms) {
        $entry = $data.Items.$key
        if ($entry -and ($entry.PSObject.Properties.Name -contains "Permissions")) {
            $notes.Add("perms:$key")
            $stripPermKeys.Add($key)
        }
    }

    if (-not $PreviewOnly) {
        $text = $raw
        foreach ($key in $removeItems) {
            [void](Remove-JsonEntryInSection -Text ([ref]$text) -SectionName "Items" -Key $key)
        }
        foreach ($key in $removeKits) {
            [void](Remove-JsonEntryInSection -Text ([ref]$text) -SectionName "Kits" -Key $key)
        }
        foreach ($key in $stripPermKeys) {
            [void](Remove-JsonPropertyInSectionEntry -Text ([ref]$text) -SectionName "Items" `
                -EntryKey $key -PropertyName "Permissions")
        }
        [System.IO.File]::WriteAllText(
            $CatalogPath,
            $text,
            [System.Text.UTF8Encoding]::new($false)
        )
        $data = $text | ConvertFrom-Json
    }

    $itemCount = if ($data.Items) { @($data.Items.PSObject.Properties).Count } else { 0 }
    $kitCount = if ($data.Kits) { @($data.Kits.PSObject.Properties).Count } else { 0 }
    Write-Host "CATALOGO: itens=$itemCount kits=$kitCount alteracoes=$($notes.Count)" -ForegroundColor Green
    $shown = [Math]::Min(25, $notes.Count)
    for ($i = 0; $i -lt $shown; $i++) {
        Write-Host "  $($notes[$i])" -ForegroundColor DarkGray
    }
    if ($notes.Count -gt 25) {
        Write-Host "  ... +$($notes.Count - 25)" -ForegroundColor DarkGray
    }
}

function Get-PermissionCleanupSql {
    param([switch]$PreviewOnly)
    $deleteIds = "6, 7, 10, 11, 12, 13, 29, 70"
    if ($PreviewOnly) {
        return @"
SELECT 'GRUPOS ANTES' AS info;
SELECT Id, GroupName FROM permissiongroups ORDER BY Id;
SELECT 'GRUPOS A APAGAR' AS info;
SELECT Id, GroupName FROM permissiongroups WHERE Id IN ($deleteIds);
"@
    }
    return @"
START TRANSACTION;
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPBronze,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPBronze', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPPrata,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPPrata', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPOuro,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPOuro', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPDiamante,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPDiamante', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'VIPDoacao,', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',VIPDoacao', '');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, 'Moderacao,', 'Mod,');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',Moderacao,', ',Mod,');
UPDATE players SET PermissionGroups = REPLACE(PermissionGroups, ',Moderacao', ',Mod');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPBronze,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPBronze', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPPrata,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPPrata', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPOuro,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPOuro', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPDiamante,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPDiamante', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'VIPDoacao,', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',VIPDoacao', '');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, 'Moderacao,', 'Mod,');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',Moderacao,', ',Mod,');
UPDATE players SET TimedPermissionGroups = REPLACE(TimedPermissionGroups, ',Moderacao', ',Mod');
DELETE FROM permissiongroups WHERE Id IN ($deleteIds);
SELECT Id, GroupName FROM permissiongroups ORDER BY Id;
COMMIT;
"@
}

function Get-ShopCleanupSql {
    param([switch]$PreviewOnly)
    if ($PreviewOnly) {
        return @"
SELECT COUNT(*) AS entitlements_vip FROM player_entitlements WHERE group_name LIKE 'VIP%';
SELECT COUNT(*) AS vip_players_rows FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'vip_players';
"@
    }
    return @"
START TRANSACTION;
DELETE FROM player_entitlements WHERE group_name LIKE 'VIP%';
SET @has_vip := (SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'vip_players');
SET @sql := IF(@has_vip > 0, 'DELETE FROM vip_players', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
COMMIT;
"@
}

function Invoke-CleanupNative {
    param(
        [string]$CatalogPath,
        [string]$MysqlClient,
        [string]$DbHost,
        [int]$DbPort,
        [string]$DbUser,
        [string]$DbPass,
        [string]$PermDb,
        [string]$ShopDb,
        [switch]$PreviewOnly
    )
    Write-Step "Limpando catalogo (PowerShell)"
    Invoke-CatalogPurgeInline -CatalogPath $CatalogPath -PreviewOnly:$PreviewOnly

    Write-Step "Limpando $PermDb (mysql.exe)"
    $permOut = Invoke-MysqlScript -Client $MysqlClient -DbHost $DbHost -DbPort $DbPort `
        -DbUser $DbUser -DbPass $DbPass -Database $PermDb `
        -Sql (Get-PermissionCleanupSql -PreviewOnly:$PreviewOnly)
    $permOut | ForEach-Object { Write-Host $_ }

    Write-Step "Limpando $ShopDb (mysql.exe)"
    try {
        $shopOut = Invoke-MysqlScript -Client $MysqlClient -DbHost $DbHost -DbPort $DbPort `
            -DbUser $DbUser -DbPass $DbPass -Database $ShopDb `
            -Sql (Get-ShopCleanupSql -PreviewOnly:$PreviewOnly)
        $shopOut | ForEach-Object { Write-Host $_ }
    } catch {
        Write-Host "LOJA AVISO: $($_.Exception.Message)" -ForegroundColor Yellow
    }
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
        Write-Host "AVISO: mysqldump nao encontrado - backup SQL ignorado (catalogo JSON foi salvo)." -ForegroundColor Yellow
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

function Get-MapFolderFromConfigPath {
    param([string]$ConfigPath)
    if ($ConfigPath -match '(?i)\\MAPAS\\([^\\]+)\\') {
        return $Matches[1]
    }
    return ""
}

function Set-CrossChatServerIdInFile {
    param(
        [string]$ConfigPath,
        [string]$ServerId
    )
    $raw = [System.IO.File]::ReadAllText($ConfigPath)
    if ($raw -match '"ServerId"\s*:\s*"') {
        $raw = [regex]::Replace(
            $raw,
            '("ServerId"\s*:\s*")[^"]*(")',
            "`${1}$ServerId`${2}",
            1
        )
    } else {
        $raw = [regex]::Replace(
            $raw,
            '("CrossChat"\s*:\s*\{)',
            "`${1}`n    ""ServerId"": ""$ServerId"",",
            1
        )
    }
    [System.IO.File]::WriteAllText(
        $ConfigPath,
        $raw,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Repair-CrossChatServerIds {
    param([string]$Root)
    $pattern = Join-Path $Root "*\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\config.json"
    $used = @{}
    $count = 0
    foreach ($f in Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue) {
        $folder = Get-MapFolderFromConfigPath $f.FullName
        if (-not $folder) { continue }
        $sid = $folder
        $key = $sid.ToLower()
        if ($used.ContainsKey($key)) {
            $used[$key] = [int]$used[$key] + 1
            $sid = "${folder}_$($used[$key])"
        } else {
            $used[$key] = 1
        }
        Set-CrossChatServerIdInFile -ConfigPath $f.FullName -ServerId $sid
        Write-Host "CrossChat ServerId: $sid <- $($f.FullName)" -ForegroundColor DarkGray
        $count++
    }
    if ($count -eq 0) {
        Write-Host "AVISO: nenhum config de mapa para CrossChat ServerId em $pattern" -ForegroundColor Yellow
    }
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
    Write-Host "Corrigindo CrossChat.ServerId por pasta MAPAS..." -ForegroundColor Cyan
    Repair-CrossChatServerIds -Root $Root
}

$tmpPy = $null

try {
Write-Step "ARKLAND - limpeza completa (catalogo + MySQL)"
$repo = Resolve-RepoRoot -Requested $RepoRoot
if ($repo) { Write-Host "Repo: $repo" -ForegroundColor DarkGray } else { Write-Host "Repo nao encontrado - purge inline no catalogo" -ForegroundColor Yellow }

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
    $sec = Read-Host ('Senha MySQL ({0}@{1})' -f $MySqlUser, $MySqlHost) -AsSecureString
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

Write-Step "Preparando limpeza (mysql.exe + PowerShell)"
$mysqlClient = Find-MysqlClient
Write-Host "mysql.exe: $mysqlClient" -ForegroundColor DarkGray

$pyExe = Find-PythonOptional
$usePythonCatalog = $false
if ($pyExe -and $repo) {
    try {
        Ensure-Pymysql -PyExe $pyExe
        $usePythonCatalog = $true
        Write-Host "Python + repo: catalog_sync completo" -ForegroundColor DarkGray
    } catch {
        Write-Host "AVISO: Python/repo indisponivel ($($_.Exception.Message)) - purge inline" -ForegroundColor Yellow
    }
} else {
    Write-Host "Sem Python no PATH - usando PowerShell + mysql.exe (normal no servidor)" -ForegroundColor DarkGray
}

Write-Step "Aplicando limpeza (catalogo + MySQL)"
if ($usePythonCatalog) {
    $tmpPy = Join-Path $env:TEMP "arkland_catalog_sync_$([Guid]::NewGuid().ToString('N')).py"
    $previewFlag = if ($PreviewOnly) { "1" } else { "0" }
    $pyContent = @"
import json
import sys
from pathlib import Path

master = Path(sys.argv[1])
repo = Path(sys.argv[2])
preview = sys.argv[3] == "1"

sys.path.insert(0, str(repo))
from src.catalog_sync import apply_catalog_sync

data = json.loads(master.read_text(encoding="utf-8"))
cleared, kit_updates = apply_catalog_sync(data)
notes = list(cleared) + list(kit_updates)
if not preview:
    master.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
items_n = len(data.get("Items") or {})
kits_n = len(data.get("Kits") or {})
print(f"CATALOGO: itens={items_n} kits={kits_n} alteracoes={len(notes)}")
for line in notes[:25]:
    print(f"  {line}")
if len(notes) > 25:
    print(f"  ... +{len(notes) - 25}")
"@
    Set-Content -LiteralPath $tmpPy -Value $pyContent -Encoding UTF8
    $pyOut = & $pyExe $tmpPy $master $repo $previewFlag 2>&1
    $pyOut | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "catalog_sync Python falhou (codigo $LASTEXITCODE)"
    }
    Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue

    Write-Step "Limpando $PermDatabase (mysql.exe)"
    $permOut = Invoke-MysqlScript -Client $mysqlClient -DbHost $MySqlHost -DbPort $MySqlPort `
        -DbUser $MySqlUser -DbPass $MySqlPassword -Database $PermDatabase `
        -Sql (Get-PermissionCleanupSql -PreviewOnly:$PreviewOnly)
    $permOut | ForEach-Object { Write-Host $_ }

    Write-Step "Limpando $ShopDatabase (mysql.exe)"
    try {
        $shopOut = Invoke-MysqlScript -Client $mysqlClient -DbHost $MySqlHost -DbPort $MySqlPort `
            -DbUser $MySqlUser -DbPass $MySqlPassword -Database $ShopDatabase `
            -Sql (Get-ShopCleanupSql -PreviewOnly:$PreviewOnly)
        $shopOut | ForEach-Object { Write-Host $_ }
    } catch {
        Write-Host "LOJA AVISO: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Invoke-CleanupNative -CatalogPath $master -MysqlClient $mysqlClient `
        -DbHost $MySqlHost -DbPort $MySqlPort -DbUser $MySqlUser -DbPass $MySqlPassword `
        -PermDb $PermDatabase -ShopDb $ShopDatabase -PreviewOnly:$PreviewOnly
}

if (-not $PreviewOnly) {
    Write-Step "Propagando catalogo para mapas e WEBSTORE"
    Sync-CatalogToMaps -Master $master -Root $MapsRoot -WebStorePath $WebStore
    Update-WebSettingsPath -SettingsPath $Settings -CatalogPath $master
} else {
    Write-Host "`nPreviewOnly - catalogo/DB nao gravados; mapas nao sincronizados." -ForegroundColor Yellow
}

Write-Step "Pronto"
if ($PreviewOnly) {
    Write-Host "Rode de novo sem -PreviewOnly para aplicar." -ForegroundColor Yellow
} else {
    Write-Host @"
1. F5 no DB Manager (permissiongroups)
2. Reinicie a Web Store
3. Shop.Reload em cada mapa (ou restart)
4. NAO use 'Provisionar grupos (RCON)'
"@ -ForegroundColor White
}
} catch {
    Show-FatalError -Err $_
    exit 1
}
