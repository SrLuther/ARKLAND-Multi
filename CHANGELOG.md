# Changelog — ARKLAND Server Manager

Todas as mudanças notáveis deste projeto serão documentadas aqui.  
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [1.3.10] — 2026-05-19

### Adicionado

- **Plugins — botão "📂 Importar"**: permite carregar um `config.json` externo (formato ArkShop legado ou CustomShop) diretamente na aba Plugins para popular toda a UI sem precisar editar o arquivo manualmente.
- **Plugins — detecção automática de formato**: arquivos com chave `Mysql` ou `General` são reconhecidos como formato ArkShop e convertidos automaticamente antes de preencher os campos.
- **Plugins — conversão ArkShop → CustomShop**: `Mysql.*` → `Database`, `General.*` → `Settings`, `Amount` → `Quantity` nos itens de kits, `ShopItems` → `Items` (itens simples).

---

## [1.3.9] — 2026-05-22

### Corrigido

- **CustomShop — crash ao inicializar**: substituído `libmysql.dll` (MySQL 8.0) por `libmariadb.dll` (MariaDB Connector/C 3.4.8) — elimina o crash de inicialização em servidores que usam MariaDB.
- **CustomShop — build**: `build_cl.bat` atualizado para linkar contra `libmariadb.lib` em vez de `libmysql.lib`; removidas dependências de `libcrypto` e `libssl` (não necessárias no MariaDB Connector/C).

---

## [1.3.8] — 2026-05-19

### Corrigido

- **CustomShop — plugin DLL**: recompilado com `/MD` (CRT dinâmico) para eliminar o crash causado por mismatch de heap entre `CustomShop.dll` e `libmysql.dll`.
- **CustomShop — instalação**: DLLs de dependência (`libmysql.dll`, `libcrypto-3-x64.dll`, `libssl-3-x64.dll`) agora instaladas diretamente em `Win64/` em vez da pasta do plugin — corrige o Error 126 e o crash ao carregar o plugin.

---

## [1.3.7] — 2026-05-19

### Corrigido

- **CustomShop — instalação**: corrigido erro Tcl `wrong # args: should be "trace remove variable name oplist command"` que aparecia ao clicar "📦 Instalar" — substituído `trace_add` manual pelo callback `command=` nativo do `CTkOptionMenu`.

---

## [1.3.6] — 2026-05-19

### Novo

- **CustomShop — Card Database (MySQL)**: Host, Porta, Usuário, Senha e nome do Banco configuráveis diretamente na aba Plugins. Requer `libmysql.dll` na mesma pasta do `CustomShop.dll`.
- **CustomShop — Card Settings**: 18 campos organizados em 4 seções — Loja (nome, tecla, pontos iniciais, itens por página, tempo de exibição, tamanho de texto, kit padrão, caminho DB), Botões (SellItems, Trading, OriginalTrading), Criaturas/Cryo (DinoCryo, SoulTraps, CryoLimited, NoNoglin) e Restrições de uso (inconsciente, algemado, carregado).
- **CustomShop — Itens "command"**: tipo `command` com campos Command, DisplayAs e ExecuteAsAdmin; layout alterna automaticamente ao mudar o tipo do item.
- **CustomShop — Card TimedPointsReward**: Enabled, Interval, StackRewards e grupos dinâmicos (nome + pontos) gerenciados direto na UI.
- **CustomShop — Permissions nos kits**: campo livre para lista de grupos (separados por vírgula); validado pelo Permissions.dll antes da compra.
- **CustomShop — build**: suporte a MySQL via `libmysql.lib`; `build_cl.bat` corrigido com `MYSQL_DIR`, headers e libpath.
- **CustomShop — Dinos nos kits**: campo `Dinos` entrega dinossauros domesticados com Level, ForceTame e Neutered configuráveis.
- **`_migrate_arkshop.py`**: conversão de dinos do ArkShop para o formato CustomShop com Blueprint, Level, ForceTame e Neutered.

### Correção

