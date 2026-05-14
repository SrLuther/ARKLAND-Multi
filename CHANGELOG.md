# Changelog — ARKLAND Server Manager

Todas as mudanças notáveis deste projeto serão documentadas aqui.  
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

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
