# Changelog

<!-- Gerado por scripts/sync_changelog_md.py — não edite manualmente. -->
<!-- Fonte: src/version.py -->

<!-- markdownlint-disable MD024 -->

## [1.9.33] - 2026-06-18

### Feature

- Novo (Web Store): Sistema de Documentação Automática do Sistema de Resgates — painéis explicativos por categoria (Itens, Kits, Dinos, Licenças, Disponível, Doação).
- Novo (Web Store): documentação gerada automaticamente por item — descrição curta/detalhada, requisitos, licença necessária, avisos e texto de confirmação no modal de resgate.

### Improvement

- Melhoria (Web Store): grid de licenças Gamma/Beta/Alfa com duração e bônus de Âmbar documentados.

## [1.9.32] - 2026-06-18

### Fix

- Fix (Web Store): card de saldo de Âmbares — valor inteiro completo em cima, rótulo Âmbar/Âmbares abaixo; fonte reduz automaticamente para caber em saldos altos (sidebar, catálogo, recarga e mobile).

## [1.9.31] - 2026-06-12

### Feature

- Novo (TEK ASE): pasta custom de INI (user_config_folder) — lê/grava fora do install_dir e sincroniza para WindowsServer no start.
- Novo (TEK + classic): toggle EnableCryoSicknessPVP (Cryo Sickness em PvP).

### Improvement

- Melhoria (Web Store): RCON ASE unificado — RconClient + ThreadPoolExecutor, retry no Shop.Reload (até 5 tentativas) e GET /api/rcon/status para teste de conectividade.
- Melhoria (Web Store): Console do Servidor — log append-only, histórico ↑/↓, Enter para enviar, loading nos botões e rate limit ajustado (60/min).
- Melhoria (Web Store): pontos e entregas 100% via banco/fila plugin — RCON bloqueado para Shop.AddPoints, Shop.SetPoints, Shop.GetPoints e Shop.Deliver.
- Melhoria (TEK): asm_rcon_window com auto-reconnect, send_command_with_retry e ping keep-alive.
- Melhoria (TEK + classic): módulos rcon_*.py ligados — auto-reconnect, retry e status no Console RCON.
- Melhoria (TEK): reload CustomShop unificado em Shop.Reload (alinhado ao plugin e Web Store).

### Fix

- Fix (TEK): remote_agent usa connect() + send_command_safe() em vez de API inexistente do RconClient.
- Fix (RCON): sanitização de senhas corrompidas com sufixo ?ServerPassword= (TEK, Web Store e RconClient).

## [1.9.30] - 2026-06-17

### Feature

- Novo (Web Store + CustomShop): sistema de licenças Gamma/Beta/Alfa — player_entitlements, TimedPoints empilhado (Default + licenças), preços 50k/75k/100k.
- Novo (Web Store): Desistência — cancelar resgate PENDENTE com reembolso de Âmbar.
- Novo (CustomShop): ShopEntitlements — grant/revoke, CanRedeem em Buy/Give kit e item.

### Improvement

- Melhoria (Web Store): resgate valida preço server-side e licenças exigidas (Permissions); Minha Área exibe licenças ativas; catálogo com cadeado.

### Fix

- Fix (Web Store): moeda Âmbar na home sem sobreposição em mobile — animação só em desktop (901px+).

## [1.9.29] - 2026-06-17

### Improvement

- Melhoria (Web Store): editor de itens com menu Modalidade no catálogo — Item, Dino, Licença, Comando e subcategorias; define Type e Category automaticamente.

## [1.9.28] - 2026-06-17

### Feature

- Novo (Web Store): moeda oficial Âmbar/Âmbares com ícone, lore completa na home (A Lenda do Âmbar de Arkland) e frase oficial da moeda.
- Novo (Web Store): aba Licenças no catálogo — permissões, nuvem e benefícios por comando.

### Improvement

- Melhoria (Web Store): interface pública sem a palavra Shop — ARKLAND Donations; normalização automática do nome exibido.
- Melhoria (Web Store): licenca_nuvem categorizada como Licenças no config.

### Fix

- Fix (TEK): MOTD visível em Detalhes do Servidor — card em largura total no topo (antes era coberto por BanList/Branch).
- Fix (TEK): painel CustomShop — padrão ARKLAND Donations em vez de ARKLAND Shop.

## [1.9.27] - 2026-06-17

### Feature

- Novo (Web Store): página inicial completa — hero, servidores do cluster, estatísticas do catálogo, pacotes PIX, utilidades e FAQ focados no jogador.
- Novo (Web Store): seção Eventos Sazonais — rates ajustados periodicamente em todos os mapas, no estilo dos servidores oficiais.
- Novo (Web Store): destaque dos mapas mod Brighamia e Alps na home.
- Novo (Web Store): catálogo público (Itens, Dinos, Kits) sem login; Steam só para doar, resgatar e Minha Área.

### Improvement

- Melhoria (Web Store): menu Downloads renomeado para Utilidades; removidos cards automáticos do instalador/releases do painel admin.
- Melhoria (Web Store): home sem versão do app nem changelog do projeto — foco nos servidores.

### Fix

- Fix (Web Store): grade de dinos no catálogo desktop; saldo de pontos via /api/player/points.
- Fix (Web Store): auditoria admin com modal formatado em vez de JSON cru; boot não exige login.

## [1.9.26] - 2026-06-12

### Feature

- Novo (Configurações): backup automático global de todos os servidores — pasta centralizada, ZIP compactado (nível 9), retenção por quantidade e botão executar agora.
- Novo (Banco de Dados): backup automático do MariaDB (arkland_shop / ark_permission) com intervalo configurável, restauração e retenção por quantidade.
- Novo (Web Store): sistema de auditoria completo — tabela audit_events, timeline por pedido e página Admin Auditoria.
- Novo (Web Store): reemissão só por admin com motivo e registro de qual admin reemitiu.

### Fix

- Fix (CustomShop): GiveItem entrega Dinos e Commands na fila web — resgates de carcharodontosaurus e itens similares passam a spawnar no jogo.
- Fix (CustomShop): GiveKit/GiveItem só marcam sucesso quando o spawn do dino realmente ocorre; /shop deixa de reportar entrega falsa.
- Fix (TEK Mods): textos e ícones da aba Mods (Workshop) corrigidos (encoding UTF-8).

## [1.9.25] - 2026-06-16

### Feature

- Novo (Web Store): sistema de auditoria completo — tabela audit_events, timeline por pedido e página Admin Auditoria.
- Novo (Web Store): reemissão só por admin com motivo e registro de qual admin reemitiu.

### Fix

- Fix (CustomShop): GiveItem entrega Dinos e Commands na fila web — resgates de carcharodontosaurus e itens similares passam a spawnar no jogo.
- Fix (CustomShop): GiveKit/GiveItem só marcam sucesso quando o spawn do dino realmente ocorre; /shop deixa de reportar entrega falsa.
- Fix (TEK Mods): textos e ícones da aba Mods (Workshop) corrigidos (encoding UTF-8).

## [1.9.24] - 2026-06-12

### Improvement

- Melhoria (Discord): erros de webhook passam a aparecer no log com corpo da resposta HTTP.

### Fix

- Fix (Discord): DiscordNotifier nunca era inicializado no app TEK — webhooks globais (start/stop/crash, backup, mods, BUFFs) voltam a funcionar.
- Fix (Discord TEK): notificações por servidor via webhook em Gerenciamento Automático + Detalhes do Discord Bot (start/stop e join/leave via ListPlayers).

## [1.9.23] - 2026-06-12

### Fix

- Fix (TEK): nova seção Mods (Workshop) na barra lateral do painel do servidor — lista de mods e atualização automática Workshop deixam de ficar escondidas em Administração.
- Fix (TEK): conflito de layout entre lista de mods e Branch SteamCMD corrigido (widgets sobrepostos na mesma linha do grid).

## [1.9.22] - 2026-06-12

### Feature

- Novo (Web Store): editor estruturado de itens + Salvar & Aplicar grava disco e recarrega CustomShop em todos os servidores cadastrados.

### Improvement

- Melhoria (Web Store): save_config sincroniza catálogo em cada plugin_config_path e Shop.Reload via RCON em todos os servidores registrados.

### Fix

- Fix (BUFFs TEK): scheduler inicia ao abrir o app; reinício aplica rates nos INIs e só marca ativo quando o servidor volta online; UI mostra estado ATIVANDO.
- Fix (BUFFs TEK): RCON usa admin_password; parada/início via asm_server_manager sem diálogos que bloqueavam a thread em background.
- Fix (ModAutoUpdater TEK): ponte unificada para servidores TEK; card na aba Mods com ativar/parar, intervalo e log; Steam API Key repassada ao salvar config global.
- Fix (AutoUpdate servidor TEK): verificação agendada aguarda SteamCMD, compara build ID e registra log; reinício opcional após update (config global).
- Fix (Web Store): resgate confirmBuy não quebra toast após fechar modal.

## [1.9.21] - 2026-06-12

### Feature

- Novo (Web Store): editor estruturado de kits — itens (Amount/Quality), dinos (Level/Gender/ForceTame) e comandos com quantidade, sem perder campos ao salvar.

### Fix

- Fix (Web Store): edição de kits preserva Dinos, Items, Commands e VipLicense existentes (merge com o JSON do config).
- Fix (CustomShop): Commands aceita string ou objeto { Command, ExecuteAsAdmin }; placeholder {steamid} além de {SteamID}.

## [1.9.20] - 2026-06-16

### Feature

- Novo (Web Store): layout responsivo para mobile e tablet — menu hambúrguer, sidebar deslizante, tabelas com scroll e modais adaptados.

### Improvement

- Melhoria (Web Store): barra mobile com saldo de pontos; catálogo e formulários empilhados em telas estreitas.

## [1.9.19] - 2026-06-16

### Feature

- Novo (CustomShop): licença VIP ao entregar kit — campo VipLicense (tier + até 30 dias) registra vip_players na entrega web.

### Improvement

- Melhoria (TimedPoints): bônus VIP por licença web resgatada ou permissão in-game; Stack configurável.

### Fix

- Fix (PIX): impede crédito duplicado de pontos — webhook e polling na mesma transação com trava no banco.
- Fix (CustomShop/TimedPoints): Default (+25 etc.) só para jogadores conectados; sem acúmulo offline.

## [1.9.18] - 2026-06-16

### Feature

- Novo (Web Store): Histórico de Doações em Minha Área — pontos creditados, data/hora, valor PIX e status de cada doação.

### Improvement

- Melhoria (Web Store): resumo de Minha Área separa doações creditadas e resgates de itens.

### Fix

- Fix (PIX): rate limit 429 no polling de status — limite dedicado ao endpoint e consultas mais espaçadas com backoff automático.

## [1.9.17] - 2026-06-12

### Feature

- Novo (Web Store/PIX): formulário do pagador antes do PIX — e-mail, nome, CPF e telefone (exigidos pelo Mercado Pago); dados repassados ao MP, sem e-mail fictício.

### Improvement

- Melhoria (Web Store): transparência sobre dados na doação — política, modal e hints deixam claro que o MP solicita os dados e a ARKLAND não usa para marketing.
- Melhoria (Loja): salvar Web Store grava credenciais MySQL em shop_db (prefs do DB Manager).

### Fix

- Fix (PIX): crédito automático de pontos após confirmação (poll 3s + webhook); payer_email gravado em point_payments.
- Fix (DB Manager): não sobrescreve mais usuário/senha com root@localhost quando MariaDB local está rodando; prioriza shop_db e config da Web Store.

## [1.9.16] - 2026-06-12

### Feature

- Novo (Web Store): ARKLAND Donations — política de doações com modal, banner e aceite obrigatório antes de doar via PIX ou resgatar com pontos.
- Novo (Web Store): admin Doações PIX — pacotes, token Mercado Pago e tabela de gestão.

### Improvement

- Melhoria (Web Store): linguagem de doação/resgate em toda a UI (sem termos de compra/venda); aba Doação PIX; resgates com pontos no catálogo.

### Fix

- Fix (Web Store): saldo de pontos na sidebar, statusbar e catálogo; retorno 0 se jogador não existe no banco.
- Fix (PIX): e-mail válido no checkout Mercado Pago (player{steamid}@arkland.com.br).
- Fix (Web Store): aba Disponível — migração orders.id para schema SQLAlchemy; setup_db.sql atualizado.

## [1.9.15] - 2026-06-12

### Fix

- Fix (HTTPS/Caddy): botões Instalar/Iniciar/Parar/Reiniciar não respondiam — _save_shop_from_ui() acessava campos do banco ainda não criados (NameError silencioso).
- Fix (HTTPS/Caddy): status Caddy atualiza ao final da aba Web Store; erros exibidos em messagebox.

## [1.9.14] - 2026-06-12

### Feature

- Novo (HTTPS): integração Caddy no app — instalar, iniciar, parar, reiniciar, firewall 80/443 e boot automático no Windows (modo Host, aba Web Store).

### Improvement

- Melhoria (HTTPS): Caddyfile gerado automaticamente (domínio → localhost:porta da loja); auto-start do Caddy após subir a web store.

### Fix

- Fix (DB): ao reiniciar o app, o Gerenciador de DB mantém a última conexão remota (ex.: arkland@192.168.15.51) em vez de sobrescrever com root@127.0.0.1 quando o MariaDB local está rodando.
- Fix (DB): auto-connect local como root não grava prefs quando shop_db aponta para servidor remoto da loja.

## [1.9.13] - 2026-06-12

### Improvement

- Melhoria (TEK): hint na seção Administradores indica caminho e momento da gravação.

### Fix

- Fix (TEK/Admins): AllowedCheaterSteamIDs.txt passa a ser gravado em ShooterGame/Saved/ ao salvar ou iniciar o servidor (modo TEK não escrevia o arquivo).
- Fix (Admins): gravação centralizada em ark_server_files.py; promoção de jogador a admin atualiza o arquivo imediatamente.