- **Navegação de abas**: carregamento totalmente lazy — eliminada travada causada por pré-construção de tabs em background.

---

## [1.3.5] — 2026-05-19

### Novo

- **Broadcast de reinício por atualização de mod**: mensagem inicial clara informando o tempo restante, contagem regressiva automática (5 min → 3 min → 1 min dependendo da janela configurada) e aviso final antes do shutdown.
- **SaveWorld antes de qualquer shutdown**: `_save_servers()` enviado a todos os servidores antes de parar para atualização de mod; mundo e perfis salvos antes do processo ser encerrado.

### Correção

- **`_graceful_shutdown`**: sleep entre `SaveWorld` e `DoExit` aumentado de 2 s para 15 s — garante que o save esteja completo antes do servidor encerrar.
- **`discord_notifier`**: classe `DiscordNotifier` duplicada e bloco de código solto (corpo de `_post_webhook` duplicado dentro da classe) removidos.
- **`server_config`**: `fields` adicionado ao import de `dataclasses`; `# type: ignore` em `asdict` e `__dataclass_fields__` (falsos positivos do Pylance).
- **`plugin_manager`**: import `MySQLError` inutilizado removido; `# type: ignore` em `mysql.connector`.
- **`dynamic_config_server`**: assinatura de `log_message` corrigida para `(self, format, *args)` — compatível com `BaseHTTPRequestHandler`.
- **`ark_ini`**: `# type: ignore[method-assign]` em todas as atribuições `optionxform = str`.
- **`beacon_client`**: import `sys` inutilizado removido.
- **`configs/config.json` (CustomShop)**: chave `"Database"` duplicada removida.

---

## [1.3.4] — 2026-05-18

### Novo

- **Diagnóstico de Cluster** (aba Avançado): botão "🔍 Diagnosticar Cluster" abre um dialog com verificação completa da configuração de cross-ARK — cluster habilitado, ID, pasta compartilhada (local ou UNC/rede), sync, `AltSaveDirectoryName`, consistência com outros servidores do cluster e permissões de download/upload.

### Correção

- **Janela CMD do SteamCMD**: a janela preta do `steamcmd.exe` não abre mais visível durante download de mods ou atualização de servidor — o processo agora roda em background com `CREATE_NO_WINDOW`.

---

## [1.3.3] — 2026-05-18

### Correção

- **Stats por Nível (aba Jogo)**: ao abrir a aba pela primeira vez, os valores de `PerLevelStatsMultiplier` eram exibidos como `1` (padrão do JSON) em vez dos valores reais do `Game.ini`. Corrigido com auto-carregamento do `Game.ini` ao construir a aba.

---

## [1.3.2] — 2026-05-18

### Correção

- **Cluster — ClusterID como flag**: o parâmetro de cluster era passado como `?ClusterID=xxx` (URL option da engine), que o ARK ignora silenciosamente. Corrigido para `-clusterid=xxx` (flag de linha de comando), que é a forma reconhecida pelo servidor.
- **Cluster — ClusterDirOverride sem aspas internas**: o argumento era gerado como `-ClusterDirOverride="path"`, forma que pode falhar no parser do ARK/Unreal Engine. Agora gerado como `-ClusterDirOverride=path` (sem aspas para caminhos simples) ou `"-ClusterDirOverride=path com espaços"` (argumento inteiro entre aspas quando necessário).

---

## [1.3.1] — 2026-05-18

### Correção

- **Protocolo RCON — WinError 10053**: o pacote sentinel enviado após cada comando usava tipo `0` (RESPONSE_VALUE), que é exclusivo do servidor→cliente. O ARK fechava a conexão ao receber esse pacote inválido do cliente. Corrigido para tipo `2` (EXECCOMMAND).
- **Timeout RCON silencioso**: comandos sem resposta do ARK (como `SaveWorld`, `Broadcast`, `DoExit`) causavam erro vermelho "timed out" no console. Agora `socket.timeout` é tratado como resposta vazia e exibe "(sem resposta)" normalmente.
- **Reconexão automática ao enviar comando**: o Console RCON agora reconecta automaticamente antes de enviar um comando se a conexão estiver caída — sem precisar clicar em "Conectar" manualmente. O status e o botão são atualizados em caso de reconexão silenciosa.

