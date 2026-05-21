"""
Versão e changelog do ARKLAND - Server Manager.
Este arquivo é a única fonte de verdade para a versão do aplicativo.
"""

APP_VERSION: str = "1.3.18"
BUILD_DATE: str = "2026-05-20"

# Cada entrada: version, date, changes (lista de strings)
CHANGELOG: list[dict] = [
    {
        "version": "1.3.18",
        "date": "2026-05-20",
        "changes": [
            "Fix (CustomShop plugin \u2014 FC_ArkShopUI): kShopBuffPath corrigido para Blueprint'/Game/Mods/FC_ArkShopUI/ArkShopUI_Buff_FCAS.ArkShopUI_Buff_FCAS' \u2014 path antigo do KinyShop causava BPLoadClass retornar null silenciosamente, impedindo qualquer dado de chegar ao mod.",
            "Feat (CustomShop plugin \u2014 FC_ArkShopUI): novo comando GetConfig / SendConfig() \u2014 responde ao mod com ShopName, UiKey, flags (DisableSell, DisableTrade, HideBuffIcon, VoteRewards, UseSteamOverlay) e labels; sem isso a UI ficava com dados padr\u00e3o.",
            "Feat (CustomShop plugin \u2014 FC_ArkShopUI): novo stub SellItem \u2014 retorna Success=false graciosamente; sem handler o ARK logava erro de comando desconhecido.",
            "Fix (CustomShop plugin \u2014 FC_ArkShopUI): InitPlayer agora envia SendConfig antes de itens/pontos/kits \u2014 garante que a UI inicialize o layout antes de renderizar conte\u00fado.",
            "Fix (CustomShop plugin \u2014 FC_ArkShopUI): Shop.Reload (admin) agora reenvia config a todos os jogadores online.",
            "Feat (CustomShop plugin \u2014 config.json): novos campos em Settings: WebsiteUrl, DiscordUrl, VoteRewards, HideBuffIcon, OverrideCurrencyIcon, UseSteamOverlay, OverrideLabels.",
            "Fix (Atualiza\u00e7\u00e3o Autom\u00e1tica de Mods): broadcast agora enviado a servidores em estado 'starting' \u2014 antes s\u00f3 'running' era verificado, servidor era parado sem nenhum aviso.",
            "Fix (Atualiza\u00e7\u00e3o Autom\u00e1tica de Mods): timeout de espera por parada aumentado 90s\u219290s+buffer(180s) \u2014 _stop_worker pode levar ~110s (90s graceful + taskkill); servidor n\u00e3o reiniciava pois status ainda era 'stopping' ao checar.",
            "Fix (Atualiza\u00e7\u00e3o Autom\u00e1tica de Mods): restart agora aceita status 'stopped' ou 'crashed'; se ainda 'stopping' ap\u00f3s timeout, aguarda 30s extra antes de iniciar.",
            "Fix (Atualiza\u00e7\u00e3o Autom\u00e1tica de Mods): download concorrente \u2014 on_done(False) chamado imediatamente quando _active=True; antes o done_event nunca era sinalizado, causando timeout de 10min e falso 'Falha ao baixar' para o segundo mod.",
        ],
    },
    {
        "version": "1.3.17",
        "date": "2026-05-20",
        "changes": [
            "Fix (Updater): removido flag /T do taskkill em _kill_lingering — o updater era filho do app principal e se autodestruía ao tentar encerrar processos restantes; agora usa apenas taskkill por nome de executável.",
            "Fix (Updater): ctypes HANDLE com restype=c_void_p no OpenProcess/WaitForSingleObject — evita truncamento em sistemas 64-bit com handles de valor alto.",
            "Fix (CustomShop plugin): ShopPerms agora enumera todos os módulos carregados via Toolhelp32 para localizar o plugin Permissions — resolve incompatibilidade com 'Permissions V2' que carregava após o CustomShop.",
        ],
    },
    {
        "version": "1.3.16",
        "date": "2026-05-20",
        "changes": [
            "Perf (Plugin — Itens/Kits): substituída paginação com CTkScrollableFrame por Treeview nativo (ttk) + painel de edição único (master-detail) — navegação entre centenas de registros sem recriação de widgets.",
            "Perf (Plugin — Mods): lista de mods paginada com navegação Anterior/Próximo (20 por página), evitando renderizar todos os mods de uma vez.",
            "Fix (Updater): processo updater desvinculado do Job Object do Windows (CREATE_BREAKAWAY_FROM_JOB) — encerrar o app principal não interrompe mais o updater em execução.",
            "Feat (Plugin — Itens/Kits): novo tipo \"dino\" nos itens do CustomShop — suporta Blueprint, Level, Gender (Male/Female/Random) e Neutered; disponível tanto no editor de Itens quanto nos itens de Kit.",
            "Feat (Dashboard): servidor em estado TRAVADO (crashed) exibe botão '💀 Forçar Enc.' em vez de Iniciar/Parar — força o encerramento do processo via taskkill /F /T.",
            "Feat (Dashboard): barra de legenda com todos os 6 status possíveis de servidor (Parado, Iniciando, Online, Encerrando, Travado, Desconhecido) com cores e descrições.",
            "Feat (Desempenho): temperatura de CPU (via psutil/ACPI WMI) e GPU (via nvidia-smi) exibidas em cada card de recurso.",
            "Feat (Desempenho): nova seção '📡 Consumo por Servidor' — tabela em tempo real com CPU% e RAM de cada processo de servidor ARK em execução.",
        ],
    },
    {
        "version": "1.3.15",
        "date": "2026-05-20",
        "changes": [
            "Nova aba \u2018\ud83d\udd34 Crashes\u2019: exibe hist\u00f3rico completo de crashes do servidor lidos de ShooterGame/Saved/Crashes/, com diagn\u00f3stico interpretado (culpado, mensagem, call stack) e bot\u00f5es para abrir pasta ou apagar registros individualmente.",
            "Discord — mensagens redesenhadas: cada evento (iniciando, online, encerrando, encerrado, crash) agora usa description do embed como mensagem principal; campos Mapa e Porta como inline para starting/running; Uptime em stopped; diagn\u00f3stico do crash em bloco de c\u00f3digo para crashed; removido o campo \u2018Dica\u2019 gen\u00e9rico de todos os eventos.",
            "Discord — crash agora inclui diagn\u00f3stico real: server_manager armazena o resultado de _read_crash_info() na inst\u00e2ncia antes de disparar o evento, e o notificador inclui o trecho no embed.",
            "Novo indicador de status \u2018ASE Permissions\u2019 na aba Plugins: exibe se o plugin est\u00e1 instalado e oferece bot\u00e3o \u2018\u2b07 Instalar Permissions\u2019 que abre o link da p\u00e1gina oficial.",
        ],
    },
    {
        "version": "1.3.14",
        "date": "2026-05-21",
        "changes": [
            "Fix (plugin_manager — PluginInfo.json): Dependencies corrigido para [\"Permissions\"] — PluginManager.install() não sobrescreve mais a declaração de dependência.",
            "Fix (plugin_manager — config padrão): seção TimedPointsReward adicionada ao _DEFAULT_CONFIG — grupos de pontos por tempo aparecem na UI após instalação limpa.",
            "Fix (Editor de Kits — Permissões): campo Permissions não embaralha mais texto ao importar config com valor em formato string (ex: \"VIPOuro, Staff\").",
            "Fix (CustomShop — SendKits C++): payload Result agora usa Result.Data consistente com SendShopItems, corrigindo envio de kits ao mod MX-E.",
        ],
    },
    {
        "version": "1.3.13",
        "date": "2026-05-20",
        "changes": [
            "Fix (CustomShop — ShopPerms): aviso \"Permissions plugin not found\" ao iniciar corrigido — Perms::Init() movido de Plugin_Init para hook BeginPlay, quando todos os plugins j\u00e1 est\u00e3o carregados no processo; controle de kit e pontos por grupo agora funcionam.",
            "Fix (Plugins — Salvar config.json): di\u00e1logo de confirma\u00e7\u00e3o agora exibe o caminho completo do arquivo gravado.",
        ],
    },
    {
        "version": "1.3.12",
        "date": "2026-05-20",
        "changes": [
            "Fix (Plugins — Desinstalar/Reinstalar): erro Tcl \"wrong # args: trace remove variable\" ao reinstalar o CustomShop — CTkOptionMenu n\u00e3o usa mais StringVar interna via variable= (evita trace Tcl em destrui\u00e7\u00e3o dos widgets).",
        ],
    },
    {
        "version": "1.3.11",
        "date": "2026-05-19",
        "changes": [
            "Fix (CustomShop — Error 126): adicionado z.dll (zlib) ao bundle — libmariadb.dll depende de z.dll que n\u00e3o estava sendo copiado para Win64/ na instala\u00e7\u00e3o.",
            "Fix (Plugins — Importar — grupos): grupos do TimedPointsReward n\u00e3o eram importados do formato ArkShop — convertido de inteiro direto para {\"Amount\": N} ao fazer a convers\u00e3o.",
        ],
    },
    {
        "version": "1.3.10",
        "date": "2026-05-19",
        "changes": [
            "Novo (Plugins — Importar config.json): botão '📂 Importar' na aba Plugins permite carregar um config.json do ArkShop (legado) ou CustomShop e popular a UI automaticamente.",
            "Novo (Plugins — Importar config.json): detecção automática de formato — ArkShop (Mysql/General) é convertido para CustomShop antes de preencher os campos.",
            "Novo (Plugins — Importar config.json): conversão ArkShop → CustomShop mapeia Mysql → Database, General → Settings, Amount → Quantity nos kits e ShopItems → Items.",
        ],
    },
    {
        "version": "1.3.9",
        "date": "2026-05-22",
        "changes": [
            "Fix (CustomShop crash): substitu\u00eddo libmysql.dll (MySQL 8.0) por libmariadb.dll (MariaDB Connector/C 3.4.8) — elimina crash de inicializa\u00e7\u00e3o em servidores que usam MariaDB.",
            "Fix (CustomShop build): build_cl.bat atualizado para linkar contra libmariadb.lib em vez de libmysql.lib.",
        ],
    },
    {
        "version": "1.3.8",
        "date": "2026-05-19",
        "changes": [
            "Fix (CustomShop instala\u00e7\u00e3o): DLLs de depend\u00eancia (libmysql, libcrypto, libssl) agora instaladas em Win64/ em vez da pasta do plugin — corre\u00e7\u00e3o do Error 126 e crash ao carregar o plugin.",
        ],
    },
    {
        "version": "1.3.7",
        "date": "2026-05-19",
        "changes": [
            "Fix (CustomShop UI): corrigido erro Tcl 'wrong # args: should be trace remove variable' ao instalar o plugin — substituido trace_add manual por callback command= nativo do CTkOptionMenu.",
        ],
    },
    {
        "version": "1.3.6",
        "date": "2026-05-19",
        "changes": [
            "Novo (CustomShop UI): card de configuracao de banco de dados MySQL na aba Plugins — Host, Porta, Usuario, Senha e nome do Banco editaveis diretamente na interface.",
            "Novo (CustomShop UI): card Settings com 18 campos organizados em 4 secoes — Loja, Botoes, Criaturas/Cryo e Restricoes de uso.",
            "Novo (CustomShop UI): suporte a itens do tipo 'command' — campos Command, DisplayAs e ExecuteAsAdmin com alternancia automatica de layout ao mudar o tipo.",
            "Novo (CustomShop UI): card TimedPointsReward — Enabled, Interval, StackRewards e grupos dinamicos (nome + pontos) adicionados e removidos na interface.",
            "Novo (CustomShop UI): campo Permissions nos kits — lista de grupos separada por virgula; validada pelo Permissions.dll antes da compra.",
            "Fix (CustomShop UI): carregamento de abas totalmente lazy — eliminava travada de navegacao causada por pre-construcao de tabs em background.",
            "Novo (CustomShop): kits com restricao de permissao via Permissions.dll — campo 'Permissions' no kit valida grupos do jogador antes da compra.",
            "Novo (CustomShop): pontos por tempo (TimedPoints) — jogadores acumulam pontos automaticamente com suporte a grupos VIP e configuracao por grupo.",
            "Novo (CustomShop): spawn de dinos em kits — campo 'Dinos' no kit entrega dinossauros domesticados, com nivel, ForceTame e Neutered configuráveis.",
            "Novo (CustomShop): suporte a MySQL via libmysql.lib — build_cl.bat corrigido com MYSQL_DIR, headers e libpath.",
            "Novo (_migrate_arkshop.py): conversao de dinos do ArkShop para o formato CustomShop com Blueprint, Level, ForceTame e Neutered.",
        ],
    },
    {
        "version": "1.3.5",
        "date": "2026-05-19",
        "changes": [
            "Novo: Atualização de mod agora broadcast mensagem clara de reinicio com contagem regressiva (5/3/1 min) e aviso final ao desligar o servidor.",
            "Novo: SaveWorld enviado a todos os servidores antes de qualquer shutdown — mundo e perfis salvos antes de aplicar atualização de mod.",
            "Fix: _graceful_shutdown aguarda 15 s apos SaveWorld (era 2 s) para garantir que o save esteja completo antes do DoExit.",
            "Fix: discord_notifier — classe DiscordNotifier duplicada e bloco de codigo solto removidos.",
            "Fix: server_config — fields importado de dataclasses; type: ignore adicionado em asdict e __dataclass_fields__.",
            "Fix: plugin_manager — import MySQLError inutilizado removido; type: ignore em mysql.connector.",
            "Fix: dynamic_config_server — assinatura de log_message corrigida para compatibilidade com BaseHTTPRequestHandler.",
            "Fix: ark_ini — atribuição de optionxform suprimida com type: ignore[method-assign].",
            "Fix: beacon_client — import sys inutilizado removido.",
            "Fix: config.json do CustomShop — chave Database duplicada removida.",
        ],
    },
    {
        "version": "1.3.4",
        "date": "2026-05-18",
        "changes": [
            "Novo: Botão 'Diagnosticar Cluster' na aba Avançado — verifica cluster ID, pasta compartilhada (local e UNC/rede), sync, AltSaveDirectoryName, consistência entre servidores e permissões de download/upload.",
            "Fix: Janela CMD do SteamCMD não abre mais durante download de mods/servidores — processo roda em background com CREATE_NO_WINDOW.",
        ],
    },
    {
        "version": "1.3.3",
        "date": "2026-05-18",
        "changes": [
            "Fix: Aba Jogo — Stats por Nível agora carrega automaticamente os valores de PerLevelStatsMultiplier do Game.ini ao abrir a aba pela primeira vez, em vez de exibir sempre o padrão 1.0.",
        ],
    },
    {
        "version": "1.3.2",
        "date": "2026-05-18",
        "changes": [
            "Fix: Cluster — ClusterID agora passado como flag -clusterid= em vez de parâmetro de URL ?ClusterID=; o ARK ignora a forma ?URL e só reconhece a flag -.",
            "Fix: Cluster — ClusterDirOverride não usa mais aspas internas (-ClusterDirOverride=\"path\") que podiam falhar no parser do ARK/UE; caminhos com espaços agora recebem o argumento inteiro entre aspas.",
        ],
    },
    {
        "version": "1.3.1",
        "date": "2026-05-18",
        "changes": [
            "Fix: Protocolo RCON corrigido — pacote sentinel agora usa tipo EXECCOMMAND (2) em vez de RESPONSE_VALUE (0), que causava WinError 10053 (ARK fechava a conexão ao receber pacote inválido do cliente).",
            "Fix: Timeout RCON (SaveWorld, Broadcast e outros comandos sem resposta) não gera mais erro vermelho — tratado silenciosamente como '(sem resposta)'.",
            "Fix: Console RCON reconecta automaticamente antes de enviar um comando se a conexão estiver caída — sem necessidade de clicar em Conectar manualmente.",
        ],
    },
    {
        "version": "1.3.0",
        "date": "2026-05-18",
        "changes": [
            "Fix: Broadcasts agora funcionam sem o Console RCON aberto — conexão RCON temporária criada automaticamente ao enviar.",
            "Novo: Botão '🔧 Testar RCON' na aba Broadcasts para verificar conectividade e funcionamento do broadcast.",
            "Novo: Notificações Discord aprimoradas — embeds com campos estruturados, timestamp, footer e dicas contextuais por tipo de evento.",
            "Novo: Notificação Discord enviada automaticamente após atualização de mods (mod_auto_updater) e após cada backup concluído.",
            "Fix: Race condition em restart_server e _reconnect_monitor — acesso a _instances agora protegido por lock.",
            "Fix: Race condition (TOCTOU) em ModManager — verificação e set de _active agora atômicos com threading.Lock.",
            "Fix: Gravação de configurações agora é atômica (arquivo .tmp + rename) — evita corrupção em caso de crash durante o save.",
            "Fix: Script de atualização substituiu System.Net.WebClient (deprecated) por Invoke-WebRequest.",
            "Fix: race condition em _update_restart no agendador de servidores.",
            "Fix: Vazamento de memória no agendador — entradas antigas de _sched_fired/_sched_warned são limpas a cada ciclo.",
            "Fix: Token vazio no agente remoto não bypassa mais autenticação.",
            "Fix: BUFF manager usava ServerChat em vez de Broadcast.",
        ],
    },
    {
        "version": "1.2.9",
        "date": "2026-05-17",
        "changes": [
            "Fix: Botão 'Iniciar' no painel de Sincronização de Cluster agora salva o perfil automaticamente antes de iniciar, evitando perda dos campos não salvos (Pasta local, Intervalo).",
        ],
    },
    {
        "version": "1.2.8",
        "date": "2026-05-17",
        "changes": [
            "Fix: CrossARK — ClusterDirOverride agora normaliza barras para \\\\  no Windows, evitando falha silenciosa na gravação de personagens.",
            "Fix: ?AltSaveDirectoryName agora é sempre adicionado quando configurado, independente de ClusterID.",
            "Fix: -UseDynamicConfig não é mais duplicado quando presente em argumentos extras.",
            "Novo: Pasta do Cluster criada automaticamente ao salvar perfil de cluster (modo local).",
            "Novo: Card de Diagnóstico no painel Clusters — indica se ClusterID, pasta e vínculos estão corretos.",
            "Novo: Painel Clusters detecta servidores com cluster manual e oferece botão 'Importar como Perfil'.",
            "Novo: Criar novo perfil de cluster pré-preenche com valores de configuração manual existente.",
        ],
    },
    {
        "version": "1.2.7",
        "date": "2026-05-17",
        "changes": [
            "Novo: Integração BattleMetrics — campo 'BattleMetrics ID' na aba Geral de cada servidor. Quando configurado, exibe status online/offline e contagem de jogadores (👥 X/Y) no painel e no dashboard, consultando a API pública a cada 60 segundos.",
        ],
    },
    {
        "version": "1.2.6",
        "date": "2026-05-17",
        "changes": [
            "Fix: Botão 'Sobre' sumia da sidebar — separador e seção SERVIDORES sobrepunham os dois últimos itens de navegação (Configurações e Sobre) após adição de novos itens ao menu.",
        ],
    },
    {
        "version": "1.2.5",
        "date": "2026-05-17",
        "changes": [
            "Novo: Notificações Discord via Webhook — envia embeds coloridos para um canal Discord em eventos de servidor (iniciando, online, parado, crash, encerrando, atualização de mods, backup). Configurável por tipo de evento nas Configurações Globais.",
            "Novo: 6 novos parâmetros de inicialização de servidor — Crossplay (-crossplay), Apenas Epic (-epiconly), Vivox (-UseVivox), Anti-dupe de item (-UseItemDupeCheck), Sem animação de spawn (?PreventSpawnAnimations=True), Dano flutuante RPG (?ShowFloatingDamageText=True).",
            "Novo: Stats por Nível expandido — tabela PerLevelStatsMultiplier agora inclui colunas Dom. Bônus (TaM / _DinoTamed_Add) e Dom. Afinid. (TmM / _DinoTamed_Affinity), cobrindo todas as 5 variantes do ARK.",
        ],
    },
    {
        "version": "1.2.4",
        "date": "2026-05-17",
        "changes": [
            "Novo: Sistema de Clusters Cross-ARK — painel dedicado para criar e gerenciar perfis de cluster (modo Local ou Rede), substituindo a configuração manual por servidor.",
            "Novo: Sincronização automática de dados de viagem — cada perfil de cluster pode sincronizar bidirecional mente a pasta local do ARK com uma pasta compartilhada de rede (caminho UNC ou drive mapeado), mantendo personagens, itens e dinos atualizados entre máquinas diferentes.",
            "Novo: Vinculação de servidores ao cluster — seleção direta dos servidores que participam de cada cluster diretamente no painel do perfil.",
            "Fix: Verificador de atualização — removido BOM (Byte Order Mark) do version.json para evitar erro 'Não foi possível verificar' em certas configurações de sistema.",
        ],
    },
    {
        "version": "1.2.3",
        "date": "2026-05-17",
        "changes": [
            "Fix: GameUserSettings.ini — chaves preservam maiúsculas/minúsculas originais (ex: RCONEnabled não virava rconenabled), evitando crash de plugins ArkAPI como ArkShop.",
            "Fix: GameUserSettings.ini e Game.ini — encoding original do arquivo (UTF-16 LE, UTF-8 com BOM, etc.) é detectado e preservado ao salvar.",
        ],
    },
    {
        "version": "1.2.2",
        "date": "2026-05-17",
        "changes": [
            "Novo: Exportar/Importar Perfil — botões na sidebar permitem salvar todos os servidores em um arquivo .arkprofile e carregá-los em outra máquina.",
            "Melhoria: Stats por Nível — tabela com fundo alternado (zebra) para facilitar leitura das colunas distantes.",
        ],
    },
    {
        "version": "1.2.1",
        "date": "2026-05-17",
        "changes": [
            "Novo: Comandos em Itens da Loja — seção 'Comandos' adicionada ao detalhe de item da loja, igual aos Kits.",
            "Fix: Beacon — token salvo em %APPDATA% (Program Files é read-only sem admin; token nunca era persistido).",
            "Fix: Beacon — painel de autenticação reaparece automaticamente após erro de token.",
            "Fix: Beacon — mensagem de erro não referencia mais arquivo interno de desenvolvedor.",
        ],
    },
    {
        "version": "1.2.0",
        "date": "2026-05-17",
        "changes": [
            "Novo: Instância única — ao tentar abrir o app já em execução (mesmo na bandeja), "
            "a janela existente é restaurada automaticamente ao foco via mutex nomeado + EnumWindows.",
            "Novo: Integração com Beacon (usebeacon.app) — autenticação OAuth Device Flow (PKCE), "
            "cache local de blueprints ARK Prime (~1963 itens, TTL 7 dias).",
            "Novo: Blueprint Picker — diálogo de busca live com filtro por categoria "
            "(Todos / Itens / Criaturas) integrado ao ArkShop (itens de kit, dinos e selas).",
            "Novo: botão '📋 Inserir seção...' no dialog de INI do mod — permite inserir seções "
            "cadastradas no painel INI (Game.ini / GUS.ini) sem substituir o conteúdo existente.",
            "Melhoria: aba Jogo usa renderização em chunks (lotes de 6 via after(0)) — "
            "elimina freeze de ~500ms causado por 44 CTkSliders ao abrir a aba pela primeira vez.",
            "Melhoria: pre-build de abas em idle com intervalo de 1500ms (antes 120ms) e sem "
            "abas pesadas na fila — elimina freezes periódicos em background.",
            "Correção: múltiplos erros Pylance corrigidos (beacon_client, server_manager, "
            "arkland_updater, _profile_tabs, beacon_explore, beacon_sync).",
        ],
    },
    {
        "version": "1.1.23",
        "date": "2026-05-17",
        "changes": [
            "Novo: Agendamentos automáticos na aba Geral — reiniciar/desligar/atualizar+reiniciar "
            "por dia da semana e hora com aviso RCON configurável.",
            "Novo: Seletor de núcleos de CPU substituindo checkbox — Padrão / Todos / N núcleos "
            "com afinidade via psutil.",
            "Novo: Calculadora de Breeding — cards visuais, campo Cuddle (Imprint) com tempo "
            "desejado, botão Wiki.",
            "Correção: botão 'Aplicar ao Servidor' na Calculadora de Breeding agora salva o "
            ".ini mesmo com servidor online.",
            "Correção: campo de texto do multiplicador no Jogo atualiza ao aplicar valores da Calculadora.",
            "Melhoria: MOTD com área de texto maior (altura 180px).",
        ],
    },
    {
        "version": "1.1.22",
        "date": "2026-05-17",
        "changes": [
            "Novo: seletor de núcleos de CPU com afinidade via psutil.",
        ],
    },
    {
        "version": "1.1.19",
        "date": "2026-05-16",
        "changes": [
            "Novo: aba Spawns — editor visual de spawn de dinos customizados "
            "(ConfigAddNPCSpawnEntriesContainer / ConfigOverrideNPCSpawnEntriesContainer). "
            "Adicione ou substitua containers de spawn por mapa, com suporte a múltiplos entries "
            "e blueprint paths, leitura e escrita automática no Game.ini.",
        ],
    },
    {
        "version": "1.1.18",
        "date": "2026-05-16",
        "changes": [
            "Correção: importação de INI agora lê args de linha de comando do .bat de startup "
            "(BabyMatureSpeedMultiplier, EggHatchSpeedMultiplier, BabyCuddleIntervalMultiplier, etc.) "
            "que ferramentas como ARK Server Manager passam diretamente ao ShooterGameServer.exe "
            "em vez de gravar no INI.",
        ],
    },
    {
        "version": "1.1.17",
        "date": "2026-05-15",
        "changes": [
            "Correção: importação de INI do disco não carregava multiplicadores de breed, RCON e MOTD — "
            "o importador agora usa a mesma lógica completa do leitor interno, cobrindo todos os campos de GameUserSettings.ini e Game.ini.",
        ],
    },
    {
        "version": "1.1.16",
        "date": "2026-05-15",
        "changes": [
            "Correção: updater não conseguia sobrescrever ARKLAND-Updater.exe pois o arquivo estava em uso — "
            "o updater agora se renomeia antes de rodar o installer, liberando o arquivo.",
            "Correção: processos ARKLAND-ServerManager.exe podiam persistir após o kill — "
            "o updater agora verifica via tasklist e repete o taskkill até confirmar que todos morreram (até 10 tentativas).",
            "Novo: ao reiniciar após atualização, o app detecta servidores ARK já em execução e reconecta automaticamente.",
        ],
    },
    {
        "version": "1.1.15",
        "date": "2026-05-15",
        "changes": [
            "Correção crítica: updater ficava preso em 'Aguardando o ARKLAND fechar' quando a opção "
            "'minimizar para bandeja' estava ativa — o fluxo de atualização agora chama _do_quit() "
            "diretamente, ignorando a bandeja.",
            "Correção: ARKLAND-Updater.exe adicionou timeout de 20 s no WaitForSingleObject — "
            "após o timeout, processos restantes são encerrados à força via taskkill.",
            "Correção: AllowedCheaterSteamIDs.txt era gravado no caminho errado (Saved/Config/WindowsServer/) — "
            "corrigido para Binaries/Win64/, que é onde o ARK efetivamente lê o arquivo.",
            "Novo: campo de busca de configurações no painel de servidor — filtra por nome, dica e aba em tempo real.",
        ],
    },
    {
        "version": "1.1.14",
        "date": "2026-05-15",
        "changes": [
            "Novo: tooltip ? flutuante na seção Comandos do kit ArkShop — exibe variáveis disponíveis "
            "({steamid}, {playerid}, {playername}) e exemplos de comandos do plugin ao passar o mouse.",
            "Novo: campo ID do kit editável no painel de detalhe — renomeação com detecção de conflito.",
            "Novo: Cluster / Múltiplos Servidores — salva ArkShop.json em vários destinos simultâneos.",
            "Novo: presets nomeados para ArkShop — salvar, carregar e excluir configurações completas "
            "(persiste em %APPDATA%\\ARKLAND-ServerManager\\arkshop_presets.json).",
            "Melhoria: botão − minimiza para a bandeja do sistema (pystray) além do botão Fechar.",
            "Melhoria: fechar o app não encerra os processos do servidor ARK — mapas continuam rodando.",
            "Melhoria: navegação O(1) — troca de tela usa grid_remove seletivo em vez de ocultar todos os frames.",
            "Correção: alterações nos campos da UI não eram persistidas ao salvar o ArkShop.json "
            "— _arkshop_collect_fields() agora chamado antes de gravar no disco.",
        ],
    },
    {
        "version": "1.1.13",
        "date": "2026-05-15",
        "changes": [
            "Correção crítica: formato .mod completamente reescrito baseado no arkmanager/doExtractMod — "
            "mod.info começa com o nome do mod (não mapCount), e o .mod exige nome, caminho, "
            "magic footer e modmeta.info. Corrige crash 'BufferCount=0' definitivamente.",
        ],
    },
    {
        "version": "1.1.12",
        "date": "2026-05-15",
        "changes": [
            "Correção crítica: gera .mod binário correto (FUGCModImport) a partir de mod.info — "
            "copiar mod.info diretamente causava crash 'BufferCount=0' no ARK.",
            "Auto-reparo em check_mod_installed também usa o gerador binário correto.",
        ],
    },
    {
        "version": "1.1.11",
        "date": "2026-05-15",
        "changes": [
            "Correção crítica: SteamCMD não cria arquivo .mod externo — _find_dot_mod agora usa mod.info como fallback.",
            "Auto-reparo em check_mod_installed: se .mod ausente mas mod.info presente na pasta instalada, copia automaticamente.",
        ],
    },
    {
        "version": "1.1.10",
        "date": "2026-05-14",
        "changes": [
            "Correção crítica: mods não carregavam pois o arquivo .mod estava ausente — check_mod_installed agora exige pasta E arquivo .mod.",
            "Busca fallback pelo .mod dentro da pasta do mod ao copiar via SteamCMD.",
            "Aviso pré-start: alerta se algum mod configurado estiver sem o arquivo .mod.",
            "Novo campo Mensagem do Dia (MOTD) na aba Geral de cada servidor.",
            "MOTD e duração salvos automaticamente no GameUserSettings.ini ([MessageOfTheDay]).",
        ],
    },
    {
        "version": "1.1.9",
        "date": "2026-05-14",
        "changes": [
            "Novo botão Clonar Configurações na aba Avançado de cada servidor.",
            "Clona mapa, senhas, mods, multiplicadores, cluster, admins e backup para outros servidores.",
            "Preserva nome, diretório de instalação, session name e portas no servidor destino.",
        ],
    },
    {
        "version": "1.1.8",
        "date": "2026-05-14",
        "changes": [
            "Parar servidor agora encerra toda a árvore de processos via taskkill /F /T /PID.",
            "Corrige bug onde o app reportava 'Servidor parado' mas o processo continuava rodando.",
            "Nova aba Backup: backup automático em intervalos configuráveis (1h–24h).",
            "Escolha de quantos backups manter, conteúdo (Saves/Config) e pasta de destino.",
            "Botão de Backup Manual e lista de backups com opções de restaurar e excluir.",
        ],
    },
    {
        "version": "1.1.7",
        "date": "2026-05-14",
        "changes": [
            "Updater: encerra à força todos os processos ARKLAND-ServerManager.exe antes de instalar (evita falha por arquivo bloqueado no Windows).",
        ],
    },
    {
        "version": "1.1.6",
        "date": "2026-05-14",
        "changes": [
            "Aba Admins: busca automática do nome Steam ao digitar o ID (Steam Community XML, sem API key), exibido na lista.",
            "Nova aba Jogadores: lista jogadores online via RCON ListPlayers com ações Kick, Ban e adicionar como Admin.",
            "Jogadores: auto-refresh a cada 30 segundos via checkbox na aba.",
            "Sistema de BUFFs de Rates Temporários: nova aba ⚡ BUFFs no sidebar com agendamento, presets, backup/restore de INI e broadcast RCON.",
            "BUFFs: tipos XP, Doma, Breeding, Farm; multiplicadores rápidos 5x/10x/15x ou custom; máx. 30 dias.",
            "Mapa Aquatica adicionado à lista de mapas oficiais.",
        ],
    },
    {
        "version": "1.1.5",
        "date": "2026-05-14",
        "changes": [
            "Correção crítica: servidor não ficava mais preso em 'PARANDO' — shutdown RCON movido para thread, cascata terminate/kill/os.kill com timeouts.",
            "Botão ⚡ Cancelar no lugar de botão desabilitado durante INICIANDO/PARANDO, permite forçar parada imediata.",
            "Timeout de inicialização aumentado de 15 para 45 minutos para mapas pesados com muitos mods.",
            "Dashboard exibe badge LAN/WAN ao lado de cada servidor, atualizado em tempo real.",
            "Nova aba Admins: gerencia Steam IDs de administradores, grava AllowedCheaterSteamIDs.txt ao salvar.",
            "ModAutoUpdater: download do mod ocorre enquanto servidor ainda roda; cópia para Mods/ apenas após servidor parar (evita file locking no Windows).",
            "Novo ARKLAND-Updater.exe: substitui script PowerShell temporário para auto-atualização do app.",
            "Lista de mods com cores alternadas (zebra) para fácil identificação de linha.",
        ],
    },
    {
        "version": "1.1.4",
        "date": "2026-05-14",
        "changes": [
            "Nomes dos mods buscados automaticamente via Steam Workshop API ao abrir a aba Mods.",
            "Lista de mods exibe ID - Nome do mod para fácil identificação.",
            "Checkbox 'Atualizar servidor ao iniciar' agora executa SteamCMD antes de iniciar o servidor.",
            "Correção do build.bat: parênteses em echo dentro de bloco if aninhado causavam erro no CMD.",
        ],
    },
    {
        "version": "1.1.3",
        "date": "2026-05-14",
        "changes": [
            "Sincronização N-way multi-ciclo: até 5 ciclos independentes, cada um com até 5 pastas — propaga sempre a versão mais nova de cada arquivo para todas as pastas do ciclo.",
            "Auto-start do sync: ao abrir o app, o sync é iniciado automaticamente se houver ciclos configurados.",
            "Interface de Sincronização redesenhada: cards dinâmicos por ciclo com botões + Pasta e + Ciclo, remoção individual e renumeração automática.",
            "Correções de lint/tipo em todos os módulos (updater, ark_ini, mod_auto_updater, mod_manager, rcon_client, server_manager, server_config, remote_agent).",
        ],
    },
    {
        "version": "1.1.2",
        "date": "2026-05-14",
        "changes": [
            "Configurações INI por mod: cada mod pode ter blocos customizados para Game.ini e GameUserSettings.ini, aplicados automaticamente aos arquivos do servidor.",
            "Nome do mod salvo automaticamente ao adicionar via busca no Workshop.",
            "Importar INI do Disco agora permite selecionar qualquer pasta (backup, outro servidor, etc.) via seletor de arquivos.",
            "Bloqueio de edição: todas as configurações ficam desabilitadas enquanto o servidor estiver em execução ou iniciando — apenas com status PARADO é possível editar.",
            "Banner de aviso visível no painel do servidor quando as configurações estão bloqueadas.",
            "Correção: método _check_updates_manual ausente causava erro ao abrir a aba Sobre.",
            "Correção: definição duplicada de _check_updates_on_start removida.",
        ],
    },
    {
        "version": "1.1.1",
        "date": "2026-05-14",
        "changes": [
            "Importação de GameUserSettings.ini e Game.ini direto do disco, preenchendo todos os campos da interface.",
            "Sincronização de arquivos INI entre servidores selecionados (GameUserSettings.ini e/ou Game.ini) via diálogo na aba Avançado.",
            "Auto-updater de mods ativado por padrão e instala mods ausentes ao iniciar.",
        ],
    },
    {
        "version": "1.1.0",
        "date": "2026-05-14",
        "changes": [
            "Transformação completa: de ferramenta de sync para gerenciador de servidores ARK",
            "Multi-servidor: gerencie múltiplos servidores ARK na mesma interface",
            "Iniciar/Parar/Reiniciar servidores + instalação via SteamCMD",
            "Ciclo de vida de status: PARADO→INICIANDO→RODANDO via log do ARK",
            "Badge LAN/WAN no header: 🏠 LAN ao iniciar, 🌐 WAN ao registrar no Steam",
            "Abas por servidor: Geral, Jogo, Avançado, Mods, Plugins, Console RCON, Logs",
            "Gerenciamento de mods: instalar/atualizar via SteamCMD, status por mod",
            "Atualização automática de mods: broadcast RCON + para/baixa/reinicia",
            "Fix: mods copiados para ShooterGame/Content/Mods/ após download",
            "Log de sync com nome, tamanho e direção de cada arquivo copiado",
            "Agente autônomo de atualização do app: baixa, instala e reinicia sozinho",
        ],
    },
    {
        "version": "1.0.9",
        "date": "2026-05-13",
        "changes": [
            "Token do agente gerado automaticamente (UUID) na primeira execução",
            "Botão Copiar token e botão Revogar (gera novo UUID) na aba Remoto",
            "Botão 'Colar meu token' no formulário de peer facilita configuração",
        ],
    },
    {
        "version": "1.0.8",
        "date": "2026-05-13",
        "changes": [
            "Porta padrão do agente remoto alterada de 19567 para 32440",
        ],
    },
    {
        "version": "1.0.7",
        "date": "2026-05-13",
        "changes": [
            "Correção: atualização automática reescrita com PowerShell (era .bat)",
            "Corrige janela que abria e fechava instantâneamente sem instalar",
        ],
    },
    {
        "version": "1.0.6",
        "date": "2026-05-13",
        "changes": [
            "Aba Remoto exibe o IP local desta máquina e o endereço completo para peers",
            "Campo Nome do peer agora é opcional (usa o IP como fallback)",
        ],
    },
    {
        "version": "1.0.5",
        "date": "2026-05-13",
        "changes": [
            "Correção de compatibilidade: build migrado para Python 3.12",
            "Corrige erro 'Failed to load Python DLL' em máquinas sem VC++ 2022 Runtime",
        ],
    },
    {
        "version": "1.0.4",
        "date": "2026-05-13",
        "changes": [
            "Correção: atualização automática aguarda o app fechar antes de instalar",
            "Script intermediário evita erro de arquivo em uso durante a instalação",
        ],
    },
    {
        "version": "1.0.3",
        "date": "2026-05-13",
        "changes": [
            "Nova aba Controle Remoto — controle outra instância do app via rede",
            "Agente HTTP integrado: exponha esta máquina para controle externo",
            "Cadastro de peers remotos com IP, porta e token de autenticação",
            "Painel de peer com stats em tempo real, logs e botões Iniciar/Parar/Forçar Sync",
        ],
    },
    {
        "version": "1.0.2",
        "date": "2026-05-13",
        "changes": [
            "Erros separados por tipo com timestamp — card Erros agora abre detalhes",
            "Botão 'Ver detalhes' no Dashboard lista cada erro individualmente",
            "Botão 'Limpar' zera histórico de erros sem reiniciar a sincronização",
        ],
    },
    {
        "version": "1.0.1",
        "date": "2026-05-12",
        "changes": [
            "Imagem do instalador corrigida (sem distorção)",
            "URL de atualização embutida — não requer configuração manual",
            "Iniciar sincronização habilitado por padrão",
            "Nova opção: Iniciar o ARKLAND - Server Manager com o Windows",
            "Ícone da barra de tarefas corrigido",
        ],
    },
    {
        "version": "1.0.0",
        "date": "2026-05-12",
        "changes": [
            "Lançamento inicial do ARKLAND - Server Manager",
            "Sincronização bidirecional automática de pastas ARK Cluster",
            "Interface moderna com Dashboard, Configurações e Logs",
            "Controle de intervalo de sincronização (1–60 s)",
            "Inicialização automática e modo debug configuráveis",
            "Estatísticas em tempo real no Dashboard (arquivos, erros, último sync)",
            "Sistema de atualização automática integrado",
        ],
    },
]