## [1.9.12] - 2026-06-12

### Feature

- Novo (Web Store): abas Catálogo — Itens, Kits, Disponível (resgate) e Recarga PIX.
- Novo (Web Store): recarga PIX via Mercado Pago (MP_ACCESS_TOKEN) com QR code e webhook.
- Novo (API): /api/player/available — resgate de entregas pendentes na web store.

### Improvement

- Melhoria (Loja): domínio padrão arkland.com.br; modo Cliente para loja/banco em servidor remoto.
- Melhoria (Loja): defaults do servidor remoto — LAN 192.168.15.51, IP público 179.185.19.88, porta 27199; MySQL de pedidos aponta para o host remoto.
- Melhoria (Loja): UI Web Store exibe URLs do servidor remoto (LAN, internet e domínio para jogadores).

### Fix

- Fix (Loja): abas Itens/Kits do painel CustomShop não duplicam conteúdo após importar catálogo.

## [1.9.11] - 2026-06-12

### Feature

- Novo (Loja): botão «Importar JSON» no painel CustomShop — carrega catálogo ArkShop (ShopItems/Kits) com conversão automática para formato CustomShop.
- Novo (Loja): importação normaliza Blueprints, Amount→Quantity, itens dino (Dinos) e command (Commands); opção mesclar/substituir e importar TimedPointsReward.

### Fix

- Fix (CustomShop): BuyItem entrega dinos e executa comandos na compra; bundles aceitam Amount como alias de Quantity.

## [1.9.10] - 2026-06-15

### Feature

- Novo (TEK): remover servidores legados (modo primitivo) em Configurações → Servidores legados, sem precisar abrir o modo primitivo.

### Fix

- Fix (BUFFs/TEK): sistema de rates temporários funciona em servidores TEK — start/stop, INI e combo unificado (TEK + legado).
- Fix (DB): botão «Sync jogadores» — recria arkland_shop.players com schema CustomShop e importa SteamId de ark_permission.players.
- Fix (DB): botão «Recarregar» na barra de conexão e na aba Dados; aviso se players tiver schema do Permissions.

## [1.9.9] - 2026-06-15

### Fix

- Fix (mods): descompressão UE4 de arquivos .z na instalação de mods — paridade ModUtils.CopyMod do ASM; PrimalGameData e mapas mod passam a carregar corretamente.
- Fix (mods): reparo automático antes do start se PrimalGameData ainda estiver comprimido (.uasset.z sem .uasset).
- Fix (mods): geração de .mod via WriteModFile (mod.info + modmeta.info) na cópia.

## [1.9.8] - 2026-06-15

### Fix

- Fix (TEK/mods): reparo de arquivos .mod antes do start — paridade modo primitivo (Steam Client oficial ou geração via mod.info).
- Fix (TEK/mods): ActiveMods no GUS inclui o ID do map mod (como no modo primitivo).
- Fix (TEK/mods): «Baixar Mods» usa +force_install_dir na pasta do servidor e validate, igual ao modo primitivo.

## [1.9.7] - 2026-06-15

### Fix

- Fix (ASM/mods): paridade mapa mod — CLI usa nome interno (não /Game/Mods/...), -TotalConversionMod= na launch, map mod baixado via workshop ID do ServerMap.
- Fix (ASM/mods): ActiveMods no GUS exclui o ID do map mod (como ASM); «Baixar Mods» inclui map mod + total conversion automaticamente.
- Fix (ASM/mods): aviso ao iniciar se Content/Mods/{id}/ ou {id}.mod estiver ausente.

## [1.9.6] - 2026-06-15

### Fix

- Fix (INI): GameUserSettings.ini garante as 7 seções canônicas do servidor ASE (mesmo vazias) — ScalabilityGroups, SessionSettings, ServerSettings, GameSession, etc.
- Fix (INI): ordem estável de seções na gravação GUS (template hosting/ASM).
- Fix (INI): apenas Version=5 injetado automaticamente; sem defaults inventados em seções vazias.

## [1.9.5] - 2026-06-15

### Fix

- Fix crítico (INI): GameUserSettings.ini agora preserva [/Script/ShooterGame.ShooterGameUserSettings] com Version=5 — sem isso o ARK regravava o arquivo inteiro com defaults no boot.
- Fix (INI): MaxPlayers espelhado em SessionSettings/GameSession além de [/Script/Engine.GameSession].
- Fix (INI): normalização de case das seções GUS evita duplicatas que invalidam o arquivo.

## [1.9.4] - 2026-06-15

### Fix

- Fix (DB Manager): layout da aba Banco de Dados restaurado — NameError interrompia a montagem do painel na v1.9.3.
- Fix (DB Manager): status arkland_shop/ark_permission integrado na barra de conexão sem quebrar o grid.

## [1.9.3] - 2026-06-12

### Feature

- Novo (DB): setup_db.sql e wizard criam ark_permission além de arkland_shop — banco vazio para o Permissions.dll.
- Novo (Permissions): template plugin/Permissions/configs/config.json incluído no bundle do app.
- Novo (Loja): sync/instalação CustomShop grava Permissions/config.json com credenciais do DB Manager (MysqlDB: ark_permission).
- Novo (DB Manager): status dos bancos arkland_shop e ark_permission, atalhos e aviso se Permissions.dll sem banco.
- Novo (Loja): botão «Provisionar grupos (RCON)» — Permissions.AddGroup a partir do catálogo CustomShop.

### Improvement

- Melhoria (Plugins): ASE Permissions marcado como obrigatório com grupos na stack CustomShop.

## [1.9.2] - 2026-06-12

### Fix

- Fix (TEK/paridade primitiva): novo _asm_persist_server — Iniciar, Reiniciar e Instalar agora seguem o mesmo fluxo do modo primitivo (widgets → JSON → INI → ação).
- Fix (TEK/SessionName): nome da sessão vazio usa automaticamente o nome do gerenciador, igual ao server_name do modo primitivo.
- Fix (TEK): caminhos duplicados de start consolidados; SteamCMD usa persistência completa antes de rodar.

## [1.9.1] - 2026-06-12

### Fix

- Fix (SteamCMD/TEK): branch vazio agora usa -beta public no AsmSteamCmd (caminho real do TEK) — a v1.9.0 só corrigia o ModManager legado.
- Fix (SteamCMD): ao trocar de preaquatica para estável, remove appmanifest antigo e força validate — corrigia instalação presa na v358.24.
- Fix (SteamCMD): Instalar/Atualizar sincroniza o painel aberto antes de rodar (branch_name não ficava vazio se não salvasse).
- Fix (ASM/SessionName): INI gravado antes de iniciar; ?SessionName= na CLI para nomes simples; aviso ao reconectar servidor já em execução.

## [1.9.0] - 2026-06-12

### Improvement

- Melhoria (Web Store): redesign da loja — hero, chips de categoria e cards com thumbnail.
- Melhoria (CustomShop): botão para recarregar plugin via RCON em todos os servidores elegíveis.

### Fix

- Fix (SteamCMD): branch vazio agora usa -beta public explicitamente na instalação/atualização do servidor.

### Other

- Nova funcionalidade (TEK): menu suspenso para eventos oficiais ARK (ActiveEvent) em Administração → Evento sazonal ARK — FearEvolved, WinterWonderland, TurkeyTrial, etc.

## [1.8.11] - 2026-06-14

### Fix

- Fix (CustomShop): ShopPoints::Exec agora trata ER_DUP_FIELDNAME (1060) como migração idempotente, evitando erro em runtime 'Duplicate column name kits'.

### Other

- Build (CustomShop): plugin recompilado e empacotado com CustomShop.dll corrigida.

## [1.8.10] - 2026-06-13

### Fix

- Fix (ASM/launch): SessionName removido da CLI em todos os casos; o nome da sessão agora é persistido somente no GameUserSettings.ini para evitar parsing inconsistente no Windows.

### Other

- Docs: ARK_SERVER_CONFIG_REFERENCE.md alinhado ao comportamento atual de launch (SessionName apenas no INI, AltSaveDirectoryName e -clusterid corrigidos no mapeamento).

## [1.8.9] - 2026-06-13

### Fix

- Fix (ASM/launch): SessionName com colchetes/espaços não vai mais na CLI com %5B/%20 — o ARK exibia o encoding literal; nome fica só no GUS.ini (aspas + UTF-16).
- Fix (ASM/launch): ?SessionName= na CLI restrito a nomes simples (A-Za-z0-9_-) para evitar 'ARK #NNNNNN' sem corromper nomes complexos.
- Fix (CustomShop): migração kits com ADD COLUMN IF NOT EXISTS e tolerância a ER_DUP_FIELDNAME (1060).

## [1.8.8] - 2026-06-13

### Fix

- Fix (Updater): encerra ARKLAND-WebStore.exe antes de instalar — corrigia erro 'DeleteFile falhou; código 5 / Acesso negado' ao atualizar.
- Fix (Updater/TEK): app fecha corretamente após iniciar o agente de atualização.
- Fix (TEK): verificação automática de atualização ao iniciar o app (regressão do app_tek).
- Fix (Web Store): auto_start_webstore usava variável shop antes de defini-la.

## [1.8.7] - 2026-06-13

### Fix

- Fix (ASM/launch): restaurado ?SessionName= na travel URL com percent-encoding — regressão da v1.7.6 causava nome genérico 'ARK #NNNNNN' na listagem.
- Fix (ASM/INI): SessionName gravado por último no GUS.ini — INI customizado/raw não pode mais sobrescrever o nome efetivo do servidor.
- Fix (CustomShop): migração da coluna kits idempotente (sem erro Duplicate column).

## [1.8.6] - 2026-06-12

### Improvement

- Melhoria (CustomShop): instalar/sincronizar grava WebApiUrl, API Key e credenciais Database (arkland_shop) do DB Manager no config.json do plugin.
- Melhoria (Web Store): IP público + URLs LAN/internet na aba; botão Firewall Windows; detecção automática de IP público; diagnóstico LAN vs localhost.

### Fix

- Fix (CustomShop): Error 126 — libmariadb.dll e z.dll copiadas para Win64/ além de Plugins/CustomShop/; diagnóstico de instalação incompleta.
- Fix (CustomShop): SSL/TLS ao conectar em 127.0.0.1:3306 — MariaDB portable não usa TLS; plugin recompilado com MYSQL_OPT_SSL_ENFORCE=0.

## [1.8.5] - 2026-06-12

### Fix

- Fix (Web Store): ARKLAND-WebStore.exe falhava com «No module named dotenv» — python-dotenv adicionado às dependências e empacotado no build PyInstaller.

## [1.8.4] - 2026-06-12

### Improvement

- Melhoria (Web Store): diagnóstico ao falhar (tail do webstore.log), espera pela porta e MariaDB antes de subir o Flask.

### Fix

- Fix (Web Store): no instalador, a loja não iniciava — o app tentava rodar app.py com ARKLAND-ServerManager.exe (não é Python). Novo ARKLAND-WebStore.exe dedicado no instalador; dados persistentes em %APPDATA%\ARKLAND-ServerManager\arkshop_web.

## [1.8.3] - 2026-06-12

### Fix

- Fix (DB): conexão travava em «Conectando...» quando o login funcionava na primeira tentativa — finalização da conexão (state.conn + status Conectado) estava só no retry do erro 1049; corrigido para qualquer conexão bem-sucedida.

## [1.8.2] - 2026-06-13

### Feature

- Novo (DB): Assistente guiado de instalação do banco arkland_shop — wizard em 3 passos (MariaDB → root → senha arkland) com setup automático e prefs salvas para a Loja.

### Fix

- Fix (DB): setup_db.sql incluído no executável PyInstaller e no instalador; cópia em %APPDATA%\ARKLAND-ServerManager — corrige «Arquivo não encontrado» no Setup limpo.
- Fix (DB): conexão retenta sem database quando arkland_shop ainda não existe (erro 1049).

### Other

- Performance: projeto UI concluído — chunking Engramas/Meio Ambiente/Estruturas, cache de busca, tail de Administração adiado, docs/UI_PATTERNS.md.

## [1.8.1] - 2026-06-12

### Feature

- Novo (WebStore — Downloads): página pública de Downloads e painel admin 'Gerenciar Links' — links manuais via config.json + injeção automática do instalador e GitHub Releases a partir do version.json.
- Novo (WebStore — /api/version): endpoint público que expõe versão, data e URL de download atual do projeto.

### Fix

- Fix (Sidebar): título 'ARK Manager' cortado na barra lateral — renomeado para 'ARKLAND / Server Manager', logo reduzida (54×36 px), padding ajustado e sidebar ampliada para 240 px; nenhum texto é truncado.
- Fix (WebStore — Catálogo): nomes de produtos exibidos como ID interno — campo Name adicionado ao config.json; fallback formatKey() converte 'metal_ingot_100' → 'Metal Ingot 100' automaticamente.
- Fix (WebStore — DB): MariaDB não iniciava antes do Flask em reinicializações — _ensure_mariadb_running() aguarda porta ativa antes de subir o processo Flask; _start_db_reconnect_watcher() reativa a conexão em background.
- Fix (WebStore — Visual): redesign 'Primitive+TEK' — paleta âmbar/fogo, textura de pedra no fundo, logo em medallion com fundo branco visível, acentos ciano substituídos por âmbar em nav, botões, cards e modais.

## [1.8.0] - 2026-06-11

### Feature