---

## [1.3.0] — 2026-05-18

### Correção

- **Broadcasts sem Console RCON aberto**: broadcasts da biblioteca e envio rápido agora criam uma conexão RCON temporária automaticamente — não é mais necessário abrir o Console RCON antes de enviar.
- **Race condition em `restart_server` e `_reconnect_monitor`**: acessos ao dicionário `_instances` e mutações de `inst.process`/`inst.pid` agora protegidos por lock.
- **Race condition (TOCTOU) em `ModManager`**: verificação e atribuição do flag `_active` agora são atômicas com `threading.Lock`, impedindo dois downloads simultâneos.
- **Gravação atômica de configurações**: `save()`, `save_servers()` e `save_clusters()` agora gravam em arquivo `.tmp` e fazem rename atômico — evita corrupção em caso de crash durante o save.
- **Script de atualização**: substituído `System.Net.WebClient` (deprecated no .NET 6+) por `Invoke-WebRequest` no script PowerShell do updater.
- **Race condition no agendador** (`_update_restart`): acesso a `_instances` protegido por lock.
- **Vazamento de memória no agendador**: entradas antigas de `_sched_fired` e `_sched_warned` limpas a cada ciclo diário.
- **Autenticação do agente remoto**: token vazio não bypassa mais a verificação de autenticação.
- **BUFF Manager**: mensagens de aviso agora usam `Broadcast` (destaque na tela) em vez de `ServerChat` (chat simples).

### Novo

- **Botão "🔧 Testar RCON"** na aba Broadcasts: verifica conectividade RCON e envia mensagem de teste, com feedback de sucesso ou erro detalhado.
- **Notificações Discord aprimoradas**: embeds com campos estruturados, timestamp ISO 8601, footer "ARKLAND Server Manager" e dicas contextuais por tipo de evento (iniciando, online, parado, crash, encerrando).
- **Notificação Discord automática após atualização de mods**: enviada pelo atualizador automático com nome do mod e servidores reiniciados.
- **Notificação Discord automática após backup**: enviada com nome do snapshot e tamanho em MB.

---

## [1.2.8] — 2026-05-17

### Correção

