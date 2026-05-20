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

# ── 1) Validar changelog em src/version.py ───────────────────────────────────
Write-Step 1 6 "Validando src/version.py..."

$versionPyPath = Join-Path $root "src\version.py"
$versionPyRaw  = [System.IO.File]::ReadAllText($versionPyPath, [System.Text.Encoding]::UTF8)

if ($versionPyRaw -notmatch ('"version"\s*:\s*"' + [regex]::Escape($Version) + '"')) {
    Write-Fail "src\version.py nao tem uma entrada de CHANGELOG para v$Version.`n`n  Adicione o bloco abaixo ao inicio da lista CHANGELOG antes de rodar este script:`n`n  {`n      `"version`": `"$Version`",`n      `"date`": `"$(Get-Date -Format 'yyyy-MM-dd')`",`n      `"changes`": [`n          `"Descreva as mudancas aqui.`",`n      ],`n  },"
}
Write-Ok "Entrada de changelog encontrada para v$Version"

# ── 2) Extrair changelog via Python (AST) ─────────────────────────────────────
$extractScript = @"
import ast, json, sys
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
$changelogJson = & $python -c $extractScript
$changes = $changelogJson | ConvertFrom-Json

# ── 3) Atualizar APP_VERSION em src/version.py ───────────────────────────────
Write-Step 2 6 "Atualizando arquivos de versao..."

$newPy = $versionPyRaw -replace 'APP_VERSION\s*:\s*str\s*=\s*"[^"]+"', "APP_VERSION: str = `"$Version`""
[System.IO.File]::WriteAllText($versionPyPath, $newPy, $utf8NoBOM)
Write-Ok "src\version.py  →  APP_VERSION = `"$Version`""

# ── 4) Atualizar version.json ─────────────────────────────────────────────────
$downloadUrl = "https://github.com/SrLuther/ARKLAND-Multi/releases/download/v$Version/ARKLAND-Multi-Setup-v$Version.exe"
$versionObj  = [ordered]@{
    version      = $Version
    date         = (Get-Date -Format "yyyy-MM-dd")
    download_url = $downloadUrl
    changelog    = $changes
}
$versionJsonStr = ($versionObj | ConvertTo-Json -Depth 5) + "`n"
[System.IO.File]::WriteAllText((Join-Path $root "version.json"), $versionJsonStr, $utf8NoBOM)
Write-Ok "version.json    →  version = `"$Version`""

# ── 5) Atualizar setup.iss ────────────────────────────────────────────────────
$issPath = Join-Path $root "setup.iss"
$iss = [System.IO.File]::ReadAllText($issPath, [System.Text.Encoding]::UTF8)
$iss = $iss -replace 'AppVersion=[\d.]+',                          "AppVersion=$Version"
$iss = $iss -replace 'OutputBaseFilename=ARKLAND-Multi-Setup-v[\d.]+', "OutputBaseFilename=ARKLAND-Multi-Setup-v$Version"
[System.IO.File]::WriteAllText($issPath, $iss, $utf8NoBOM)
Write-Ok "setup.iss       →  AppVersion = $Version"

# ── 6) Build ──────────────────────────────────────────────────────────────────
Write-Step 3 6 "Rodando build.bat..."
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

# ── 7) Git commit + push ──────────────────────────────────────────────────────
Write-Step 4 6 "Commitando alteracoes..."
git add -A
git commit -m "release: v$Version"
git push
Write-Ok "Commit + push → main"

# ── 8) GitHub Release ─────────────────────────────────────────────────────────
Write-Step 5 6 "Obtendo token GitHub..."
$credLines = "protocol=https`nhost=github.com`n" | git credential fill 2>$null
$ghToken   = ($credLines | Where-Object { $_ -match "^password=" }) -replace "^password=", ""
if (-not $ghToken) { Write-Fail "Token GitHub nao encontrado no Windows Credential Manager" }
Write-Ok "Token obtido"

Write-Step 6 6 "Publicando GitHub Release v$Version..."
$gh = @{ Authorization = "token $ghToken"; Accept = "application/vnd.github+json" }

# Montar notas da release
$noteLines = @("## O que ha de novo`n")
foreach ($c in $changes) { $noteLines += "- $c" }
$noteLines += "`n---`n**Instalacao silenciosa:**``ARKLAND-Multi-Setup-v$Version.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-``"
$notesBody = ($noteLines -join "`n") -replace '"', '\"' -replace "`n", '\n'

$releaseBodyJson = "{`"tag_name`":`"v$Version`",`"name`":`"v$Version`",`"body`":`"$notesBody`",`"draft`":false,`"prerelease`":false}"
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/SrLuther/ARKLAND-Multi/releases" `
    -Method Post -Headers $gh -Body $releaseBodyJson -ContentType "application/json; charset=utf-8"
Write-Ok "Release criada: $($release.html_url)"

$uploadUrl = $release.upload_url -replace '\{.*\}', "?name=ARKLAND-Multi-Setup-v$Version.exe"
$asset = Invoke-RestMethod -Uri $uploadUrl -Method Post -Headers $gh `
    -InFile $installer -ContentType "application/octet-stream"
Write-Ok "Asset enviado:  $($asset.browser_download_url)"

# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  RELEASE v$Version PUBLICADA COM SUCESSO!" -ForegroundColor Green
Write-Host "  $($release.html_url)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