- Novo (TEK v2 — Interface): layout híbrido D completo em todas as 24+ seções — cards duplos, dual-label PT+EN, slider condicional (≥1200px), checkboxes em grid.
- Novo (TEK v2 — i18n): 100% dos campos com tradução PT-BR — 320 entradas no catálogo, 0 pendências; hints/tooltips por campo com exibição por clique.
- Novo (TEK v2 — Modified+Reset): badge ● ciano e botão ↺ em todos os campos que diferem do padrão ARK — cobertura nos helpers legados e nos cards novos.
- Novo (TEK v2 — Fase 3 CLI): seção 'Avançado — Linha de comando' em Administração com 7 grupos de cards: Inicialização, Rede/plataformas, Segurança, Performance, Gameplay CLI, Logs de admin, Web Alarm.
- Novo (TEK v2 — Fase 4 Agregados): editores estruturados para HarvestResourceItemAmountClassMultipliers, DinoClassDamage/Resistance, TamedDinoClassDamage/Resistance, DinoSpawnWeightMultipliers, PreventDinoTameClassNames — grupo 'Agregados' na navegação.
- Novo (TEK v2 — Fase 5 SM): seção 'Extensões SM' com ItemStackSizeMultiplier, SpoilingTimeMultiplier, MaxTributeDinos/Items, BabyImprintAmountMultiplier, EnableCreativeMode — grupo 'SM / Avançado' na navegação.
- Novo (TEK v2 — SpawnExact): gerador completo de SpawnExactDino compatível com ArkUtils — species search via Obelisk ASB, 7 stats wild/tamed, 6 regiões de cor, imprint %, blueprints favoritos, histórico, presets, copiar e enviar via RCON.
- Novo (TEK v2 — Obelisk): cliente Python para o manifest ArkUtils Obelisk (values.json) com cache local, deduplicação e exibição de variantes (Alpha, Boss…).
- Novo (TEK v2 — Arquivos do Servidor): cards individuais para Administradores, Whitelist e Exclusive Join com contador dinâmico de IDs e botão 'Colar ID(s)'.
- Novo (SpawnExact — CustomShop): botão 'Adicionar ao Kit' exporta o comando SpawnExactDino diretamente para um kit do config.json da loja.

### Fix

- Fix (Loja/WebStore): aba Web Store carregava incompleta — NameError em _save_shop_from_ui (acesso a _port_var antes de sua criação); CTkEntry não aceita command= (ValueError); ambos corrigidos.
- Fix (Loja/WebStore): URL central agora populada diretamente de resolve_central_url(shop) na inicialização, sem chamar _save_shop_from_ui antes de todos os widgets existirem.

## [1.7.6] - 2026-06-10

### Improvement

- Melhoria (Start): aviso ao iniciar servidor em v358.x (fora do branch preaquatica) com opção de atualizar via SteamCMD antes do start.

### Fix

- Fix (ASM/launch): SessionName removido da CLI — RunServer.cmd passa pelo cmd.exe que expandia %20/%5B e corrompia nomes (ex: BBRDBARKLANDDBPVEDB5X…). Nome só no INI.
- Fix (ASM/launch): RunServer.cmd escapa % como %% para evitar corrupção de argumentos.
- Fix (SteamCMD): Instalar/Atualizar usa validate automaticamente quando a pasta já tem servidor — força manifest e arquivos atualizados.

## [1.7.5] - 2026-06-09

### Feature

- Novo (Loja): botão 📦 Instalar CustomShop — copia DLLs embutidas do app para ArkApi/Plugins/CustomShop/ em todos os servidores (config.json existente preservado).
- Novo (Loja): suporte TEK — painel Web Store lista servidores asm_config_manager e config_manager com indicador de instalação do plugin.

### Improvement

- Melhoria (Loja): Aplicar em todos os plugins e registro arkshop_web incluem servidores TEK; AsmServerConfig ganha shop_server_id e customshop_config_path.

## [1.7.4] - 2026-06-10

### Improvement

- Melhoria (SteamCMD): aviso quando a pasta de instalação já contém servidor antigo; log exibe build Steam ao concluir.

### Fix

- Fix (SteamCMD/TEK): +force_install_dir agora vem ANTES de +login — ordem exigida pela Valve; ordem errada fazia servidor instalar/atualizar na versão antiga (ex: 358.24).
- Fix (SteamCMD/TEK): instalação ao criar servidor usa validate e verifica appmanifest_376030.acf na pasta configurada.

## [1.7.3] - 2026-06-10

### Fix

- Fix (ASM/SessionName): fallback automático — se 'Nome da sessão' estiver vazio, usa o nome do servidor no gerenciador (card/sidebar) para INI e CLI.
- Fix (ASM/import): corrigida leitura de SessionName ao importar servidor existente (bug lia MaxPlayers em vez de SessionName e podia zerar o nome).

## [1.7.2] - 2026-06-10

### Fix

- Fix (ASM/INI): SessionName com colchetes/espaços agora gravado entre aspas — valores como [ARKLAND] Teste quebravam o parser do ARK e geravam 'ARK #NNNNNN'.
- Fix (ASM/INI): SessionName duplicado em [SessionSettings] e [ServerSettings]; escrita UTF-16 nativa (sem configparser.write).
- Fix (ASM/launch): ?SessionName= na CLI com percent-encoding (%20, %5B…) — funciona com espaços e caracteres especiais sem quebrar o cmd.exe.

## [1.7.1] - 2026-06-10

### Improvement

- Melhoria (SteamCMD): log imediato e janela visível ao baixar servidor/mods — feedback antes da auto-atualização do SteamCMD (1–2 min).
- Melhoria (Mods): um único SteamCMD para todos os mods da lista (antes: 1 por mod).
- Melhoria (TEK): botão 📁 na pasta de instalação ao criar servidor; pergunta se deseja instalar o servidor agora após criar.

### Fix

- Fix (ASM/launch): restaurado ?SessionName= na CLI para nomes sem espaços — regressão da v1.7.0 causava nome genérico 'ARK #NNNNNN' na listagem.
- Fix (ASM/INI): MaxPlayers gravado em [/Script/Engine.GameSession] (seção correta do ASM).
- Fix (ASM/start): Iniciar/Restart pelo dashboard ou card agora sincroniza o painel aberto antes de gravar INI e lançar o servidor.

## [1.7.0] - 2026-06-10

### Feature

- Novo (Loja): arquitetura multi-máquina — uma loja web central (host) e apps cliente na LAN apontando para o mesmo arkshop_web e API key.
- Novo (Loja): entrega in-game via plugin CustomShop — compras ficam PENDENTES na web e são entregues automaticamente ao jogador (GiveItem/GiveKit), sem mod MX-E Ark Shop UI nem dependência do ArkShop original.
- Novo (Loja): painel 🛒 Loja reformado — aba Web Store (modo Host/Cliente), teste de conexão, sync de catálogo e botão Aplicar em todos os plugins.

### Improvement

- Melhoria (Plugin): CustomShop recompilável — HttpClient, build_cl.bat e CustomShop.vcxproj alinhados; DLL embutida no instalador do app.

### Fix

- Fix (Loja): API /api/pending e /api/pending/delivered corrigidas para entrega via fila do plugin (delivery_mode=plugin por padrão).
- Fix (ASM/launch): SessionName removido permanentemente da CLI — nome do servidor fica somente no GameUserSettings.ini ([SessionSettings]/SessionName).
- Fix (ASM/INI): DifficultyOffset gravado apenas quando enable_difficulty_override=True.

## [1.6.0] - 2026-06-06

### Feature

- Novo (Crash Monitor): aba 'Crashes' por servidor com cards em tempo real — timestamp, tipo (crash/falha de início), call stack, botão 'Marcar visto'. Dados persistidos em data/crashes.json entre sessões.
- Novo (Crash Monitor): página global 'Crashes' no menu lateral mostra todos os servidores em um só lugar, com filtro por servidor e contagem de não vistos.
- Novo (Crash Monitor): badge [N] ao lado de 'Crashes' na sidebar atualiza em tempo real via callback quando qualquer servidor crasha.

### Improvement

- Melhoria (Navegação): trocar de página não reconstrói mais os frames — uso de grid_remove/grid em vez de destroy/recreate. Navegação instantânea.
- Melhoria (Painel): seções de configuração abertas sob demanda (lazy loading) — startup mais rápido, menos uso de memória em repouso.

### Fix

- Fix: _try_psutil() no gráfico de performance retornava sempre True em vez de _PSUTIL_OK — métricas de CPU/RAM podiam falhar silenciosamente sem psutil.
- Fix: watermark de background usava PIL.Image diretamente em vez do alias _PILImage, causando NameError em builds sem PIL no namespace global.

## [1.5.13] - 2026-06-02

### Fix

- Fix (ASM/launch): removido check de processo pré-existente do _start_worker. Antes: ao clicar Iniciar, se o servidor já estivesse rodando (iniciado manualmente ou por outra ferramenta), o app reutilizava o processo sem reiniciar — o GUS.ini recém-escrito nunca era relido pelo servidor, resultando em nome 'ARK #902606' ao invés do nome configurado. Agora o Start sempre lança um novo processo.
- Fix (ASM/launch): SessionName também incluído na travel URL da CLI quando não contém espaços (?SessionName=Nome), além do GUS.ini — garante dupla cobertura para nomes sem espaço.

## [1.5.12] - 2026-06-01

### Fix

- Fix (ASM/ini): INI escrito com 'key=value' sem espaços ao redor do '=' — formato nativo do ARK. Antes: 'key = value' (configparser padrão).

## [1.5.11] - 2026-05-31

### Fix

- Fix (ASM/painel): Iniciar e Restart agora sincronizam silenciosamente os campos da UI (install_dir, session_name, portas, etc.) para o cfg antes de iniciar — sem dialog, sem salvar no JSON. Resolve: nome errado no servidor ('ARK #200440'), servidor não listando, validação falhando por install_dir vazio.

## [1.5.10] - 2026-05-31

### Fix

- Fix (ASM/painel): botões Iniciar e Restart não salvam mais automaticamente. Salvar é ação exclusiva do botão Salvar.

## [1.5.9] - 2026-05-31

### Fix

- Fix (ASM/launch): cluster ID agora gerado como flag '-clusterid=ID' em vez de URL param '?ClusterId=ID'. O ARK ignora '?ClusterId=' completamente — confirmado pelo servidor saudável de referência e pelo primitivo (src/server_config.py).
- Fix (ASM/launch): 'cluster_dir_override' agora incluído no comando como '-ClusterDirOverride=PATH'. O campo existia no dataclass mas não era usado no build_launch_args.
- Fix (ASM/launch): removido '?PreventDownloadItems=False' da CLI — parâmetro não existe no ARK e não consta em nenhuma referência válida.

## [1.5.8] - 2026-05-31

### Fix

- Fix (ASM/launch): parâmetros de mapa (MAP?Port=?QueryPort=...) não devem ser envolvidos em aspas. O parser de command line do Unreal Engine (ARK) lê o token raw e incluía as aspas literalmente, fazendo com que ?Port=, ?QueryPort=, ?AltSaveDirectoryName= e outros parâmetros fossem ignorados. Como SessionName foi removido da CLI (v1.5.5) não há mais espaços no map string.
- Fix (ASM/launch): adicionado /min ao comando start do RunServer.cmd — janela do servidor inicia minimizada, igual ao comportamento do servidor saudável de referência.

## [1.5.7] - 2026-05-31

### Fix

- Fix (ASM): parâmetro AltSaveDir corrigido para AltSaveDirectoryName — ARK ignorava silenciosamente o parâmetro errado, resultando no mapa de saves padrão em vez da pasta configurada.
- Fix (ASM/INI): arquivos GameUserSettings.ini e Game.ini agora são gravados em UTF-16 LE (exigido pelo ARK no Windows). Gravação em UTF-8 causava leitura incorreta de algumas chaves como SessionName.
- Fix (ASM/INI): leitura dos arquivos INI agora tenta UTF-16, UTF-8 BOM, UTF-8 e latin-1 em ordem — compatível com arquivos criados pelo ARK, pelo ARKLAND e por editores externos.

## [1.5.6] - 2026-05-31

### Fix

- Fix (ASM): campo IP Bind (MultiHome) não é mais preenchido automaticamente ao abrir o painel — o campo fica vazio por padrão (ARK escuta em todas as interfaces). O botão 'Detectar IP' continua disponível para uso manual quando necessário.
- Fix (ASM/INI): StructureDamageRepairCooldown movido para GameUserSettings.ini [ServerSettings] (estava incorretamente em Game.ini).
- Fix (ASM/INI): RandomSupplyCratePoints corrigido para bRandomSupplyCratePoints (prefixo 'b' obrigatório).

## [1.5.5] - 2026-05-31

### Fix

- Fix (ASM): corrigida causa raiz do servidor não iniciar — SessionName com espaços (ex: '[ARKLAND] Teste Server') quebrava o parsing do cmd.exe pois o mapa+opções não estava entre aspas. Agora o combined_map é gerado corretamente entre aspas conforme documentação oficial do ARK.
- Fix (ASM): removido SessionName da linha de comando (já está no GameUserSettings.ini). Colocar duplicado causava conflito.

## [1.5.4] - 2026-05-31

### Fix

- Fix (ASM): campo IP Bind (MultiHome) agora é verdadeiramente opcional — removido da validação obrigatória. O servidor inicia normalmente sem IP preenchido (ARK escuta em todas as interfaces por padrão).
- Fix (ASM): removido asterisco e placeholder enganoso do campo IP Bind.

## [1.5.3] - 2026-05-31

### Fix

- Fix (ASM): MultiHome (IP Bind) removido do mapa de INI — não deve ser escrito no GameUserSettings.ini. O valor continua sendo passado apenas como argumento de linha de comando (?MultiHome=IP), que é o comportamento correto do ARK.

## [1.5.2] - 2026-05-31

### Fix

- Fix (ASM): deteccao de IP para MultiHome corrigida — agora usa o IP da interface de rede local (socket) em vez do IP externo/publico. MultiHome precisa do IP local (ex: 192.168.x.x) para o servidor fazer bind corretamente; usar o IP publico do roteador causava crash instantaneo.
- Fix (ASM): mensagem de validacao e placeholder atualizados para orientar o IP correto (IP local, nao IP externo).

## [1.5.1] - 2026-05-31

### Feature