- **CrossARK — ClusterDirOverride com barras erradas**: o caminho da pasta do cluster agora é normalizado automaticamente para `\` no Windows, evitando falha silenciosa na gravação de personagens durante viagem entre mapas.
- **`?AltSaveDirectoryName` independente do cluster**: o parâmetro agora é sempre adicionado quando configurado, independentemente de ClusterID estar ativo.
- **`-UseDynamicConfig` duplicado**: a flag não aparece mais duas vezes quando presente em argumentos extras.

### Novo

- **Pasta do Cluster criada automaticamente**: ao salvar um perfil de cluster (modo local), a pasta é criada no disco se não existir — com notificação toast de confirmação.
- **Diagnóstico no painel Clusters**: novo card exibe status em tempo real — ClusterID configurado, pasta existente, servidores vinculados — com alertas visuais para itens ausentes.
- **Migração de cluster manual para perfil**: quando há servidores com CrossARK configurado manualmente sem perfil, o painel Clusters exibe um aviso com botão "Importar como Perfil" que centraliza a configuração e vincula todos os servidores automaticamente.
- **Novo Cluster pré-preenchido**: ao criar um novo perfil, o ClusterID e a pasta são pré-preenchidos com os valores de servidores que já têm configuração manual.

---

## [1.2.7] — 2026-05-17

### Novo

- **Integração BattleMetrics**: campo "BattleMetrics ID" adicionado na aba Geral de cada servidor (seção Rede e Portas). Quando configurado, o app consulta a API pública do BattleMetrics a cada 60 segundos e exibe o status online/offline e a contagem de jogadores (`👥 X/Y`) no cabeçalho do painel do servidor e no card do dashboard.

---

## [1.2.6] — 2026-05-17

### Correção

- **Botão "Sobre" sumia da sidebar**: separador e seção SERVIDORES estavam sobrepostos sobre os dois últimos itens de navegação (Configurações e Sobre) após adição de novos itens ao menu. Corrigido ajustando as linhas do grid para acomodar todos os 8 botões de navegação.

---

## [1.2.5] — 2026-05-17

### Novo

- **Notificações Discord via Webhook**: seção dedicada nas Configurações Globais para enviar embeds coloridos ao Discord em eventos de servidor (iniciando, online, parado, crash, encerrando). Configurável por tipo de evento (start, stop, crash, atualização de mod, backup). Sem dependências externas — usa `urllib` da stdlib.

- **Novos parâmetros de inicialização de servidor**: checkboxes adicionados na aba Geral de cada servidor: **Crossplay** (`-crossplay`), **Apenas Epic** (`-epiconly`), **Vivox** (`-UseVivox`), **Anti-dupe de item** (`-UseItemDupeCheck`), **Sem animação de spawn** (`?PreventSpawnAnimations=True`), **Dano flutuante RPG** (`?ShowFloatingDamageText=True`).

- **Stats por Nível — colunas TaM e TmM**: tabela de `PerLevelStatsMultiplier` expandida com as colunas **Dom. Bônus (TaM)** (`_DinoTamed_Add`) e **Dom. Afinid. (TmM)** (`_DinoTamed_Affinity`), cobrindo todas as cinco variantes do ARK (IdM, TaM, TmM, IwM, PlM).

---

## [1.2.4] — 2026-05-17

### Novo

- **Sistema de Clusters Cross-ARK**: painel dedicado para criar e gerenciar perfis de cluster (modo **Local** — mesma máquina/mesmo app, ou **Rede** — máquinas diferentes via pasta UNC/drive mapeado), substituindo a configuração manual por servidor. Servidores são vinculados ao perfil diretamente no painel do cluster.

- **Sincronização automática de dados de viagem**: cada perfil de cluster pode sincronizar bidirecional mente a pasta local do ARK (`ShooterGame/Saved/clusters`) com a pasta compartilhada de rede, mantendo personagens, itens e dinos atualizados entre máquinas diferentes. Controles de start/stop e sync manual por perfil; engines de sync iniciam automaticamente com o app.

### Correção

- **Verificador de atualização**: removido BOM (*Byte Order Mark*) do `version.json` gerado pelo `_release.ps1` — o `[System.Text.Encoding]::UTF8` do .NET inclui BOM, fazendo o parser falhar com "Não foi possível verificar". Corrigido com `New-Object System.Text.UTF8Encoding $false`.

---

## [1.2.3] — 2026-05-17

### Correção

- **`GameUserSettings.ini` — case de chaves preservado**: chaves como `RCONEnabled` não eram mais normalizadas para minúsculas (`rconenabled`), evitando crash de plugins ArkAPI como ArkShop que exigem grafia exata.

- **`GameUserSettings.ini` e `Game.ini` — encoding preservado**: o encoding original do arquivo (UTF-16 LE, UTF-8 com BOM, etc.) é detectado na leitura e mantido ao salvar.

---

## [1.2.2] — 2026-05-17

### Novo

- **Exportar/Importar Perfil**: botões na sidebar permitem salvar todos os servidores em um arquivo `.arkprofile` e carregá-los em outra máquina.

### Melhorado

- **Stats por Nível**: tabela com fundo alternado (zebra) para facilitar a leitura das colunas distantes.

---

## [1.2.1] — 2026-05-17

### Novo

- **ArkShop — Comandos em Itens da Loja**: seção **Comandos** adicionada ao painel de detalhe de item da loja, com o mesmo funcionamento já existente nos Kits — botão `+ Comando`, campo de texto para o comando e checkbox **Admin** (`ExecuteAsAdmin`). Os comandos são salvos no JSON sob a chave `Commands` e removidos automaticamente quando a lista está vazia.

### Correção

- **Beacon — Token salvo em `%APPDATA%`**: `_token_path()` agora sempre grava em `%APPDATA%\ARKLAND-ServerManager\beacon_token.json`, independente de rodar como executável compilado ou em desenvolvimento. Anteriormente, em modo PyInstaller (frozen), o token era salvo ao lado do `.exe` em `C:\Program Files\` — pasta somente-leitura sem privilégio de administrador — causando falha silenciosa no `_save_token` (bloco `except: pass`). Resultado: o usuário completava o login, mas o token nunca era persistido, e a autenticação precisava ser refeita a cada sessão.

- **Beacon — Painel de autenticação reaparece após erro de token**: ao carregar blueprints via `_do_load`, se o token estiver ausente ou expirado, o botão **🔑 Reconectar com Beacon** reaparece automaticamente no rodapé do diálogo — sem precisar fechar e reabrir. Anteriormente o botão só aparecia na abertura inicial (bloco `else:`), deixando o usuário sem forma de reautenticar após uma falha mid-session.

- **Beacon — Mensagem de erro intuitiva**: a exceção em `fetch_all` não referencia mais `beacon_sync.py` (arquivo exclusivo de desenvolvimento). Nova mensagem: *"Clique em 'Conectar com Beacon' para autenticar novamente."*

---

## [1.2.0] — 2026-05-17

### Novo

- **Instância Única — Guard de duplo lançamento**: ao tentar abrir o app enquanto ele já estiver rodando (incluindo recolhido na bandeja do sistema), a segunda instância **restaura automaticamente a janela existente** para o foco (equivalente a clicar no ícone da bandeja) e encerra silenciosamente. Implementado via mutex nomeado do Windows (`CreateMutexW`) + `EnumWindows` para localizar a janela pelo título — funciona mesmo com `withdraw()` ativo. Fallback: se a janela não for encontrada, exibe aviso informando que o app já está em execução.

- **Integração com Beacon (usebeacon.app)**: novo módulo `src/beacon_client.py` — cliente completo para a API pública do Beacon, repositório autoritativo de blueprints ARK derivados do DevKit. Recursos:
  - **Autenticação OAuth Device Flow com PKCE**: sem armazenar segredos no código. O app inicia o fluxo, exibe o código de dispositivo e a URL, abre o navegador automaticamente e aguarda a confirmação em background. Token persistido localmente com renovação automática.
  - **Cache local de blueprints**: ~1963 itens ARK Prime baixados em até 8 páginas paginadas, salvos em `%APPDATA%\ARKLAND-ServerManager\beacon_blueprints_cache.json` com TTL de 7 dias — evita requisições repetidas entre sessões.
  - **Singleton `get_beacon_client()`**: instância única compartilhada entre todos os pontos de uso na sessão.

- **Blueprint Picker — ArkShop**: botão 🔍 adicionado em todos os campos `Blueprint'...'` do ArkShop. Ao clicar, abre diálogo de busca com:
  - Filtro de categoria via radio buttons: **Todos** / **Itens** (por engramId) / **Criaturas** (por creatureId)
  - Campo de busca live por nome ou `classString` (case-insensitive, limite de 150 resultados)
  - Lista com zebra striping, badge de tipo (🦕 criaturas · 🎒 engrams · 📦 itens), nome em negrito e `classString` em cinza
  - Clique em qualquer item preenche automaticamente o campo com `Blueprint'<path>'`
  - Integrado em: **Itens de Kit** (campo Blueprint), **Dinos de Kit** (Blueprint do dino + SaddleBlueprint), **Itens da Loja** (campo Blueprint)
  - Fluxo de autenticação inline: se ainda não autenticado, exibe botão "🔑 Conectar com Beacon", código de dispositivo copiável e status em tempo real — sem sair do diálogo

- **INI do Mod — Botão "📋 Inserir seção..."**: cada cabeçalho de arquivo INI no diálogo de configuração de mod (`Game.ini` e `GameUserSettings.ini`) ganhou um botão **📋 Inserir seção...**. Ao clicar, abre um painel lateral com todas as seções cadastradas no painel INI principal do servidor, exibidas como checkboxes com badge indicando a origem (`game` / `gus`). Selecione uma ou mais seções e clique em **✅ Inserir selecionadas** — o conteúdo é **acrescentado** ao final da caixa de texto, sem substituir o que já foi digitado.

### Melhorado

- **Aba Jogo — Renderização em Chunks**: a aba Jogo possuía 44 `CTkSlider` (cada um cria um Canvas internamente), causando freeze perceptível de ~500 ms na primeira abertura. A renderização foi refatorada para **lotes de 6 linhas** despachados via `after(0)` — o controle retorna ao event loop entre cada batch, eliminando completamente o freeze. A lógica de configuração dos widgets permanece idêntica; apenas o momento de criação foi diferido.

- **Pre-build de Abas em Idle — Intervalo Ampliado**: o mecanismo `_idle_build` faz pre-build silencioso das abas pesadas em background. O intervalo entre builds consecutivos passou de **120 ms para 1500 ms**, e as abas **Jogo**, **Spawns** e **Loot** foram removidas da fila de pre-build automático — evitava micro-freezes periódicos causados pelos 44 sliders sendo criados em background. A aba Jogo agora é construída em chunks quando o usuário de fato a abre.

### Correção

- **Pylance — `_requests` e `_psutil` Optional**: módulos opcionais tipados como `ModuleType | None` causavam erros `Cannot access attribute` após guards booleanos. Corrigido com `assert module is not None` logo após cada guard em `src/server_manager.py` (`_psutil` em `reconnect_existing`, `_reconnect_monitor`, `_start_worker`) e `beacon_client.py` (`_requests` em `authenticate_async._worker` e `fetch_all`).

- **Pylance — `headers: dict[str, str | bytes]`**: tipo inferido `dict[str, str]` era incompatível com `MutableMapping[str, str | bytes]` esperado por `requests.get`. Corrigido com anotação explícita nos arquivos: `beacon_client.py`, `beacon_explore.py`, `beacon_explore2.py`, `beacon_sync.py`.

- **Pylance — `arkland_updater.py` / fallback `tkinter as ctk`**: import de fallback `import tkinter as ctk` era interpretado pelo Pylance como módulo `tkinter`, gerando dezenas de erros em atributos `CTk*`. Reestruturado para `if TYPE_CHECKING: import customtkinter as ctk / else: try/except`.

- **Pylance — `_profile_tabs.py`**: nome de classe incorreto (`App` em vez de `ARKServerManagerApp`) e assinatura errada do construtor `ServerManager(cm, None)` corrigidos.

---

## [1.1.23] — 2026-05-17

### Novo

- **Agendamentos Automáticos de Servidor**: nova seção "⏰ Agendamentos Automáticos" na aba Geral de cada servidor. Permite criar múltiplas tarefas agendadas com:
  - Horário de execução (formato HH:MM)
  - Ação: **Reiniciar**, **Desligar** ou **Atualizar + Reiniciar**
  - Dias da semana selecionáveis individualmente (Seg a Dom)
  - Aviso antecipado via RCON Broadcast: 0, 5, 10, 15, 30 ou 60 minutos antes
  - Ativar/desativar cada tarefa individualmente sem removê-la
  - Thread dedicada (`ARKTaskScheduler`) verificando a cada 30 s; fogo único por tarefa por dia (não repete na mesma data)
  - Tarefas salvas em `scheduled_tasks` no perfil do servidor (JSON)

- **Seletor de Núcleos de CPU**: o checkbox "Usar todos os núcleos de CPU" foi substituído por um `OptionMenu` com três modos:
  - **Padrão (ARK decide)** — sem flag adicional
  - **Todos os núcleos** — adiciona `-useallavailablecores` ao launch
  - **N núcleos (1 … máx. detectado)** — aplica afinidade de processo via `psutil.cpu_affinity()` logo após o `Popen`, limitando o processo do servidor aos primeiros N núcleos lógicos

- **Calculadora de Breeding — campo Cuddle (Imprint)**: o painel de cálculo agora inclui o multiplicador `BabyCuddleIntervalMultiplier`. Campo "🤗 Cuddle (Imprint)" com entrada de tempo desejado (hh:mm:ss), resultado em `×N` e nota informativa *"Valor global — igual para todos os dinos, por isso não aparece na tabela abaixo"*.

- **Calculadora de Breeding — botão Wiki**: botão "📋 Tabela base (Wiki)" que abre diretamente a página de Breeding da ARK Wiki (`ark.wiki.gg/wiki/Breeding#Incubation`) no navegador padrão.

