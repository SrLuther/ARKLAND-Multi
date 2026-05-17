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
## O que ha de novo

### Novo
- **Agendamentos automáticos** na aba Geral - reiniciar/desligar/atualizar+reiniciar por dia da semana e hora com aviso RCON configurável
- **Seletor de núcleos de CPU** substituindo checkbox - Padrao / Todos / N nucleos com afinidade via psutil
- **Calculadora de Breeding** - cards visuais, campo Cuddle (Imprint) com tempo desejado, botao Wiki

### Correcao
- Botao 'Aplicar ao Servidor' na Calculadora de Breeding agora salva o .ini mesmo com servidor online
- Campo de texto do multiplicador no Jogo atualiza ao aplicar valores da Calculadora

### Melhoria
- MOTD com area de texto maior (altura 180px)

---
**Instalacao silenciosa:**
ARKLAND-Multi-Setup-v1.1.23.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
"@

# 1) Criar release
$bodyObj = [ordered]@{
    tag_name         = "v1.1.23"
    target_commitish = "main"
    name             = "ARKLAND Server Manager v1.1.23"
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
$installerPath = "installer\ARKLAND-Multi-Setup-v1.1.23.exe"
$fileName = "ARKLAND-Multi-Setup-v1.1.23.exe"
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