- Feat (ASM): deteccao automatica de IP publico no campo IP Bind (MultiHome) — botao Detectar IP consulta ipify/checkip/icanhazip e preenche o campo automaticamente.
- Feat (ASM): se o campo IP Bind estiver vazio ao abrir o painel do servidor, a deteccao e disparada automaticamente.

## [1.5.0] - 2026-05-31

### Fix

- Fix (ASM): validacao de configuracao obrigatoria antes de iniciar servidor — bloqueia start se install_dir, session_name, admin_password ou IP Bind (MultiHome) estiverem vazios.
- Fix (ASM): campo IP Bind (MultiHome) marcado como obrigatorio (*) com placeholder de ajuda na UI.

## [1.4.9] - 2026-05-31

### Fix

- Fix (ASM): lancamento do servidor agora usa RunServer.cmd + ShellExecute identico ao modo PRIMITIVE — remove __COMPAT_LAYER antes do startfile para evitar crash no CheckOnTimerCallbacks (ArkShopUI/ArkApi).
- Fix (ASM): stop agora usa taskkill /F /T para encerrar toda a arvore de processos (incluindo filhos criados pelo cmd.exe start).

## [1.4.8] - 2026-05-31

### Fix

- Fix (ASM): SessionName agora incluido nos argumentos de inicializacao do servidor — nome aparece corretamente na lista de servidores.
- Fix (ASM): parametro AltSaveDir corrigido (era AltSaveDirectoryName).

## [1.4.7] - 2026-05-31

### Fix

- Fix (ASM): salvar configuracoes no painel agora escreve imediatamente os arquivos GameUserSettings.ini e Game.ini do servidor.

## [1.4.6] - 2026-05-31

### Fix

- Fix (ASM): inicializacao do servidor abre janela CMD visivel com saida do processo.

## [1.4.5] - 2026-05-31

### Feature

- Novo (UI): marca d'agua do logo ARKLAND exibida em todas as paginas do app.
- Novo (ASM - Toolbar): botao Log adicionado na toolbar de ferramentas de cada servidor — exibe ShooterGame.log com auto-refresh, colorização e seguir fim.

## [1.4.4] - 2026-05-31

### Fix

- Fix (ASM - SteamCMD): instalacao do servidor agora respeita o caminho definido; argumentos passados como tokens separados ao Popen (fix force_install_dir ignorado).

## [1.4.3] - 2026-05-31

### Feature

- Novo (ASM - Painel): status de instalacao de cada mod exibido em tempo real.
- Novo (app): sync e agente remoto iniciados automaticamente ao abrir o app se configurados.

### Fix

- Fix (UI - Modo Claro): corrigidas cores hardcoded escuras no card de servidor, dashboard, badges de status, chips, toolbar, botoes de acao, icones dos stats, cabecalhos de grupo e bulk actions.
- Fix (ASM - Mods): _copy_mod_to_server agora trata subpasta WindowsNoEditor/ e cria o arquivo .mod exigido pelo ARK.
- Fix (ASM - Mods): download_mods reporta apenas os mods copiados com sucesso.

## [1.4.2] - 2026-05-31

### Feature

- Novo (UI): modo claro (Light Mode) — botão ☀ Claro / 🌙 Escuro na sidebar, preferência persistida em ui_prefs.json.

### Fix

- Fix (ASM — SteamCMD): caminho do steamcmd.exe configurado em Configurações agora é lido corretamente em Redownload Mods, Baixar Mods, Instalar Servidor, Validar e Workshop.
- Fix (sidebar — servidores): servidor adicionado pelo diálogo + não aparecia na lista lateral; corrigido para todos os 3 modos de importação.

## [1.4.1] - 2026-05-31

### Feature

- Novo (ASM TEK — Mods): gerenciador de mods com tabela de 3 colunas — ID editável, nome e data de atualização preenchidos automaticamente via Steam Workshop API (POST GetPublishedFileDetails). Botões: '+ Mod', 'Buscar Info' (async thread), 'Redownload Mods' (SteamCMD) e 'Validar IDs' (marca IDs inválidos com ❌). Cache por sessão evita consultas redundantes.
- Novo (UI): watermark de fundo — logo ark_manager.png exibida em 600×400 px na área principal com 6% de opacidade, preservada atrás de todo conteúdo de navegação.

### Fix

- Fix (sidebar — logo): imagem ark_manager.png exibida com proporção correta 3:2 (66×44 px) em vez de quadrado distorcido (44×44).

## [1.4.0] - 2026-05-31

### Feature

- Novo (ASM TEK): Dashboard agrupado por pastas de servidores com headers de grupo e botão 'Iniciar Todos'.
- Novo (ASM TEK): Barra de ações em lote — Selecionar Todos, Iniciar, Parar, Reiniciar e Atualizar Mods para múltiplos servidores.
- Novo (ASM TEK): Sistema de Presets de configuração — salva/aplica/remove presets por categoria (players, dinos, breeding, environment, structures, rules).
- Novo (ASM TEK): Exportar/importar perfil de servidor (.arkprofile) e clonar servidor.
- Novo (ASM TEK): Tribe Log Viewer — visualizador com tail em tempo real, filtros por tipo de evento e exportação.
- Novo (ASM TEK): Importar servidor a partir de instalação existente (lê GameUserSettings.ini/Game.ini/RunServer.bat) ou de arquivo .arkprofile.
- Novo (ASM TEK): Editor visual de Engramas — tabela interativa para OverrideNamedEngramEntries com geração automática de Game.ini.
- Novo (ASM TEK): Gráfico de curva XP + preview de linhas geradas na seção de Progressões de Nível.
- Novo (ASM TEK): Editor visual de Spawner — árvore de containers NPCSpawn com gerenciamento de entradas e serialização Game.ini.
- Novo (ASM TEK): Motor de backup em nuvem — suporte a armazenamento local e Amazon S3 com credenciais protegidas.
- Novo (ASM TEK): Assistente IA contextual — heurísticas offline + integração opcional com OpenAI GPT-4o-mini.
- Novo (ASM TEK): Monitor avançado — gráficos históricos 24h de CPU%, RAM e players + alertas configuráveis com notificação Discord e reinício automático.

## [1.3.57] - 2026-05-27

### Fix

- Fix (src/pages/tab_advanced.py): campo 'Nome da Pasta de Saves' (AltSaveDirectoryName) ficava desabilitado quando um perfil de cluster estava vinculado ao servidor — agora sempre editável, independente do perfil de cluster selecionado.

## [1.3.56] - 2026-05-27

### Fix

- Fix (src/server_config.py + src/asm_engine/asm_server_config.py): valor padrão de AltSaveDirectoryName alterado para 'savegame' — campo vazio ou em branco é normalizado automaticamente para 'savegame' via __post_init__, evitando que servidores iniciem sem diretório de save definido.

## [1.3.55] - 2026-05-27

### Feature

- Feature (pages/tab_chat.py + broadcast_sched_*.py): sistema de broadcasts automáticos por intervalo — nova inner-tab '🕐 Automáticos' na aba Chat/Broadcasts. Cada broadcast automático tem rótulo, mensagem, intervalo em minutos, ativar/desativar, envio imediato e exibição do próximo envio. Loop de tick a cada 30 s garante entregas pontuais sem bloquear a UI. Dados salvos em auto_broadcasts por servidor.
- Feature (mod_changelog_scraper.py + discord_notifier.py + mod_auto_updater.py): notas de atualização de mods enviadas ao Discord. Ao detectar update, o ARKLAND faz scraping do Steam Workshop e inclui as release notes no embed. Suporte a webhook separado para mods (mod_changelog_webhook) em Configurações Globais — se vazio, usa o webhook principal.

### Fix

- Fix (pages/tab_rcon.py + rcon_connect.py): campos editáveis de Host e Porta removidos do console RCON — host e porta agora são lidos diretamente de srv.server_ip e srv.rcon_port, eliminando redundância e possibilidade de divergência.
- Fix (pages/tab_game.py): crash ao abrir aba de jogo — tk.Frame(bg='transparent') substituído por ctk.CTkFrame(fg_color='transparent'). O tkinter nativo não aceita 'transparent' como cor de fundo.

## [1.3.52] - 2026-05-26

### Feature

- Feature (remote_agent.py + pages/): Pareamento LAN — ao clicar em 'Conectar' em uma máquina descoberta na rede local, o ARKLAND envia uma solicitação de autorização para a outra máquina em vez de pedir o token manualmente. Na máquina alvo, um dialog 'Solicitação de Acesso' aparece com botões ✅ Autorizar / ❌ Negar (auto-nega após 60 s). Na máquina solicitante, um dialog de espera faz polling a cada 2 s; ao ser autorizado, a conexão é salva e o controle remoto abre automaticamente. Entrada de token mantida apenas para conexões não-LAN (via código de identidade).

## [1.3.50] - 2026-05-26

### Feature

- Feature (pages/refresh_remote_instances_list.py): botão '✏️' em cada máquina remota salva permite atualizar o token sem remover e re-adicionar a conexão.

### Fix

- Fix crítico (sync_engine.py): token de autenticação do agente remoto agora é sempre buscado em tempo real de config.remote_instances (pelo host+porta), em vez de usar o token congelado dentro do BASE64 do caminho. Resolve 'Não autorizado' persistente mesmo após regenerar o token — sem precisar recriar as pastas nos ciclos.
- Fix (sync_engine.py): se a listagem de qualquer pasta do ciclo falhar (ex: 401, timeout), o ciclo inteiro é abortado imediatamente. Antes, a pasta remota era tratada como vazia e o engine tentava copiar todos os arquivos locais para lá, gerando flood de erros 'Cópia X: Não autorizado' e WinError 10053/10054.
- Fix (pages/add_sync_folder.py): novas pastas remotas agora usam formato '@remote:HOST:PORT|path' em vez de '@remote|BASE64|path' — elimina o token do caminho salvo. Pastas antigas no formato legado continuam funcionando normalmente.
- Fix (pages/welcome_screen.py + app.py): modo TEK removido da tela inicial e bloqueado no backend (_launch_mode).
- Fix crítico (ark_ini.py): seções do Game.ini com nomes em case diferente (ex: '[/script/shootergame.shootergamemode]' vs '[/Script/ShooterGame.ShooterGameMode]') eram tratadas como seções distintas pelo configparser, causando duplicação de seção ao salvar e leitura de valores padrão ao carregar (configs apareciam 'desmarcadas' após reiniciar). Nova função _normalize_section_case() unifica a seção para o nome canônico antes de leitura e escrita — elimina a duplicação e restaura os valores corretamente.

## [1.3.49] - 2026-05-26

### Feature

- Feature (pages/add_sync_cycle.py + sync_engine.py): filtro 'Apenas nomes numéricos' por ciclo de sync. Quando marcado, somente arquivos com nome puramente numérico (ex: Steam IDs de cluster ARK) são sincronizados. Config salva como dict com campo 'numeric_only'; formato legado (lista de paths) mantido compatível.

### Fix

- Fix (remote_agent.py): fs_list agora propaga erros HTTP (401, 500 etc.) em vez de retornar lista vazia silenciosamente. Antes, um 401 fazia o sync enxergar a pasta remota como vazia e tentar copiar tudo, resultando em flood de erros 'Não autorizado'.
- Fix (pages/start_remote_agent.py): token do agente é gerado automaticamente (secrets.token_urlsafe) se estiver vazio ao ativar o agente. Evita que o agente rejeite todas as requisições por falta de token.
- Fix (pages/tab_plugins.py): removido 'Plugin Limit Fix' do catálogo de sugestões — é um plugin para ARK: Survival Ascended (ASA), não compatível com ASE/ArkApi.

### Refactor

- Refactor (pages/start_remote_agent.py + remote_panel.py): token encurtado de UUID (36 chars) para secrets.token_urlsafe(12) (16 chars). Tokens existentes continuam funcionando sem necessidade de regeneração.

## [1.3.48] - 2026-05-26

### Feature

- Feature (sync_engine.py + remote_agent.py): sincronização remota de pastas entre máquinas na mesma rede. Endpoints GET /fs/list, GET /fs/read e POST /fs/write adicionados ao RemoteAgent; SyncEngine refatorado com abstrações _LocalSyncFolder e _RemoteSyncFolder. Caminhos remotos usam prefixo @remote|IDENTITY_CODE|PATH.
- Feature (remote_agent.py): descoberta automática de instâncias ARKLAND na rede local via UDP broadcast (porta 32441). Classe UdpDiscovery anuncia nome/IP/porta a cada 30 s e mantém lista de peers com TTL de 90 s. Token não é transmitido.
- Feature (pages/remote_panel.py): seção 'Descoberta na Rede (LAN)' na aba Acesso Remoto. Lista instâncias detectadas automaticamente; botão Conectar pede apenas o token (sem copiar código base64). Atualização automática a cada 6 s.
- Feature (pages/add_sync_folder.py): botão de pasta remota (ἱ0) em cada linha de ciclo de sync. Diálogo seleciona instância remota salva + caminho na máquina remota. Entry exibe o caminho em modo readonly quando remota.

### Fix

- Fix (pages/ini_paste_section.py): 'Colar Seção' não importava parse_ini_text_to_sections — NameError silencioso impedia a importação de qualquer conteúdo. Corrigido o import; placeholder atualizado para mostrar exemplo com múltiplas seções.

## [1.3.47] - 2026-05-26

### Fix

- Fix (mod_auto_updater.py): logs de download de mods não apareciam no painel de Atualização Automática. Chamadas a download_mods em _install_missing_mods e _handle_mod_update não passavam on_log=self._log, descartando silenciosamente todas as mensagens do SteamCMD e status de instalação.
- Fix (pages/ini_import.py): 'Importar INI do Disco' falhava silenciosamente ao abrir — import 'from .ark_ini' apontava para src/pages/ (inexistente) em vez de src/. Corrigido para 'from ..ark_ini' nas duas ocorrências (default_dir e _load_from_folder).
- Fix (pages/fetch_mod_names_async.py): nomes de mods nunca eram carregados após adicionar IDs — urllib.parse e urllib.request usados mas não importados. A exceção NameError era engolida pelo except genérico, resultando em IDs sem nome na lista de mods.

