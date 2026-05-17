param()
Set-Location "C:\Users\Ciano\Documents\arkland-multi"

# Obter token do credential store
$lines = "protocol=https`nhost=github.com`n" | git credential fill 2>$null
$token = ($lines | Where-Object { $_ -match "^password=" }) -replace "^password=", ""

if (-not $token) { Write-Error "Token nao encontrado"; exit 1 }

$headers = @{
    "Authorization"        = "Bearer $token"
    "Accept"               = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$notes = @"
## O que há de novo

### Novo
- **Integração com Beacon (usebeacon.app)** — autenticação OAuth Device Flow (PKCE), cache local de blueprints ARK Prime (~1963 itens, TTL 7 dias)
- **Blueprint Picker** — botão 🔍 em todos os campos Blueprint do ArkShop: busca live por nome ou classString, filtro por Itens/Criaturas/Todos, integrado em kit itens, kit dinos, selas e itens da loja
- **INI do Mod — Inserir seção** — botão 📋 Inserir seção... nos headers Game.ini e GUS.ini do dialog de mod: insere seções cadastradas sem substituir o conteúdo existente

### Melhoria
- Aba Jogo: renderização em chunks (after(0)) — elimina freeze de ~500ms dos 44 CTkSliders
- Pre-build de abas em idle com 1500ms de intervalo — zero freezes periódicos em background

### Correção
- Erros Pylance corrigidos em beacon_client, server_manager, arkland_updater, beacon_explore, beacon_sync

---
**Instalação silenciosa:**
ARKLAND-Multi-Setup-v1.2.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
"@

# 1) Criar release
$bodyObj = [ordered]@{
    tag_name         = "v1.2.0"
    target_commitish = "main"
    name             = "ARKLAND Server Manager v1.2.0"
    body             = $notes
    draft            = $false
    prerelease       = $false
}
$bodyJson = $bodyObj | ConvertTo-Json -Depth 3

Write-Host "[1/2] Criando release..."
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/SrLuther/ARKLAND-Multi/releases" `
    -Method POST -Headers $headers -Body $bodyJson -ContentType "application/json; charset=utf-8"

Write-Host "      Release criado: $($release.html_url)"

# 2) Upload do installer
$uploadBase = $release.upload_url -replace '\{[^}]+\}', ''
$installerPath = "installer\ARKLAND-Multi-Setup-v1.2.0.exe"
$fileName = "ARKLAND-Multi-Setup-v1.2.0.exe"
$uploadUri = "${uploadBase}?name=${fileName}&label=${fileName}"

Write-Host "[2/2] Fazendo upload: $installerPath ($([Math]::Round((Get-Item $installerPath).Length/1MB, 1)) MB)..."

$uploadHeaders = @{
    "Authorization"        = "Bearer $token"
    "Accept"               = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
    "Content-Type"         = "application/octet-stream"
}

$asset = Invoke-RestMethod -Uri $uploadUri -Method POST -Headers $uploadHeaders `
    -InFile $installerPath

Write-Host "      Asset: $($asset.browser_download_url)"
Write-Host ""
Write-Host "=== RELEASE PUBLICADO: $($release.html_url) ==="

