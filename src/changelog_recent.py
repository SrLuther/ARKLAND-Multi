"""Changelog recente do ARKLAND (versões recentes)."""
from typing import List

CHANGELOG_RECENT: List[dict] = [
    {
        "version": "1.6.1",
        "date": "2026-06-08",
        "changes": [
            "Fix (ASM/launch): SessionName removido permanentemente da CLI — conforme documentação "
            "v1.5.5+ do ARK_SERVER_CONFIG_REFERENCE.md. O nome do servidor fica SOMENTE no "
            "GameUserSettings.ini ([SessionSettings]/SessionName). O código anterior readicionava "
            "SessionName na CLI quando não continha espaços (v1.5.13), mas isso era inconsistente "
            "com a documentação e o comportamento do ASM original em C#.",
            "Fix (ASM/INI): DifficultyOffset agora gravado condicionalmente — só é válido quando "
            "enable_difficulty_override=True (linha 61 do INI_MAP).",
        ],
    },
    {
        "version": "1.6.0",
        "date": "2026-06-06",
        "changes": [
            "Novo (Crash Monitor): aba 'Crashes' por servidor com cards em tempo real — "
            "timestamp, tipo (crash/falha de início), call stack, botão 'Marcar visto'. "
            "Dados persistidos em data/crashes.json entre sessões.",
            "Novo (Crash Monitor): página global 'Crashes' no menu lateral mostra todos os "
            "servidores em um só lugar, com filtro por servidor e contagem de não vistos.",
            "Novo (Crash Monitor): badge [N] ao lado de 'Crashes' na sidebar atualiza em "
            "tempo real via callback quando qualquer servidor crasha.",
            "Melhoria (Navegação): trocar de página não reconstrói mais os frames — "
            "uso de grid_remove/grid em vez de destroy/recreate. Navegação instantânea.",
            "Melhoria (Painel): seções de configuração abertas sob demanda (lazy loading) "
            "— startup mais rápido, menos uso de memória em repouso.",
            "Fix: _try_psutil() no gráfico de performance retornava sempre True em vez de "
            "_PSUTIL_OK — métricas de CPU/RAM podiam falhar silenciosamente sem psutil.",
            "Fix: watermark de background usava PIL.Image diretamente em vez do alias "
            "_PILImage, causando NameError em builds sem PIL no namespace global.",
        ],
    },
    {
        "version": "1.5.13",
        "date": "2026-06-02",
        "changes": [
            "Fix (ASM/launch): removido check de processo pré-existente do _start_worker. "
            "Antes: ao clicar Iniciar, se o servidor já estivesse rodando (iniciado manualmente "
            "ou por outra ferramenta), o app reutilizava o processo sem reiniciar — o GUS.ini "
            "recém-escrito nunca era relido pelo servidor, resultando em nome 'ARK #902606' "
            "ao invés do nome configurado. Agora o Start sempre lança um novo processo.",
            "Fix (ASM/launch): SessionName também incluído na travel URL da CLI quando não "
            "contém espaços (?SessionName=Nome), além do GUS.ini — garante dupla cobertura "
            "para nomes sem espaço.",
        ],
    },
    {
        "version": "1.5.12",
        "date": "2026-06-01",
        "changes": [
            "Fix (ASM/ini): INI escrito com 'key=value' sem espaços ao redor do '=' — "
            "formato nativo do ARK. Antes: 'key = value' (configparser padrão).",
        ],
    },
    {
        "version": "1.5.11",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM/painel): Iniciar e Restart agora sincronizam silenciosamente os campos da UI "
            "(install_dir, session_name, portas, etc.) para o cfg antes de iniciar — sem dialog, "
            "sem salvar no JSON. Resolve: nome errado no servidor ('ARK #200440'), "
            "servidor não listando, validação falhando por install_dir vazio.",
        ],
    },
    {
        "version": "1.5.10",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM/painel): botões Iniciar e Restart não salvam mais automaticamente. "
            "Salvar é ação exclusiva do botão Salvar.",
        ],
    },
    {
        "version": "1.5.9",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM/launch): cluster ID agora gerado como flag '-clusterid=ID' em vez de URL param '?ClusterId=ID'. "
            "O ARK ignora '?ClusterId=' completamente — confirmado pelo servidor saudável de referência e pelo primitivo (src/server_config.py).",
            "Fix (ASM/launch): 'cluster_dir_override' agora incluído no comando como '-ClusterDirOverride=PATH'. "
            "O campo existia no dataclass mas não era usado no build_launch_args.",
            "Fix (ASM/launch): removido '?PreventDownloadItems=False' da CLI — parâmetro não existe no ARK e não consta em nenhuma referência válida.",
        ],
    },
    {
        "version": "1.5.8",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM/launch): parâmetros de mapa (MAP?Port=?QueryPort=...) não devem ser envolvidos em aspas. "
            "O parser de command line do Unreal Engine (ARK) lê o token raw e incluía as aspas literalmente, "
            "fazendo com que ?Port=, ?QueryPort=, ?AltSaveDirectoryName= e outros parâmetros fossem ignorados. "
            "Como SessionName foi removido da CLI (v1.5.5) não há mais espaços no map string.",
            "Fix (ASM/launch): adicionado /min ao comando start do RunServer.cmd — janela do servidor inicia minimizada, "
            "igual ao comportamento do servidor saudável de referência.",
        ],
    },
    {
        "version": "1.5.7",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): parâmetro AltSaveDir corrigido para AltSaveDirectoryName — ARK ignorava silenciosamente o parâmetro errado, resultando no mapa de saves padrão em vez da pasta configurada.",
            "Fix (ASM/INI): arquivos GameUserSettings.ini e Game.ini agora são gravados em UTF-16 LE (exigido pelo ARK no Windows). Gravação em UTF-8 causava leitura incorreta de algumas chaves como SessionName.",
            "Fix (ASM/INI): leitura dos arquivos INI agora tenta UTF-16, UTF-8 BOM, UTF-8 e latin-1 em ordem — compatível com arquivos criados pelo ARK, pelo ARKLAND e por editores externos.",
        ],
    },
    {
        "version": "1.5.6",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): campo IP Bind (MultiHome) não é mais preenchido automaticamente ao abrir o painel — o campo fica vazio por padrão (ARK escuta em todas as interfaces). O botão 'Detectar IP' continua disponível para uso manual quando necessário.",
            "Fix (ASM/INI): StructureDamageRepairCooldown movido para GameUserSettings.ini [ServerSettings] (estava incorretamente em Game.ini).",
            "Fix (ASM/INI): RandomSupplyCratePoints corrigido para bRandomSupplyCratePoints (prefixo 'b' obrigatório).",
        ],
    },
    {
        "version": "1.5.5",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): corrigida causa raiz do servidor não iniciar — SessionName com espaços (ex: '[ARKLAND] Teste Server') quebrava o parsing do cmd.exe pois o mapa+opções não estava entre aspas. Agora o combined_map é gerado corretamente entre aspas conforme documentação oficial do ARK.",
            "Fix (ASM): removido SessionName da linha de comando (já está no GameUserSettings.ini). Colocar duplicado causava conflito.",
        ],
    },
    {
        "version": "1.5.4",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): campo IP Bind (MultiHome) agora é verdadeiramente opcional — removido da validação obrigatória. O servidor inicia normalmente sem IP preenchido (ARK escuta em todas as interfaces por padrão).",
            "Fix (ASM): removido asterisco e placeholder enganoso do campo IP Bind.",
        ],
    },
    {
        "version": "1.5.3",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): MultiHome (IP Bind) removido do mapa de INI — não deve ser escrito no GameUserSettings.ini. O valor continua sendo passado apenas como argumento de linha de comando (?MultiHome=IP), que é o comportamento correto do ARK.",
        ],
    },
    {
        "version": "1.5.2",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): deteccao de IP para MultiHome corrigida — agora usa o IP da interface de rede local (socket) em vez do IP externo/publico. MultiHome precisa do IP local (ex: 192.168.x.x) para o servidor fazer bind corretamente; usar o IP publico do roteador causava crash instantaneo.",
            "Fix (ASM): mensagem de validacao e placeholder atualizados para orientar o IP correto (IP local, nao IP externo).",
        ],
    },
    {
        "version": "1.5.1",
        "date": "2026-05-31",
        "changes": [
            "Feat (ASM): deteccao automatica de IP publico no campo IP Bind (MultiHome) — botao Detectar IP consulta ipify/checkip/icanhazip e preenche o campo automaticamente.",
            "Feat (ASM): se o campo IP Bind estiver vazio ao abrir o painel do servidor, a deteccao e disparada automaticamente.",
        ],
    },
    {
        "version": "1.5.0",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): validacao de configuracao obrigatoria antes de iniciar servidor — bloqueia start se install_dir, session_name, admin_password ou IP Bind (MultiHome) estiverem vazios.",
            "Fix (ASM): campo IP Bind (MultiHome) marcado como obrigatorio (*) com placeholder de ajuda na UI.",
        ],
    },
    {
        "version": "1.4.9",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): lancamento do servidor agora usa RunServer.cmd + ShellExecute identico ao modo PRIMITIVE — remove __COMPAT_LAYER antes do startfile para evitar crash no CheckOnTimerCallbacks (ArkShopUI/ArkApi).",
            "Fix (ASM): stop agora usa taskkill /F /T para encerrar toda a arvore de processos (incluindo filhos criados pelo cmd.exe start).",
        ],
    },
    {
        "version": "1.4.8",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): SessionName agora incluido nos argumentos de inicializacao do servidor — nome aparece corretamente na lista de servidores.",
            "Fix (ASM): parametro AltSaveDir corrigido (era AltSaveDirectoryName).",
        ],
    },
    {
        "version": "1.4.7",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): salvar configuracoes no painel agora escreve imediatamente os arquivos GameUserSettings.ini e Game.ini do servidor.",
        ],
    },
    {
        "version": "1.4.6",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM): inicializacao do servidor abre janela CMD visivel com saida do processo.",
        ],
    },
    {
        "version": "1.4.5",
        "date": "2026-05-31",
        "changes": [
            "Novo (UI): marca d'agua do logo ARKLAND exibida em todas as paginas do app.",
            "Novo (ASM - Toolbar): botao Log adicionado na toolbar de ferramentas de cada servidor — exibe ShooterGame.log com auto-refresh, colorização e seguir fim.",
        ],
    },
    {
        "version": "1.4.4",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM - SteamCMD): instalacao do servidor agora respeita o caminho definido; argumentos passados como tokens separados ao Popen (fix force_install_dir ignorado).",
        ],
    },
    {
        "version": "1.4.3",
        "date": "2026-05-31",
        "changes": [
            "Fix (UI - Modo Claro): corrigidas cores hardcoded escuras no card de servidor, dashboard, badges de status, chips, toolbar, botoes de acao, icones dos stats, cabecalhos de grupo e bulk actions.",
            "Fix (ASM - Mods): _copy_mod_to_server agora trata subpasta WindowsNoEditor/ e cria o arquivo .mod exigido pelo ARK.",
            "Fix (ASM - Mods): download_mods reporta apenas os mods copiados com sucesso.",
            "Novo (ASM - Painel): status de instalacao de cada mod exibido em tempo real.",
            "Novo (app): sync e agente remoto iniciados automaticamente ao abrir o app se configurados.",
        ],
    },

    {
        "version": "1.4.2",
        "date": "2026-05-31",
        "changes": [
            "Fix (ASM — SteamCMD): caminho do steamcmd.exe configurado em Configura\u00e7\u00f5es agora \u00e9 lido corretamente em Redownload Mods, Baixar Mods, Instalar Servidor, Validar e Workshop.",
            "Fix (sidebar \u2014 servidores): servidor adicionado pelo di\u00e1logo + n\u00e3o aparecia na lista lateral; corrigido para todos os 3 modos de importa\u00e7\u00e3o.",
            "Novo (UI): modo claro (Light Mode) — bot\u00e3o \u2600 Claro / \U0001f319 Escuro na sidebar, prefer\u00eancia persistida em ui_prefs.json.",
        ],
    },
    {
        "version": "1.4.1",
        "date": "2026-05-31",
        "changes": [
            "Novo (ASM TEK — Mods): gerenciador de mods com tabela de 3 colunas — ID editável, nome e data de atualização preenchidos automaticamente via Steam Workshop API (POST GetPublishedFileDetails). Botões: '+ Mod', 'Buscar Info' (async thread), 'Redownload Mods' (SteamCMD) e 'Validar IDs' (marca IDs inválidos com ❌). Cache por sessão evita consultas redundantes.",
            "Fix (sidebar — logo): imagem ark_manager.png exibida com proporção correta 3:2 (66×44 px) em vez de quadrado distorcido (44×44).",
            "Novo (UI): watermark de fundo — logo ark_manager.png exibida em 600×400 px na área principal com 6% de opacidade, preservada atrás de todo conteúdo de navegação.",
        ],
    },
    {
        "version": "1.4.0",
        "date": "2026-05-31",
        "changes": [
            "Novo (ASM TEK): Dashboard agrupado por pastas de servidores com headers de grupo e botão 'Iniciar Todos'.",
            "Novo (ASM TEK): Barra de ações em lote — Selecionar Todos, Iniciar, Parar, Reiniciar e Atualizar Mods para múltiplos servidores.",
            "Novo (ASM TEK): Sistema de Presets de configuração — salva/aplica/remove presets por categoria (players, dinos, breeding, environment, structures, rules).",
            "Novo (ASM TEK): Exportar/importar perfil de servidor (.arkprofile) e clonar servidor.",
            "Novo (ASM TEK): Tribe Log Viewer — visualizador com tail em tempo real, filtros por tipo de evento e exportação.",
            "Novo (ASM TEK): Importar servidor a partir de instalação existente (lê GameUserSettings.ini/Game.ini/RunServer.bat) ou de arquivo .arkprofile.",
            "Novo (ASM TEK): Editor visual de Engramas — tabela interativa para OverrideNamedEngramEntries com geração automática de Game.ini.",
            "Novo (ASM TEK): Gráfico de curva XP + preview de linhas geradas na seção de Progressões de Nível.",
            "Novo (ASM TEK): Editor visual de Spawner — árvore de containers NPCSpawn com gerenciamento de entradas e serialização Game.ini.",
            "Novo (ASM TEK): Motor de backup em nuvem — suporte a armazenamento local e Amazon S3 com credenciais protegidas.",
            "Novo (ASM TEK): Assistente IA contextual — heurísticas offline + integração opcional com OpenAI GPT-4o-mini.",
            "Novo (ASM TEK): Monitor avançado — gráficos históricos 24h de CPU%, RAM e players + alertas configuráveis com notificação Discord e reinício automático.",
        ],
    },
    {
        "version": "1.3.57",
        "date": "2026-05-27",
        "changes": [
            "Fix (src/pages/tab_advanced.py): campo 'Nome da Pasta de Saves' (AltSaveDirectoryName) "
            "ficava desabilitado quando um perfil de cluster estava vinculado ao servidor — "
            "agora sempre editável, independente do perfil de cluster selecionado.",
        ],
    },
    {
        "version": "1.3.56",
        "date": "2026-05-27",
        "changes": [
            "Fix (src/server_config.py + src/asm_engine/asm_server_config.py): valor padrão de "
            "AltSaveDirectoryName alterado para 'savegame' — campo vazio ou em branco é normalizado "
            "automaticamente para 'savegame' via __post_init__, evitando que servidores iniciem "
            "sem diretório de save definido.",
        ],
    },
    {
        "version": "1.3.55",
        "date": "2026-05-27",
        "changes": [
            "Feature (pages/tab_chat.py + broadcast_sched_*.py): sistema de broadcasts automáticos "
            "por intervalo — nova inner-tab '🕐 Automáticos' na aba Chat/Broadcasts. Cada broadcast "
            "automático tem rótulo, mensagem, intervalo em minutos, ativar/desativar, envio imediato "
            "e exibição do próximo envio. Loop de tick a cada 30 s garante entregas pontuais sem "
            "bloquear a UI. Dados salvos em auto_broadcasts por servidor.",
            "Fix (pages/tab_rcon.py + rcon_connect.py): campos editáveis de Host e Porta removidos "
            "do console RCON — host e porta agora são lidos diretamente de srv.server_ip e "
            "srv.rcon_port, eliminando redundância e possibilidade de divergência.",
            "Feature (mod_changelog_scraper.py + discord_notifier.py + mod_auto_updater.py): "
            "notas de atualização de mods enviadas ao Discord. Ao detectar update, o ARKLAND "
            "faz scraping do Steam Workshop e inclui as release notes no embed. Suporte a "
            "webhook separado para mods (mod_changelog_webhook) em Configurações Globais — "
            "se vazio, usa o webhook principal.",
            "Fix (pages/tab_game.py): crash ao abrir aba de jogo — tk.Frame(bg='transparent') "
            "substituído por ctk.CTkFrame(fg_color='transparent'). O tkinter nativo não aceita "
            "'transparent' como cor de fundo.",
        ],
    },
    {
        "version": "1.3.52",
        "date": "2026-05-26",
        "changes": [
            "Feature (remote_agent.py + pages/): Pareamento LAN — ao clicar em 'Conectar' em "
            "uma máquina descoberta na rede local, o ARKLAND envia uma solicitação de autorização "
            "para a outra máquina em vez de pedir o token manualmente. Na máquina alvo, um dialog "
            "'Solicitação de Acesso' aparece com botões ✅ Autorizar / ❌ Negar (auto-nega após "
            "60 s). Na máquina solicitante, um dialog de espera faz polling a cada 2 s; ao ser "
            "autorizado, a conexão é salva e o controle remoto abre automaticamente. Entrada de "
            "token mantida apenas para conexões não-LAN (via código de identidade).",
        ],
    },
    {
        "version": "1.3.50",
        "date": "2026-05-26",
        "changes": [
            "Fix crítico (sync_engine.py): token de autenticação do agente remoto agora é sempre "
            "buscado em tempo real de config.remote_instances (pelo host+porta), em vez de usar "
            "o token congelado dentro do BASE64 do caminho. Resolve 'Não autorizado' persistente "
            "mesmo após regenerar o token — sem precisar recriar as pastas nos ciclos.",
            "Fix (sync_engine.py): se a listagem de qualquer pasta do ciclo falhar (ex: 401, "
            "timeout), o ciclo inteiro é abortado imediatamente. Antes, a pasta remota era "
            "tratada como vazia e o engine tentava copiar todos os arquivos locais para lá, "
            "gerando flood de erros 'Cópia X: Não autorizado' e WinError 10053/10054.",
            "Fix (pages/add_sync_folder.py): novas pastas remotas agora usam formato "
            "'@remote:HOST:PORT|path' em vez de '@remote|BASE64|path' — elimina o token do "
            "caminho salvo. Pastas antigas no formato legado continuam funcionando normalmente.",
            "Feature (pages/refresh_remote_instances_list.py): botão '✏️' em cada máquina "
            "remota salva permite atualizar o token sem remover e re-adicionar a conexão.",
            "Fix (pages/welcome_screen.py + app.py): modo TEK removido da tela inicial e "
            "bloqueado no backend (_launch_mode).",
            "Fix crítico (ark_ini.py): seções do Game.ini com nomes em case diferente "
            "(ex: '[/script/shootergame.shootergamemode]' vs '[/Script/ShooterGame.ShooterGameMode]') "
            "eram tratadas como seções distintas pelo configparser, causando duplicação de seção "
            "ao salvar e leitura de valores padrão ao carregar (configs apareciam 'desmarcadas' "
            "após reiniciar). Nova função _normalize_section_case() unifica a seção para o nome "
            "canônico antes de leitura e escrita — elimina a duplicação e restaura os valores "
            "corretamente.",
        ],
    },
    {
        "version": "1.3.49",
        "date": "2026-05-26",
        "changes": [
            "Fix (remote_agent.py): fs_list agora propaga erros HTTP (401, 500 etc.) em vez de "
            "retornar lista vazia silenciosamente. Antes, um 401 fazia o sync enxergar a pasta "
            "remota como vazia e tentar copiar tudo, resultando em flood de erros 'Não autorizado'.",
            "Fix (pages/start_remote_agent.py): token do agente é gerado automaticamente "
            "(secrets.token_urlsafe) se estiver vazio ao ativar o agente. Evita que o agente "
            "rejeite todas as requisições por falta de token.",
            "Feature (pages/add_sync_cycle.py + sync_engine.py): filtro 'Apenas nomes numéricos' "
            "por ciclo de sync. Quando marcado, somente arquivos com nome puramente numérico "
            "(ex: Steam IDs de cluster ARK) são sincronizados. Config salva como dict com "
            "campo 'numeric_only'; formato legado (lista de paths) mantido compatível.",
            "Fix (pages/tab_plugins.py): removido 'Plugin Limit Fix' do catálogo de sugestões "
            "— é um plugin para ARK: Survival Ascended (ASA), não compatível com ASE/ArkApi.",
            "Refactor (pages/start_remote_agent.py + remote_panel.py): token encurtado de UUID "
            "(36 chars) para secrets.token_urlsafe(12) (16 chars). Tokens existentes "
            "continuam funcionando sem necessidade de regeneração.",
        ],
    },
    {
        "version": "1.3.48",
        "date": "2026-05-26",
        "changes": [
            "Feature (sync_engine.py + remote_agent.py): sincronização remota de pastas entre "
            "máquinas na mesma rede. Endpoints GET /fs/list, GET /fs/read e POST /fs/write "
            "adicionados ao RemoteAgent; SyncEngine refatorado com abstrações _LocalSyncFolder "
            "e _RemoteSyncFolder. Caminhos remotos usam prefixo @remote|IDENTITY_CODE|PATH.",
            "Feature (remote_agent.py): descoberta automática de instâncias ARKLAND na rede "
            "local via UDP broadcast (porta 32441). Classe UdpDiscovery anuncia nome/IP/porta "
            "a cada 30 s e mantém lista de peers com TTL de 90 s. Token não é transmitido.",
            "Feature (pages/remote_panel.py): seção 'Descoberta na Rede (LAN)' na aba Acesso "
            "Remoto. Lista instâncias detectadas automaticamente; botão Conectar pede apenas "
            "o token (sem copiar código base64). Atualização automática a cada 6 s.",
            "Feature (pages/add_sync_folder.py): botão de pasta remota (\u1f310) em cada linha "
            "de ciclo de sync. Diálogo seleciona instância remota salva + caminho na máquina "
            "remota. Entry exibe o caminho em modo readonly quando remota.",
            "Fix (pages/ini_paste_section.py): 'Colar Seção' não importava "
            "parse_ini_text_to_sections — NameError silencioso impedia a importação de "
            "qualquer conteúdo. Corrigido o import; placeholder atualizado para mostrar "
            "exemplo com múltiplas seções.",
        ],
    },
    {
        "version": "1.3.47",
        "date": "2026-05-26",
        "changes": [
            "Fix (mod_auto_updater.py): logs de download de mods não apareciam no painel de "
            "Atualização Automática. Chamadas a download_mods em _install_missing_mods e "
            "_handle_mod_update não passavam on_log=self._log, descartando silenciosamente "
            "todas as mensagens do SteamCMD e status de instalação.",
            "Fix (pages/ini_import.py): 'Importar INI do Disco' falhava silenciosamente ao "
            "abrir — import 'from .ark_ini' apontava para src/pages/ (inexistente) em vez de "
            "src/. Corrigido para 'from ..ark_ini' nas duas ocorrências (default_dir e "
            "_load_from_folder).",
            "Fix (pages/fetch_mod_names_async.py): nomes de mods nunca eram carregados após "
            "adicionar IDs — urllib.parse e urllib.request usados mas não importados. "
            "A exceção NameError era engolida pelo except genérico, resultando em IDs sem nome "
            "na lista de mods.",
        ],
    },
    {
        "version": "1.3.46",
        "date": "2026-05-26",
        "changes": [
            "Fix (rcon_client.py): removida abordagem de sentinel no protocolo RCON. "
            "O sentinel (EXECCOMMAND vazio enviado logo após o comando real) podia ser respondido "
            "pelo ARK antes da resposta do comando principal, causando retorno vazio para "
            "ListPlayers e outros comandos mesmo com jogadores conectados. "
            "Substituído por espera direta com timeout de 3s e matching por packet ID; "
            "pacotes órfãos de comandos anteriores são descartados automaticamente.",
            "Fix (broadcast_rcon.py): corrigido AttributeError 'module datetime has no attribute now' "
            "— import trocado de 'import datetime' para 'from datetime import datetime'. "
            "Corrigido também import ausente de RconClient que causava NameError ao enviar "
            "Broadcast via conexão temporária (servidor sem RCON aberto no console).",
            "Fix (rcon_exec.py): feedback do console RCON melhorado — comandos executados com "
            "sucesso mas sem retorno (SaveWorld, Broadcast, DoExit…) exibem '(ok)' em verde "
            "em vez de '(sem resposta)', distinguindo execução bem-sucedida de erro real.",
            "Feat (add_mod.py, tab_mods.py): suporte a múltiplos IDs no campo de mods da aba "
            "principal — cole IDs separados por vírgula (ex: 731604991, 880871931) para adicionar "
            "todos em lote de uma vez sem precisar abrir o diálogo de busca.",
            "Feat (mod_search_dialog.py): busca em lote no Steam Workshop — ao colar múltiplos "
            "IDs separados por vírgula no campo de busca, o diálogo faz uma única chamada à API "
            "e lista todos os mods encontrados com nome, ID e botões individuais '➕ Adicionar'. "
            "Botão 'Adicionar Todos (N)' no topo adiciona toda a lista e fecha o diálogo.",
        ],
    },
    {
        "version": "1.3.45",
        "date": "2026-05-25",
        "changes": [
            "Feat (tab_general.py): sele\u00e7\u00e3o de branch SteamCMD por bot\u00f5es r\u00e1pidos na aba Geral. "
            "Bot\u00f5es '\u2705 Padr\u00e3o (Est\u00e1vel)' e '\U0001f995 Pre-Aquatica' definem o campo branch_name automaticamente. "
            "Campo de texto permanece vis\u00edvel para branches personalizadas. "
            "Sele\u00e7\u00e3o 'preaquatica' instrui o SteamCMD a baixar a vers\u00e3o ASE pr\u00e9-Aquatica (compatibilidade com ArkShopUI V1.x e plugins ASE antigos).",
            "Feat (build_server_card.py): card do servidor exibe a vers\u00e3o instalada: "
            "'\u2705 Vers\u00e3o: Padr\u00e3o (Est\u00e1vel)', '\U0001f995 Vers\u00e3o: Pre-Aquatica' ou '\U0001f3ae Branch: <nome>' para branches personalizadas.",
        ],
    },
    {
        "version": "1.3.44",
        "date": "2026-05-25",
        "changes": [
            "Fix (server_manager.py): remo\u00e7\u00e3o de __COMPAT_LAYER do ambiente do processo antes de iniciar o servidor. "
            "O Windows aplica o shim DetectorsAppHealth ao ARKLAND-Multi.exe, que era propagado "
            "via ShellExecute para o ShooterGameServer.exe. Com o shim ativo, o SEH do ArkApi era "
            "interceptado e exce\u00e7\u00f5es recuper\u00e1veis no CheckOnTimerCallbacks viravam crash fatal do servidor. "
            "O ASM n\u00e3o sofre esse problema por n\u00e3o ter o shim aplicado. "
            "Corrigido removendo temporariamente __COMPAT_LAYER antes do os.startfile() e restaurando ap\u00f3s.",
        ],
    },
    {
        "version": "1.3.43",
        "date": "2026-05-25",
        "changes": [
            "Feat (dialogs/mod_download_dialog.py): popup de progresso de download de mods. "
            "Ao clicar em 'Baixar / Atualizar Todos os Mods' ou no bot\u00e3o de download individual, "
            "um dialog exibe a lista de mods com status em tempo real (Aguardando \u2192 Baixando... \u2192 Instalado / Erro). "
            "O SteamCMD \u00e9 aberto em janela pr\u00f3pria vis\u00edvel mostrando o download. "
            "Ap\u00f3s o SteamCMD encerrar, mensagens de c\u00f3pia e gera\u00e7\u00e3o do .mod aparecem no log do dialog. "
            "Bot\u00e3o 'Fechar' permanece desabilitado at\u00e9 a opera\u00e7\u00e3o concluir.",
        ],
    },
    {
        "version": "1.3.42",
        "date": "2026-05-25",
        "changes": [
            "Fix (mod_manager.py + server_manager.py): fallback de gera\u00e7\u00e3o de .mod reativado como \u00faltimo recurso. "
            "Quando o arquivo .mod oficial do Steam Client n\u00e3o est\u00e1 dispon\u00edvel no cache local "
            "(mods baixados via SteamCMD sem estar subscrito no Steam Client), "
            "o ARKLAND gera o .mod a partir do mod.info com modPath vazio (formato correto). "
            "N\u00e3o \u00e9 mais necess\u00e1rio re-baixar mods pelo Steam Client para que o servidor inicie.",
        ],
    },
    {
        "version": "1.3.41",
        "date": "2026-05-25",
        "changes": [
            "Fix (server_manager.py): reparo automático de arquivos .mod ao iniciar servidor. "
            "A cada start, o ARKLAND copia o .mod oficial do Steam Client para o diretório "
            "ShooterGame/Content/Mods/ de cada mod configurado no servidor. Cobre dois casos: "
            "(1) arquivo .mod ausente (deletado ou nunca criado); "
            "(2) arquivo .mod gerado por versões anteriores do ARKLAND com modPath incorreto (T11). "
            "Não é mais necessário copiar manualmente o .mod antes de testar.",
        ],
    },
    {
        "version": "1.3.40",
        "date": "2026-05-25",
        "changes": [
            "Fix (mod_manager.py — T11): ARKLAND não gera mais arquivos .mod — usa exclusivamente o "
            ".mod oficial do Steam Client. Arquivos .mod gerados pelo ARKLAND tinham modPath preenchido "
            "(../../../ShooterGame/Content/Mods/<id>), enquanto o arquivo oficial do Steam Client tem "
            "modPath vazio. Esse desvio causava falha no mount do VFS do mod pelo ARK, deixando a classe "
            "Blueprint do buff ArkShopUI_Buff_FCAS como null e resultando em crash no timer callback "
            "(~5 min após jogador conectar). Novo método _find_official_dot_mod() localiza o .mod correto "
            "via registro do Windows + libraryfolders.vdf. Novo método repair_mod_files() substitui .mod "
            "incorretos de mods já instalados pelo arquivo oficial.",
            "Feat (mod_auto_updater.py + config_manager.py + global_config.py): suporte a Steam Web API Key "
            "nas configurações globais. A key é enviada nas requisições ao ISteamRemoteStorage/"
            "GetPublishedFileDetails para verificação de atualizações de mods. Campo adicionado na aba "
            "Configurações Globais com hint para steamcommunity.com/dev/apikey.",
        ],
    },
    {
        "version": "1.3.39",
        "date": "2026-05-23",
        "changes": [
            "Fix (plugin): plugin CustomShop descontinuado e removido do projeto. "
            "Hipótese T10: o hook HandleNewPlayer do CustomShop chamava InitPlayer + GetOrAddShopBuff() "
            "a cada jogador conectado, podendo corromper o estado interno do ArkShopUI.dll e causar crash "
            "no timer callback (~5 min após jogador entrar). "
            "Aba Plugins reimplementada: exibe os 5 plugins oficiais ASE (Server API, Permissions, ArkShop, "
            "ArkShopUI, Plugin Limit Fix) com botão 'Download' (abre página oficial) e botão 'Instalar' "
            "(seleciona ZIP ou DLL e extrai para o diretório correto do servidor).",
        ],
    },
    {
        "version": "1.3.38",
        "date": "2026-05-23",
        "changes": [
            "Fix (server_config.py): causa raiz do crash ArkShopUI.dll encontrada após 8 tentativas. "
            "O ARKLAND passava mods por dois canais ao mesmo tempo: ?GameModIds= na linha de comando "
            "E ActiveMods= no GameUserSettings.ini. O ASM usa apenas ActiveMods= no INI. "
            "Isso alterava a sequência de inicialização dos mods e deixava o ArkShopUI.dll em estado "
            "inválido, causando crash no timer callback (~5 min após jogador conectar). "
            "?GameModIds= removido de build_launch_args(); mods carregados exclusivamente via ActiveMods= no INI.",
        ],
    },
    {
        "version": "1.3.37",
        "date": "2026-05-22",
        "changes": [
            "Fix (server_manager.py): Tentativa 8 — método de lançamento do servidor replicado exatamente do ASM. ASM usa UseShellExecute=true (os.startfile() em Python) para lançar RunServer.cmd, o que usa ShellExecute do Windows e não herda env, handles ou job objects do processo pai. Conteúdo de RunServer.cmd também atualizado para ser idêntico ao gerado pelo ASM: start \"<nome>\" /normal <cmd>. Resolve possível causa de crash do ArkShopUI.dll via herança de handles do PyInstaller.",
        ],
    },
    {
        "version": "1.3.36",
        "date": "2026-05-22",
        "changes": [
            "Fix (server_manager.py): servidor agora é lançado via cmd.exe /c RunServer.cmd — método idêntico ao ASM (start \"ARK Server\" /min /normal). O RunServer.cmd era gerado mas não usado para lançar o servidor. O PID do ShooterGameServer.exe é rastreado via psutil após o cmd.exe sair. Adicionadas _PsutilProcessWrapper e _find_server_process para compatibilidade. Tentativa de resolver crash ArkShopUI.dll no timer callback (~5 min após start).",
        ],
    },
    {
        "version": "1.3.34",
        "date": "2026-05-22",
        "changes": [
            "Fix (server_manager.py): remove variáveis PyInstaller do ambiente do servidor — TCL_LIBRARY, TK_LIBRARY, _PYI_*, __COMPAT_LAYER (DetectorsAppHealth), CHROME_CRASHPAD_PIPE_NAME. O __COMPAT_LAYER herdado do ARKLAND aplicava shims de compatibilidade do Windows ao ShooterGameServer.exe, podendo interferir no SEH do ArkApi e converter exceções internas em crashes fatais no CheckOnTimerCallbacks (ArkShopUI).",
            "Fix (server_manager.py): RunServer.cmd agora gerado com 'start \"ARK Server\" /min /normal' — formato idêntico ao ASM.",
        ],
    },
    {
        "version": "1.3.33",
        "date": "2026-05-22",
        "changes": [
            "Fix (server_manager.py): flag CREATE_BREAKAWAY_FROM_JOB adicionada ao Popen — servidor sai do job object do PyInstaller/ARKLAND e roda completamente independente, igual ao lançamento manual. Possível causa raiz do crash ArkShopUI.dll.",
            "Feat (server_manager.py): gera RunServer.cmd em ShooterGame/Saved/Config/WindowsServer/ (padrão do ASM) a cada inicialização do servidor.",
        ],
    },
    {
        "version": "1.3.32",
        "date": "2026-05-22",
        "changes": [
            "Debug (server_manager.py): ao iniciar servidor, grava '_arkland_debug.txt' em Binaries/Win64 com PATH completo, todas variáveis de ambiente e commandline — para diagnóstico do crash ArkShopUI.dll. O caminho do ArkApi.log também é exibido na aba Logs.",
        ],
    },
    {
        "version": "1.3.31",
        "date": "2026-05-22",
        "changes": [
            "Fix (remote_panel.py): botão 'Testar' agora testa 127.0.0.1 E o IP LAN local — exibe diagnóstico preciso: 'responde local mas não na LAN' indica Windows Firewall bloqueando por perfil.",
            "Feat (remote_panel.py): botão '🔒 Firewall' cria regra de entrada TCP no Windows Defender Firewall via UAC (netsh advfirewall, profile=any) sem precisar abrir o painel de firewall manualmente.",
        ],
    },
    {
        "version": "1.3.30",
        "date": "2026-05-22",
        "changes": [
            "Fix (remote_agent.py): is_running agora verifica se a thread do servidor está viva (_thread.is_alive()), evitando falso positivo quando o servidor morre silenciosamente.",
            "Fix (remote_agent.py): endpoint GET /ping sem autenticação adicionado — permite teste de alcance sem token.",
            "Fix (start_remote_agent.py): autodiagnóstico após start — após 2 s testa 127.0.0.1:porta e exibe aviso detalhado se não responder (Windows Firewall).",
            "Feat (remote_panel.py): botão 'Testar' no painel do agente — ping local imediato com instruções sobre Windows Firewall.",
            "Fix (remote_control_dialog.py): mensagem 'Sem resposta' agora menciona Firewall do Windows.",
        ],
    },
    {
        "version": "1.3.29",
        "date": "2026-05-22",
        "changes": [
            "Debug (server_manager.py): logging ENV-DEBUG adicionado antes do Popen — exibe sys._MEIPASS, entradas _MEI* residuais no PATH e localização de z.dll/libmariadb.dll para rastrear causa raiz do crash ArkShopUI.",
            "Fix (tab_crashes.py + server_manager.py): aba Crashes agora detecta todos os tipos de crash — além de pastas com .dmp, parseia blocos 'Fatal error!' do ShooterGame.log como registros sintéticos; registros de log exibem badge '[ShooterGame.log]' e botão 'Abrir log' em vez de 'Abrir pasta'.",
        ],
    },
    {
        "version": "1.3.28",
        "date": "2026-05-22",
        "changes": [
            "Fix (server_manager.py): servidor iniciado com CREATE_NEW_CONSOLE e ambiente sem _MEIPASS no PATH — elimina herança de DLLs do PyInstaller que causavam crash fatal (ArkShopUI timer callback) ao conectar jogadores.",
            "Fix (plugin_manager.py): uninstall() agora remove libmariadb.dll e z.dll que install() havia copiado para Win64/.",
            "Fix (plugin_manager.py): novo método cleanup_stale_win64_dlls() remove DLLs residuais do CustomShop quando o plugin não está instalado.",
            "Fix (app.py): _cleanup_stale_plugin_dlls() chamado no startup para limpar automaticamente servidores já afetados.",
        ],
    },
    {
        "version": "1.3.27",
        "date": "2026-05-22",
        "changes": [
            "Fix (remote_control_dialog.py): race condition em _poll() — ao fechar a janela de controle remoto enquanto uma tentativa de conexão estava pendente (timeout de 6 s), win.after() era chamado num widget já destruído, causando TclError silencioso no thread daemon.",
            "Fix (remote_control_dialog.py): mensagens de erro de conexão agora são traduzidas para PT-BR (urlopen timed out → sem resposta; connection refused → agente não rodando; 401 → token inválido).",
        ],
    },
    {
        "version": "1.3.26",
        "date": "2026-05-22",
        "changes": [
            "Fix (add_server_dialog.py): ARK_MAP_NAMES, ARK_MAPS e ServerConfig não importados — dialog 'Novo Servidor' lançava NameError ao abrir (list comprehension do ComboBox de mapa) e ao criar o servidor; imports adicionados de server_config.py.",
        ],
    },
    {
        "version": "1.3.25",
        "date": "2026-05-21",
        "changes": [
            "Fix (remote_control_dialog.py): RemoteClient não importado — janela de controle remoto abria vazia pois a criação do client lançava NameError; import adicionado de remote_agent.py.",
        ],
    },
    {
        "version": "1.3.24",
        "date": "2026-05-21",
        "changes": [
            "Fix (start_remote_agent.py): RemoteAgent não importado — botão 'Ativar Agente' lançava NameError silencioso; import adicionado de remote_agent.py.",
        ],
    },
    {
        "version": "1.3.23",
        "date": "2026-05-21",
        "changes": [
            "Fix (ini_import.py): dialog 'Importar INI do Disco' com geometry 620x220 cortava o campo de pasta e os botões — altura aumentada para 280.",
            "Fix (get_cluster_health.py): 'from .server_config import ClusterProfile' corrigido para 'from ..server_config' — botão Diagnosticar Cluster lançava NameError ao abrir.",
            "Fix (server_save.py): SERVER_STATUS_STOPPED, snapshot_server, diff_snapshots, _ARK_EVENT_LABEL_TO_ID e ArkIniManager não importados — salvar configurações e iniciar servidor falhavam silenciosamente.",
        ],
    },
    {
        "version": "1.3.22",
        "date": "2026-05-21",
        "changes": [
            "Refactor (arquitetura): app.py monol\u00edtico (~13.000 linhas) desmembrado em 170+ m\u00f3dulos especializados em src/pages/ e 9 di\u00e1logos em src/dialogs/ — cada funcionalidade agora em arquivo pr\u00f3prio (tab_general, tab_game, tab_advanced, tab_spawns, tab_loot, tab_mods, tab_plugins, tab_ini_mods, tab_rcon, tab_chat, tab_logs, tab_crashes, tab_backup, build_tab_admins, build_tab_historico, build_tab_jogadores, server_panel, server_save, sidebar, performance_panel, remote_panel, cluster_detail, broadcast_*, ini_*, rcon_*, chat_*, player_*, buff_*, backup_*, etc.).",
            "Refactor (ui_constants.py): paleta de cores, Tooltip, _resource_path e constantes de UI extra\u00eddas do app.py para m\u00f3dulo compartilhado; importado por app.py, pages/ e dialogs/.",
            "Refactor (app.py): reduzido a ~1.000 linhas de orquestrador puro — apenas inicializa\u00e7\u00e3o, bind de m\u00e9todos de conex\u00e3o e roteamento; toda l\u00f3gica de UI delegada via imports lazy a pages/ e dialogs/.",
            "Refactor (server_panel.py): constru\u00e7\u00e3o de abas lazy via _on_tab_change + placeholder 'Carregando...' — abas s\u00f3 s\u00e3o constru\u00eddas na primeira vez que o usu\u00e1rio as visita.",
            "Fix (tab_general.py): scroll.unbind('<Configure>') nunca revinculado ap\u00f3s build — layout de 2 colunas e scroll restaurados ao adicionar scroll.bind + scrollregion ao final da fun\u00e7\u00e3o.",
            "Fix (tab_advanced.py): NameError 'profiles' na linha 136 impedia renderiza\u00e7\u00e3o da aba Avan\u00e7ado e bloqueava restaura\u00e7\u00e3o do scroll; profiles/profile_names agora definidos antes do uso.",
            "Fix (tab_crashes.py): import relativo 'from .server_manager' corrigido para 'from ..server_manager'.",
            "Fix (tab_plugins.py): 'ttk' n\u00e3o importado (NameError ao abrir aba Plugins); 'webbrowser' ausente (NameError ao instalar Permissions) — ambos adicionados.",
            "Fix (on_update_result.py): APP_VERSION n\u00e3o importado — verificador de atualiza\u00e7\u00f5es lan\u00e7ava NameError ao receber resposta do servidor.",
            "Fix (tab_game.py): 'from .ark_ini' corrigido para 'from ..ark_ini' (_level_to_xp usada em _level_cap_row).",
            "Fix (get_change_logger.py): ChangeLogger importado apenas em TYPE_CHECKING — movido para import de runtime para evitar NameError ao acessar aba Hist\u00f3rico.",
        ],
    },
]