## [1.3.46] - 2026-05-26

### Feature

- Feat (add_mod.py, tab_mods.py): suporte a múltiplos IDs no campo de mods da aba principal — cole IDs separados por vírgula (ex: 731604991, 880871931) para adicionar todos em lote de uma vez sem precisar abrir o diálogo de busca.
- Feat (mod_search_dialog.py): busca em lote no Steam Workshop — ao colar múltiplos IDs separados por vírgula no campo de busca, o diálogo faz uma única chamada à API e lista todos os mods encontrados com nome, ID e botões individuais '➕ Adicionar'. Botão 'Adicionar Todos (N)' no topo adiciona toda a lista e fecha o diálogo.

### Fix

- Fix (rcon_client.py): removida abordagem de sentinel no protocolo RCON. O sentinel (EXECCOMMAND vazio enviado logo após o comando real) podia ser respondido pelo ARK antes da resposta do comando principal, causando retorno vazio para ListPlayers e outros comandos mesmo com jogadores conectados. Substituído por espera direta com timeout de 3s e matching por packet ID; pacotes órfãos de comandos anteriores são descartados automaticamente.
- Fix (broadcast_rcon.py): corrigido AttributeError 'module datetime has no attribute now' — import trocado de 'import datetime' para 'from datetime import datetime'. Corrigido também import ausente de RconClient que causava NameError ao enviar Broadcast via conexão temporária (servidor sem RCON aberto no console).
- Fix (rcon_exec.py): feedback do console RCON melhorado — comandos executados com sucesso mas sem retorno (SaveWorld, Broadcast, DoExit…) exibem '(ok)' em verde em vez de '(sem resposta)', distinguindo execução bem-sucedida de erro real.

## [1.3.45] - 2026-05-25

### Feature

- Feat (tab_general.py): seleção de branch SteamCMD por botões rápidos na aba Geral. Botões '✅ Padrão (Estável)' e '🦕 Pre-Aquatica' definem o campo branch_name automaticamente. Campo de texto permanece visível para branches personalizadas. Seleção 'preaquatica' instrui o SteamCMD a baixar a versão ASE pré-Aquatica (compatibilidade com ArkShopUI V1.x e plugins ASE antigos).
- Feat (build_server_card.py): card do servidor exibe a versão instalada: '✅ Versão: Padrão (Estável)', '🦕 Versão: Pre-Aquatica' ou '🎮 Branch: <nome>' para branches personalizadas.

## [1.3.44] - 2026-05-25

### Fix

- Fix (server_manager.py): remoção de __COMPAT_LAYER do ambiente do processo antes de iniciar o servidor. O Windows aplica o shim DetectorsAppHealth ao ARKLAND-Multi.exe, que era propagado via ShellExecute para o ShooterGameServer.exe. Com o shim ativo, o SEH do ArkApi era interceptado e exceções recuperáveis no CheckOnTimerCallbacks viravam crash fatal do servidor. O ASM não sofre esse problema por não ter o shim aplicado. Corrigido removendo temporariamente __COMPAT_LAYER antes do os.startfile() e restaurando após.

## [1.3.43] - 2026-05-25

### Feature

- Feat (dialogs/mod_download_dialog.py): popup de progresso de download de mods. Ao clicar em 'Baixar / Atualizar Todos os Mods' ou no botão de download individual, um dialog exibe a lista de mods com status em tempo real (Aguardando → Baixando... → Instalado / Erro). O SteamCMD é aberto em janela própria visível mostrando o download. Após o SteamCMD encerrar, mensagens de cópia e geração do .mod aparecem no log do dialog. Botão 'Fechar' permanece desabilitado até a operação concluir.

## [1.3.42] - 2026-05-25

### Fix

- Fix (mod_manager.py + server_manager.py): fallback de geração de .mod reativado como último recurso. Quando o arquivo .mod oficial do Steam Client não está disponível no cache local (mods baixados via SteamCMD sem estar subscrito no Steam Client), o ARKLAND gera o .mod a partir do mod.info com modPath vazio (formato correto). Não é mais necessário re-baixar mods pelo Steam Client para que o servidor inicie.

## [1.3.41] - 2026-05-25

### Fix

- Fix (server_manager.py): reparo automático de arquivos .mod ao iniciar servidor. A cada start, o ARKLAND copia o .mod oficial do Steam Client para o diretório ShooterGame/Content/Mods/ de cada mod configurado no servidor. Cobre dois casos: (1) arquivo .mod ausente (deletado ou nunca criado); (2) arquivo .mod gerado por versões anteriores do ARKLAND com modPath incorreto (T11). Não é mais necessário copiar manualmente o .mod antes de testar.

## [1.3.40] - 2026-05-25

### Feature

- Feat (mod_auto_updater.py + config_manager.py + global_config.py): suporte a Steam Web API Key nas configurações globais. A key é enviada nas requisições ao ISteamRemoteStorage/GetPublishedFileDetails para verificação de atualizações de mods. Campo adicionado na aba Configurações Globais com hint para steamcommunity.com/dev/apikey.

### Fix

- Fix (mod_manager.py — T11): ARKLAND não gera mais arquivos .mod — usa exclusivamente o .mod oficial do Steam Client. Arquivos .mod gerados pelo ARKLAND tinham modPath preenchido (../../../ShooterGame/Content/Mods/<id>), enquanto o arquivo oficial do Steam Client tem modPath vazio. Esse desvio causava falha no mount do VFS do mod pelo ARK, deixando a classe Blueprint do buff ArkShopUI_Buff_FCAS como null e resultando em crash no timer callback (~5 min após jogador conectar). Novo método _find_official_dot_mod() localiza o .mod correto via registro do Windows + libraryfolders.vdf. Novo método repair_mod_files() substitui .mod incorretos de mods já instalados pelo arquivo oficial.

## [1.3.39] - 2026-05-23

### Fix

- Fix (plugin): plugin CustomShop descontinuado e removido do projeto. Hipótese T10: o hook HandleNewPlayer do CustomShop chamava InitPlayer + GetOrAddShopBuff() a cada jogador conectado, podendo corromper o estado interno do ArkShopUI.dll e causar crash no timer callback (~5 min após jogador entrar). Aba Plugins reimplementada: exibe os 5 plugins oficiais ASE (Server API, Permissions, ArkShop, ArkShopUI, Plugin Limit Fix) com botão 'Download' (abre página oficial) e botão 'Instalar' (seleciona ZIP ou DLL e extrai para o diretório correto do servidor).

## [1.3.38] - 2026-05-23

### Fix

- Fix (server_config.py): causa raiz do crash ArkShopUI.dll encontrada após 8 tentativas. O ARKLAND passava mods por dois canais ao mesmo tempo: ?GameModIds= na linha de comando E ActiveMods= no GameUserSettings.ini. O ASM usa apenas ActiveMods= no INI. Isso alterava a sequência de inicialização dos mods e deixava o ArkShopUI.dll em estado inválido, causando crash no timer callback (~5 min após jogador conectar). ?GameModIds= removido de build_launch_args(); mods carregados exclusivamente via ActiveMods= no INI.

## [1.3.37] - 2026-05-22

### Fix

- Fix (server_manager.py): Tentativa 8 — método de lançamento do servidor replicado exatamente do ASM. ASM usa UseShellExecute=true (os.startfile() em Python) para lançar RunServer.cmd, o que usa ShellExecute do Windows e não herda env, handles ou job objects do processo pai. Conteúdo de RunServer.cmd também atualizado para ser idêntico ao gerado pelo ASM: start "<nome>" /normal <cmd>. Resolve possível causa de crash do ArkShopUI.dll via herança de handles do PyInstaller.

## [1.3.36] - 2026-05-22

### Fix

- Fix (server_manager.py): servidor agora é lançado via cmd.exe /c RunServer.cmd — método idêntico ao ASM (start "ARK Server" /min /normal). O RunServer.cmd era gerado mas não usado para lançar o servidor. O PID do ShooterGameServer.exe é rastreado via psutil após o cmd.exe sair. Adicionadas _PsutilProcessWrapper e _find_server_process para compatibilidade. Tentativa de resolver crash ArkShopUI.dll no timer callback (~5 min após start).

## [1.3.34] - 2026-05-22

### Fix

- Fix (server_manager.py): remove variáveis PyInstaller do ambiente do servidor — TCL_LIBRARY, TK_LIBRARY, _PYI_*, __COMPAT_LAYER (DetectorsAppHealth), CHROME_CRASHPAD_PIPE_NAME. O __COMPAT_LAYER herdado do ARKLAND aplicava shims de compatibilidade do Windows ao ShooterGameServer.exe, podendo interferir no SEH do ArkApi e converter exceções internas em crashes fatais no CheckOnTimerCallbacks (ArkShopUI).
- Fix (server_manager.py): RunServer.cmd agora gerado com 'start "ARK Server" /min /normal' — formato idêntico ao ASM.

## [1.3.33] - 2026-05-22

### Feature

- Feat (server_manager.py): gera RunServer.cmd em ShooterGame/Saved/Config/WindowsServer/ (padrão do ASM) a cada inicialização do servidor.

### Fix

- Fix (server_manager.py): flag CREATE_BREAKAWAY_FROM_JOB adicionada ao Popen — servidor sai do job object do PyInstaller/ARKLAND e roda completamente independente, igual ao lançamento manual. Possível causa raiz do crash ArkShopUI.dll.

## [1.3.32] - 2026-05-22

### Other

- Debug (server_manager.py): ao iniciar servidor, grava '_arkland_debug.txt' em Binaries/Win64 com PATH completo, todas variáveis de ambiente e commandline — para diagnóstico do crash ArkShopUI.dll. O caminho do ArkApi.log também é exibido na aba Logs.

## [1.3.31] - 2026-05-22

### Feature

- Feat (remote_panel.py): botão '🔒 Firewall' cria regra de entrada TCP no Windows Defender Firewall via UAC (netsh advfirewall, profile=any) sem precisar abrir o painel de firewall manualmente.

### Fix

- Fix (remote_panel.py): botão 'Testar' agora testa 127.0.0.1 E o IP LAN local — exibe diagnóstico preciso: 'responde local mas não na LAN' indica Windows Firewall bloqueando por perfil.

## [1.3.30] - 2026-05-22

### Feature

- Feat (remote_panel.py): botão 'Testar' no painel do agente — ping local imediato com instruções sobre Windows Firewall.

### Fix

- Fix (remote_agent.py): is_running agora verifica se a thread do servidor está viva (_thread.is_alive()), evitando falso positivo quando o servidor morre silenciosamente.
- Fix (remote_agent.py): endpoint GET /ping sem autenticação adicionado — permite teste de alcance sem token.
- Fix (start_remote_agent.py): autodiagnóstico após start — após 2 s testa 127.0.0.1:porta e exibe aviso detalhado se não responder (Windows Firewall).
- Fix (remote_control_dialog.py): mensagem 'Sem resposta' agora menciona Firewall do Windows.

## [1.3.29] - 2026-05-22

### Fix

- Fix (tab_crashes.py + server_manager.py): aba Crashes agora detecta todos os tipos de crash — além de pastas com .dmp, parseia blocos 'Fatal error!' do ShooterGame.log como registros sintéticos; registros de log exibem badge '[ShooterGame.log]' e botão 'Abrir log' em vez de 'Abrir pasta'.

### Other

- Debug (server_manager.py): logging ENV-DEBUG adicionado antes do Popen — exibe sys._MEIPASS, entradas _MEI* residuais no PATH e localização de z.dll/libmariadb.dll para rastrear causa raiz do crash ArkShopUI.

## [1.3.28] - 2026-05-22

### Fix

- Fix (server_manager.py): servidor iniciado com CREATE_NEW_CONSOLE e ambiente sem _MEIPASS no PATH — elimina herança de DLLs do PyInstaller que causavam crash fatal (ArkShopUI timer callback) ao conectar jogadores.
- Fix (plugin_manager.py): uninstall() agora remove libmariadb.dll e z.dll que install() havia copiado para Win64/.
- Fix (plugin_manager.py): novo método cleanup_stale_win64_dlls() remove DLLs residuais do CustomShop quando o plugin não está instalado.
- Fix (app.py): _cleanup_stale_plugin_dlls() chamado no startup para limpar automaticamente servidores já afetados.

## [1.3.27] - 2026-05-22

### Fix

- Fix (remote_control_dialog.py): race condition em _poll() — ao fechar a janela de controle remoto enquanto uma tentativa de conexão estava pendente (timeout de 6 s), win.after() era chamado num widget já destruído, causando TclError silencioso no thread daemon.
- Fix (remote_control_dialog.py): mensagens de erro de conexão agora são traduzidas para PT-BR (urlopen timed out → sem resposta; connection refused → agente não rodando; 401 → token inválido).

## [1.3.26] - 2026-05-22

### Fix

- Fix (add_server_dialog.py): ARK_MAP_NAMES, ARK_MAPS e ServerConfig não importados — dialog 'Novo Servidor' lançava NameError ao abrir (list comprehension do ComboBox de mapa) e ao criar o servidor; imports adicionados de server_config.py.

## [1.3.25] - 2026-05-21

### Fix

- Fix (remote_control_dialog.py): RemoteClient não importado — janela de controle remoto abria vazia pois a criação do client lançava NameError; import adicionado de remote_agent.py.

## [1.3.24] - 2026-05-21

### Fix

- Fix (start_remote_agent.py): RemoteAgent não importado — botão 'Ativar Agente' lançava NameError silencioso; import adicionado de remote_agent.py.

## [1.3.23] - 2026-05-21

### Fix