### Melhorado

- **Calculadora de Breeding — visual em cards**: cada coluna de cálculo (Maturação, Incubação, Cooldown Acas., Cuddle) agora exibe fundo escuro `#0e1018` com borda sutil `#1e2840`, separando visualmente os campos e facilitando a leitura.

- **Calculadora de Breeding — renomeações**: coluna da tabela e campo de cálculo "Acasalamento" renomeados para **"Cooldown Acas."**; hint text ajustado para "Cooldown desejado (hh:mm:ss)".

- **MOTD — área de texto maior**: o campo de Mensagem do Dia (MOTD) na aba Geral passou de `height=100` para `height=180` px, exibindo mais linhas sem scroll.

### Correção

- **Calculadora de Breeding — "Aplicar ao Servidor" sem efeito**: ao clicar em "Aplicar ao Servidor" com o servidor online, `_save_server_config` retornava imediatamente pelo bloqueio de servidor em execução, sem gravar o `GameUserSettings.ini`. Corrigido com parâmetro `force=True` que pula a verificação de status — a gravação ocorre normalmente (as alterações entram em vigor no próximo reinício do servidor).

- **Calculadora de Breeding — campo de multiplicador não atualizava**: após clicar em "Aplicar", o slider da aba Jogo se movia para o novo valor mas o campo de texto exibia o valor anterior. Corrigido adicionando `var.trace_add("write", ...)` em cada `frow`, mantendo `entry_var` sincronizado quando a `DoubleVar` é alterada programaticamente.

