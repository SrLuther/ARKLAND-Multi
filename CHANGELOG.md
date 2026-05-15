# Changelog — ARKLAND Server Manager

Todas as mudanças notáveis deste projeto serão documentadas aqui.  
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [1.1.14] — 2026-05-15

### Novo — Tooltip de ajuda na seção Comandos do ArkShop

- Botão `?` circular adicionado ao cabeçalho da seção **Comandos** no painel de detalhe de kit.
- Ao passar o mouse, exibe tooltip flutuante com as variáveis disponíveis (`{steamid}`, `{playerid}`, `{playername}`) e exemplos de comandos do plugin ArkShop (`AddPoints`, `RemovePoints`, `GiveItem`, `AddExperience`, `PrintToPlayer`, `RenamePlayer`, etc.).
- Classe utilitária `_Tooltip` adicionada — reutilizável em qualquer widget do app, com delay configurável e posicionamento automático.

### Novo — Campo ID do kit editável

- O ID do kit agora aparece como campo de texto editável no topo do painel de detalhe.
- Renomear o ID atualiza automaticamente todas as referências internas; conflitos com IDs existentes são detectados e bloqueados com mensagem de erro.

### Novo — Cluster / Múltiplos Servidores

- Nova seção **"Cluster / múltiplos servidores"** no painel ArkShop.
- Permite adicionar quantos caminhos destino forem necessários; ao salvar, o `ArkShop.json` é gravado em todos simultaneamente.
- Útil para clusters com múltiplos mapas que compartilham a mesma loja.

### Novo — Presets nomeados para ArkShop

- Nova seção **Presets** com menu de seleção e três ações: 💾 Salvar, 📂 Carregar, 🗑 Excluir.
- Salva a configuração completa (path, MySQL, Discord, General, Kits, ShopItems e destinos extras) como preset nomeado.
- Presets persistem entre sessões em `%APPDATA%\ARKLAND-ServerManager\arkshop_presets.json`.

### Melhoria — Minimizar para bandeja ao clicar em `−`

- O botão de minimizar da janela (`−`) agora envia o app para a bandeja do sistema quando a opção "Minimizar para bandeja" está ativa, além do botão Fechar (`×`).

### Melhoria — App não encerra servidores ARK ao fechar

- Fechar o ARKLAND Server Manager não mata mais os processos dos servidores ARK (mapas).
- Apenas recursos internos do app são encerrados (sync engine, mod updater, buff manager, backup manager, RCON clients).

### Melhoria — Navegação O(1)

- Troca de tela passou de O(n) para O(1): em vez de iterar e ocultar todos os frames a cada clique, apenas o frame anterior e o novo são alternados via `grid_remove` / `grid`.
- Elimina lag perceptível em workspaces com muitos servidores configurados.

### Correção — Alterações da UI não persistiam ao salvar ArkShop.json

- `_arkshop_save` agora chama `_arkshop_collect_fields()` antes de ler o editor JSON, garantindo que todos os campos editados na UI (kits, itens, configurações gerais) sejam incluídos no arquivo salvo.

### Correção — Tipos Pylance

- `Optional[ctk.CTkFrame]` substituído por `Any` nos atributos de frame do ArkShop.
- Adicionado `# type: ignore[arg-type]` em callbacks `on_done`/`on_result` (lambdas que retornam id do `after()`).
- `btn._status_dot` acessado via `getattr(btn, "_status_dot", None)` para eliminar aviso de atributo desconhecido.
- `CTkSlider from_/to` com `# type: ignore[arg-type]` (aceita `float` em runtime, type hint declarado como `int`).
- `.vscode/settings.json` criado apontando o interpretador Python para `.venv`.

---

## [1.1.13] — 2026-05-15

### Correção crítica — Formato `.mod` completamente reescrito