- Fix (ini_import.py): dialog 'Importar INI do Disco' com geometry 620x220 cortava o campo de pasta e os botões — altura aumentada para 280.
- Fix (get_cluster_health.py): 'from .server_config import ClusterProfile' corrigido para 'from ..server_config' — botão Diagnosticar Cluster lançava NameError ao abrir.
- Fix (server_save.py): SERVER_STATUS_STOPPED, snapshot_server, diff_snapshots, _ARK_EVENT_LABEL_TO_ID e ArkIniManager não importados — salvar configurações e iniciar servidor falhavam silenciosamente.

## [1.3.22] - 2026-05-21

### Fix

- Fix (tab_general.py): scroll.unbind('<Configure>') nunca revinculado após build — layout de 2 colunas e scroll restaurados ao adicionar scroll.bind + scrollregion ao final da função.
- Fix (tab_advanced.py): NameError 'profiles' na linha 136 impedia renderização da aba Avançado e bloqueava restauração do scroll; profiles/profile_names agora definidos antes do uso.
- Fix (tab_crashes.py): import relativo 'from .server_manager' corrigido para 'from ..server_manager'.
- Fix (tab_plugins.py): 'ttk' não importado (NameError ao abrir aba Plugins); 'webbrowser' ausente (NameError ao instalar Permissions) — ambos adicionados.
- Fix (on_update_result.py): APP_VERSION não importado — verificador de atualizações lançava NameError ao receber resposta do servidor.
- Fix (tab_game.py): 'from .ark_ini' corrigido para 'from ..ark_ini' (_level_to_xp usada em _level_cap_row).
- Fix (get_change_logger.py): ChangeLogger importado apenas em TYPE_CHECKING — movido para import de runtime para evitar NameError ao acessar aba Histórico.

### Refactor

- Refactor (arquitetura): app.py monolítico (~13.000 linhas) desmembrado em 170+ módulos especializados em src/pages/ e 9 diálogos em src/dialogs/ — cada funcionalidade agora em arquivo próprio (tab_general, tab_game, tab_advanced, tab_spawns, tab_loot, tab_mods, tab_plugins, tab_ini_mods, tab_rcon, tab_chat, tab_logs, tab_crashes, tab_backup, build_tab_admins, build_tab_historico, build_tab_jogadores, server_panel, server_save, sidebar, performance_panel, remote_panel, cluster_detail, broadcast_*, ini_*, rcon_*, chat_*, player_*, buff_*, backup_*, etc.).
- Refactor (ui_constants.py): paleta de cores, Tooltip, _resource_path e constantes de UI extraídas do app.py para módulo compartilhado; importado por app.py, pages/ e dialogs/.
- Refactor (app.py): reduzido a ~1.000 linhas de orquestrador puro — apenas inicialização, bind de métodos de conexão e roteamento; toda lógica de UI delegada via imports lazy a pages/ e dialogs/.
- Refactor (server_panel.py): construção de abas lazy via _on_tab_change + placeholder 'Carregando...' — abas só são construídas na primeira vez que o usuário as visita.

## [1.3.21] - 2026-05-21

### Feature

- Feat (Paridade ASM — ServerGameSettings): ~35 novos campos GUS [ServerSettings]: tamed_dino_damage/resistance_multiplier, dino_character_stamina_drain_multiplier, dino_turret_damage_multiplier, max_personal_tamed_dinos, day/night cycle speed scales, disable_weather_fog, allow_pvp/pve_gamma, allow_hit_markers, disable_imprint_dino_buff, allow_anyone_baby_imprint_cuddle, allow_flying_stamina_recovery, prevent_mate_boost, allow_multiple_attached_c4, estruturas/decay (auto_destroy_decayed_dinos, pve_dino_decay_period_multiplier, disable_dino_decay_pvp, pvp_structure_decay, max_structures_visible, max_platform_saddle_structure_limit, etc.), allow_cave_building_pve, enable_diseases, allow_tribe_alliances, override_npc_network_stasis_range_scale.
- Feat (Paridade ASM — ServerAdvancedSettings): ~40 novos campos Game.ini [ShooterGameMode]: passive_tame_interval_multiplier, wild/tamed dino food/torpor drain multipliers, base_temperature_multiplier, disable_dino_riding/taming, disable_friendly_fire_pvp/pve, disable_loot_crates, increase_pvp_respawn_interval, prevent_offline_pvp_connection_invincible_interval, allow_tribe_war_pve/cancel, max_alliances/tribes_per_tribe/alliance, allow_custom_recipes, use_corpse_locator, supply_crate_loot_quality_multiplier, global_corpse_decomposition/battery_durability multipliers, poop/hair/resource multipliers, disable_structure_placement_collision, pvp_zone_structure_damage_multiplier, limit_turrets_in_range, fast_decay_interval.
- Feat (Paridade ASM — ServerConfig): ~35 novos campos: server_ip (MultiHome), use_raw_sockets, no/force_net_threading, public_ip_for_epic, spectator_password, enable_ban_list_url, rcon_server_game_log_buffer, admin_logging, enable_extinction_event, disable_vac, disable_anti_speed_hack, speed_hack_bias, use_cache, use_old_save_format, use_no_memory_bias, stasis_keep_controllers, use_no_hang_detection, server_allow_ansel, no_dinos, force_dx10/shader_model4/low_memory, enable_allow_cave_flyers, enable_auto_destroy_structures, enable_web_alarm, enable_server_admin_logs, max_tribe_logs, tribute_*_expiration_seconds, minimum_dino_reupload_interval, cross_ark_allow_foreign_dino_downloads, branch_name/password.
- Feat (ark_ini.py): _GUS_SERVER_SETTINGS expandido para 95 entradas; save_game_user_settings() grava inversões booleanas (PreventDiseases, PreventTribeAlliances, DisablePvEGamma, PvPDinoDecay) e todos os novos campos ServerConfig; save_game_ini() escreve ~40 novos campos [ShooterGameMode]; populate_config_from_gus/game_ini() lêem todos os novos campos.
- Feat (build_launch_args): novos URL params ?MultiHome= e ?bRawSockets; novas flags -insecure, -noantispeedhack, -speedhackbias=, -nocombineclientmoves, -nonetthreading, -forcenetthreading, -PublicIPForEpic=, -ForceAllowCaveFlyers, -AutoDestroyStructures, -nofishloot, -usecache, -oldsaveformat, -nomemorybias, -StasisKeepControllers, -NoHangDetection, -ServerAllowAnsel, -NoDinos, -d3d10, -sm4, -lowmemory, -servergamelog, -servergamelogincludetribelogs, -ServerRCONOutputTribeLogs, -NotifyAdminCommandsInChat, -webalarm.
- Feat (ModManager): suporte a branch SteamCMD via -beta <name> e -betapassword <pwd> usando campos branch_name/branch_password do ServerConfig.
- Feat (Acesso Remoto): novo painel Remoto na barra lateral — código de identidade base64, RemoteAgent com rotas GET /servers e POST /server/{id}/start|stop|restart|rcon, RemoteClient HTTP, janela de controle remoto com polling a cada 3s, console RCON embutido, regenerar token, lista de máquinas remotas salvas.

## [1.3.18] - 2026-05-20

### Feature

- Feat (CustomShop plugin — FC_ArkShopUI): novo comando GetConfig / SendConfig() — responde ao mod com ShopName, UiKey, flags (DisableSell, DisableTrade, HideBuffIcon, VoteRewards, UseSteamOverlay) e labels; sem isso a UI ficava com dados padrão.
- Feat (CustomShop plugin — FC_ArkShopUI): novo stub SellItem — retorna Success=false graciosamente; sem handler o ARK logava erro de comando desconhecido.
- Feat (CustomShop plugin — config.json): novos campos em Settings: WebsiteUrl, DiscordUrl, VoteRewards, HideBuffIcon, OverrideCurrencyIcon, UseSteamOverlay, OverrideLabels.

### Fix

- Fix (CustomShop plugin — FC_ArkShopUI): kShopBuffPath corrigido para Blueprint'/Game/Mods/FC_ArkShopUI/ArkShopUI_Buff_FCAS.ArkShopUI_Buff_FCAS' — path antigo do KinyShop causava BPLoadClass retornar null silenciosamente, impedindo qualquer dado de chegar ao mod.
- Fix (CustomShop plugin — FC_ArkShopUI): InitPlayer agora envia SendConfig antes de itens/pontos/kits — garante que a UI inicialize o layout antes de renderizar conteúdo.
- Fix (CustomShop plugin — FC_ArkShopUI): Shop.Reload (admin) agora reenvia config a todos os jogadores online.
- Fix (Atualização Automática de Mods): broadcast agora enviado a servidores em estado 'starting' — antes só 'running' era verificado, servidor era parado sem nenhum aviso.
- Fix (Atualização Automática de Mods): timeout de espera por parada aumentado 90s→90s+buffer(180s) — _stop_worker pode levar ~110s (90s graceful + taskkill); servidor não reiniciava pois status ainda era 'stopping' ao checar.
- Fix (Atualização Automática de Mods): restart agora aceita status 'stopped' ou 'crashed'; se ainda 'stopping' após timeout, aguarda 30s extra antes de iniciar.
- Fix (Atualização Automática de Mods): download concorrente — on_done(False) chamado imediatamente quando _active=True; antes o done_event nunca era sinalizado, causando timeout de 10min e falso 'Falha ao baixar' para o segundo mod.

## [1.3.17] - 2026-05-20

### Fix

- Fix (Updater): removido flag /T do taskkill em _kill_lingering — o updater era filho do app principal e se autodestruía ao tentar encerrar processos restantes; agora usa apenas taskkill por nome de executável.
- Fix (Updater): ctypes HANDLE com restype=c_void_p no OpenProcess/WaitForSingleObject — evita truncamento em sistemas 64-bit com handles de valor alto.
- Fix (CustomShop plugin): ShopPerms agora enumera todos os módulos carregados via Toolhelp32 para localizar o plugin Permissions — resolve incompatibilidade com 'Permissions V2' que carregava após o CustomShop.

## [1.3.16] - 2026-05-20

### Feature

- Feat (Plugin — Itens/Kits): novo tipo "dino" nos itens do CustomShop — suporta Blueprint, Level, Gender (Male/Female/Random) e Neutered; disponível tanto no editor de Itens quanto nos itens de Kit.
- Feat (Dashboard): servidor em estado TRAVADO (crashed) exibe botão '💀 Forçar Enc.' em vez de Iniciar/Parar — força o encerramento do processo via taskkill /F /T.
- Feat (Dashboard): barra de legenda com todos os 6 status possíveis de servidor (Parado, Iniciando, Online, Encerrando, Travado, Desconhecido) com cores e descrições.
- Feat (Desempenho): temperatura de CPU (via psutil/ACPI WMI) e GPU (via nvidia-smi) exibidas em cada card de recurso.
- Feat (Desempenho): nova seção '📡 Consumo por Servidor' — tabela em tempo real com CPU% e RAM de cada processo de servidor ARK em execução.

### Fix

- Fix (Updater): processo updater desvinculado do Job Object do Windows (CREATE_BREAKAWAY_FROM_JOB) — encerrar o app principal não interrompe mais o updater em execução.

### Other

- Perf (Plugin — Itens/Kits): substituída paginação com CTkScrollableFrame por Treeview nativo (ttk) + painel de edição único (master-detail) — navegação entre centenas de registros sem recriação de widgets.
- Perf (Plugin — Mods): lista de mods paginada com navegação Anterior/Próximo (20 por página), evitando renderizar todos os mods de uma vez.

## [1.3.15] - 2026-05-20

### Feature

- Novo indicador de status ‘ASE Permissions’ na aba Plugins: exibe se o plugin está instalado e oferece botão ‘⬇ Instalar Permissions’ que abre o link da página oficial.

### Other

- Nova aba ‘������ Crashes’: exibe histórico completo de crashes do servidor lidos de ShooterGame/Saved/Crashes/, com diagnóstico interpretado (culpado, mensagem, call stack) e botões para abrir pasta ou apagar registros individualmente.
- Discord — mensagens redesenhadas: cada evento (iniciando, online, encerrando, encerrado, crash) agora usa description do embed como mensagem principal; campos Mapa e Porta como inline para starting/running; Uptime em stopped; diagnóstico do crash em bloco de código para crashed; removido o campo ‘Dica’ genérico de todos os eventos.
- Discord — crash agora inclui diagnóstico real: server_manager armazena o resultado de _read_crash_info() na instância antes de disparar o evento, e o notificador inclui o trecho no embed.

## [1.3.14] - 2026-05-21

### Fix

- Fix (plugin_manager — PluginInfo.json): Dependencies corrigido para ["Permissions"] — PluginManager.install() não sobrescreve mais a declaração de dependência.
- Fix (plugin_manager — config padrão): seção TimedPointsReward adicionada ao _DEFAULT_CONFIG — grupos de pontos por tempo aparecem na UI após instalação limpa.
- Fix (Editor de Kits — Permissões): campo Permissions não embaralha mais texto ao importar config com valor em formato string (ex: "VIPOuro, Staff").
- Fix (CustomShop — SendKits C++): payload Result agora usa Result.Data consistente com SendShopItems, corrigindo envio de kits ao mod MX-E.

## [1.3.13] - 2026-05-20

### Fix

- Fix (CustomShop — ShopPerms): aviso "Permissions plugin not found" ao iniciar corrigido — Perms::Init() movido de Plugin_Init para hook BeginPlay, quando todos os plugins já estão carregados no processo; controle de kit e pontos por grupo agora funcionam.
- Fix (Plugins — Salvar config.json): diálogo de confirmação agora exibe o caminho completo do arquivo gravado.

## [1.3.12] - 2026-05-20

### Fix

- Fix (Plugins — Desinstalar/Reinstalar): erro Tcl "wrong # args: trace remove variable" ao reinstalar o CustomShop — CTkOptionMenu não usa mais StringVar interna via variable= (evita trace Tcl em destruição dos widgets).

## [1.3.11] - 2026-05-19

### Fix

