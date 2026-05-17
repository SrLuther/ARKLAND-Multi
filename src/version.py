"""
Versão e changelog do ARKLAND - Server Manager.
Este arquivo é a única fonte de verdade para a versão do aplicativo.
"""

APP_VERSION: str = "1.2.3"
BUILD_DATE: str = "2026-05-17"

# Cada entrada: version, date, changes (lista de strings)
CHANGELOG: list[dict] = [
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