- **Corrige definitivamente o crash** `Invalid BufferCount=0 while reading .../Mods/{id}.mod` ao iniciar servidor com mods.
- A versão anterior (`1.1.12`) gerava o `.mod` com estrutura errada: tratava o primeiro `uint32` do `mod.info` como `mapCount`, mas na realidade é o comprimento do nome do mod (`nameLen`).
- O arquivo `.mod` gerado também estava incompleto — faltava o nome do mod, o caminho canônico, o magic footer e o conteúdo do `modmeta.info`.
- `_create_dot_mod_from_mod_info` completamente reescrito com base no formato documentado pelo `arkmanager/doExtractMod`:
  - Lê `nameLen` + `modName` do cabeçalho do `mod.info` antes de `numMaps`
  - Escreve: `modID` → `modName` → `modPath` (`../../../ShooterGame/Content/Mods/{id}`) → mapa(s) → magic footer `\x33\xFF\x22\xFF\x02\x00\x00\x00\x01` → conteúdo do `modmeta.info`
- **Ação necessária:** apagar os `.mod` corrompidos gerados por versões anteriores em `ShooterGame\Content\Mods\` e re-baixar os mods pelo app.

---

## [1.1.12] — 2026-05-15

### Correção — Crash "BufferCount=0" ao iniciar servidor com mods

- **Corrige crash crítico** `Invalid BufferCount=0 while reading .../Mods/{id}.mod` que derrubava o ARK ao iniciar com mods baixados via SteamCMD.
- A versão anterior copiava `mod.info` diretamente como `{id}.mod`, mas os dois têm **formatos binários distintos**. O ARK interpretava os bytes de `mod.info` como `FUGCModImport` (uint64 ModID + FString + TArray maps) e obtinha offsets inválidos, causando o crash.
- `_create_dot_mod_from_mod_info` agora **gera o binário `.mod` correto** — lê o `mapCount` e os caminhos de mapa do `mod.info` e escreve no formato exato `FUGCModImport` esperado pelo ARK.
- `check_mod_installed` (auto-reparo) também usa o gerador binário correto.
- **Ação necessária:** apagar o arquivo `{mod_id}.mod` corrompido em `ShooterGame\Content\Mods\` e re-baixar o mod pelo app.

---

## [1.1.11] — 2026-05-15

### Correção — Mods não instalados com SteamCMD

- **Corrige bug crítico** onde o SteamCMD nunca cria o arquivo `.mod` externo ao baixar mods via `workshop_download_item` — somente a pasta é criada.
- `_find_dot_mod` agora usa `mod.info` (dentro da pasta do mod) como fallback (caso 4), que é o arquivo de metadados que o SteamCMD **sempre** baixa.
- `check_mod_installed` agora realiza **auto-reparo**: se a pasta do mod existe e o `.mod` está ausente mas `mod.info` está presente, copia automaticamente e loga `"auto-reparado a partir de mod.info"` — corrige instalações feitas por versões anteriores sem precisar re-baixar.
- Log indica se o `.mod` foi copiado de um `.mod` original ou gerado a partir de `mod.info`.

---

## [1.1.10] — 2026-05-14

### Correção — Mods não carregando no servidor

- **Corrige bug crítico** onde mods apareciam como "instalados" na aba Mods mas o ARK os ignorava ao iniciar.
- `check_mod_installed` agora exige a presença da pasta **e** do arquivo `.mod` — sem o `.mod` o ARK não carrega o mod.
- Adicionado fallback ao copiar mods: busca o arquivo `.mod` dentro da pasta do mod caso não esteja ao lado dela (comportamento de algumas versões do SteamCMD).
- O erro de `.mod` ausente agora é logado como `[ATENÇÃO]` no nível `error` em vez de um aviso discreto.
- Aviso pré-start: ao iniciar um servidor, o app verifica se todos os mods configurados possuem o arquivo `.mod`. Se algum estiver incompleto, exibe diálogo perguntando se deseja continuar.

### Novo — Mensagem do Dia (MOTD)

- Novo campo **Mensagem do Dia** na aba Geral de cada servidor.
- Mensagem e duração (segundos) são salvas automaticamente no `GameUserSettings.ini` na seção `[MessageOfTheDay]`.

---

## [1.1.9] — 2026-05-14

### Clonar Configurações entre Servidores

- Novo botão **📋 Clonar Configurações** na aba Avançado de cada servidor.
- Permite copiar todas as configurações de um servidor para um ou mais servidores de destino.
- São copiados: mapa, senhas, mods, multiplicadores, configurações avançadas, cluster, admins, backup e argumentos extras.
- Preservados no servidor de destino: nome interno, diretório de instalação, session name e portas.
- Reconstrói automaticamente o painel de cada servidor destino após a clonagem.

---

## [1.1.8] — 2026-05-14

### Parar Servidor — Encerramento de Árvore de Processos

- Ao parar um servidor, o app agora usa `taskkill /F /T /PID` para encerrar toda a árvore de processos filhos do `ShooterGameServer.exe`.
- Corrige o bug onde o app reportava "Servidor parado" mas o processo do servidor continuava rodando em segundo plano.
- Fallback para `terminate()` / `kill()` caso `taskkill` não esteja disponível.

### Nova Aba Backup

- Nova aba **Backup** adicionada ao painel de cada servidor.
- Habilita backup automático em intervalos configuráveis (1h, 2h, 3h, 6h, 12h, 24h).
- Escolha quantos backups manter (os mais antigos são excluídos automaticamente).
- Seleção do conteúdo: Saves (dados de jogadores/mundo) e/ou Config (arquivos .ini).
- Pasta de destino personalizável com seletor de diretório.
- Botão de **Backup Manual** para snapshots imediatos.
- Lista de backups disponíveis com opções de restaurar e excluir.
- Layout coeso com o padrão visual do restante do aplicativo.

---

## [1.1.7] — 2026-05-14

### Updater — Encerramento Forçado

- O ARKLAND Updater agora mata à força todos os processos `ARKLAND-ServerManager.exe` antes de executar o installer, evitando falha por arquivo bloqueado no Windows.
- Usa `taskkill /F /T /PID` para encerrar a árvore do processo principal e `taskkill /F /IM` para cobrir instâncias extras.

---

## [1.1.6] — 2026-05-14

### Aba Admins — Busca de Nome Steam

- Ao digitar um Steam ID (64-bit), o sistema busca automaticamente o nome do perfil via Steam Community (API pública, sem chave) com debounce de 900 ms.
- Label dinâmica exibe `✅ NomeDoJogador` (verde) ou `⚠️ Perfil privado ou ID inválido` (vermelho).
- O nome resolvido é salvo junto ao ID e exibido na lista: `🎮 76561198... • NomeDoJogador`.
- Ao remover um admin o nome em cache também é limpo.

### Nova Aba Jogadores

- Nova aba **Jogadores** adicionada ao painel de cada servidor (entre Admins e Plugins).
- Lista em tempo real dos jogadores conectados via RCON (`ListPlayers`).
- Exibe nome e Steam ID de cada jogador.
- Ações por jogador:
  - **⭐ Admin** — adiciona o jogador diretamente à lista de admins (oculto se já for admin).
  - **👢 Kick** — confirma e executa `KickPlayer <steamid>`.
  - **🔨 Ban** — confirma com instrução de desfazer e executa `BanPlayer <steamid>`.
- **Auto-refresh** a cada 30 segundos via checkbox na aba.
- Requer conexão RCON ativa (aba "Console RCON").

### Sistema de BUFFs de Rates Temporários

- Nova aba **⚡ BUFFs** no sidebar lateral.
- Gerenciador de eventos de rates temporários estilo eventos oficiais Studio Wildcard.
- Tipos suportados: XP, Doma, Breeding, Farm (combináveis no mesmo evento).
- Multiplicadores rápidos: **5x / 10x / 15x** ou **custom** por campo.
- Agendamento com datas de início e fim (máx. 30 dias), detecção de conflito de sobreposição.
- Presets salvos reutilizáveis com gerenciador dedicado.
- Ao ativar: broadcast RCON → parada do servidor → backup do INI → aplicação dos rates → restart.
- Ao desativar: broadcast RCON → parada → restore do backup → restart.
- Card de buff ativo, lista de agendados com cancelamento, histórico de eventos.

### Mapa Aquatica

- **Aquatica** adicionado à lista de mapas oficiais.

---

## [1.1.5] — 2026-05-14

### Parar Servidor — Correções Críticas

- **`_graceful_shutdown` movido para dentro da thread de parada** — o clique em "Parar" não bloqueia mais a interface enquanto o RCON envia `SaveWorld` + `DoExit`.
- **Cascata de terminação robusta**: RCON gracioso (aguarda até 90 s) → `terminate()` (+10 s) → `kill()` (+10 s) → `os.kill(pid, 9)` como último recurso. Elimina o bug de servidor preso em "PARANDO" para sempre.
- `_start_worker` limpa `inst.process` e `inst.pid` mesmo quando o processo morre durante STOPPING/STARTING.

### Iniciar Servidor — Timeout Aumentado

- Timeout de detecção de "servidor pronto" aumentado de **15 → 45 minutos** para acomodar mapas pesados com muitos mods (ex: Fjordur).

### Botão ⚡ Cancelar

- Quando o servidor está em **INICIANDO** ou **PARANDO**, o botão muda para **⚡ Cancelar** (âmbar) e executa parada forçada imediata — disponível tanto no painel do servidor quanto no Dashboard.

### Dashboard — Visibilidade LAN / WAN

- Cada card do Dashboard exibe agora o badge **🌐 WAN** (verde) ou **🏠 LAN** (âmbar) ao lado do nome do servidor, assim que a visibilidade for detectada.
- O dashboard é atualizado automaticamente quando a visibilidade muda.

### Aba Admins

- Nova aba **Admins** no painel de cada servidor (entre Mods e Plugins).
- Campo para adicionar Steam IDs de administradores (validação: apenas dígitos, mínimo 15 caracteres).
- Lista scrollável com botão de remoção por linha.
- Ao salvar, grava `AllowedCheaterSteamIDs.txt` em `ShooterGame/Saved/Config/WindowsServer/`.

### Atualização Automática de Mods — Novo Fluxo

- O download do mod começa **imediatamente**, enquanto o servidor ainda está em execução.
- Avisos de broadcast são enviados aos jogadores **durante** o download.
- O servidor só é parado **após** o download concluir + o timer de aviso esvaziar.

### ARKLAND Updater — Sub-app de Auto-Update

- Novo executável standalone `ARKLAND-Updater.exe` (via `arkland_updater.py` + `ARKLAND-Updater.spec`).
- Aguarda o app principal fechar, baixa o instalador com barra de progresso, executa silenciosamente e reinicia o app.
- Substitui o script PowerShell temporário usado anteriormente.

### Interface — Lista de Mods

- Linhas da lista de mods com **cores alternadas** (zebra) para facilitar identificar quais botões pertencem a qual mod.

---

## [1.1.4] — 2026-05-14

### Mods — Nomes Automáticos

- Nomes dos mods buscados automaticamente via Steam Workshop API ao adicionar pelo ID.
- Lista de mods exibe **ID — Nome do mod** em vez de só o ID numérico.
- Cache de nomes persistido no `config.json` para evitar requisições repetidas.

### Atualização do Servidor ao Iniciar

- Checkbox **"Atualizar servidor ao iniciar"** agora executa o SteamCMD antes de iniciar o processo do servidor, garantindo que os arquivos estejam atualizados.

### Correções

- Corrigido `build.bat` para compatibilidade com CMD puro (sem PowerShell).

---

## [1.1.3] — 2026-05-14

### Sincronização N-way Multi-Ciclo

- **Até 5 ciclos independentes**, cada ciclo com **até 5 pastas**: o sync propaga sempre a versão mais nova de cada arquivo para todas as pastas do ciclo (bidirecional N-way).
- **Auto-start**: ao abrir o app, o sync é iniciado automaticamente se houver ciclos configurados.
- **Interface redesenhada**: cards dinâmicos por ciclo — adicione/remova ciclos e pastas individualmente, com renumeração automática e limite visual de slots.
- Botão **+ Adicionar Ciclo** desabilitado automaticamente ao atingir o limite de 5 ciclos.
- Compatibilidade retroativa: configurações antigas (`local_cluster_path`/`shared_path`) migradas automaticamente para o novo formato `sync_cycles`.

### Correções e Qualidade

- Corrigidos todos os erros de lint/tipo (Pylance/Ruff) em `updater.py`, `ark_ini.py`, `mod_auto_updater.py`, `mod_manager.py`, `rcon_client.py`, `server_manager.py`, `server_config.py` e `remote_agent.py`.

---

## [1.1.2] — 2026-05-14

### Mods — Configurações INI Personalizadas

- **Configurações INI por mod**: cada mod da lista possui o botão **⚙️ INI** que abre um editor com campos separados para `Game.ini` e `GameUserSettings.ini`. Os blocos são injetados nos arquivos do servidor ao clicar em "Salvar e Aplicar".
- Nome do mod salvo automaticamente ao adicionar via busca no Workshop; exibido na lista de mods junto ao ID.
- Botão ⚙️ INI fica destacado em roxo quando o mod já possui configuração salva.

### Importar INI do Disco — Seleção de Pasta

- O botão **Importar INI do Disco** agora abre um dialog com campo de caminho editável e botão 📁 para navegar até qualquer pasta — ideal para importar de backups ou de outro servidor.

### Segurança — Bloqueio de Edição

- Todas as configurações das abas (Geral, Jogo, Avançado, Mods, Plugins) ficam **desabilitadas** enquanto o servidor estiver em execução ou iniciando.
- Banner laranja `🔒 Configurações bloqueadas` exibido no painel do servidor quando bloqueado.
- `_save_server_config` valida o status novamente antes de persistir, impedindo qualquer escrita acidental nos INIs.

### Correções

- Corrigido erro `AttributeError: '_tkinter.tkapp' object has no attribute '_check_updates_manual'` ao abrir a aba Sobre.
- Removida definição duplicada de `_check_updates_on_start`.

---

## [1.1.1] — 2026-05-14

### Importação e Sincronização de Configurações (NOVO)

- **Importar INI**: botão na aba Avançado permite importar todas as configurações diretamente dos arquivos GameUserSettings.ini e Game.ini do disco, preenchendo automaticamente todos os campos da interface.
- **Sincronizar INI entre servidores**: botão na aba Avançado abre diálogo para selecionar quais servidores receberão os arquivos INI do servidor atual (GameUserSettings.ini e/ou Game.ini). Permite sincronizar configurações avançadas entre múltiplos servidores com um clique.

---

## [1.1.0] — 2026-05-14 — *Transformação completa: de ferramenta de sync para Server Manager*

Esta versão representa uma reescrita quase completa do projeto. O **ARKLAND-Multi** deixou de ser
um utilitário de sincronização de cluster e passou a ser um **gerenciador completo de servidores
ARK: Survival Evolved**, mantendo a sincronização de cluster como uma das funcionalidades.

### Gerenciamento de Servidores (NOVO)

- **Multi-servidor**: suporte a múltiplos servidores ARK na mesma interface, cada um com painel independente
- **Iniciar / Parar / Reiniciar** servidores ARK Dedicated diretamente pelo app
- **Instalação e validação** do servidor via SteamCMD (`app_update 376030`) pela aba Geral
- **Ciclo de vida de status** completo: PARADO → INICIANDO → RODANDO → PARANDO → CRASHADO
- Status **INICIANDO → RODANDO** detectado via monitoramento do arquivo de log real do ARK (`ShooterGame/Saved/Logs/ShooterGame.log`) — sem travar indefinidamente
- **Badge LAN / WAN** no header de cada servidor: 🏠 LAN ao iniciar, 🌐 WAN quando registrado no Steam
- **Uptime** em tempo real exibido no card do servidor

### Configuração de Servidores (NOVO)

- Aba **Geral**: nome, porta, query port, senha, máx. jogadores, diretório de instalação
- Aba **Jogo**: mapa, sessão, modo de jogo, dificuldade, PvP/PvE, configs de gameplay
- Aba **Avançado**: parâmetros customizados de linha de comando, flags extras
- Aba **Console RCON**: console interativo via RCON integrado
- Aba **Logs**: visualização em tempo real dos logs do servidor ARK

### Gerenciamento de Mods (NOVO)

- Aba **Mods** por servidor: adicionar/remover mods pelo ID do Workshop, instalar/atualizar via SteamCMD
- Mods instalados via SteamCMD são copiados automaticamente para `ShooterGame/Content/Mods/`
- Indicador de status por mod: ✅ instalado / ❌ não instalado
- Botões para abrir a página do mod no Steam Workshop
- **Atualização automática de mods**: verifica o Steam Workshop periodicamente, avisa jogadores via broadcast RCON, para o servidor, baixa a atualização e reinicia automaticamente

### Gerenciamento de Plugins (NOVO)

- Aba **Plugins** por servidor: gerenciamento de plugins ArkApi
- Instalar/remover plugins `.dll` e `.so`
- Detecta automaticamente se o ArkApi está instalado

### Sincronização de Cluster (MANTIDO E MELHORADO)

- Sincronização bidirecional de pastas de cluster ARK mantida
- Log de sincronização agora exibe o **nome, tamanho e direção** de cada arquivo copiado

### Sistema de Atualização do App (REESCRITO)

- Agente autônomo de atualização: ao clicar em "Instalar", um **processo separado** é lançado
- O agente aguarda o app fechar → baixa o instalador → instala silenciosamente → reinicia o ARKLAND automaticamente
- Não requer intervenção manual após confirmar

### Gerenciamento de Servidores (NOVO)

- **Multi-servidor**: suporte a múltiplos servidores ARK na mesma interface, cada um com painel independente
- **Iniciar / Parar / Reiniciar** servidores ARK Dedicated diretamente pelo app
- **Instalação e validação** do servidor via SteamCMD (`app_update 376030`) pela aba Geral
- **Ciclo de vida de status** completo: PARADO → INICIANDO → RODANDO → PARANDO → CRASHADO
- Status **INICIANDO → RODANDO** detectado via monitoramento do arquivo de log real do ARK (`ShooterGame/Saved/Logs/ShooterGame.log`) — sem travar indefinidamente
- **Badge LAN / WAN** no header de cada servidor: 🏠 LAN ao iniciar, 🌐 WAN quando registrado no Steam
- **Uptime** em tempo real exibido no card do servidor

### Configuração de Servidores (NOVO)

- Aba **Geral**: nome, porta, query port, senha, máx. jogadores, diretório de instalação
- Aba **Jogo**: mapa, sessão, modo de jogo, dificuldade, PvP/PvE, configs de gameplay
- Aba **Avançado**: parâmetros customizados de linha de comando, flags extras
- Aba **Console RCON**: console interativo via RCON integrado
- Aba **Logs**: visualização em tempo real dos logs do servidor ARK

### Gerenciamento de Mods (NOVO)

- Aba **Mods** por servidor: adicionar/remover mods pelo ID do Workshop, instalar/atualizar via SteamCMD
- Mods instalados via SteamCMD são copiados automaticamente para `ShooterGame/Content/Mods/`
- Indicador de status por mod: ✅ instalado / ❌ não instalado
- Botões para abrir a página do mod no Steam Workshop
- **Atualização automática de mods**: verifica o Steam Workshop periodicamente, avisa jogadores via broadcast RCON, para o servidor, baixa a atualização e reinicia automaticamente

### Gerenciamento de Plugins (NOVO)

- Aba **Plugins** por servidor: gerenciamento de plugins ArkApi
- Instalar/remover plugins `.dll` e `.so`
- Detecta automaticamente se o ArkApi está instalado

### Sincronização de Cluster (MANTIDO E MELHORADO)

- Sincronização bidirecional de pastas de cluster ARK mantida
- Log de sincronização agora exibe o **nome, tamanho e direção** de cada arquivo copiado

### Sistema de Atualização do App (REESCRITO)

- Agente autônomo de atualização: ao clicar em "Instalar", um **processo separado** é lançado
- O agente aguarda o app fechar → baixa o instalador → instala silenciosamente → reinicia o ARKLAND automaticamente
- Não requer intervenção manual após confirmar

### Importação e Sincronização de Configurações (NOVO)

- **Importar INI**: botão na aba Avançado permite importar todas as configurações diretamente dos arquivos GameUserSettings.ini e Game.ini do disco, preenchendo automaticamente todos os campos da interface.
- **Sincronizar INI entre servidores**: botão na aba Avançado abre diálogo para selecionar quais servidores receberão os arquivos INI do servidor atual (GameUserSettings.ini e/ou Game.ini). Permite sincronizar configurações avançadas entre múltiplos servidores com um clique.

---

## [1.0.9] — 2026-05-13

### Adicionado

- Token do agente gerado automaticamente (UUID) na primeira execução
- Botão **Copiar** e botão **Revogar** (gera novo UUID) na aba Remoto
- Botão **Colar meu token** no formulário de peer facilita a configuração

---

## [1.0.8] — 2026-05-13

### Alterado

- Porta padrão do agente remoto alterada de 19567 para 32440

---

## [1.0.7] — 2026-05-13

### Corrigido

- Atualização automática reescrita com PowerShell (era `.bat`)
- Corrige janela que abria e fechava instantaneamente sem instalar nada

---

## [1.0.6] — 2026-05-13

### Adicionado

- Aba Remoto exibe o IP local desta máquina e o endereço completo para configurar peers
- Campo Nome do peer agora é opcional (usa o IP como nome quando não preenchido)

---

## [1.0.5] — 2026-05-13

### Corrigido

- Compatibilidade: build migrado para Python 3.12
- Corrige erro `Failed to load Python DLL` em máquinas sem VC++ 2022 Runtime instalado

---

## [1.0.3] — 2026-05-13

### Adicionado

- Nova aba **Controle Remoto** — controle outra instância do app via rede
- Agente HTTP integrado: exponha esta máquina para controle externo (porta e token configuráveis)
- Cadastro de peers remotos com nome, IP, porta e token de autenticação
- Painel de peer com stats em tempo real, logs e botões Iniciar / Parar / Forçar Sync

---

## [1.0.2] — 2026-05-13

### Adicionado

- Erros separados por tipo com timestamp — card Erros no Dashboard agora abre janela de detalhes
- Botão "Ver detalhes" lista cada erro individualmente com hora, tipo e mensagem
- Botão "Limpar" zera o histórico de erros sem reiniciar a sincronização

---

## [1.0.1] — 2026-05-12

### Corrigido / Adicionado

- Imagem do instalador corrigida (sem distorção)
- URL de atualização embutida — não requer configuração manual
- Iniciar sincronização habilitado por padrão
- Nova opção: Iniciar o ARKLAND-Multi com o Windows
- Ícone da barra de tarefas corrigido

---

## [1.0.0] — 2026-05-12

### Adicionado

- Lançamento inicial do ARKLAND-Multi
- Sincronização bidirecional automática de pastas ARK Cluster
- Interface moderna com Dashboard, Configurações e Logs
- Controle de intervalo de sincronização (1–60 s)
- Inicialização automática e modo debug configuráveis
- Estatísticas em tempo real no Dashboard (arquivos, erros, último sync)
- Sistema de atualização automática integrado (verificação + download + instalação)
- Aba "Sobre" com histórico de versões e controle de update
- Notificação visual na sidebar quando há nova versão disponível
- Script de build (`build.bat`) com PyInstaller
- Script de instalador (`setup.iss`) para Inno Setup

---

<!-- Modelo para próximas versões:

## [X.Y.Z] — AAAA-MM-DD

### Adicionado
- ...

### Alterado
- ...

### Corrigido
- ...

### Removido
- ...
-->