- Fix (CustomShop — Error 126): adicionado z.dll (zlib) ao bundle — libmariadb.dll depende de z.dll que não estava sendo copiado para Win64/ na instalação.
- Fix (Plugins — Importar — grupos): grupos do TimedPointsReward não eram importados do formato ArkShop — convertido de inteiro direto para {"Amount": N} ao fazer a conversão.

## [1.3.10] - 2026-05-19

### Feature

- Novo (Plugins — Importar config.json): botão '📂 Importar' na aba Plugins permite carregar um config.json do ArkShop (legado) ou CustomShop e popular a UI automaticamente.
- Novo (Plugins — Importar config.json): detecção automática de formato — ArkShop (Mysql/General) é convertido para CustomShop antes de preencher os campos.
- Novo (Plugins — Importar config.json): conversão ArkShop → CustomShop mapeia Mysql → Database, General → Settings, Amount → Quantity nos kits e ShopItems → Items.

## [1.3.9] - 2026-05-22

### Fix

- Fix (CustomShop crash): substituído libmysql.dll (MySQL 8.0) por libmariadb.dll (MariaDB Connector/C 3.4.8) — elimina crash de inicialização em servidores que usam MariaDB.
- Fix (CustomShop build): build_cl.bat atualizado para linkar contra libmariadb.lib em vez de libmysql.lib.

## [1.3.8] - 2026-05-19

### Fix

- Fix (CustomShop instalação): DLLs de dependência (libmysql, libcrypto, libssl) agora instaladas em Win64/ em vez da pasta do plugin — correção do Error 126 e crash ao carregar o plugin.

## [1.3.7] - 2026-05-19

### Fix

- Fix (CustomShop UI): corrigido erro Tcl 'wrong # args: should be trace remove variable' ao instalar o plugin — substituido trace_add manual por callback command= nativo do CTkOptionMenu.

## [1.3.6] - 2026-05-19

### Feature

- Novo (CustomShop UI): card de configuracao de banco de dados MySQL na aba Plugins — Host, Porta, Usuario, Senha e nome do Banco editaveis diretamente na interface.
- Novo (CustomShop UI): card Settings com 18 campos organizados em 4 secoes — Loja, Botoes, Criaturas/Cryo e Restricoes de uso.
- Novo (CustomShop UI): suporte a itens do tipo 'command' — campos Command, DisplayAs e ExecuteAsAdmin com alternancia automatica de layout ao mudar o tipo.
- Novo (CustomShop UI): card TimedPointsReward — Enabled, Interval, StackRewards e grupos dinamicos (nome + pontos) adicionados e removidos na interface.
- Novo (CustomShop UI): campo Permissions nos kits — lista de grupos separada por virgula; validada pelo Permissions.dll antes da compra.
- Novo (CustomShop): kits com restricao de permissao via Permissions.dll — campo 'Permissions' no kit valida grupos do jogador antes da compra.
- Novo (CustomShop): pontos por tempo (TimedPoints) — jogadores acumulam pontos automaticamente com suporte a grupos VIP e configuracao por grupo.
- Novo (CustomShop): spawn de dinos em kits — campo 'Dinos' no kit entrega dinossauros domesticados, com nivel, ForceTame e Neutered configuráveis.
- Novo (CustomShop): suporte a MySQL via libmysql.lib — build_cl.bat corrigido com MYSQL_DIR, headers e libpath.
- Novo (_migrate_arkshop.py): conversao de dinos do ArkShop para o formato CustomShop com Blueprint, Level, ForceTame e Neutered.

### Fix

- Fix (CustomShop UI): carregamento de abas totalmente lazy — eliminava travada de navegacao causada por pre-construcao de tabs em background.

## [1.3.5] - 2026-05-19

### Feature

- Novo: Atualização de mod agora broadcast mensagem clara de reinicio com contagem regressiva (5/3/1 min) e aviso final ao desligar o servidor.
- Novo: SaveWorld enviado a todos os servidores antes de qualquer shutdown — mundo e perfis salvos antes de aplicar atualização de mod.

### Fix

- Fix: _graceful_shutdown aguarda 15 s apos SaveWorld (era 2 s) para garantir que o save esteja completo antes do DoExit.
- Fix: discord_notifier — classe DiscordNotifier duplicada e bloco de codigo solto removidos.
- Fix: server_config — fields importado de dataclasses; type: ignore adicionado em asdict e __dataclass_fields__.
- Fix: plugin_manager — import MySQLError inutilizado removido; type: ignore em mysql.connector.
- Fix: dynamic_config_server — assinatura de log_message corrigida para compatibilidade com BaseHTTPRequestHandler.
- Fix: ark_ini — atribuição de optionxform suprimida com type: ignore[method-assign].
- Fix: beacon_client — import sys inutilizado removido.
- Fix: config.json do CustomShop — chave Database duplicada removida.

## [1.3.4] - 2026-05-18

### Feature

- Novo: Botão 'Diagnosticar Cluster' na aba Avançado — verifica cluster ID, pasta compartilhada (local e UNC/rede), sync, AltSaveDirectoryName, consistência entre servidores e permissões de download/upload.

### Fix

- Fix: Janela CMD do SteamCMD não abre mais durante download de mods/servidores — processo roda em background com CREATE_NO_WINDOW.

## [1.3.3] - 2026-05-18

### Fix

- Fix: Aba Jogo — Stats por Nível agora carrega automaticamente os valores de PerLevelStatsMultiplier do Game.ini ao abrir a aba pela primeira vez, em vez de exibir sempre o padrão 1.0.

## [1.3.2] - 2026-05-18

### Fix

- Fix: Cluster — ClusterID agora passado como flag -clusterid= em vez de parâmetro de URL ?ClusterID=; o ARK ignora a forma ?URL e só reconhece a flag -.
- Fix: Cluster — ClusterDirOverride não usa mais aspas internas (-ClusterDirOverride="path") que podiam falhar no parser do ARK/UE; caminhos com espaços agora recebem o argumento inteiro entre aspas.

## [1.3.1] - 2026-05-18

### Fix

- Fix: Protocolo RCON corrigido — pacote sentinel agora usa tipo EXECCOMMAND (2) em vez de RESPONSE_VALUE (0), que causava WinError 10053 (ARK fechava a conexão ao receber pacote inválido do cliente).
- Fix: Timeout RCON (SaveWorld, Broadcast e outros comandos sem resposta) não gera mais erro vermelho — tratado silenciosamente como '(sem resposta)'.
- Fix: Console RCON reconecta automaticamente antes de enviar um comando se a conexão estiver caída — sem necessidade de clicar em Conectar manualmente.

## [1.3.0] - 2026-05-18

### Feature

- Novo: Botão '🔧 Testar RCON' na aba Broadcasts para verificar conectividade e funcionamento do broadcast.
- Novo: Notificações Discord aprimoradas — embeds com campos estruturados, timestamp, footer e dicas contextuais por tipo de evento.
- Novo: Notificação Discord enviada automaticamente após atualização de mods (mod_auto_updater) e após cada backup concluído.

### Fix

- Fix: Broadcasts agora funcionam sem o Console RCON aberto — conexão RCON temporária criada automaticamente ao enviar.
- Fix: Race condition em restart_server e _reconnect_monitor — acesso a _instances agora protegido por lock.
- Fix: Race condition (TOCTOU) em ModManager — verificação e set de _active agora atômicos com threading.Lock.
- Fix: Gravação de configurações agora é atômica (arquivo .tmp + rename) — evita corrupção em caso de crash durante o save.
- Fix: Script de atualização substituiu System.Net.WebClient (deprecated) por Invoke-WebRequest.
- Fix: race condition em _update_restart no agendador de servidores.
- Fix: Vazamento de memória no agendador — entradas antigas de _sched_fired/_sched_warned são limpas a cada ciclo.
- Fix: Token vazio no agente remoto não bypassa mais autenticação.
- Fix: BUFF manager usava ServerChat em vez de Broadcast.

## [1.2.9] - 2026-05-17

### Fix

- Fix: Botão 'Iniciar' no painel de Sincronização de Cluster agora salva o perfil automaticamente antes de iniciar, evitando perda dos campos não salvos (Pasta local, Intervalo).

## [1.2.8] - 2026-05-17

### Feature

- Novo: Pasta do Cluster criada automaticamente ao salvar perfil de cluster (modo local).
- Novo: Card de Diagnóstico no painel Clusters — indica se ClusterID, pasta e vínculos estão corretos.
- Novo: Painel Clusters detecta servidores com cluster manual e oferece botão 'Importar como Perfil'.
- Novo: Criar novo perfil de cluster pré-preenche com valores de configuração manual existente.

### Fix

- Fix: CrossARK — ClusterDirOverride agora normaliza barras para \\  no Windows, evitando falha silenciosa na gravação de personagens.
- Fix: ?AltSaveDirectoryName agora é sempre adicionado quando configurado, independente de ClusterID.
- Fix: -UseDynamicConfig não é mais duplicado quando presente em argumentos extras.

## [1.2.7] - 2026-05-17

### Feature

- Novo: Integração BattleMetrics — campo 'BattleMetrics ID' na aba Geral de cada servidor. Quando configurado, exibe status online/offline e contagem de jogadores (👥 X/Y) no painel e no dashboard, consultando a API pública a cada 60 segundos.

## [1.2.6] - 2026-05-17

### Fix

- Fix: Botão 'Sobre' sumia da sidebar — separador e seção SERVIDORES sobrepunham os dois últimos itens de navegação (Configurações e Sobre) após adição de novos itens ao menu.

## [1.2.5] - 2026-05-17

### Feature

- Novo: Notificações Discord via Webhook — envia embeds coloridos para um canal Discord em eventos de servidor (iniciando, online, parado, crash, encerrando, atualização de mods, backup). Configurável por tipo de evento nas Configurações Globais.
- Novo: 6 novos parâmetros de inicialização de servidor — Crossplay (-crossplay), Apenas Epic (-epiconly), Vivox (-UseVivox), Anti-dupe de item (-UseItemDupeCheck), Sem animação de spawn (?PreventSpawnAnimations=True), Dano flutuante RPG (?ShowFloatingDamageText=True).
- Novo: Stats por Nível expandido — tabela PerLevelStatsMultiplier agora inclui colunas Dom. Bônus (TaM / _DinoTamed_Add) e Dom. Afinid. (TmM / _DinoTamed_Affinity), cobrindo todas as 5 variantes do ARK.

## [1.2.4] - 2026-05-17

### Feature

- Novo: Sistema de Clusters Cross-ARK — painel dedicado para criar e gerenciar perfis de cluster (modo Local ou Rede), substituindo a configuração manual por servidor.
- Novo: Sincronização automática de dados de viagem — cada perfil de cluster pode sincronizar bidirecional mente a pasta local do ARK com uma pasta compartilhada de rede (caminho UNC ou drive mapeado), mantendo personagens, itens e dinos atualizados entre máquinas diferentes.
- Novo: Vinculação de servidores ao cluster — seleção direta dos servidores que participam de cada cluster diretamente no painel do perfil.

### Fix

- Fix: Verificador de atualização — removido BOM (Byte Order Mark) do version.json para evitar erro 'Não foi possível verificar' em certas configurações de sistema.

## [1.2.3] - 2026-05-17

### Fix

- Fix: GameUserSettings.ini — chaves preservam maiúsculas/minúsculas originais (ex: RCONEnabled não virava rconenabled), evitando crash de plugins ArkAPI como ArkShop.
- Fix: GameUserSettings.ini e Game.ini — encoding original do arquivo (UTF-16 LE, UTF-8 com BOM, etc.) é detectado e preservado ao salvar.

## [1.2.2] - 2026-05-17

### Feature

- Novo: Exportar/Importar Perfil — botões na sidebar permitem salvar todos os servidores em um arquivo .arkprofile e carregá-los em outra máquina.

### Improvement

- Melhoria: Stats por Nível — tabela com fundo alternado (zebra) para facilitar leitura das colunas distantes.

## [1.2.1] - 2026-05-17

### Feature

- Novo: Comandos em Itens da Loja — seção 'Comandos' adicionada ao detalhe de item da loja, igual aos Kits.

### Fix

- Fix: Beacon — token salvo em %APPDATA% (Program Files é read-only sem admin; token nunca era persistido).
- Fix: Beacon — painel de autenticação reaparece automaticamente após erro de token.
- Fix: Beacon — mensagem de erro não referencia mais arquivo interno de desenvolvedor.

## [1.2.0] - 2026-05-17

### Feature

- Novo: Instância única — ao tentar abrir o app já em execução (mesmo na bandeja), a janela existente é restaurada automaticamente ao foco via mutex nomeado + EnumWindows.
- Novo: Integração com Beacon (usebeacon.app) — autenticação OAuth Device Flow (PKCE), cache local de blueprints ARK Prime (~1963 itens, TTL 7 dias).
- Novo: Blueprint Picker — diálogo de busca live com filtro por categoria (Todos / Itens / Criaturas) integrado ao ArkShop (itens de kit, dinos e selas).
- Novo: botão '📋 Inserir seção...' no dialog de INI do mod — permite inserir seções cadastradas no painel INI (Game.ini / GUS.ini) sem substituir o conteúdo existente.

### Improvement

- Melhoria: aba Jogo usa renderização em chunks (lotes de 6 via after(0)) — elimina freeze de ~500ms causado por 44 CTkSliders ao abrir a aba pela primeira vez.
- Melhoria: pre-build de abas em idle com intervalo de 1500ms (antes 120ms) e sem abas pesadas na fila — elimina freezes periódicos em background.

### Other

- Correção: múltiplos erros Pylance corrigidos (beacon_client, server_manager, arkland_updater, _profile_tabs, beacon_explore, beacon_sync).

## [1.1.23] - 2026-05-17

### Feature

- Novo: Agendamentos automáticos na aba Geral — reiniciar/desligar/atualizar+reiniciar por dia da semana e hora com aviso RCON configurável.
- Novo: Seletor de núcleos de CPU substituindo checkbox — Padrão / Todos / N núcleos com afinidade via psutil.
- Novo: Calculadora de Breeding — cards visuais, campo Cuddle (Imprint) com tempo desejado, botão Wiki.

