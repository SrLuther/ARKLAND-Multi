# ARK Survival Evolved — Referência Completa de Configuração de Servidor

> Base de conhecimento interna do projeto ARKLAND Multi.  
> Atualizado em: 2026-05-31 (v1.5.5)

---

## Sumário

1. [Estrutura de Arquivos do Servidor](#1-estrutura-de-arquivos-do-servidor)
2. [Sintaxe de Lançamento (Windows)](#2-sintaxe-de-lançamento-windows)
3. [Parâmetros de Linha de Comando](#3-parâmetros-de-linha-de-comando)
4. [GameUserSettings.ini — Seções e Chaves](#4-gameusersettingsini--seções-e-chaves)
5. [Game.ini — Seções e Chaves](#5-gameini--seções-e-chaves)
6. [Portas de Rede](#6-portas-de-rede)
7. [Modos de Jogo e Mapas Válidos](#7-modos-de-jogo-e-mapas-válidos)
8. [Configuração de Cluster Cross-ARK](#8-configuração-de-cluster-cross-ark)
9. [RCON](#9-rcon)
10. [Mods (Steam Workshop)](#10-mods-steam-workshop)
11. [Regras Gerais de INI](#11-regras-gerais-de-ini)
12. [Bugs e Armadilhas Conhecidas](#12-bugs-e-armadilhas-conhecidas)
13. [Mapeamento ARKLAND → ARK (Referência Interna)](#13-mapeamento-arkland--ark-referência-interna)

---

## 1. Estrutura de Arquivos do Servidor

```
<install_dir>/
├── ShooterGame/
│   ├── Binaries/Win64/
│   │   └── ShooterGameServer.exe          ← executável do servidor
│   ├── Content/                           ← assets do jogo (não editar)
│   └── Saved/
│       ├── Config/WindowsServer/
│       │   ├── GameUserSettings.ini       ← configurações principais
│       │   ├── Game.ini                   ← configurações de gameplay
│       │   └── RunServer.cmd              ← script de inicialização (gerado pelo ARKLAND)
│       ├── Logs/
│       │   └── ShooterGame.log            ← log principal do servidor
│       └── SavedArks/                     ← saves do mundo (ou subpasta de AltSaveDirectoryName)
│           └── <AltSaveDirectoryName>/
└── Engine/
    └── Binaries/ThirdParty/SteamCMD/      ← SteamCMD (se instalado junto)
```

**Caminhos importantes:**
- INI: `<install_dir>/ShooterGame/Saved/Config/WindowsServer/`
- Log: `<install_dir>/ShooterGame/Saved/Logs/ShooterGame.log`
- Saves: `<install_dir>/ShooterGame/Saved/SavedArks/`

---

## 2. Sintaxe de Lançamento (Windows)

### Formato correto (obrigatório)

```bat
start "Título da Janela" /normal "C:\caminho\ShooterGameServer.exe" "MAPA?listen?Opcao1=Valor1?Opcao2=Valor2" -flag1 -flag2
```

> **CRÍTICO:** No Windows, o bloco `MAPA?...opções...` **DEVE estar entre aspas duplas**.  
> O `cmd.exe` interpreta espaços como separadores de argumento. Se o valor de qualquer opção  
> contiver espaço (ex: `SessionName=Meu Servidor ARK`), o processo recebe argumentos  
> corrompidos e fecha imediatamente **sem logar o motivo**.

### Exemplo real gerado pelo ARKLAND:

```bat
@echo off
"C:\ARK Manager\servers\01\ShooterGame\Binaries\Win64\ShooterGameServer.exe" "ScorchedEarth_P?listen?Port=7794?QueryPort=27102?MaxPlayers=10" -nosteamclient -game -server -log
```

### Por que NÃO usar `SessionName` na CLI

O `SessionName` com espaços quebra o parsing mesmo entre aspas em algumas versões do engine.  
O ARKLAND o grava **somente no `GameUserSettings.ini`** sob `[SessionSettings] SessionName=`.

---

## 3. Parâmetros de Linha de Comando

### Opções do mapa (formato `?Chave=Valor`, sem espaços)

| Parâmetro | Exemplo | Descrição |
|---|---|---|
| `listen` | `?listen` | Obrigatório. Modo servidor dedicado |
| `Port` | `?Port=7777` | Porta de jogo (UDP) |
| `QueryPort` | `?QueryPort=27015` | Porta de descoberta Steam (UDP) |
| `MaxPlayers` | `?MaxPlayers=70` | Máximo de jogadores simultâneos |
| `MultiHome` | `?MultiHome=192.168.1.10` | Bind em IP específico (só se houver múltiplas interfaces) |
| `AltSaveDirectoryName` | `?AltSaveDirectoryName=server01` | Subpasta de saves — evita conflito entre instâncias |
| `ClusterId` | `?ClusterId=meucluster` | ID do cluster Cross-ARK |
| `PreventDownloadItems` | `?PreventDownloadItems=False` | Usado junto com ClusterId |

> **`MultiHome` é CLI-only**: Não vai ao INI. Só inclua se a máquina tiver múltiplas placas  
> de rede e você quiser forçar bind em uma interface específica. Omitir = escuta em todas.

### Flags (formato `-flag`)

| Flag | Descrição |
|---|---|
| `-server` | Obrigatório. Marca como servidor dedicado |
| `-log` | Obrigatório. Ativa gravação de log em disco |
| `-game` | Obrigatório (junto com `-nosteamclient`) |
| `-nosteamclient` | Desabilita cliente Steam no processo servidor |
| `-ForceAllowCaveFlyers` | Permite voadores em cavernas |
| `-crossplay` | Permite Epic Games Store + Steam juntos |
| `-epiconly` | Apenas jogadores Epic (sem Steam) |
| `-UseBattlEye` | Ativa anti-cheat BattlEye |
| `-insecure` | Desativa VAC (apenas para testes) |
| `-servergamelog` | Ativa log de admin detalhado |
| `-NoDinos` | Inicia sem spawn de dinossauros |
| `-noantispeedhack` | Desativa proteção anti-speedhack |
| `-d3d10` | Força DirectX 10 (menor uso de VRAM) |
| `-lowmemory` | Modo de baixo uso de memória |
| `-clusterid=VALOR` | Alternativa ao `?ClusterId=` (formato diferente) |

---

## 4. GameUserSettings.ini — Seções e Chaves

Arquivo: `ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini`

### [SessionSettings]

| Chave INI | Tipo | Padrão | Descrição |
|---|---|---|---|
| `SessionName` | string | `"My ARK Server"` | Nome exibido no browser de servidores |
| `Port` | int | `7777` | Porta de jogo (deve coincidir com CLI `?Port=`) |
| `QueryPort` | int | `27015` | Porta Steam Query |

### [ServerSettings]

| Chave INI | Tipo | Padrão | Descrição |
|---|---|---|---|
| `ServerAdminPassword` | string | `""` | Senha de admin (enablecheats) |
| `ServerPassword` | string | `""` | Senha para entrar no servidor |
| `SpectatorPassword` | string | `""` | Senha para modo espectador |
| `RCONEnabled` | bool | `True` | Ativa RCON |
| `RCONPort` | int | `27020` | Porta RCON (TCP) |
| `RCONServerGameLogBuffer` | int | `600` | Linhas de log mantidas no buffer RCON |
| `ActiveMods` | string | `""` | IDs de mods separados por vírgula ex: `123456,789012` |
| `AutoSavePeriodMinutes` | float | `15.0` | Intervalo de autosave em minutos |
| `KickIdlePlayersPeriod` | float | `3600.0` | Segundos para kick de jogador inativo |
| `ServerHardcore` | bool | `False` | Modo Hardcore (morte = deleção de personagem) |
| `ServerPVE` | bool | `False` | `True` = PvE. **Inverte lógica:** campo `enable_pvp=True` → `ServerPVE=False` |
| `DifficultyOffset` | float | `0.2` | Dificuldade base (0.0 a 1.0) |
| `OverrideOfficialDifficulty` | float | `5.0` | Nível máximo de wild dino (só válido se `DifficultyOffset=1.0`) |
| `MaxTamedDinos` | int | `5000` | Limite global de dinos domesticados |
| `XPMultiplier` | float | `1.0` | Multiplicador de XP |
| `TamingSpeedMultiplier` | float | `1.0` | Velocidade de domesticação |
| `HarvestAmountMultiplier` | float | `1.0` | Quantidade colhida |
| `PlayerDamageMultiplier` | float | `1.0` | Dano do jogador |
| `PlayerResistanceMultiplier` | float | `1.0` | Resistência do jogador |
| `DinoCountMultiplier` | float | `1.0` | Quantidade de dinos selvagens |
| `AllowThirdPersonPlayer` | bool | `True` | Câmera em terceira pessoa |
| `ShowMapPlayerLocation` | bool | `True` | Mostrar posição no mapa |
| `ServerCrosshair` | bool | `True` | Mira na tela |
| `AllowHitMarkers` | bool | `True` | Marcador de hit |
| `EnablePVPGamma` | bool | `False` | Gamma no PvP |
| `PreventTribeAlliances` | bool | `False` | `True` = proíbe alianças. **Inverte:** campo `allow_tribe_alliances=True` → `False` |
| `PreventDiseases` | bool | `False` | `True` = sem doenças. **Inverte:** campo `enable_diseases=True` → `False` |
| `NoTributeDownloads` | bool | `False` | `True` = sem downloads de tributo. **Inverte:** campo `enable_tribute_downloads` |
| `AdminLogging` | bool | `False` | Loga comandos admin no chat |
| `BanListURL` | string | `http://arkdedicated.com/banlist.txt` | URL da lista de ban |
| `TribeLogDestroyedEnemyStructures` | bool | `False` | Loga destruição de estruturas inimigas |
| `MaxNumberOfPlayersInTribe` | int | `0` | Limite de membros por tribo (0 = sem limite) |

### [GameSession]

| Chave INI | Tipo | Padrão | Descrição |
|---|---|---|---|
| `MaxPlayers` | int | `70` | Deve coincidir com `?MaxPlayers=` na CLI |

### [MessageOfTheDay]

| Chave INI | Tipo | Padrão | Descrição |
|---|---|---|---|
| `Message` | string | `""` | Mensagem exibida ao conectar |
| `Duration` | int | `20` | Duração em segundos |

---

## 5. Game.ini — Seções e Chaves

Arquivo: `ShooterGame/Saved/Config/WindowsServer/Game.ini`

A seção principal é `[/Script/ShooterGame.ShooterGameMode]`.

### Campos mais usados

| Chave INI | Tipo | Padrão | Descrição |
|---|---|---|---|
| `bDisableFriendlyFire` | bool | `False` | Sem fogo amigo (PvP) |
| `bPvEDisableFriendlyFire` | bool | `False` | Sem fogo amigo (PvE) |
| `bDisableLootCrates` | bool | `False` | Remove supply drops |
| `bAllowCustomRecipes` | bool | `True` | Receitas customizadas |
| `MatingIntervalMultiplier` | float | `1.0` | Intervalo entre acasalamentos |
| `EggHatchSpeedMultiplier` | float | `1.0` | Velocidade de chocagem |
| `BabyMatureSpeedMultiplier` | float | `1.0` | Velocidade de crescimento |
| `BabyFoodConsumptionSpeedMultiplier` | float | `1.0` | Consumo de comida de filhote |
| `BabyCuddleIntervalMultiplier` | float | `1.0` | Intervalo entre mimados |
| `BabyImprintingStatScaleMultiplier` | float | `1.0` | Escala de bônus de imprinting |
| `PassiveTameIntervalMultiplier` | float | `1.0` | Intervalo de tame passivo |
| `bDisableDinoRiding` | bool | `False` | Proíbe montar dinos |
| `bDisableDinoTaming` | bool | `False` | Proíbe domesticar dinos |
| `MaxTribeLogs` | int | `100` | Linhas máx. no log de tribo |
| `bAutoPvETimer` | bool | `False` | Timer automático PvE/PvP |
| `bAutoPvEUseSystemTime` | bool | `False` | Usa horário do sistema no timer PvE |
| `GlobalCorpseDecompositionTimeMultiplier` | float | `1.0` | Tempo de decomposição de corpo |
| `PoopIntervalMultiplier` | float | `1.0` | Frequência de cocô |
| `HairGrowthSpeedMultiplier` | float | `1.0` | Velocidade de crescimento de cabelo |
| `ResourceNoReplenishRadiusPlayers` | float | `1.0` | Raio de não-reaparecimento próximo a jogadores |
| `ResourceNoReplenishRadiusStructures` | float | `1.0` | Raio de não-reaparecimento próximo a estruturas |

### Multiplicadores de Stats por Nível (PerLevelStatsMultiplier)

Índices de stat:

| Índice | Stat |
|---|---|
| 0 | Vida (Health) |
| 1 | Stamina |
| 2 | Torpor |
| 3 | Oxigênio |
| 4 | Comida |
| 5 | Água |
| 6 | Temperatura |
| 7 | Peso |
| 8 | Dano (Melee) |
| 9 | Velocidade de Movimento |
| 10 | Fortitude |
| 11 | Crafting |

Formato no INI:
```ini
[/Script/ShooterGame.ShooterGameMode]
PerLevelStatsMultiplier_Player[0]=1.5
PerLevelStatsMultiplier_DinoWild[8]=1.0
PerLevelStatsMultiplier_DinoTamed[0]=0.2
PerLevelStatsMultiplier_DinoTamed_Add[0]=0.14
PerLevelStatsMultiplier_DinoTamed_Affinity[0]=0.44
```

---

## 6. Portas de Rede

| Porta | Protocolo | Uso | Campo Config |
|---|---|---|---|
| 7777 (padrão) | UDP | Porta de jogo — jogadores conectam aqui | `server_port` / `?Port=` |
| 27015 (padrão) | UDP | Steam Query — listagem de servidores | `query_port` / `?QueryPort=` |
| 27020 (padrão) | TCP | RCON — controle remoto | `rcon_port` |

**Regras para múltiplos servidores na mesma máquina:**
- Cada servidor precisa de portas **únicas** (jogo, query e RCON).
- Separação sugerida: incrementar de 3 em 3 (ex: 7777/27015/27020, 7780/27018/27023).
- Liberar no Windows Firewall (regras de entrada UDP para jogo+query, TCP para RCON).
- No roteador: encaminhar (port forward) apenas as portas de jogo e query.

---

## 7. Modos de Jogo e Mapas Válidos

### Mapas internos (sem mods)

| Mapa Exibido | Valor CLI | Observação |
|---|---|---|
| The Island | `TheIsland` | Mapa original |
| The Center | `TheCenter` | |
| Scorched Earth | `ScorchedEarth_P` | DLC, requer posse |
| Ragnarok | `Ragnarok` | |
| Aberration | `Aberration_P` | DLC |
| Extinction | `Extinction` | DLC |
| Valguero | `Valguero_P` | |
| Genesis Part 1 | `Genesis` | DLC |
| Genesis Part 2 | `Gen2` | DLC |
| Crystal Isles | `CrystalIsles` | |
| Lost Island | `LostIsland` | |
| Fjordur | `Fjordur` | |

### Mapas de mods
Usar o ID do mod no parâmetro `?GameModIds=` ou o nome do mapa conforme a publicação no Workshop.

---

## 8. Configuração de Cluster Cross-ARK

Cluster permite transferência de jogadores, itens e dinos entre servidores.

### Parâmetros CLI necessários em cada servidor do cluster

```bat
"ShooterGameServer.exe" "MAPA?listen?Port=7777?QueryPort=27015?ClusterId=meu_cluster_unico?AltSaveDirectoryName=servidor01?PreventDownloadItems=False" -server -log -nosteamclient -game
```

### Pasta do cluster

- Todos os servidores do cluster precisam acessar **a mesma pasta** de cluster.
- Local (mesma máquina): pasta compartilhada acessível por todos os processos.
- Rede: caminho UNC `\\servidor\pasta` ou unidade mapeada.

### Flag adicional no engine (não CLI, mas via arquivo de config)

No `Engine.ini` de cada servidor, adicionar:
```ini
[/Script/Engine.GameNetworkManager]
TotalNetBandwidth=104857600
```

### Prevenção de downloads (opcional por servidor)

```ini
[ServerSettings]
PreventDownloadSurvivors=False
PreventDownloadItems=False
PreventDownloadDinos=False
```

---

## 9. RCON

RCON (Remote Console) permite enviar comandos ao servidor sem estar em jogo.

### Configuração mínima

```ini
[ServerSettings]
RCONEnabled=True
RCONPort=27020
ServerAdminPassword=SuaSenhaAqui
```

### Comandos úteis via RCON

| Comando | Efeito |
|---|---|
| `saveworld` | Salva o mundo manualmente |
| `listplayers` | Lista jogadores online (Nome, SteamID) |
| `kickplayer <SteamID>` | Expulsa jogador |
| `ban <SteamID>` | Bane jogador |
| `broadcast <mensagem>` | Envia mensagem para todos |
| `serverchat <mensagem>` | Mensagem de chat do servidor |
| `destroywilddinos` | Destrói todos dinos selvagens (respawn limpo) |
| `cheat saveworld` | Forçar save (com cheats ativos) |
| `doexit` | Encerra o servidor |

---

## 10. Mods (Steam Workshop)

### Instalação via SteamCMD

```bat
steamcmd.exe +login anonymous +app_update 376030 +workshop_download_item 346110 <MOD_ID> +quit
```

### Ativação no servidor

No `GameUserSettings.ini`:
```ini
[ServerSettings]
ActiveMods=123456,789012,345678
```

Ou na CLI:
```
?GameModIds=123456,789012
```

> **Nota:** A ordem dos mods importa. Mods com conflito devem ser ordenados conforme recomendação do autor.

### Mods que modificam INI

Alguns mods requerem entradas em `Game.ini` ou `GameUserSettings.ini`.  
Adicionar nas seções customizadas correspondentes — **nunca nas seções que o ARKLAND gerencia automaticamente** (para evitar sobrescrita).

---

## 11. Regras Gerais de INI

1. **Encoding**: Os arquivos INI do ARK devem ser **UTF-16 LE com BOM** no Windows.  
   Salvar como UTF-8 causa falha silenciosa na leitura de algumas chaves.

2. **Case-sensitivity das chaves**: O ARK é sensível a maiúsculas/minúsculas em muitas chaves.  
   `ServerAdminPassword` ≠ `serveradminpassword`.

3. **Booleanos**: Usar `True`/`False` com inicial maiúscula. Valores `true`/`false` funcionam mas não são oficiais.

4. **Listas**: `ActiveMods` usa vírgula sem espaço: `123456,789012` (nunca `123456, 789012`).

5. **Seções obrigatórias**: Mesmo que vazia, a seção `[SessionSettings]` deve existir no GUS.

6. **Recarga de INI sem restart**: Alguns valores do `[ServerSettings]` podem ser recarregados  
   via RCON com `cheat reloadconfig` — mas a maioria requer reinício.

7. **Campos com lógica invertida** (conforme INI_MAP do ARKLAND):
   - `ServerPVE` = `NOT enable_pvp`
   - `PreventTribeAlliances` = `NOT allow_tribe_alliances`
   - `PreventDiseases` = `NOT enable_diseases`
   - `NoTributeDownloads` = `NOT enable_tribute_downloads`
   - `ServerForceNoHud` = `NOT allow_hud`
   - `DisablePvEGamma` = `NOT allow_pve_gamma`

---

## 12. Bugs e Armadilhas Conhecidas

### ❌ SessionName com espaços na CLI (causa: servidor não inicia)

**Problema:** Incluir `?SessionName=Nome Com Espacos` na linha de comando sem aspas  
faz o `cmd.exe` quebrar o argumento nos espaços. O ARK recebe mapa corrompido e fecha.

**Solução:** O ARKLAND (v1.5.5+) **não coloca `SessionName` na CLI**. O nome vai somente  
no `GameUserSettings.ini` sob `[SessionSettings] SessionName=`.

---

### ❌ Mapa+opções sem aspas (Windows, causa: servidor não inicia)

**Problema:** Sintaxe sem aspas:
```
ShooterGameServer.exe ScorchedEarth_P?listen?Port=7777 -server -log
```
Funciona apenas se nenhum valor contiver espaço. Com espaços, falha silenciosamente.

**Solução correta:**
```
"ShooterGameServer.exe" "ScorchedEarth_P?listen?Port=7777" -server -log
```

---

### ❌ MultiHome com IP público (causa: servidor não ativa conexões)

**Problema:** Preencher `MultiHome` com o IP público de VPS ou roteador impede o ARK  
de bindar na interface correta — ele precisa do **IP local da interface de rede**.

**Regra:** Omitir `?MultiHome=` na maioria dos casos. Usar somente quando a máquina  
tiver múltiplas NICs e for necessário forçar uma delas. Usar o IP **privado/local** da NIC.

---

### ❌ MultiHome no INI (causa: crash ao iniciar)

**Problema:** Versões antigas do ARKLAND (< v1.5.3) escreviam `MultiHome` no  
`GameUserSettings.ini`. O ARK não reconhece essa chave no INI e pode crashar.

**Solução:** `MultiHome` é **CLI-only** (`?MultiHome=`). Nunca vai ao INI.

---

### ❌ AltSaveDir vs AltSaveDirectoryName

**Parâmetro correto:** `?AltSaveDirectoryName=nomeDaPasta`  
**Parâmetro errado:** `?AltSaveDir=...` (não reconhecido pelo ARK)

---

### ❌ ClusterId vs clusterid

- CLI como opção de mapa: `?ClusterId=valor` (sensível a case)
- CLI como flag: `-clusterid=valor` (alternativa, lowercase)
- **Nunca** colocar no INI.

---

### ❌ Encoding errado nos arquivos INI

**Sintoma:** Servidor inicia mas ignora configurações, ou nome do servidor aparece com caracteres  
estranhos.

**Causa:** Arquivo salvo em UTF-8 em vez de UTF-16 LE com BOM.

**Solução:** O ARKLAND usa `open(path, 'w', encoding='utf-16')` para gravar os INIs.

---

### ❌ Porta ocupada (servidor não inicia, sem log de erro)

O ARK fecha silenciosamente se a porta de jogo ou query já estiver em uso.

**Verificar com PowerShell:**
```powershell
netstat -ano | findstr ":7777"
```

---

## 13. Mapeamento ARKLAND → ARK (Referência Interna)

Esta seção documenta como o ARKLAND traduz campos internos para o ARK.  
Fonte: `src/asm_engine/asm_ini_manager.py` (INI_MAP) e `build_launch_args()`.

### Campos CLI-only (não vão ao INI)

| Campo ARKLAND | Argumento CLI | Tipo |
|---|---|---|
| `server_map` | `MAPA?listen?...` | Parte do combined_map |
| `server_port` | `?Port=` | combined_map (E também INI) |
| `query_port` | `?QueryPort=` | combined_map (E também INI) |
| `max_players` | `?MaxPlayers=` | combined_map (E também INI) |
| `server_ip` | `?MultiHome=` | combined_map somente |
| `alt_save_directory_name` | `?AltSaveDir=` | combined_map somente |
| `cross_ark_cluster_id` | `?ClusterId=` | combined_map somente |
| `allow_cave_flyers` | `-ForceAllowCaveFlyers` | flag |
| `additional_args` | flags extras | flags |

> **Nota:** `server_port`, `query_port` e `max_players` aparecem tanto na CLI  
> quanto no INI. O ARK usa o INI para persistência e a CLI tem precedência no boot.

### Campos INI com lógica invertida

| Campo ARKLAND | Chave INI | Lógica |
|---|---|---|
| `enable_pvp = True` | `ServerPVE = False` | Invertido |
| `allow_tribe_alliances = True` | `PreventTribeAlliances = False` | Invertido |
| `enable_diseases = True` | `PreventDiseases = False` | Invertido |
| `enable_tribute_downloads = True` | `NoTributeDownloads = False` | Invertido |
| `allow_hud = True` | `ServerForceNoHud = False` | Invertido |
| `allow_pve_gamma = True` | `DisablePvEGamma = False` | Invertido |
| `pvp_dino_decay = True` | `PvPDinoDecay = True` | Invertido no campo (ver código) |

### Campos condicionais (só gravados se ativos)

| Campo ARKLAND | Condição para gravar |
|---|---|
| `override_official_difficulty` | `enable_difficulty_override = True` |
| `max_tribe_size` | `max_tribe_size != 0` |
| `override_max_xp_player` | `override_max_xp_player != 0` |
| `ban_list_url` | `enable_ban_list_url = True` |
| `motd` + `motd_duration` | `motd != ""` |

---

*Documento gerado automaticamente a partir do código-fonte do ARKLAND Multi v1.5.5.*  
*Para atualizações, referenciar: `src/asm_engine/asm_ini_manager.py`, `src/asm_engine/asm_server_manager.py`, `src/server_config.py`*