---

## [1.1.22] — 2026-05-16

### Melhorado

- **Diagnóstico de Crash Aprimorado**: ao detectar encerramento inesperado de servidor (crash), o ARKLAND-Multi agora lê automaticamente os arquivos de crash gerados pelo ARK (`ShooterGame/Saved/Crashes/<timestamp>/CrashContext.runtime-xml`, `.dmp`) e o tail do `ShooterGame.log` para identificar o DLL/plugin responsável pelo crash. O call stack e a mensagem de erro são exibidos diretamente no painel de log do servidor com destaque, facilitando o diagnóstico sem necessidade de abrir arquivos manualmente. O módulo/plugin culpado (ex.: `ArkShopUI.dll`) é identificado ignorando DLLs do engine (kernel32, ntdll, ShooterGameServer, etc.).

---

## [1.1.20] — 2026-05-27

### Novo

- **Aba Spawns — Multiplicadores por Classe de Dino**: quatro novas seções na aba "Spawns" para configurar `DinoClassResistanceMultipliers`, `DinoClassDamageMultipliers`, `TamedDinoClassResistanceMultipliers` e `TamedDinoClassDamageMultipliers`. Interface tabular com classe e multiplicador por linha, suporte a leitura/escrita automática do `Game.ini`.
- **Aba Loot — Editor Visual de Supply Crates**: nova aba "Loot" para configurar `ConfigOverrideSupplyCrateItems`. Editor hierárquico de 3 níveis (Crate → Item Set → Item Entry) com todos os campos relevantes: quantidade, qualidade, blueprint chance, classe dos itens.
- **Correção crítica**: restaurada a declaração `class ArkIniManager` que havia sido removida acidentalmente na v1.1.19, causando falha silenciosa no gerenciamento de INIs.