### Improvement

- Melhoria: MOTD com área de texto maior (altura 180px).

### Other

- Correção: botão 'Aplicar ao Servidor' na Calculadora de Breeding agora salva o .ini mesmo com servidor online.
- Correção: campo de texto do multiplicador no Jogo atualiza ao aplicar valores da Calculadora.

## [1.1.22] - 2026-05-17

### Feature

- Novo: seletor de núcleos de CPU com afinidade via psutil.

## [1.1.19] - 2026-05-16

### Feature

- Novo: aba Spawns — editor visual de spawn de dinos customizados (ConfigAddNPCSpawnEntriesContainer / ConfigOverrideNPCSpawnEntriesContainer). Adicione ou substitua containers de spawn por mapa, com suporte a múltiplos entries e blueprint paths, leitura e escrita automática no Game.ini.

## [1.1.18] - 2026-05-16

### Other

- Correção: importação de INI agora lê args de linha de comando do .bat de startup (BabyMatureSpeedMultiplier, EggHatchSpeedMultiplier, BabyCuddleIntervalMultiplier, etc.) que ferramentas como ARK Server Manager passam diretamente ao ShooterGameServer.exe em vez de gravar no INI.

## [1.1.17] - 2026-05-15

### Other

- Correção: importação de INI do disco não carregava multiplicadores de breed, RCON e MOTD — o importador agora usa a mesma lógica completa do leitor interno, cobrindo todos os campos de GameUserSettings.ini e Game.ini.

## [1.1.16] - 2026-05-15

### Feature

- Novo: ao reiniciar após atualização, o app detecta servidores ARK já em execução e reconecta automaticamente.

### Other

- Correção: updater não conseguia sobrescrever ARKLAND-Updater.exe pois o arquivo estava em uso — o updater agora se renomeia antes de rodar o installer, liberando o arquivo.
- Correção: processos ARKLAND-ServerManager.exe podiam persistir após o kill — o updater agora verifica via tasklist e repete o taskkill até confirmar que todos morreram (até 10 tentativas).

## [1.1.15] - 2026-05-15

### Feature

- Novo: campo de busca de configurações no painel de servidor — filtra por nome, dica e aba em tempo real.

### Other

- Correção crítica: updater ficava preso em 'Aguardando o ARKLAND fechar' quando a opção 'minimizar para bandeja' estava ativa — o fluxo de atualização agora chama _do_quit() diretamente, ignorando a bandeja.
- Correção: ARKLAND-Updater.exe adicionou timeout de 20 s no WaitForSingleObject — após o timeout, processos restantes são encerrados à força via taskkill.
- Correção: AllowedCheaterSteamIDs.txt era gravado no caminho errado (Saved/Config/WindowsServer/) — corrigido para Binaries/Win64/, que é onde o ARK efetivamente lê o arquivo.

## [1.1.14] - 2026-05-15

### Feature

- Novo: tooltip ? flutuante na seção Comandos do kit ArkShop — exibe variáveis disponíveis ({steamid}, {playerid}, {playername}) e exemplos de comandos do plugin ao passar o mouse.
- Novo: campo ID do kit editável no painel de detalhe — renomeação com detecção de conflito.
- Novo: Cluster / Múltiplos Servidores — salva ArkShop.json em vários destinos simultâneos.
- Novo: presets nomeados para ArkShop — salvar, carregar e excluir configurações completas (persiste em %APPDATA%\ARKLAND-ServerManager\arkshop_presets.json).

### Improvement

- Melhoria: botão − minimiza para a bandeja do sistema (pystray) além do botão Fechar.
- Melhoria: fechar o app não encerra os processos do servidor ARK — mapas continuam rodando.
- Melhoria: navegação O(1) — troca de tela usa grid_remove seletivo em vez de ocultar todos os frames.

### Other

- Correção: alterações nos campos da UI não eram persistidas ao salvar o ArkShop.json — _arkshop_collect_fields() agora chamado antes de gravar no disco.

## [1.1.13] - 2026-05-15

### Other

- Correção crítica: formato .mod completamente reescrito baseado no arkmanager/doExtractMod — mod.info começa com o nome do mod (não mapCount), e o .mod exige nome, caminho, magic footer e modmeta.info. Corrige crash 'BufferCount=0' definitivamente.

## [1.1.12] - 2026-05-15

### Other

- Correção crítica: gera .mod binário correto (FUGCModImport) a partir de mod.info — copiar mod.info diretamente causava crash 'BufferCount=0' no ARK.
- Auto-reparo em check_mod_installed também usa o gerador binário correto.

## [1.1.11] - 2026-05-15

### Other

- Correção crítica: SteamCMD não cria arquivo .mod externo — _find_dot_mod agora usa mod.info como fallback.
- Auto-reparo em check_mod_installed: se .mod ausente mas mod.info presente na pasta instalada, copia automaticamente.

## [1.1.10] - 2026-05-14

### Feature

- Novo campo Mensagem do Dia (MOTD) na aba Geral de cada servidor.

### Other

- Correção crítica: mods não carregavam pois o arquivo .mod estava ausente — check_mod_installed agora exige pasta E arquivo .mod.
- Busca fallback pelo .mod dentro da pasta do mod ao copiar via SteamCMD.
- Aviso pré-start: alerta se algum mod configurado estiver sem o arquivo .mod.
- MOTD e duração salvos automaticamente no GameUserSettings.ini ([MessageOfTheDay]).

## [1.1.9] - 2026-05-14

### Feature

- Novo botão Clonar Configurações na aba Avançado de cada servidor.

### Other

- Clona mapa, senhas, mods, multiplicadores, cluster, admins e backup para outros servidores.
- Preserva nome, diretório de instalação, session name e portas no servidor destino.

## [1.1.8] - 2026-05-14

### Other

- Parar servidor agora encerra toda a árvore de processos via taskkill /F /T /PID.
- Corrige bug onde o app reportava 'Servidor parado' mas o processo continuava rodando.
- Nova aba Backup: backup automático em intervalos configuráveis (1h–24h).
- Escolha de quantos backups manter, conteúdo (Saves/Config) e pasta de destino.
- Botão de Backup Manual e lista de backups com opções de restaurar e excluir.

## [1.1.7] - 2026-05-14

### Other

- Updater: encerra à força todos os processos ARKLAND-ServerManager.exe antes de instalar (evita falha por arquivo bloqueado no Windows).

## [1.1.6] - 2026-05-14

### Other

- Aba Admins: busca automática do nome Steam ao digitar o ID (Steam Community XML, sem API key), exibido na lista.
- Nova aba Jogadores: lista jogadores online via RCON ListPlayers com ações Kick, Ban e adicionar como Admin.
- Jogadores: auto-refresh a cada 30 segundos via checkbox na aba.
- Sistema de BUFFs de Rates Temporários: nova aba ⚡ BUFFs no sidebar com agendamento, presets, backup/restore de INI e broadcast RCON.
- BUFFs: tipos XP, Doma, Breeding, Farm; multiplicadores rápidos 5x/10x/15x ou custom; máx. 30 dias.
- Mapa Aquatica adicionado à lista de mapas oficiais.

## [1.1.5] - 2026-05-14

### Feature

- Novo ARKLAND-Updater.exe: substitui script PowerShell temporário para auto-atualização do app.

### Other

- Correção crítica: servidor não ficava mais preso em 'PARANDO' — shutdown RCON movido para thread, cascata terminate/kill/os.kill com timeouts.
- Botão ⚡ Cancelar no lugar de botão desabilitado durante INICIANDO/PARANDO, permite forçar parada imediata.
- Timeout de inicialização aumentado de 15 para 45 minutos para mapas pesados com muitos mods.
- Dashboard exibe badge LAN/WAN ao lado de cada servidor, atualizado em tempo real.
- Nova aba Admins: gerencia Steam IDs de administradores, grava AllowedCheaterSteamIDs.txt ao salvar.
- ModAutoUpdater: download do mod ocorre enquanto servidor ainda roda; cópia para Mods/ apenas após servidor parar (evita file locking no Windows).
- Lista de mods com cores alternadas (zebra) para fácil identificação de linha.

## [1.1.4] - 2026-05-14

### Other

- Nomes dos mods buscados automaticamente via Steam Workshop API ao abrir a aba Mods.
- Lista de mods exibe ID - Nome do mod para fácil identificação.
- Checkbox 'Atualizar servidor ao iniciar' agora executa SteamCMD antes de iniciar o servidor.
- Correção do build.bat: parênteses em echo dentro de bloco if aninhado causavam erro no CMD.

## [1.1.3] - 2026-05-14

### Other

- Sincronização N-way multi-ciclo: até 5 ciclos independentes, cada um com até 5 pastas — propaga sempre a versão mais nova de cada arquivo para todas as pastas do ciclo.
- Auto-start do sync: ao abrir o app, o sync é iniciado automaticamente se houver ciclos configurados.
- Interface de Sincronização redesenhada: cards dinâmicos por ciclo com botões + Pasta e + Ciclo, remoção individual e renumeração automática.
- Correções de lint/tipo em todos os módulos (updater, ark_ini, mod_auto_updater, mod_manager, rcon_client, server_manager, server_config, remote_agent).

## [1.1.2] - 2026-05-14

### Other

- Configurações INI por mod: cada mod pode ter blocos customizados para Game.ini e GameUserSettings.ini, aplicados automaticamente aos arquivos do servidor.
- Nome do mod salvo automaticamente ao adicionar via busca no Workshop.
- Importar INI do Disco agora permite selecionar qualquer pasta (backup, outro servidor, etc.) via seletor de arquivos.
- Bloqueio de edição: todas as configurações ficam desabilitadas enquanto o servidor estiver em execução ou iniciando — apenas com status PARADO é possível editar.
- Banner de aviso visível no painel do servidor quando as configurações estão bloqueadas.
- Correção: método _check_updates_manual ausente causava erro ao abrir a aba Sobre.
- Correção: definição duplicada de _check_updates_on_start removida.

## [1.1.1] - 2026-05-14

### Other

- Importação de GameUserSettings.ini e Game.ini direto do disco, preenchendo todos os campos da interface.
- Sincronização de arquivos INI entre servidores selecionados (GameUserSettings.ini e/ou Game.ini) via diálogo na aba Avançado.
- Auto-updater de mods ativado por padrão e instala mods ausentes ao iniciar.

## [1.1.0] - 2026-05-14

### Fix

- Fix: mods copiados para ShooterGame/Content/Mods/ após download

### Other

- Transformação completa: de ferramenta de sync para gerenciador de servidores ARK
- Multi-servidor: gerencie múltiplos servidores ARK na mesma interface
- Iniciar/Parar/Reiniciar servidores + instalação via SteamCMD
- Ciclo de vida de status: PARADO→INICIANDO→RODANDO via log do ARK
- Badge LAN/WAN no header: 🏠 LAN ao iniciar, 🌐 WAN ao registrar no Steam
- Abas por servidor: Geral, Jogo, Avançado, Mods, Plugins, Console RCON, Logs
- Gerenciamento de mods: instalar/atualizar via SteamCMD, status por mod
- Atualização automática de mods: broadcast RCON + para/baixa/reinicia
- Log de sync com nome, tamanho e direção de cada arquivo copiado
- Agente autônomo de atualização do app: baixa, instala e reinicia sozinho

## [1.0.9] - 2026-05-13

### Other

- Token do agente gerado automaticamente (UUID) na primeira execução
- Botão Copiar token e botão Revogar (gera novo UUID) na aba Remoto
- Botão 'Colar meu token' no formulário de peer facilita configuração

## [1.0.8] - 2026-05-13

### Other

- Porta padrão do agente remoto alterada de 19567 para 32440

## [1.0.7] - 2026-05-13

### Other

- Correção: atualização automática reescrita com PowerShell (era .bat)
- Corrige janela que abria e fechava instantâneamente sem instalar

## [1.0.6] - 2026-05-13

### Other

- Aba Remoto exibe o IP local desta máquina e o endereço completo para peers
- Campo Nome do peer agora é opcional (usa o IP como fallback)

## [1.0.5] - 2026-05-13

### Other

- Correção de compatibilidade: build migrado para Python 3.12
- Corrige erro 'Failed to load Python DLL' em máquinas sem VC++ 2022 Runtime

## [1.0.4] - 2026-05-13

### Other

- Correção: atualização automática aguarda o app fechar antes de instalar
- Script intermediário evita erro de arquivo em uso durante a instalação

## [1.0.3] - 2026-05-13

### Other

- Nova aba Controle Remoto — controle outra instância do app via rede
- Agente HTTP integrado: exponha esta máquina para controle externo
- Cadastro de peers remotos com IP, porta e token de autenticação
- Painel de peer com stats em tempo real, logs e botões Iniciar/Parar/Forçar Sync

## [1.0.2] - 2026-05-13

### Other

- Erros separados por tipo com timestamp — card Erros agora abre detalhes
- Botão 'Ver detalhes' no Dashboard lista cada erro individualmente
- Botão 'Limpar' zera histórico de erros sem reiniciar a sincronização

## [1.0.1] - 2026-05-12

### Other

- Imagem do instalador corrigida (sem distorção)
- URL de atualização embutida — não requer configuração manual
- Iniciar sincronização habilitado por padrão
- Nova opção: Iniciar o ARKLAND - Server Manager com o Windows
- Ícone da barra de tarefas corrigido

## [1.0.0] - 2026-05-12

### Other

- Lançamento inicial do ARKLAND - Server Manager
- Sincronização bidirecional automática de pastas ARK Cluster
- Interface moderna com Dashboard, Configurações e Logs
- Controle de intervalo de sincronização (1–60 s)
- Inicialização automática e modo debug configuráveis
- Estatísticas em tempo real no Dashboard (arquivos, erros, último sync)
- Sistema de atualização automática integrado
