<#
.SYNOPSIS
    Instala Caddy (reverse proxy HTTPS) para arkland.com.br -> Web Store local.

.DESCRIPTION
    Execute como Administrador na máquina HOST da loja (SHOPBASE / 192.168.15.51).
    Requisitos externos:
      - DNS A de arkland.com.br -> IP publico desta rede
      - Roteador: portas 80 e 443 -> IP LAN desta maquina
      - Web Store rodando em localhost (padrao porta 27199)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\setup_loja_https.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\setup_loja_https.ps1 -Domain arkland.com.br -BackendPort 27199
#>
[CmdletBinding()]
param(
    [string]$Domain = "arkland.com.br",
    [int]$BackendPort = 27199,
    [string]$InstallDir = "C:\caddy",
    [string]$Email = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host ""
        Write-Host "ERRO: execute como Administrador (botao direito -> Executar como administrador)." -ForegroundColor Red
        exit 1
    }
}

function Write-Step($text) {
    Write-Host ""
    Write-Host ">> $text" -ForegroundColor Cyan
}

function Test-Backend {
    param([int]$Port)
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 5
        return $true, "HTTP $($r.StatusCode)"
    } catch {
        return $false, $_.Exception.Message
    }
}

Require-Admin

Write-Host ""
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "  ARKLAND — Setup HTTPS (Caddy) -> localhost:$BackendPort" -ForegroundColor Yellow
Write-Host "  Dominio: $Domain, www.$Domain" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow

# ── 1) Web Store local ───────────────────────────────────────────────────────
Write-Step "Testando Web Store em http://127.0.0.1:$BackendPort ..."
$ok, $msg = Test-Backend -Port $BackendPort
if ($ok) {
    Write-Host "   OK  Loja respondendo ($msg)" -ForegroundColor Green
} else {
    Write-Host "   AVISO: loja nao respondeu em localhost:$BackendPort" -ForegroundColor Yellow
    Write-Host "   $msg" -ForegroundColor Yellow
    Write-Host "   Inicie a Web Store no ARKLAND (modo Host) antes de testar o dominio." -ForegroundColor Yellow
    $cont = if ($Force) { "s" } else { Read-Host "Continuar mesmo assim? (s/N)" }
    if ($cont -notmatch '^[sS]') { exit 1 }
}

# ── 2) Firewall Windows ──────────────────────────────────────────────────────
Write-Step "Regras de firewall (TCP 80 e 443)..."
foreach ($port in 80, 443) {
    $name = "ARKLAND Caddy $port"
    $existing = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "   OK  Regra ja existe: $name" -ForegroundColor DarkGreen
    } else {
        New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $port | Out-Null
        Write-Host "   OK  Criada: $name" -ForegroundColor Green
    }
}

# ── 3) Baixar Caddy ──────────────────────────────────────────────────────────
Write-Step "Instalando Caddy em $InstallDir ..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$caddyExe = Join-Path $InstallDir "caddy.exe"

if (-not (Test-Path $caddyExe)) {
    Write-Host "   Obtendo URL do ultimo release..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/caddyserver/caddy/releases/latest" -UseBasicParsing
    $asset = $release.assets | Where-Object { $_.name -match '^caddy_.*_windows_amd64\.zip$' } | Select-Object -First 1
    if (-not $asset) {
        throw "Release Windows amd64 do Caddy nao encontrado no GitHub."
    }
    $releaseUrl = $asset.browser_download_url
    $zip = Join-Path $env:TEMP "caddy_windows_amd64.zip"
    Write-Host "   Baixando $($asset.name) ..."
    Invoke-WebRequest -Uri $releaseUrl -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $InstallDir -Force
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    Write-Host "   OK  caddy.exe instalado" -ForegroundColor Green
} else {
    Write-Host "   OK  caddy.exe ja existe" -ForegroundColor DarkGreen
}

# ── 4) Caddyfile ─────────────────────────────────────────────────────────────
Write-Step "Gravando Caddyfile..."
$caddyfile = Join-Path $InstallDir "Caddyfile"
$globalBlock = ""
if ($Email.Trim()) {
    $globalBlock = @"
{
    email $Email
}

"@
}

$cfg = @"
$globalBlock$Domain, www.$Domain {
    reverse_proxy 127.0.0.1:$BackendPort {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
        header_up X-Forwarded-Host {host}
    }
}
"@

Set-Content -Path $caddyfile -Value $cfg.TrimEnd() -Encoding UTF8
Write-Host "   OK  $caddyfile" -ForegroundColor Green

# ── 5) Validar config ────────────────────────────────────────────────────────
Write-Step "Validando configuracao..."
Push-Location $InstallDir
& $caddyExe validate --config $caddyfile
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Host "ERRO: Caddyfile invalido." -ForegroundColor Red
    exit 1
}
Pop-Location
Write-Host "   OK  Config valida" -ForegroundColor Green

# ── 6) Servico Windows ───────────────────────────────────────────────────────
Write-Step "Registrando servico Windows Caddy..."
Push-Location $InstallDir

# Para servico anterior (reinstala limpo) — ignorar se nunca instalado
$prevErr = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $caddyExe stop 2>&1 | Out-Null
& $caddyExe uninstall 2>&1 | Out-Null
$ErrorActionPreference = $prevErr

& $caddyExe install --config $caddyfile
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Host "ERRO: falha ao instalar servico Caddy." -ForegroundColor Red
    exit 1
}

& $caddyExe start
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Host "ERRO: falha ao iniciar Caddy." -ForegroundColor Red
    exit 1
}
Pop-Location
Write-Host "   OK  Servico Caddy iniciado" -ForegroundColor Green

Start-Sleep -Seconds 3

# ── 7) Testes locais ─────────────────────────────────────────────────────────
Write-Step "Testes locais..."
foreach ($url in @("http://127.0.0.1/")) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
        Write-Host "   OK  $url -> HTTP $($r.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "   --  $url -> $($_.Exception.Message)" -ForegroundColor Yellow
    }
}
Write-Host "   (HTTPS local pode falhar antes do certificado; teste https://$Domain no celular 4G)" -ForegroundColor Gray

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  CONCLUIDO" -ForegroundColor Green
Write-Host ""
Write-Host "  Teste no navegador (de outra rede ou celular 4G):" -ForegroundColor White
Write-Host "    https://$Domain" -ForegroundColor White
Write-Host "    https://www.$Domain" -ForegroundColor White
Write-Host ""
Write-Host "  Se falhar:" -ForegroundColor Gray
Write-Host "    1. Roteador: 80 e 443 -> IP LAN desta maquina" -ForegroundColor Gray
Write-Host "    2. DNS: $Domain -> IP publico (nslookup $Domain)" -ForegroundColor Gray
Write-Host "    3. Web Store online na porta $BackendPort" -ForegroundColor Gray
Write-Host "    4. Logs: Get-Content C:\caddy\access.log -Tail 20  (se habilitado)" -ForegroundColor Gray
Write-Host "    5. Servico: Get-Service caddy" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
