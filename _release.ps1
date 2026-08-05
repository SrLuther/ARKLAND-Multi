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
      - plugin/*/PluginInfo.json  → sincronizado a partir de plugin_version.txt
        (versões dos plugins são independentes; NÃO sobrescreve com APP_VERSION)

    Gates obrigatórios (falham o release se em falta):
      - Entrada CHANGELOG em src/version.py para a versão do app
      - Plugins oficiais (CustomShop, CustomDinoDeliver, ArkPlayer, ArkEventHunt):
        se o código C++ mudou desde o último bump, exige plugin_version.txt maior
        + secção no plugin/*/CHANGELOG.md (scripts/check_plugin_release_gate.py)

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

# ── 0b) Gate de versão dos plugins (código alterado ⇒ bump + CHANGELOG) ───────
Write-Step 0 7 "Validando versoes dos plugins (CustomShop / CustomDinoDeliver / ArkPlayer / ArkEventHunt)..."
& $python (Join-Path $root "scripts\check_plugin_release_gate.py")
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Gate de plugins falhou. Bumpe plugin_version.txt + plugin/*/CHANGELOG.md e sincronize com scripts\sync_plugin_versions.py antes de continuar."
}
Write-Ok "Plugins alinhados (versao + CHANGELOG + PluginInfo)"

# ── 1) Validar changelog em src/version.py ───────────────────────────────────
Write-Step 1 7 "Validando src/version.py..."

$versionPyPath = Join-Path $root "src\version.py"
$versionPyRaw  = [System.IO.File]::ReadAllText($versionPyPath, [System.Text.Encoding]::UTF8)

if ($versionPyRaw -notmatch ('"version"\s*:\s*"' + [regex]::Escape($Version) + '"')) {
    Write-Fail "src\version.py nao tem uma entrada de CHANGELOG para v$Version.`n`n  Adicione o bloco abaixo ao inicio da lista CHANGELOG antes de rodar este script:`n`n  {`n      `"version`": `"$Version`",`n      `"date`": `"$(Get-Date -Format 'yyyy-MM-dd')`",`n      `"changes`": [`n          `"Descreva as mudancas aqui.`",`n      ],`n  },"
}
Write-Ok "Entrada de changelog encontrada para v$Version"

# ── 2) Extrair changelog via Python (AST) ─────────────────────────────────────
$extractScript = @"
import ast, json, sys, io
# Força stdout UTF-8 para suportar emojis e caracteres especiais no changelog
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
with open('src/version.py', encoding='utf-8-sig') as f:
    src = f.read()
tree = ast.parse(src)
for node in ast.walk(tree):
    # Suporta tanto 'CHANGELOG = [...]' (Assign) quanto 'CHANGELOG: list[dict] = [...]' (AnnAssign)
    value_node = None
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == 'CHANGELOG':
                value_node = node.value
    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.target.id == 'CHANGELOG' and node.value:
            value_node = node.value
    if value_node is not None:
        for entry in ast.literal_eval(value_node):
            if entry['version'] == '$Version':
                print(json.dumps(entry['changes'], ensure_ascii=False))
                sys.exit(0)
print('[]')
"@
# Garante que o PowerShell leia o stdout do Python como UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$changelogJson = & $python -c $extractScript
$changes = $changelogJson | ConvertFrom-Json

# ── 3) Atualizar APP_VERSION em src/version.py ───────────────────────────────
Write-Step 2 7 "Atualizando arquivos de versao..."

$newPy = $versionPyRaw -replace 'APP_VERSION\s*:\s*str\s*=\s*"[^"]+"', "APP_VERSION: str = `"$Version`""
[System.IO.File]::WriteAllText($versionPyPath, $newPy, $utf8NoBOM)
Write-Ok "src\version.py  →  APP_VERSION = `"$Version`""

# ── 4) Atualizar version.json ─────────────────────────────────────────────────
$downloadUrl = "https://github.com/SrLuther/ARKLAND-Multi/releases/download/v$Version/ARKLAND-Multi-Setup-v$Version.exe"
# PS5.1: ConvertTo-Json serializa arrays em hashtables como {value:[...],Count:n}
# → geramos o JSON manualmente para garantir um array JSON puro no campo changelog.
$date        = Get-Date -Format "yyyy-MM-dd"
$escapedItems = $changes | ForEach-Object {
    '"' + ($_ -replace '\\', '\\' -replace '"', '\"') + '"'
}
$changelogInline = $escapedItems -join ",`n        "
$versionJsonStr = @"
{
    "version": "$Version",
    "date": "$date",
    "download_url": "$downloadUrl",
    "changelog": [
        $changelogInline
    ]
}
"@
[System.IO.File]::WriteAllText((Join-Path $root "version.json"), $versionJsonStr, $utf8NoBOM)
Write-Ok "version.json    →  version = `"$Version`""

# ── 5) Atualizar setup.iss ────────────────────────────────────────────────────
$issPath = Join-Path $root "setup.iss"
$iss = [System.IO.File]::ReadAllText($issPath, [System.Text.Encoding]::UTF8)
$expectedInstallerBase = "ARKLAND-Multi-Setup-v$Version"
if ($iss -match '#define ReleaseVersion') {
    $iss = $iss -replace '#define ReleaseVersion "[^"]+"', "#define ReleaseVersion `"$Version`""
} else {
    $iss = $iss -replace 'AppVersion=[\d.]+', "AppVersion=$Version"
    $iss = $iss -replace 'OutputBaseFilename=ARKLAND-Multi-Setup-v[\d.]+', "OutputBaseFilename=$expectedInstallerBase"
}
[System.IO.File]::WriteAllText($issPath, $iss, $utf8NoBOM)
$issCheck = [System.IO.File]::ReadAllText($issPath, [System.Text.Encoding]::UTF8)
if ($issCheck -match '#define ReleaseVersion') {
    if ($issCheck -notmatch ('#define ReleaseVersion "' + [regex]::Escape($Version) + '"')) {
        Write-Fail "setup.iss: ReleaseVersion nao foi atualizado para $Version"
    }
    if ($issCheck -notmatch [regex]::Escape('OutputBaseFilename=ARKLAND-Multi-Setup-v{#ReleaseVersion}')) {
        Write-Fail "setup.iss: OutputBaseFilename deve usar ARKLAND-Multi-Setup-v{#ReleaseVersion}"
    }
} elseif ($issCheck -notmatch [regex]::Escape("OutputBaseFilename=$expectedInstallerBase")) {
    Write-Fail "setup.iss: OutputBaseFilename nao foi atualizado para $expectedInstallerBase"
}
Write-Ok "setup.iss       ->  AppVersion + OutputBaseFilename = $Version"

# BUILD_DATE em src/version.py
$newPy = $newPy -replace 'BUILD_DATE\s*:\s*str\s*=\s*"[^"]+"', "BUILD_DATE: str = `"$date`""
[System.IO.File]::WriteAllText($versionPyPath, $newPy, $utf8NoBOM)
Write-Ok "src\version.py  →  BUILD_DATE = $date"

# PluginInfo.json sincronizado a partir de plugin_version.txt (sem --from-app)
& $python (Join-Path $root "scripts\sync_plugin_versions.py") --all
if ($LASTEXITCODE -ne 0) { Write-Fail "scripts\sync_plugin_versions.py --all falhou" }
Write-Ok "PluginInfo.json  →  sincronizado com plugin_version.txt (CustomShop + CustomDinoDeliver + ArkPlayer + ArkEventHunt)"

# CHANGELOG.md gerado a partir de version.py
& $python (Join-Path $root "scripts\sync_changelog_md.py")
if ($LASTEXITCODE -ne 0) { Write-Fail "scripts\sync_changelog_md.py falhou" }
Write-Ok "CHANGELOG.md    →  sincronizado com src\version.py"

# ── 6) Build ──────────────────────────────────────────────────────────────────
Write-Step 3 7 "Rodando build.bat..."
Push-Location $root
# 2>&1 faz o merge de stderr→stdout no nível do cmd, evitando NativeCommandError
# quando $ErrorActionPreference = Stop e o script está num pipeline (Tee-Object).
cmd /c "build.bat 2>&1"
$buildExit = $LASTEXITCODE
Pop-Location
if ($buildExit -ne 0) { Write-Fail "build.bat falhou (exit $buildExit)" }

$installer = Join-Path $root "installer\ARKLAND-Multi-Setup-v$Version.exe"
if (-not (Test-Path $installer)) { Write-Fail "Installer nao encontrado apos build: $installer" }
Write-Ok "Installer: $installer  ($([Math]::Round((Get-Item $installer).Length/1MB,1)) MB)"

# Gate duro: installer gordo (~427 MB) = WebStore.spec sem exclusao raw/demo nao entrou no build
$installerMb = [Math]::Round((Get-Item $installer).Length / 1MB, 1)
$webStoreExe = Join-Path $root "dist\ARKLAND-WebStore.exe"
if (Test-Path $webStoreExe) {
    $wsMb = [Math]::Round((Get-Item $webStoreExe).Length / 1MB, 1)
    Write-Ok "WebStore.exe: $wsMb MB"
    if ($wsMb -gt 80) {
        Write-Fail "ARKLAND-WebStore.exe com $wsMb MB (esperado ~30-50 MB). Spec sem raw/demo nao entrou - NAO publicar."
    }
}
if ($installerMb -gt 150) {
    Write-Fail "Installer com $installerMb MB (>150 MB). Ainda gordo como v1.10.66 (~427 MB) - NAO publicar. Corrija ARKLAND-WebStore.spec e rebuild."
}
Write-Ok "Size gate OK ($installerMb MB <= 150 MB)"

# ── 7) Git commit + push ──────────────────────────────────────────────────────
Write-Step 4 7 "Commitando alteracoes..."
# Redirect stderr→stdout: git CRLF warnings viram NativeCommandError com
# $ErrorActionPreference=Stop / StrictMode e abortam o release a meio.
cmd /c "git add -A 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Fail "git add falhou (exit $LASTEXITCODE)" }
cmd /c "git commit -m `"release: v$Version`" 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Fail "git commit falhou (exit $LASTEXITCODE)" }
cmd /c "git push 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Fail "git push falhou (exit $LASTEXITCODE)" }
Write-Ok "Commit + push → main"

# ── 8) GitHub Release ─────────────────────────────────────────────────────────
Write-Step 5 7 "Obtendo token GitHub..."
$credLines = "protocol=https`nhost=github.com`n" | git credential fill 2>$null
$ghToken   = ($credLines | Where-Object { $_ -match "^password=" }) -replace "^password=", ""
if (-not $ghToken) { Write-Fail "Token GitHub nao encontrado no Windows Credential Manager" }
Write-Ok "Token obtido"

Write-Step 6 7 "Publicando GitHub Release v$Version..."

# Python faz o request HTTP diretamente — evita o bug do PS 5.1 onde
# Invoke-RestMethod corrompe strings Unicode mesmo com charset=utf-8.
# json.dumps com ensure_ascii=True garante JSON puro ASCII (\uXXXX).
$ghScript = @"
import json, sys, urllib.request

token  = '$ghToken'
version = '$Version'
installer = r'$installer'

with open(r'$(Join-Path $root "version.json")', encoding='utf-8') as f:
    data = json.load(f)

lines = ['## O que ha de novo\n']
for c in data['changelog']:
    lines.append('- ' + c)
lines.append('\n---\n**Instalacao silenciosa:** ARKLAND-Multi-Setup-v{v}.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'.format(v=version))
body = '\n'.join(lines)

headers = {'Authorization': 'token ' + token, 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json; charset=utf-8'}

payload = json.dumps({'tag_name': 'v'+version, 'name': 'v'+version, 'body': body, 'draft': False, 'prerelease': False}, ensure_ascii=True).encode('ascii')
req = urllib.request.Request('https://api.github.com/repos/SrLuther/ARKLAND-Multi/releases', data=payload, headers=headers)
with urllib.request.urlopen(req) as r:
    rel = json.loads(r.read())

upload_url = rel['upload_url'].split('{')[0] + '?name=ARKLAND-Multi-Setup-v' + version + '.exe'
with open(installer, 'rb') as f:
    asset_data = f.read()
asset_headers = {'Authorization': 'token ' + token, 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/octet-stream'}
asset_req = urllib.request.Request(upload_url, data=asset_data, headers=asset_headers)
with urllib.request.urlopen(asset_req) as r:
    asset = json.loads(r.read())

print(rel['html_url'])
print(asset['browser_download_url'])
"@

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ghOut = & $python -c $ghScript
if ($LASTEXITCODE -ne 0) { Write-Fail "Falha ao publicar release no GitHub" }
$releaseUrl = $ghOut[0]
$assetUrl   = $ghOut[1]
Write-Ok "Release criada: $releaseUrl"
Write-Ok "Asset enviado:  $assetUrl"

# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  RELEASE v$Version PUBLICADA COM SUCESSO!" -ForegroundColor Green
Write-Host "  $releaseUrl" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