---

## [1.1.19] — 2026-05-16

### Novo

- **Aba Spawns — Editor Visual de Spawn de Dinos Customizados**: nova aba "Spawns" no painel de configuração de cada servidor. Permite adicionar (`ConfigAddNPCSpawnEntriesContainer`) e substituir (`ConfigOverrideNPCSpawnEntriesContainer`) containers de spawn de dinos sem editar o `Game.ini` manualmente. Recursos:
  - Dropdown com os containers de spawn conhecidos de todos os mapas oficiais (Island, Scorched Earth, Aberration, Extinction, Ragnarok, Valguero, Crystal Isles, Genesis 1 e 2).
  - Múltiplos entries por container, cada um com nome, peso e blueprint paths (um por linha).
  - Para containers de substituição: campo `MaxDesiredNumEnemiesMultiplier`.
  - Leitura automática de linhas existentes ao importar/carregar `Game.ini`.
  - Escrita correta de chaves duplicadas no `Game.ini` (configparser não suporta nativo).

---

## [1.1.18] — 2026-05-16

### Correção

- **Importar INI: multiplicadores de breed via linha de comando** (fix issue #1): ferramentas como ARK Server Manager passam alguns multiplicadores (`BabyMatureSpeedMultiplier`, `EggHatchSpeedMultiplier`, `BabyCuddleIntervalMultiplier`, etc.) como args `?Key=Value` na linha de chamada do ShooterGameServer.exe, em vez de gravá-los no INI. O importador agora localiza automaticamente o `.bat`/`.cmd` de startup na pasta selecionada ou em até 4 pastas-pai, extrai esses args e os aplica sobre o ServerConfig com a mesma precedência que o ARK usa em runtime.

---

## [1.1.17] — 2026-05-15

### Correção

- **Importação de INI do disco incompleta**: ao usar "Importar INI do Disco", multiplicadores de breed (`BabyMatureSpeedMultiplier`, `MatingIntervalMultiplier`, `EggHatchSpeedMultiplier`, etc.), RCON e Mensagem do Dia não eram carregados — ficavam em valores vanilla. Corrigido: o importador agora delega para as mesmas funções internas usadas pelo leitor de INI normal, cobrindo todos os campos de `GameUserSettings.ini` e `Game.ini`.

---

## [1.1.16] — 2026-05-15

### Novo

- **Reconexão automática de servidores**: ao reiniciar após uma atualização, o app detecta servidores ARK (`ShooterGameServer.exe`) já em execução e os reconecta automaticamente, mantendo status, uptime e controle sem precisar reiniciar o servidor.

### Correção

- **Updater — arquivo em uso**: `ARKLAND-Updater.exe` ficava bloqueado durante a instalação (o próprio updater estava rodando). Corrigido: o updater agora se renomeia para `.old.exe` antes de acionar o installer, liberando o arquivo para ser sobrescrito.
- **Updater — processos persistentes**: processos `ARKLAND-ServerManager.exe` podiam continuar no Gerenciador de Tarefas mesmo após o `taskkill`. O updater agora verifica via `tasklist` se os processos realmente morreram e repete o kill até confirmar (até 10 tentativas / 10 s).

---

## [1.1.15] — 2026-05-15

### Novo

- **Busca de configurações**: barra de busca no painel de servidor que filtra todas as opções por nome, dica e aba em tempo real — clique no resultado para navegar diretamente à aba correta.

### Correção

- **Updater preso** em "Aguardando o ARKLAND fechar": quando a opção *minimizar para bandeja* estava ativa, o app ia para a bandeja em vez de fechar — o fluxo de atualização agora chama `_do_quit()` diretamente, bypassando a bandeja.
- **ARKLAND-Updater.exe**: `WaitForSingleObject` trocado de `INFINITE` para timeout de 20 s — após expirar, processos restantes são encerrados à força via `taskkill`.
- **Admins**: `AllowedCheaterSteamIDs.txt` era gravado em `Saved/Config/WindowsServer/` — corrigido para `Binaries/Win64/`, onde o ARK realmente lê o arquivo.

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
