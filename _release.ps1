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
      - Plugins oficiais (CustomShop, CustomDinoDeliver, ArkPlayer, ArkEventHunt, EngramLevel):
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
if (-not (Test-Path $python)) {
    $python = Join-Path $root ".python-full\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    $python = Join-Path $root ".venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}
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
Write-Step 0 7 "Validando versoes dos plugins (CustomShop / CustomDinoDeliver / ArkPlayer / ArkEventHunt / EngramLevel)..."
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

# Changelog e metadados sao lidos/gravados diretamente pelo Python em UTF-8.

# ── 3) Atualizar APP_VERSION em src/version.py ───────────────────────────────
Write-Step 2 7 "Atualizando arquivos de versao..."

$newPy = $versionPyRaw -replace 'APP_VERSION\s*:\s*str\s*=\s*"[^"]+"', "APP_VERSION: str = `"$Version`""
[System.IO.File]::WriteAllText($versionPyPath, $newPy, $utf8NoBOM)
Write-Ok "src\version.py  →  APP_VERSION = `"$Version`""

# ── 4) Atualizar version.json ─────────────────────────────────────────────────
$downloadUrl = "https://github.com/SrLuther/ARKLAND-Multi/releases/download/v$Version/ARKLAND-Multi-Setup-v$Version.exe"
$date = Get-Date -Format "yyyy-MM-dd"
# Gera version.json no Python para nao passar acentos por stdout/ConvertFrom-Json
# do Windows PowerShell, que pode substitui-los por '?'.
$versionJsonScript = @"
import ast, json
from pathlib import Path

source = Path('src/version.py').read_text(encoding='utf-8-sig')
tree = ast.parse(source)
entries = None
for node in tree.body:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'CHANGELOG':
        entries = ast.literal_eval(node.value)
        break
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CHANGELOG' for t in node.targets):
        entries = ast.literal_eval(node.value)
        break
entry = next((item for item in entries or [] if item.get('version') == '$Version'), None)
if entry is None:
    raise SystemExit('CHANGELOG entry not found')
payload = {'version': '$Version', 'date': '$date', 'download_url': '$downloadUrl', 'changelog': entry.get('changes', [])}
Path('version.json').write_text(json.dumps(payload, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')
print('version.json written as UTF-8')
"@
& $python -c $versionJsonScript
if ($LASTEXITCODE -ne 0) { Write-Fail "version.json generation failed" }
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
Write-Ok "PluginInfo.json  →  sincronizado com plugin_version.txt (CustomShop + CustomDinoDeliver + ArkPlayer + ArkEventHunt + EngramLevel)"

# CHANGELOG.md gerado a partir de version.py
& $python (Join-Path $root "scripts\sync_changelog_md.py") --render-only
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
# Stage apenas arquivos já versionados. Artefatos, backups e dados de usuário
# soltos na pasta não devem entrar no commit automático do release.
# Redirect stderr→stdout: git CRLF warnings viram NativeCommandError com
# $ErrorActionPreference=Stop / StrictMode e abortam o release a meio.
cmd /c "git add -u 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Fail "git add falhou (exit $LASTEXITCODE)" }
# Fontes novas da reestruturação não aparecem em `git add -u`; liste-as
# explicitamente para que o código-fonte do release corresponda ao executável.
$releaseNewFiles = @(
    "docs/ARKLAND_AUDITORIA_TECNICA_COMPLETA_2026-10-28.md",
    "docs/ESCOPO_RELEASE_1.11.0.md",
    "src/asm_engine/ini_document.py",
    "src/asm_engine/level_progression.py",
    "src/data/ark_ase_server_cli_catalog.json",
    "src/data/ark_ase_server_ini_catalog.json",
    "src/ini_sync.py",
    "src/ui/level_progression_editor.py",
    "src/ui/server_cli_catalog.py",
    "src/ui/server_ini_catalog.py",
    "plugin/arkshop_web/discord_engagement_routes.py",
    "plugin/arkshop_web/static/betland.jpg",
    "src/discord_bot/activity_rewards.py",
    "tests/test_ark_ini_config_only_writer.py",
    "tests/test_asm_ini_lossless_writer.py",
    "tests/test_ini_document.py",
    "tests/test_ini_sync.py",
    "tests/test_level_progression_models.py",
    "tests/test_server_ini_catalog.py",
    "tests/test_update_ark_ase_config_catalog.py",
    "tools/update_ark_ase_config_catalog.py"
)
cmd /c "git add -- $($releaseNewFiles -join ' ') 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Fail "git add de fontes novas falhou (exit $LASTEXITCODE)" }
# catalog.json do usuário: tira do stage sem alterar o working tree.
cmd /c "git reset HEAD -- plugin/CustomShop/catalog.json 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Fail "git reset HEAD do catalog.json falhou (exit $LASTEXITCODE)" }
cmd /c "git reset HEAD -- plugin/CustomShop/ArkServerAPI 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Fail "git reset HEAD do ArkServerAPI falhou (exit $LASTEXITCODE)" }
$stagedNames = cmd /c "git diff --cached --name-only 2>&1"
foreach ($name in @($stagedNames)) {
    $norm = ([string]$name -replace '\\', '/')
    $drop = $false
    if ($norm -like "_release_*.log" -or $norm -like "*/_release_*.log") { $drop = $true }
    if ($norm -eq "catalog.json" -or $norm -like "*/catalog.json" -or $norm -eq "catalogo.json" -or $norm -like "*/catalogo.json") { $drop = $true }
    if ($norm -eq "ig/betland.jpg") { $drop = $true }
    # Objetos e executaveis de teste do MSVC sao artefatos locais do build.
    if ($norm -like "plugin/CustomShop/obj/*") { $drop = $true }
    # Proposta comercial independente, fora do escopo funcional deste release.
    if ($norm -eq "docs/LICENCAS_PRECOS_PROPOSTA.md") { $drop = $true }
    if ($drop) {
        cmd /c "git reset HEAD -- `"$name`" 2>&1"
        if ($LASTEXITCODE -ne 0) { Write-Fail "nao foi possivel tirar $name do stage" }
    }
}
$catalogOut = cmd /c "git diff --cached --name-only -- plugin/CustomShop/catalog.json 2>&1"
$catalogHit = @($catalogOut) | Where-Object { ($_ -replace '\\', '/') -eq "plugin/CustomShop/catalog.json" }
if ($catalogHit) { Write-Fail "catalog.json ainda esta no stage — release abortado" }
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

