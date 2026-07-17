"""
Versão e changelog do ARKLAND - Server Manager.
Este arquivo é a única fonte de verdade para a versão do aplicativo.
"""

APP_VERSION: str = "1.10.56"
BUILD_DATE: str = "2026-07-17"

# Cada entrada: version, date, changes (lista de strings)
# Entrada "Unreleased" = notas para a próxima release (não bump APP_VERSION até ship).
CHANGELOG: list[dict] = [
    {
        "version": "Unreleased",
        "date": "",
        "changes": [],
    },
    {
        "version": "1.10.56",
        "date": "2026-07-17",
        "changes": [
            "Fix P0 (Web Store / Admin): detalhe de jogador PESADO (ex. griao com milhares de pedidos) deixava de completar — o GET essencial ainda varria orders/point_payments/market_listings e o pending de kits, cujo custo escala com o volume do jogador, estourando o budget → «parcial eterno» / Timeout 15s. Agora o essencial só faz leituras baratas por PK/índice (cartão, pontos, entitlements, kit_stash) e responde <8s SEMPRE, mesmo com 10k+ pedidos; pedidos, doações, listings e limites de kits ficam 100% no endpoint /heavy (lazy).",
            "Fix (Web Store / Admin): essencial não é mais bloqueado pela criação de índices hot-path — como já não toca nas tabelas grandes, serve o cartão na hora e apenas agenda o self-heal de índices (usado pelo /heavy).",
            "Fix (Web Store / DB): contagem de pedidos de kit pendentes (_pending_kit_order_counts) ganhou LIMIT rígido (ARKSHOP_PENDING_KIT_ORDERS_CAP=500) — fetchall sem teto escalava com jogadores muito ativos e segurava o worker.",
            "Fix (Web Store / Admin UI): painel mostra «Carregando pedidos, doações e limites de kits…» (neutro) durante o lazy load normal; o aviso âmbar «servidor sob carga» fica reservado para pressão real de budget/índices. Timeout frontend mantido em 15s.",
            "Test (Web Store / Admin): essencial adia secções pesadas (partial_reason='deferred'), nunca varre tabelas grandes nem depende de índices; endpoint /heavy completa pedidos/doações/kits; cap de pending kits.",
        ],
    },
    {
        "version": "1.10.55",
        "date": "2026-07-17",
        "changes": [
            "Fix P0 (Web Store / Admin): detalhe de jogador não bloqueia mais o worker HTTP em DDL/queries pesadas; se índices hot-path faltarem, o GET essencial responde parcial rápido e agenda self-heal assíncrono.",
            "Fix (Web Store / Admin): pedidos, doações, entitlements, listings e limites de kits foram movidos para endpoint heavy/lazy com budget próprio; painel completa automaticamente após os índices ficarem prontos e o botão Recarregar tenta só o complemento.",
            "Fix (Web Store / DB): self-heal de índices hot-path tem single-flight, READY apenas após confirmação e logs explícitos de start/done/failure; MySQL nunca roda DDL longo no request crítico.",
            "Test (Web Store / Admin+DB): detalhe parcial não executa consultas lentas no fallback; índices ausentes retornam parcial sem chamar full path; endpoint heavy completa pedidos/doações/kits.",
        ],
    },
    {
        "version": "1.10.54",
        "date": "2026-07-17",
        "changes": [
            "Fix P0 (Web Store / DB): `_ensure_hot_path_indexes` marcava READY=True mesmo quando CREATE INDEX falhava por read_timeout=12s no boot — detalhe admin nunca re-tentava e estourava Timeout 15s (lista OK; ex. griao). READY só com all_present; DDL em engine sem read_timeout curto; self-heal no GET detalhe.",
            "Fix (Web Store / Admin): detalhe combina points+kits numa query; budget backend de 9s com no máximo 2 workers, cancelamento entre queries e resposta parcial quando a DB ultrapassa o budget. Timeout frontend permanece 15s.",
            "Feat (Web Store / PWA): loja instalável no celular e PC — manifest, service worker, botão «Instalar app» (Chromium) e dica iOS (Minha Área + rodapé); ícones de atalho derivados da logo oficial ArkLandBR.png.",
            "Fix (Web Store / PWA): service worker nunca armazena /api/* nem HTML autenticado — APIs network-only; navegação sem Cache Storage; só assets estáticos usam cache.",
            "Build (Web Store): manifest, service worker, pwa-install.js e ícones (192/512/apple-touch) no bundle frozen via static/.",
            "Test (Web Store / Admin+DB+PWA): READY só com índices presentes; DDL omite read_timeout; detalhe rápido/completo, fallback parcial e budget desligado; manifest, service worker, rotas de ícones e instalação.",
            "Nota: guards de I/O externo (RCON async/pool, MP throttle, câmbio SWR, Discord ticket async, Steam 5s) já na 1.10.53 — esta build inclui esse código + PWA + fix hot-path.",
        ],
    },
    {
        "version": "1.10.53",
        "date": "2026-07-17",
        "changes": [
            "Fix (Web Store / Admin): detalhe GET /api/admin/players/<id> ainda estourava o timeout 15s do frontend sob carga — causa raiz: N×SELECT idêntico em orders (~40 kits DefaultAmount) via _count_pending_kit_orders + SHOW COLUMNS/inspect em cada lista + JOINs com COLLATE que impediam índices + filesort sem índices hot-path. Timeout UI mantido em 15s; detalhe deve responder em <2s. Pending kits: 1 query + contagem em memória.",
            "Fix (Web Store / Admin): lista /api/admin/players — COUNT(*) barato só em store_users quando a busca não precisa de players+market; schema store_users e _db_table_exists em flag/cache por processo (fim do SHOW COLUMNS/inspect por request).",
            "Fix (Web Store / DB): índices hot-path via ensure_schema — store_users(last_login_at, created_at), orders(original_order_id, steam_id+created_at, steam_id+item_type+status), point_payments(steam_id+created_at); setup_db.sql alinhado. JOINs steam_id sem COLLATE após migrate (optimizer usa índice).",
            "Fix (Web Store / DB): pool MySQL default 15+30 overflow, pool_timeout/read_timeout 12s; overrides ARKSHOP_DB_POOL_SIZE / MAX_OVERFLOW / POOL_TIMEOUT / READ_TIMEOUT / WRITE_TIMEOUT / CONNECT_TIMEOUT.",
            "Fix (Web Store): /api/player/summary colapsa 6 COUNT(*) + sessão extra de points em 2 agregações + 1 sessão; cache mtime de catalog_id_migration.json e fingerprint de configs (TTL 2s) nos dropdowns do detalhe.",
            "Fix (Web Store / Concorrência): WSGI prefer Waitress (ARKSHOP_HTTP_THREADS=16) em vez de Flask/Werkzeug threaded=True — sob RCON/DB lentos o threaded enfileirava handlers até timeout no browser.",
            "Fix (Web Store / Concorrência): sync-all-permissions em background (202 + poll /status); TribeSync liberta sessão MySQL antes do RCON e dispara mapas em paralelo; workers tribe_log/catalog_feed com scoped_session.remove(); tribe_routes idempotente; limiter defaults 600/h (antes 50/h); auth/me+health com override; single-flight admin SteamIDs e catalog_feed; Âmbarômetro sem backfill no hot-path HTTP.",
            "Fix (Web Store / RCON): compra/claim de licença (loja, SeasonLand, loteria) esperava Permissions.AddTimed via RCON SEQUENCIAL em todos os mapas — com 6 mapas offline até ~108s (6×18s) segurando worker Waitress. MySQL ark_permission continua síncrono (fonte do plugin); fan-out RCON vai para thread background (rcon_async) com log de falhas parciais. Rotas admin mantêm resultado por mapa, agora em PARALELO (~1×timeout, não N×).",
            "Fix (Web Store / RCON): pool web-rcon 4→12 workers (ARKSHOP_RCON_POOL_WORKERS) e deadline no retry — future.result(timeout) não cancela task em execução; retries órfãos (connect_retries=5, sleeps 2+4+6+8s) viravam zombies saturando o pool e enfileirando todo RCON seguinte. Retry agora checa deadline antes de cada tentativa/sleep.",
            "Fix (Web Store / Mercado Pago): GET /api/player/pix/<id>/status fazia HTTP síncrono ao MP (timeout 30s) em CADA poll do frontend, segurando worker + sessão MySQL sob instabilidade do MP. Poll externo agora com throttle por pagamento (mín. 8s entre fetches; entre eles responde status do DB) e timeout 8s; webhook mantém 30s.",
            "Fix (Web Store / Catalogo): cotações BRL→USD/EUR stale-while-revalidate — ao expirar o cache 1h, /api/catalog devolvia só após fetch do frankfurter.app (timeout 10s, thundering herd por hora). Agora serve o valor stale e refaz em background com single-flight; falha re-tenta em 5min; force_refresh segue síncrono.",
            "Fix (Web Store / Tickets): notificação Discord (HTTP 12s) saiu do request de criar/responder ticket — envia em thread daemon; in-app segue síncrono.",
            "Fix (Web Store / Login Steam): callback de login usava GetPlayerSummaries com timeout 12s; agora 5s com fallback ao nick em cache do DB.",
            "Test (Web Store / I/O externo): guards — compra usa rcon_async; fan-out paralelo 6 mapas <1×timeout; deadline corta retries zombie no rcon_bridge; throttle MP por pagamento + timeout 8s propagado; câmbio stale sem bloquear + single-flight; Discord de ticket fora da thread do request.",
            "Fix (Web Store / I/O externo): grant/revoke de licença com rcon_async (fan-out RCON em background); exchange_rates/PIX/Discord/RCON bridge com timeouts e sem I/O síncrono bloqueante nos hot-paths HTTP do jogador.",
            "Fix (Web Store / Frontend): timeout de detalhe admin mantido em 15s; saldo com cooldown 10s + dedup/abort; catálogo e lista admin com AbortController; Minha Área carrega secções em paralelo (Promise.all); mutações admin sem tempestade list+detail; Âmbarômetro com timeout 12s via fetchJson.",
            "Test (Web Store / Admin+DB): kit_limits 1 query pending; store_users schema skip; table_exists cache; collation JOIN pós-normalize; hot_path indexes idempotente; COUNT lista sem JOIN desnecessário.",
            "Test (Web Store / Concorrência+I/O): guards de limiter, sync-all async, tribe_routes idempotente, DB liberada antes de RCON, runtime workers once; RCON fan-out async e timeouts de I/O externo.",
        ],
    },
    {
        "version": "1.10.52",
        "date": "2026-07-16",
        "changes": [
            "Fix (Web Store / Admin): «Falha ao carregar detalhes» — evidência em webstore.log: GET /api/admin/players/<id> devolvia 200 (sem exception), mas o frontend abortava aos 15s. Sob carga o detalhe demorava dezenas de segundos porque (1) reparseava config.json ~1.1MB em todos os mapas via _read_richest_license_catalog_config a cada clique, (2) abria sessões MySQL extra para points/entitlements, (3) podia chamar Steam mesmo com nick em cache; CrossChat Discord ainda spamava ~2s no processo antigo (230 avisos vs 41 HTTP na janela 18:1x). Fix: detalhe só lê steam_persona do DB (zero Steam), reutiliza 1 sessão DB, cache mtime do catálogo de licenças/kits; UI mostra a mensagem real de timeout e não re-dispara detalhe a cada reload da lista.",
            "Fix (Web Store): /api/auth/me forçava Steam GetPlayerSummaries (timeout 12s, ignora cache) em toda navegação via _refresh_steam_persona — causa partilhada de fila no Werkzeug threaded. Passa a cache-first (_backfill_steam_personas) como a lista admin.",
            "Test (Web Store / Admin): detalhe sem Steam API; auth/me cache-first; _catalog_license_options/_catalog_kit_options cacheados por fingerprint mtime.",
        ],
    },
    {
        "version": "1.10.51",
        "date": "2026-07-16",
        "changes": [
            "Fix (Web Store / SeasonLand): recompensas resgatadas (fila PENDENTE com original_order_id `sp:…`) deixam de ser elegíveis a desistência, contestação, auto-cancel 48h ou reembolso em Âmbar — o fallback para preço de catálogo quando points_spent=0 permitia converter claim grátis em Âmbar.",
            "Fix (Web Store / Admin): Gerenciar Jogadores — «Falha ao carregar detalhes» ao abrir um jogador: o detalhe ainda consultava a Steam API de forma síncrona (timeout 12s) mesmo com nick em cache, estourando os 15s do frontend. Detalhe agora usa cache de nick Steam (API só para missing, timeout 4s), como a lista na 1.10.50.",
            "Fix (Web Store / Licenças + TimedPoints): «licenca_delta +0» persistia na 1.10.50 — rows legadas com acento/caixa/espaços («licença_delta», «LICENCA_DELTA») escapavam da normalização SKU→PermissionGroup; fold Unicode no lookup (UI, migrate repair, grant). Sync ark_permission (permission_entitlements_sync) também normaliza: reconcile detecta e reescreve TimedPermissionGroups com SKU cru (plugin dava +0 no bónus Delta=5), grant/revoke migram alias legado. keyvault segue +0 por design (só recursos de nuvem).",
            "Test (Web Store / Licenças): variantes legadas acentuadas → Delta; endpoint /api/player/entitlements com row `licenca_delta` devolve Delta +5 e total 30; reconcile ark_permission marca SKU cru como irregular.",
        ],
    },
    {
        "version": "1.10.50",
        "date": "2026-07-16",
        "changes": [
            "Fix (Web Store / Admin): Gerenciar Jogadores — timeout 15s; lista usa cache de nick Steam (API só para missing, timeout 4s) e entitlements em lote em vez de N+1.",
        ],
    },
    {
        "version": "1.10.49",
        "date": "2026-07-16",
        "changes": [
            "Remoção (Web Store / Chat Cluster): elimina chat global, APIs /api/chat e /api/admin/chat, ponte Discord (spam/canal indisponível) e aba Chat Cluster no TEK — causa de lentidão e timeouts no site.",
            "Remoção (Web Store): dependency discord.py; tickets Discord passam a exigir token dedicado (já não reutilizam token do Chat Cluster).",
            "Feat (Backup): filtro de conteúdo — omite por padrão .bak e backups datados do ARK (Map_DD.MM.YYYY_HH.MM.SS.ark); ZIPs ~60–75% menores sem alterar retenção 1h/10; desligável em Config Global.",
        ],
    },
    {
        "version": "1.10.48",
        "date": "2026-07-16",
        "changes": [
            "Fix CRÍTICO (TEK / ForceDay): SetDay via RCON crasha ASE 361.7 (UShooterCheatManager::SetDay no tick RCON) — derrubou todos os mapas online na 1.10.47. Kill-switch: zero SetDay por RCON; ForceDay OFF ao carregar config; UI «Aplicar agora» recusada; sem auto-apply no start/restart.",
            "Nota (TEK / ForceDay): «cheat SetDay» não é alternativa segura (mesmo CheatManager). DayNumber alinhado só com método futuro comprovado (plugin/save offline). Shop.Reload RCON mantido (stack do crash apontava SetDay, não Reload).",
            "Audit (TEK / ForceDay): confirma todos os caminhos SetDay RCON mortos — start/restart nunca agenda schedule_force_day; save/UI forçam enabled=False; teste de persistência OFF ao carregar config antiga.",
            "Fix (Loja): aba em branco — SyntaxError (nonlocal data após uso) impedia import do painel; caminho mestre em Label (sem CTkEntry readonly); try/except com messagebox+traceback.",
            "Fix (Web Store): arranque — .exe frozen já não faz sys.exit sem ARKSHOP_WEB_SECRET (usa web_secret.txt / geração); recupera WEBSTORE/config.json stub (~176 B); settings stub só-com-config_path faz merge em memória; launch pré-aquece catálogo+secret; log claro se porta ocupada.",
        ],
    },
    {
        "version": "1.10.47",
        "date": "2026-07-16",
        "changes": [
            "Fix (TEK / ForceDay): race no restart — STOPPED limpava force_day_pending depois do start o re-marcar; só 1 mapa (ou nenhum) recebia SetDay. Restart marca janela protegida + reaplica se RUNNING não disparar de novo.",
            "Feat (TEK / ForceDay): botão «Aplicar agora em todos os online» + prompt ao salvar configs — alinha DayNumber nos 6 mapas sem reinício.",
            "Feat (CustomShop): botão único «Propagar mestre → mapas + loja» — fonte FIXA (CustomShop/configs/config.json); substitui WEBSTORE, bin e todos os mapas; sem reconcile WEBSTORE→mestre.",
            "Fix (CustomShop / Catalogo): apply_catalog_sync deixava de poluir Name/Description dos kits com «Âmbar (50% da licença)…»; títulos curtos (KIT ARMAS ETEREO, etc.).",
            "Feat (Web Store / Admin): importar config.json (upload) → mestre canônico → propagar mapas+loja → Shop.Reload RCON; relatório etapa-a-etapa e RCON por mapa (ligação + comando).",
        ],
    },
    {
        "version": "1.10.46",
        "date": "2026-07-16",
        "changes": [
            "Feat (CustomShop / ItensAlfa): kits kit_itensalfa_armas_* e kit_itensalfa_ferramentas_* por tier (planilha Cheats por Classe); Permissions Admins+N+N+1; ONIPRESENTE→onipotente; ETEREA→etereo. Sem secção Exótico na planilha. BPs só em kits (Mjolnir, ShoulderCannon_G2, Pike/PumpAction_GOD sem SKU individual).",
            "Fix (CustomShop / Catalogo): reverte Permissions erradas em dinos L1/L200 e pack10 (bionicrex, desmodus, carcha, etc.) — cadeado de licenca fica so nos itens ItensAlfa (58 SKUs), nao nos dinos de kit.",
            "Fix (CustomShop / ItensAlfa): denylist no build de kits — Criofreezer (AlfaCrioFreezer) e Alfa Fabric banidos do cluster; nunca entram em kits/catálogo via planilha.",
            "Melhoria (CustomShop / ItensAlfa): Names/Descriptions dos kits limpos (ex. KIT ARMAS ETEREO); Permissions nos SKUs individuais de armas/ferramentas ItensAlfa.",
            "Feat (Web Store / Catalogo): icones gerados para todos os dinos do catalogo (386/386) em species/icons/generated — cobertura completa incl. Abyss, Brighamia e SmallBosses.",
        ],
    },
    {
        "version": "1.10.45",
        "date": "2026-07-15",
        "changes": [
            "Fix (TEK): restaura Iniciar/Parar/Reiniciar quebrados na 1.10.44 — scan de reconnect chamava callback de status COM o lock preso; o callback reentrava em clear_force_day_pending e deadlockava a thread (UI congelava / botões «não faziam nada»).",
            "Fix (TEK): defer de notify RUNNING/STOPPED para fora do lock no attach e no reconcile de ghosts; mantém scan multi-estratégia.",
            "Fix (TEK / UI): pós-reconnect volta ao refresh leve (sem destruir todos os cards) — evita widgets mortos sob clique.",
            "Melhoria (TEK): lifecycle start/stop/restart passa a logar a mensagem de on_done (fim do no-op silencioso «já em execução»).",
            "Test (TEK): regressão de deadlock status-callback+lock no scan/reconcile.",
        ],
    },
    {
        "version": "1.10.44",
        "date": "2026-07-15",
        "changes": [
            "Fix (TEK / Reconnect): scan multi-estratégia — portas TCP/UDP PRIMEIRO (host .bug: exe/cmdline vazios → 6/6), depois install_dir no exe, QueryFullProcessImageName, cmdline (?Port=/QueryPort), last-PID persistido e título da janela; log hit/miss por mapa.",
            "Fix (TEK / UI): após reconnect, rebuild de TODOS os cards + sidebar + ONLINE a partir do mesmo count_running(); ghost RUNNING com poll morto → STOPPED (fim do ONLINE=1 com cards PARADO).",
            "Fix (Web Store / Mercado + Dino Lab): anuncio de cryo do Dino Lab escapava o bloqueio — lookup passa a casar tambem por canonical_id e par signed (ex.: 13CE1FC2-89271B4F), repara dino_id* no boot, exige dino_identity no preview/upload e rejeita compra de anuncio bloqueado.",
            "Fix (CustomShop 1.10.21): /enviar e /confirmar falham fechados se a identidade da cryo nao puder ser lida ou se o HTTP de bloqueio Dino Lab falhar.",
            "Fix (CustomShop / Catalogo): dinos isolados (L1+L200) e pack10 cujos BPs estao em kit_gamma/beta/alfa passam a exigir o mesmo Permissions do kit de entrada (Gamma/Beta/Alfa); abyss e resto do catalogo ficam abertos. Script tools/lock_license_kit_dinos.py.",
            "Fix (Web Store / Licenças + TimedPoints): UI «licenca_delta +0» — group_name SKU era tratado como PermissionGroup; normaliza licenca_*→Delta…Exotico no grant/UI, bónus lido de TimedPointsReward.Groups, migrate repara rows legadas; keyvault continua +0. CustomShop 1.10.22 Grant/HasActive idem.",
            "Test (TEK): fixture .bug 6/6 via portas; ghost RUNNING→0; estratégias exe/cmdline.",
            "Test (Web Store / Dino Lab): regressao Manticora canonical alto-bit + preview/upload sem identidade.",
            "Test (Web Store / Licenças): SKU→grupo, bónus Delta=5, repair licenca_exotico→Exotico, keyvault +0.",
        ],
    },
    {
        "version": "1.10.43",
        "date": "2026-07-15",
        "changes": [
            "Fix (TEK / Reconnect): no host real (.bug) os 6 ShooterGameServer vinham com ExecutablePath e CommandLine vazios — regras só-exe/cmdline (v1.10.20) davam 0/6. Adjunct por portas TCP/UDP (server/query/RCON) reconecta 6/6 (BR/CI/AL/G2/VL/AM, portas 7790/7796/…).",
            "Fix (TEK / Reconnect): count_running e log de boot usam status RUNNING real (sem falso «detectou N»); scans de boot em 0,5/2,5/8 s; após reconnect dispara _asm_status_tick.",
            "Fix (TEK / Players): após reconnect, tick rico sonda A2S fresco no query_port (bind + 127.0.0.1) e atualiza inst.a2s_players; fallback RCON ListPlayers — caminho em app_tek._asm_status_tick.",
            "Feat (TEK / Desligamento programado): diálogo multi-servidor com «Marcar todos», tempo em segundos, avisos RCON em milestones sensatos (60/30/10/5…, sem spam em waits longos), cancelável no card; ao zerar usa stop gracioso existente (saveworld/doexit). Também na barra em massa do dashboard.",
            "Feat (Web Store / Dino Lab Encomendas): auditoria admin — histórico unificado com badge Encomenda; DETALHES (snapshot imutável de specs), REENVIAR (FALHA) e REEMBOLSAR; steam_id + nick (steam_persona).",
            "Melhoria (Web Store / Dino Lab): checkout congela spec_snapshot (espécie, sexo, níveis, cores, stats, mapa, preço, timestamps); GET /api/admin/dino-order/<id> com trilha de status.",
            "Melhoria (CustomShop / TimedPoints 1.10.20): chat ao receber Âmbar inclui URL da loja (Settings.WebsiteUrl / WebApiUrl).",
            "Test (TEK): fixture .bug (exe+cmdline vazios → 0/6 clássico, 6/6 com portas); count_running; milestones/broadcasts do desligamento programado.",
            "Test (Web Store / Dino Lab Encomendas): cobertura snapshot, nick, origem no Histórico, reenvio+estorno a partir de FALHA.",
        ],
    },
    {
        "version": "1.10.42",
        "date": "2026-07-15",
        "changes": [
            "Fix (TEK): restaura reconexão de mapas após restart do app como em v1.10.36 — matching por install_dir no exe (substring) e ?Port=/-port= na CLI; as mudanças de v1.10.40/41 (boundary de path + scan over-clever) regressaram o path que já funcionava.",
            "Fix (TEK): colapsa barras repetidas no install_dir (D:\\\\ARK → d:/ark) para não falhar match com paths Windows escapados.",
            "Melhoria (TEK): QueryPort na cmdline, install_dir na cmdline (exe vazio), e fallback por portas TCP/UDP / título da janela só como ADJUNTO — nunca substitui o path 1.10.36 quando exe/cmdline funcionam.",
            "Fix (TEK): mantém poll AccessDenied≠morto (de 1.10.41) e register_servers + retentativas de scan no boot.",
            "Test (TEK): cobertura do baseline 1.10.36 (exe+install_dir), shared install+porta, fallback por porta, normalize de barras duplas.",
        ],
    },
    {
        "version": "1.10.41",
        "date": "2026-07-15",
        "changes": [
            "Fix (TEK): reconnect pós-restart — a v1.10.40 só casava por exe/cmdline; se ambos vierem vazios o mapa ficava PARADO. Agora casa também por portas TCP/UDP (server/query/RCON) via psutil.net_connections + netstat -ano, título da janela RunServer e QueryFullProcessImageName.",
            "Fix (TEK): _PsutilProcessWrapper.poll deixa de tratar exceções de permissão (ex. AccessDenied) como processo morto — evitava ONLINE→TRAVADO após reconnect.",
            "Melhoria (TEK): logs de diagnóstico no scan (Reconnect [mapa] via …; resumo 0 reconectados com candidatos/portas; PID sem match com exe/cmdline/portas).",
            "Test (TEK): modo de falha v1.10.40 (exe+cmdline vazios), multi-mapa mesmo install_dir só por portas, parser netstat, poll com permissão negada.",
        ],
    },
    {
        "version": "1.10.40",
        "date": "2026-07-15",
        "changes": [
            "Fix (TEK): após restart do app, mapas/servidores ShooterGameServer já em execução são reconectados — matching por install_dir na cmdline (exe vazio), QueryPort, mapa e retentativas de scan no boot.",
            "Test (TEK): cobertura de _process_matches_cfg e relê de cmdline via psutil.Process(pid).",
        ],
    },
    {
        "version": "1.10.39",
        "date": "2026-07-15",
        "changes": [
            "Fix (Web Store / Dino Lab Encomendas): fila admin operacional inclui PENDENTE e ENTREGANDO (auto-aprovados pagos) alem de AGUARDANDO_APROVACAO e FALHA; historico separado; status_label e badges «Paga — …»; reenvio de FALHA.",
            "Fix (Web Store / Encomenda): quote com floor_quality B=0 restaurado a partir de defaults do repo quando live stale; payment_status_label na API.",
            "Melhoria (Web Store / Dino Lab): filtros UI (fila ativa vs historico, status); rota admin /history; steam_id na fila.",
            "Fix (Web Store / Dino Lab Encomendas): estorno PENDENTE/FALHA → CANCELADO + credito Âmbar; UI Rejeitar/Estornar/Reenviar ligada; fluxo ops E2E completo.",
            "Test (Web Store / Dino Lab Encomendas): cobertura fila, historico, payment_status, estorno e reenvio (25 testes).",
        ],
    },

    {
        "version": "1.10.38",
        "date": "2026-07-15",
        "changes": [
            "Feat (Web Store / SeasonLand): recalibra curva de XP do Pass — progressiva +25%/nivel com B=3 (delta(n)=max(1,round(B*1.25**(n-1)))); Free L28=6.192 XP (budget 7.500 @ 30d x 5h sem licenca); L30/freeze=9.682 XP.",
            "Melhoria (Web Store / SeasonLand): MAX_XP dinamico da curva; API/admin expoe xp_cap + xp_curve; UI mostra cap live em vez de 4.875 fixo.",
            "Test (Web Store / SeasonLand): cobertura da curva progressiva, Free milestones e freeze @ 9.682.",
            "Docs: ARKBANK_SPEC 0.5.11 — curva B=3 locked, tabela Free, pacing 5 h/dia (250 XP/dia).",
        ],
    },
    {
        "version": "1.10.37",
        "date": "2026-07-14",
        "changes": [
        "Feat (TEK / Configurações Globais): forçar DayNumber no start/restart "
            "(force_day_on_start_enabled + force_day_on_start, default 20) — "
            "SetDay via RCON com poll/retry até o servidor responder; opcional "
            "SaveWorld; aplica a todos os mapas; não altera rates de dia.",
        "Feat (Web Store / SeasonLand): motor Season Pass live — calendário admin "
            "(Iniciar season / Iniciar próxima), XP TimedPoints multi-mapa via outbox "
            "ARKBANK→add_timed_xp no scheduler webstore, Premium Â→cofre, claims "
            "Free/Premium com grant engine (Â / fila / licença + escolha tier "
            "superior).",
        "Feat (Web Store / SeasonLand): meta colectiva (Cofre da temporada) — "
            "progresso de inflows ARKBANK da season, barra %, flag meta_reached e "
            "agenda do evento só pela admin (sem auto-fire); config admin "
            "target/event_at/notes.",
        "Melhoria (Web Store / SeasonLand admin): formulário de grants com labels "
            "claras (Tipo, ID/SKU, Quantidade/Â, Dias, Texto); helper sku_pending; "
            "copy e confirmações para iniciar / avançar season (estado, janela de "
            "resgate, fecho de unclaimed).",
        "Feat (Web Store + CustomShop / Licenças): até 2 tiers pagos activos "
            "simultâneos; mesmo SKU continua a empilhar +30d; 3.º tier distinto "
            "rejeitado (license_slots_full). TimedPoints: entre pagos vence o maior "
            "bónus; Default/staff empilham.",
        "Fix (Web Store / Kits + Licenças): renovação restaura resgates de kits "
            "da licença mesmo com pedido PENDENTE antigo (Amount = DefaultAmount + "
            "pending); match de grupo case-insensitive; resposta kits_reset; UI "
            "refresca entitlements + kit-limits após compra; gate Permissions ignora "
            "Admins/Staff.",
        "Fix (CustomShop / Licenças): ShopEntitlements::Grant reseta players.kits "
            "dos kits DefaultAmount do grupo (paridade web). Bump CustomShop v1.10.18 "
            "→ v1.10.19.",
        "Fix (Web Store / UI): overflow horizontal em SeasonLand/home no mobile "
            "(overflow-x + overflow-wrap); carrossel com alturas/nav responsivos.",
        "Docs: ARKBANK_SPEC §15.12 checklist ops readiness + passos "
            "deploy/activação SeasonLand; regulamentos / economia alinhados.",
        "Note (ops): go-live — redeploy webstore, CustomShop 1.10.19 com outbox "
            "TimedPoints, preencher SKUs nos grants admin, depois «Iniciar season».",
        ],
    },
    {
        "version": "1.10.36",
        "date": "2026-07-14",
        "changes": [
            "Feat (Web Store / SeasonLand): rename Season Pass → SeasonLand, logo dedicada, bloco informativo na home e painel admin de config do passe.",
            "Feat (Web Store / Home): mural de avisos vira carrossel de cards (CRUD admin, upload de imagens, reordenação, rotação 5 s).",
            "Melhoria (Web Store / Admin mural): dimensões 1200 × 675 px (16:9) em destaque — banner, helper no upload, placeholder e validação client-side ao escolher ficheiro.",
            "Feat (Web Store / Regulamento): página Season Pass restilizada (regulamento_season_pass.html).",
            "Docs: actualizações ARKBANK_SPEC + regulamentos Season Pass / servidor.",
        ],
    },
    {
        "version": "1.10.35",
        "date": "2026-07-14",
        "changes": [
            "Feat (Web Store / Season Pass): UI + stubs API (Free/Premium), regulamento Season Pass; preview público sem login Steam (compra Premium continua a exigir autenticação).",
            "Feat (CustomShop / Catálogo): kits Pack10 em massa — nome «KIT 10 FÊMEAS LVL 1 - {NOME}», preço 10×L1×0.60 (~191 kits).",
            "Feat (CustomShop / Catálogo): ARK Additions — Ceratosaurus, Deinotherium e Helicoprion (L1 + L200) e respectivos Pack10.",
            "Feat (CustomShop / ItensAlfa): selas com Quality=100 + Armor no máx. do tier (ex. Omega armadura 790) via apply_itensalfa_licenses.",
            "Fix (Web Store / Encomenda): market_economy volta a fazer merge com market_species_defaults (repo) e restaura floor_quality B no quote.",
            "Note: auditoria de dinos duplicados no catálogo ainda pendente (não bloqueia este patch).",
        ],
    },
    {
        "version": "1.10.34",
        "date": "2026-07-13",
        "changes": [
            "Fix (Nível do jogador): checkbox «Progressões customizadas» voltou a "
            "ser livre (remove force ON quando base >105). Com base >105 e "
            "progressões OFF: aviso na UI — ARK não honra o teto (reverte "
            "vanilla); limpa rampa/OverrideMaxXP/engrams do Game.ini e remove "
            "legado no GUS. Com ON mantém escrita no Game.ini (curva soft "
            "70×1.05^i, 400 EP). Docs PLAYER_MAX_LEVEL_SPEC.",
        ],
    },
    {
        "version": "1.10.33",
        "date": "2026-07-13",
        "changes": [
            "Fix (Nível do jogador): OverrideMaxExperiencePointsPlayer volta para "
            "Game.ini [/Script/ShooterGame.ShooterGameMode] (docs ARK) — remove "
            "caminho falso «vanilla GUS-only» para base 160. Base >105 força "
            "progressões: rampa + OverrideMaxXP + engrams 400/nível (curva soft "
            "70×1.05^i). Cap legado no GUS é removido ao salvar. Regenerar INI + "
            "reiniciar mapas.",
        ],
    },
    {
        "version": "1.10.32",
        "date": "2026-07-13",
        "changes": [
            "Feat (Web Store / ARKBANK): tesouraria do cluster — ledger "
            "(saldo pode ser negativo), hooks catálogo/desistência 20%, "
            "casal 40%→ARKBANK (não sorteio), encomenda, doação R$1=1000Â, "
            "TimedPoints via outbox; aba admin ARKBANK + APIs.",
            "Feat (Web Store / Catálogo): desistência e auto-cancel passam a "
            "reembolsar 80% do valor pago (retenção 20%); destino ARKBANK "
            "quando o ledger existir (docs/ARKBANK_SPEC.md §6.1). "
            "Regulamento §8.4.2 + UI.",
            "Docs: ARKBANK v0.4 MVP — inflow doações PIX/cartão confirmadas "
            "(R$ 1,00 = 1.000 Âmbar na tesouraria, paralelo ao pacote/pote) "
            "+ retenção catálogo 20% → banco; hooks em `_finalize_pix_payment`.",
            "Melhoria (Nível do jogador): curva geométrica custom default "
            "70×1.05^i (antes 1.15); presets Hard/Extreme suavizados (mult≤1.08); "
            "hints UI. Preferir vanilla. Mapas existentes: regenerar rampa no "
            "gerador e salvar perfil — sem migração automática de asm_servers.json. "
            "Docs PLAYER_MAX_LEVEL_SPEC.",
            "Feat (CustomShop): TimedPoints enfileira outbox ARKBANK "
            "(arkbank_timed_outbox). Bump CustomShop v1.10.17 → v1.10.18.",
        ],
    },
    {
        "version": "1.10.31",
        "date": "2026-07-13",
        "changes": [
            "Fix (Web Store / Mercado): card de casal — breakdown claro "
            "(Macho/Fêmea pedido+sugerido → Isolados → Preço do casal Y); "
            "input da Minha Loja edita só o pedido individual (`asking_price`), "
            "nunca Y; sem misturar Y nos Pedidos.",
            "Fix (Web Store / Encomenda): imagens da vitrine passam a preencher "
            "a área do card (deixam de ficar em ~64px no centro).",
            "Docs: ARKBANK planning spec (`docs/ARKBANK_SPEC.md`).",
        ],
    },
    {
        "version": "1.10.30",
        "date": "2026-07-12",
        "changes": [
            "Fix (Área da Tribo / Web): crash no arranque Flask — "
            "`@api_key_required` sem () nas rotas invite/join, leave e "
            "ownership-transfer registava endpoint `decorator` e abortava "
            "com AssertionError (site não subia após 1.10.29).",
        ],
    },
    {
        "version": "1.10.29",
        "date": "2026-07-12",
        "changes": [
            "Feat (Área da Tribo / Cluster): códigos de convite /tribe.CODE "
            "(máx. 30 dias, regenerável), pedidos PENDING/ACCEPTED/DENIED, "
            "membros confirmados (confirmed_via=code|sync), split só "
            "confirmados; leave in-game revoga membership web só naquele mapa; "
            "Principal/Fob com cooldown 24h e ≤1 principal por SteamID; "
            "transferência de ownership + alertas admin; painel admin Tribos "
            "(lista; limites de construção adiados/sem enforcement); CustomShop "
            "chat /tribe.CODE + presença tribe_id=0. Docs §20.8 + regulamento "
            "§8.10.1. Bump CustomShop v1.10.16 → v1.10.17.",
            "Feat (Web Store / Encomenda): vitrine em grade 3×5 (desktop); modal com "
            "campos numéricos de todos os stats, nível auto (1+soma), regiões 1–6 "
            "legendadas e aceite §8.12 antes do checkout.",
            "Feat (Web Store / Licenças): painel «Benefícios por licença» com abas "
            "Gamma/Beta/Alfa/Nuvem e bullets detalhados (Timed Points, acesso "
            "ItensAlfa, renovação de kits, cofre /upload·/download, Mercado P2P) "
            "a partir de config.json / LICENSE_TIMED_BONUS / regulamento §8.5–8.7.",
            "Feat (Broadcasts TEK): pacote Regulamento — mensagens curtas "
            "das regras de alto impacto (doação/licença §3.5, RMT, cheats, "
            "conduta, estruturas, mercado, etc.); botão «Regulamento» no "
            "painel Broadcasts (ativar/editar/intervalo no ciclo existente).",
            "Feat (CustomShop / ItensAlfa): 35 selas TEK (7 espécies × "
            "Delta→Omega) no catálogo — Megalodon, Mosassauro, Rex, Rock Drake, "
            "Astrodelph, Astrocetus, Tapejara; preços CSV×1,15; licença próprio+"
            "um acima; também incluídas nos kits Delta→Omega.",
            "Feat (Web Store / Kits): cards e modal com detalhe estruturado "
            "(armaduras/armas/ferramentas/selas + stats da planilha "
            "itensalfa_kit_descriptions.json); KitDescription com contagens; "
            "título via Name.",
            "Feat (Área da Tribo / Log): espelho do TribeLog por mapa — "
            "tabela tribe_logs, POST /api/tribe/log/ingest, GET /api/tribe/log/"
            "<mapa>, poller TribeLog.log + remote_agent /tribelog; aba Log "
            "em Minha Tribo (um stream por mapa selecionado).",
            "Fix (Área da Tribo / Minha Tribo): is_owner reflete o proprietário "
            "in-game (OwnerPlayerDataID), não quem ativou o painel; remove lock "
            "web que reescrevia is_owner por steam do painel; Admin com badge "
            "correto; lista completa via FTribeData (offline com pdid:<id>); "
            "CustomShop deixa de usar IsTribeOwner (marcava Admin como dono).",
            "Fix (Web Store / Encomenda): cotação no wizard — debounce 280ms + abort "
            "de pedidos antigos; quote deixa de re-listar todo o catálogo "
            "(timeout 15s ao mexer nos sliders); rate limit 90/min.",
            "Fix (Web Store / Encomenda): nomes amigáveis na galeria e Dino Lab — "
            "defaults/catálogo primeiro (Shadowmane, Small Manticore, Meraxes); "
            "remove «Nível 200» e ids crus (lionfishlion, sb_*_200, meraxes_femea).",
            "Docs (Área da Tribo): decisões finais Jul/2026 — limites de construção "
            "adiados (sem enforcement); breeding só regulamento; 1 pessoa=1 "
            "Principal; logs do grupo para todos; admin (exceto support) no "
            "painel/códigos; §20.8 + regulamento §8.10.1 v1.3.",
            "Docs (Área da Tribo): PROJETO_AREA_TRIBO.md §20 (cluster/códigos/"
            "Principal-Fob); regulamento §8.10.1 + ponteiro em §4.2; bump "
            "regulamento 1.2.",
            "Docs (Regulamento §8.12): Encomenda de Dinos — vitrine, preço α/β, "
            "nível auto, contestação via ticket; version bump 1.1 na Web Store.",
        ],
    },
    {
        "version": "1.10.28",
        "date": "2026-07-12",
        "changes": [
            "Feat (Web Store / Catálogo): desistência e auto-cancel reembolsam 90% "
            "do valor pago (retenção 10%); reembolso 100% só via contestação + "
            "ticket com explicação obrigatória (mín. 20 caracteres). Docs §8.4 + UI.",
            "Feat (Web Store / Mercado): desistência/expiração de claim em casal — "
            "reembolso 60% de Y; vendedor recupera dinos e sofre estorno de Y; "
            "pote do sorteio sem estorno; solteiros mantêm reembolso integral no "
            "claim. Texto: «Em caso de desistência, o reembolso é de apenas 60% "
            "do valor pago». Docs §8.7 + UI tutorial.",
            "Feat (Web Store / Mercado): venda em casal (M+F) — vínculo "
            "pair_mate_listing_id, checkout Y=(P1+P2)×0,60, crédito "
            "prize_amber_from_market +=0,40×S na campanha ativa do Sorteio; "
            "solteiros inalterados (fee_amount=0); tribo reparte sobre Y; "
            "card público sem badge −40%/taxa. Docs §8.7 + ECONOMIA.",
            "Feat (Web Store / Encomenda): cotação Lab com breakdown explícito "
            "(stats V, cores C, α, β, total); α/β alinhados a _floor_quality; "
            "UI wizard + Simular preço. Docs ENCOMENDA_DINO_SPEC.",
            "Feat (Web Store / Encomenda): vitrine rotativa — 10 slots (mix 6 grande "
            "+ 2 médio + 2 pequeno) + até 5 permanentes; duração em dias "
            "(7/15/custom); auto-rotação ao expirar; «Rodar agora»; catálogo "
            "jogador filtrado pela vitrine. Admin: Dino Lab → Vitrine.",
            "Feat (CustomDinoDeliver): `/dinoclass` (alias `/dumpdino`) — admin "
            "imprime GetClass *_C + path do dino mais próximo "
            "(PropagatorDinoBlacklist / ItensAlfa). Bump v1.10.14 → v1.10.15. "
            "Docs/ARKLAND_PLUGIN_DEBUG.md.",
            "Fix (CustomShop / economia opção A): L1 Price = root_value "
            "(sync_shop_l1_prices_from_root.py + kits pack10 a 25% off); "
            "L200 = round(0.40 × V254) com V254=min(R+B, market_absolute_max); "
            "docs/SHOP_L200_PRICING.md.",
            "Fix (CustomShop): dinos *_l200 com sexo aleatório — remove Gender "
            "(plugin não força male/female); Name/Description sem «Fêmea»; "
            "apply_shop_l200_prices.py e docs/SHOP_L200_PRICING.md.",
            "Fix (Plugins / Debug ARKLAND): pasta logs/ + README + boot em "
            "arkland_debug.log sempre no arranque; TribeSync avisa se ServerId/"
            "MySQL offline. Bump CustomShop v1.10.15 → v1.10.16; "
            "CustomDinoDeliver v1.10.13 → v1.10.15. Docs/ARKLAND_PLUGIN_DEBUG.md.",
            "Docs (Regulamento v1.1): §3.5 aconselha não doar entre jogadores e "
            "proíbe doar recursos/dinos/itens que exigem licença ativa "
            "(punição administrativa); §8.4 desistência 90%/contestação+ticket; "
            "§8.7 casal 60% + contribuição sorteio; solteiros claim integral.",
        ],
    },
    {
        "version": "1.10.27",
        "date": "2026-07-12",
        "changes": [
            "Feat (CustomShop / Web Store): dinos nível 200 no catálogo — "
            "entradas `*_l200` com preço "
            "`P200 = round(clamp(P1 × k, P1+1, 0.75×M))` "
            "(k=1.40 configurável, M=root_value); skip se 0.75×M ≤ P1; "
            "aba dedicada «Dinos 200» (aba Dinos só L1); "
            "script idempotente tools/apply_shop_l200_prices.py; "
            "docs/SHOP_L200_PRICING.md.",
            "Fix (CustomShop): alinhamento catálogo — ID `astrodelphis_1` → "
            "`astrodelphis` (defaults/mercado); `MarketInclude: true` nos 81 L1 "
            "em falta; 29 `*_l200` reaplicados com defaults do repo "
            "(não WEBSTORE Desktop); configs espelhados em bin.",
        ],
    },
    {
        "version": "1.10.26",
        "date": "2026-07-12",
        "changes": [
            "Feat (Web Store / Dino Lab): sync catálogo CustomShop → "
            "market_species_defaults — 20 itens L1 em falta (Meraxes, Brighamia, "
            "Tek Strider) passam a listar no Mercado/Dino Lab; botão «Simular preço» "
            "estima encomenda (floor_quality + cores + taxas) sem debitar; "
            "POST /api/admin/custom-dino/simulate e validate?dry_run=1.",
            "Feat (Plugins / Debug ARKLAND): logging dedicado (JSONL + ring buffer + "
            "MySQL `arkland_plugin_debug`) independente do ArkApi Log — níveis "
            "ERROR→TRACE, categorias, correlation_id; Admin «Debug Plugins»; "
            "docs/ARKLAND_PLUGIN_DEBUG.md. Default Debug.Enabled=false. "
            "Bump CustomShop v1.10.13 → v1.10.14; CustomDinoDeliver v1.10.12 → v1.10.13.",
            "Feat (Área da Tribo / Mercado): regras finais de repartição — opt-in "
            "por jogador (fora do pool = 100% nas vendas próprias); default 60/40 "
            "(quem envia / demais do pool); dono edita %; snapshot na ativação do "
            "anúncio; proteção de dono no TribeSync/web (não sobrescreve "
            "proprietário já registado). Docs §18 atualizado.",
            "Feat (CustomShop / TribeSync): sync pull sem RCON — «Verificar de novo» "
            "cria tribe_sync_requests na MySQL; plugin (~15s) grava presença/membros/"
            "map_links na mesma DB; HTTP presença como redundância; RCON só atalho. "
            "Bump CustomShop v1.10.11 → v1.10.12.",
            "Fix (CustomShop / TribeSync): MyTribeData com TribeID=0 mas GetTribeId/"
            "TargetingTeam válidos — deixa de abortar antes do POST /api/tribe/presence; "
            "Shop.Reload reconfigura HttpClient. Bump CustomShop v1.10.10 → v1.10.11.",
            "Bump (CustomShop): v1.10.12 → v1.10.13 — proteção de dono no auto-link.",
        ],
    },
    {
        "version": "1.10.25",
        "date": "2026-07-12",
        "changes": [
            "Fix (ActiveEvent / ASE): a cmdline passa a usar a flag oficial "
            "`-ActiveEvent=` (wiki) em vez de `?ActiveEvent=` na travel URL — "
            "corrige Páscoa, vday e demais eventos que apareciam no log mas não "
            "ativavam dinos coloridos; perfil prevalece sobre Additional Args; "
            "aplicar Eventos Globais sincroniza o combo do painel aberto (evita wipe).",
        ],
    },
    {
        "version": "1.10.24",
        "date": "2026-07-12",
        "changes": [
            "Fix (Web Store / Sorteio): editor de campanha lista automaticamente kits e "
            "licenças do catálogo CustomShop (checkboxes via "
            "`GET /api/admin/lottery/prize-options`); corrige dropdown vazio por IDs "
            "duplicados no `<select>`; cada ganhador recebe 1× de cada prémio extra "
            "seleccionado + parcela de Âmbares; entrega automática no draw.",
        ],
    },
    {
        "version": "1.10.23",
        "date": "2026-07-12",
        "changes": [
            "Feat (Web Store / Sorteio): prémios de catálogo — kits (kit_*) e licenças "
            "(licenca_*/Type license) configuráveis na admin; cada titular recebe Âmbares + "
            "pedidos na fila da loja (licença activa entitlement como compra).",
            "Feat (Web Store / Sorteio): após COMPLETED o auto-chain cria o próximo sorteio em "
            "DRAFT com janela de preparação de 24h (`starts_at`); só vira ACTIVE (venda de "
            "números) depois — staff pode editar prémio, kits/licenças, título e datas; "
            "auto-ativação no worker.",
            "Fix (Web Store / Sorteio): relatório COMPLETED e página pública passam a mostrar "
            "sempre números sorteados e vencedores; modal de resultado após o draw "
            "(antes de/independente do próximo); `last_completed` + `upcoming` em "
            "`/api/public/lottery/current`.",
            "Feat (Web Store / Kits ItensAlfa): «o que inclui» — descrições e conteúdo dos kits "
            "a partir de itensalfa_kit_descriptions.json no enrich do catálogo (cards e modal).",
            "Fix (CustomShop / TribeSync): silêncio total no login — logs em cada tentativa/skip; "
            "resolve PC por SteamID; ServerId independente de CrossChat.Enabled "
            "(Settings.ServerId + CrossChat.ServerId + mapa); sync TEK grava ServerId "
            "mesmo com chat off; painel deixa de apagar ServerId ao guardar CrossChat.",
            "Fix (CustomShop / HangWatcher): WinHttpSetTimeouts no HttpClient; TribeSync poll "
            "separado do DeliverPending; SyncAllOnlinePlayers 1 POST/s; retries login param no sucesso.",
            "Fix (CustomDinoDeliver / HangWatcher): WinHttpSetTimeouts no DinoHttpClient "
            "(mitiga bloqueio longo no game thread se a API não responder).",
            "Bump (CustomShop): v1.10.9 → v1.10.10 — TribeSync logs + ServerId desacoplado.",
            "Bump (CustomShop): v1.10.8 → v1.10.9 — HTTP timeouts + TribeSync não empilha no tick.",
            "Bump (CustomDinoDeliver): v1.10.11 → v1.10.12 — HTTP timeouts.",
        ],
    },
    {
        "version": "1.10.22",
        "date": "2026-07-11",
        "changes": [
            "Fix (CustomShop / TribeSync): retries pós-login (8/20/45/90s), poll ~3 min, "
            "Shop.Reload/Shop.TribeSync e validação HTTP — corrige «Nenhuma presença» "
            "quando a tribo demora ou o jogador já estava online; aviso se ServerId em falta.",
            "Fix (Web Store / Minha Tribo): toast dedupe + aviso curto no Verificar de novo "
            "(não empilha 5 toasts iguais); ignora server_id=unknown no auto-link.",
            "Bump (CustomShop): v1.10.7 → v1.10.8 — TribeSync retries/poll.",
            "Feat (Plugins): CHANGELOG.md por plugin (CustomShop, CustomDinoDeliver); "
            "gate no _release.ps1 (scripts/check_plugin_release_gate.py) exige bump de "
            "plugin_version.txt + secção no changelog do plugin quando o código C++ muda; "
            "«Versões esperadas» na UI lê PluginInfo.json embutido (VersionLabel).",
            "Bump (CustomShop): v1.10.6 → v1.10.7 — ShopTribeSync, SyncPlayerOnJoin/licenças "
            "e melhorias cryo/mercado; sync PluginInfo + plugin_version.h.",
            "Bump (CustomDinoDeliver / Dino Lab): v1.10.10 → v1.10.11 — SpawnExact wild_stats, "
            "find-after-spawn e NormalizeBlueprintPath (stats/Titan Wyvern).",
            "Feat (Web Store / Pedidos): desistência com regras — licenças irrevogáveis "
            "(sem cancel/reembolso); itens/kits só após 24h; auto-cancel + reembolso Âmbar "
            "em PENDENTE ≥48h no worker arkshop-retry (idempotente).",
            "Feat (CustomShop / ItensAlfa): catálogo completo de armas/ferramentas da planilha "
            "(14 armas + 9 ferramentas por BP disponível) na loja e nos kits kit_itensalfa_*; "
            "+120 SKUs; BPs só da planilha (sem inventar).",
            "Feat (CustomShop / ItensAlfa): acréscimo de +15% em todos os preços de itens, kits "
            "e criaturas ItensAlfa (base proposta × 1.15); licenças licenca_* sem alteração.",
            "Feat (CustomShop / ItensAlfa): criaturas/veículos TEK (HoverSkiff, Enforcer, Defender, "
            "Submarine, Stryder Alfa/Universal/PerfectPVE/PerfectPVP) passam a exigir QUALQUER "
            "licença Delta→Exótico (sem Nuvem/keyvault); armaduras/armas/kits mantêm gate N+N−1.",
            "Fix (CustomShop): remove Mek/MiniMegaMek/Exo-Mek e HoverSail do catálogo "
            "(crash no servidor) — IDs abyss_hover_sail, itensalfa_hoversail_alfa, "
            "itensalfa_exomek_alfa, itensalfa_mek_alfa/omega/minimega; HoverSkiff/Enforcer/"
            "Defender/Stryder/Submarine mantidos; apply_itensalfa bloqueia reintrodução.",
        ],
    },
    {
        "version": "1.10.21",
        "date": "2026-07-11",
        "changes": [
            "Feat (CustomShop / ShopTribeSync): presença do proprietário no login "
            "(OwnerPlayerDataID/Proprietário) → API de mapa; CustomShop.dll recompilado "
            "com ShopTribeSync no build_cl.",
            "Fix (Web Store / Minha Tribo): auto-link sem tribe_name, POST /api/tribe/sync "
            "no Verificar de novo, ServerId no CrossChat mesmo desligado.",
            "Fix (Licenças / Permissions): renovação soma dias no ark_permission e no RCON "
            "AddTimed (horas = expires residual+novos), em vez de substituir por now+Days — "
            "corrigia keyvault/~17d após compra de 30d com residual; afecta todos os tiers "
            "temporários (Delta→Exótico, Nuvem, VIP).",
            "Fix (config): licenca_nuvem volta a Type license + LicenseGrant keyvault/30d "
            "(regressão Type command sem Grant).",
            "Fix (CustomShop / SyncPlayerOnJoin): grupos temporários realinhados ao expires do DB "
            "mesmo se já estiverem no Permissions (evita residual stale).",
            "Fix (Web Store / claim): ENTREGUE por «já licenciado» só se source=order_id; "
            "re-sync Permissions ao finalizar — residual antigo não salta a entrega da renovação.",
            "Fix (Dino Lab / Problema A — stats): encomenda com HP/melee passa a gerar "
            "spawn_exact.wild_stats quando custom_dino_spawn_exact=true; plugin deixa de "
            "escolher tame antigo no find-after-spawn (cryopod com stats errados).",
            "Fix (Dino Lab / Problema B — Titan Wyvern): NormalizeBlueprintPath endurecido; "
            "find-after-spawn com raio 15k, retry e só dinos novos; erro "
            "spawn_exact_not_found em vez de identity_capture_failed falso; aspas no log "
            "eram artefacto de formatação (BP do catálogo estava correcto).",
        ],
    },
    {
        "version": "1.10.20",
        "date": "2026-07-11",
        "changes": [
            "Feat (CustomShop / ItensAlfa): 13 criaturas/veículos TEK da planilha (HoverSkiff/Sail, Exo-Mek, Mek, Enforcer, Defender, Submarine, Stryder PerfectPVE) com gates N+N−1; Stryder só PerfectPVE (Delta→Exótico, sem Nuvem/keyvault).",
            "Feat (Web Store / Home): mural de avisos editável pelo admin (título + corpo) — schema home_notice no boot, API admin e card na home pública.",
            "Feat (Server Manager): mod_path_blacklist em %APPDATA%/ARKLAND-ServerManager/config.json — apaga paths relativos (default ShooterGame/Content/Mods/1565015734/Mek) antes de start/restart e no boot TEK; também após instalar o mod.",
            "Fix (Web Store / Minha Tribo): botão Ativar painel de tribo + fluxo membros — showToast→toast, empty state pós-ativação, modais, backfill de mapas, adicionar membro por SteamID (MVP).",
            "Fix (CustomShop / XP): exp_1000 passa a executar AddExperience com ExecuteAsAdmin — jogador comum recebia confirmação sem ganhar XP.",
            "Fix (CustomShop / ItensAlfa): remove VisousMod do catálogo — armas/ferramentas/armaduras TEK substituídas por BPs ItensAlfa da planilha; Blindado/Gen2 e armas Exótico sem BP removidos; kits VIP e kit_itensalfa_* actualizados.",
        ],
    },
    {
        "version": "1.10.19",
        "date": "2026-07-10",
        "changes": [
            "Feat (Licenças ItensAlfa): escada Delta→Exótico (6k–230k Â) — 9 tiers, renovação −20%, TimedPoints, gates N+N−1, kits kit_itensalfa_*; migration tools/migrate_itensalfa_licenses.py + SQL.",
            "Feat (Web Store / boot): migration ItensAlfa (license_tier_catalog) corre automaticamente em _migrate_schema via ensure_itensalfa_licenses_schema (idempotente).",
            "Feat (CustomShop / Catálogo): 91 novas espécies vanilla/DLC Level 1 (98→189 entries; market defaults 78→169) com preços por tier/papel.",
            "Feat (Área da Tribo / Mercado): schema e rotas de tribo no boot + repartição de payout no mercado.",
            "Fix (ActiveEvent / Eventos Globais): restart e start não apagam mais Easter/Páscoa — widgets obsoletos do painel do servidor só sincronizam quando o painel está aberto.",
            "Fix (ActiveEvent / legado): aplicar evento global atualiza a instância em memória do servidor legado para o próximo start usar ?ActiveEvent= correto.",
        ],
    },
    {
        "version": "1.10.18",
        "date": "2026-07-09",
        "changes": [
            "Feat (Eventos Globais): painel unificado para ActiveEvent (Páscoa, Halloween…) — aplicar em todos ou servidores selecionados, agendamento com broadcasts 10/5/3/2/1 min, restart automático e avisos por 1 h.",
            "Melhoria (Eventos Globais): aba renomeada de Eventos Sazonais; rates temporários separados na seção inferior; legendas explicativas dos botões.",
            "Melhoria (Sidebar TEK): área rolável entre logo e rodapé — servidores visíveis em monitores menores.",
            "Feat (Dashboard): seção Armazenamento com espaço livre/total por disco (C:, D:, …) e barra de uso.",
        ],
    },
    {
        "version": "1.10.17",
        "date": "2026-07-09",
        "changes": [
            "Fix (ActiveEvent / INI): caminho canônico WindowsServer para leitura e escrita de GUS/Game.ini; user_config_folder só espelha; ActiveEvent do perfil TEK prevalece sobre blocos raw/custom.",
            "Fix (Eventos Sazonais): restore de backup de buff preserva ActiveEvent (Páscoa/Easter, etc.) do perfil ou do GUS atual — evento sazonal não some ao encerrar buff.",
            "Feature (Web Store / Ícones): pipeline de 56 WebPs de recursos (manifesto, registry, catalog_enrich) com fallback por categoria quando sem ícone dedicado.",
            "Fix (Web Store / Catálogo): cards de dino exibiam área preta com só badge de tier — agora mostram thumbnail da espécie (WebP) com fallback por tier, como no Mercado.",
            "Fix (Web Store / Update): auto_start_webstore reinicia processo stale quando /api/version difere do TEK após instalação — não exige parar/iniciar manualmente.",
        ],
    },
    {
        "version": "1.10.16",
        "date": "2026-07-09",
        "changes": [
            "Improvement (Web Store / Ícones): resolução canônica dos novos WebPs unificada entre registro de espécies, Mercado, Encomenda Dino, Dino Lab e históricos/admin com fallback consistente por tier.",
            "Feature (Web Store / Ícones): manifesto expandido com novos ícones WebP oficiais e aliases visuais para criaturas vanilla exibidas na loja.",
        ],
    },
    {
        "version": "1.10.15",
        "date": "2026-07-08",
        "changes": [
            "Feat (Web Store): auto-feed do catálogo CustomShop para Mercado e Dino Lab com deduplicação forte (blueprint, espécie e nome).",
            "Fix (CustomShop / Abyssal): blueprint paths corrigidos — segmento /Abyssal/ alinhado ao padrão wiki em config, registry e testes.",
            "Fix (Eventos Sazonais): após restaurar backup INI, perfil TEK/ASM é ressincronizado em memória e persistência (rates do evento não ficam presos).",
        ],
    },
    {
        "version": "1.10.14",
        "date": "2026-07-07",
        "changes": [
            "Feat (Web Store): referência de Color IDs — tabela estática (criaturas 1–100, tintas 201–226, especiais) com busca, abas e copiar ID ao clicar; modal e painéis em Encomenda Dino, entrega e showcase do Dino Lab.",
        ],
    },
    {
        "version": "1.10.13",
        "date": "2026-07-07",
        "changes": [
            "Fix (Nível do jogador): modo simples (vanilla) — espelha ASM EnableLevelProgressions=false; não reescreve LevelExperienceRampOverrides, remove rampa antiga no save, cap via OverrideMaxExperiencePointsPlayer no GUS com curva vanilla.",
            "Feat (Nível do jogador): toggle Progressões customizadas no painel TEK/ASM — rampa single-line e engramas 400/nível só quando habilitado.",
            "Fix (Encomenda Dino): modal corrigido, vitrine/galeria de showcase, deduplicação de pedidos e melhorias na Web Store.",
        ],
    },
    {
        "version": "1.10.12",
        "date": "2026-07-07",
        "changes": [
            "Feat (Encomenda Dino): MVP na Web Store — aba Encomendas no Dino Lab, API de pedidos, integração com entrega custom e spec ENCOMENDA_DINO.",
            "Fix (Web Store / Sugestões): painel admin de sugestões corrigido (carregamento e ações); testes de regressão.",
            "Melhoria (Tutoriais): comandos atualizados — removido /c; documentados /dinolab e aliases legados.",
            "Fix (Nível do jogador): detecção de curva XP legada na rampa (infer_xp_curve_from_ramp), preservação do cap geométrico ao sincronizar Game.ini.",
        ],
    },
    {
        "version": "1.10.11",
        "date": "2026-07-07",
        "changes": [
            "Fix (Nível do jogador): modelo unificado — admin define só o nível base; sistema deriva +100 (75 boss na rampa + 25 conquistas), rampa Game.ini com base+75 slots, cap XP no base e 400 pontos de engrama fixos por nível.",
            "Melhoria (Nível do jogador): painel TEK/ASM simplificado — removidos tiers/checkboxes; teto, rampa e engramas calculados automaticamente.",
        ],
    },
    {
        "version": "1.10.10",
        "date": "2026-07-07",
        "changes": [
            "Feat (Dino Lab / Mercado): bloqueio MVP de venda — registro de DinoID na entrega, checagem no /enviar com linhagem via HTTP, endpoints admin e audit.",
            "Fix (CustomDinoDeliver): crash ao usar SpawnExact — SEH isolado, validação de contexto e limites de nível.",
            "Fix (CustomShop): bloqueio Dino Lab no mercado (/enviar e /confirmar) com mensagem ao jogador; /rastreardebug para staff.",
        ],
    },
    {
        "version": "1.10.9",
        "date": "2026-07-07",
        "changes": [
            "Melhoria (Eventos Sazonais): rebrand e painel de gestão alinhados à nomenclatura Eventos Sazonais (UI, criação e cards de evento ativo).",
            "Feat (Eventos Sazonais): backup dos .ini em zip em ARKLAND SERVER/BACKUP/.ini/{servidor}/ antes de aplicar alterações.",
            "Feat (Eventos Sazonais): área de emergência — listar backups, restaurar servidor ou cluster inteiro (aviso 5 min → SaveWorld → stop → restore → start).",
            "Feat (Eventos Sazonais): multiplicadores por setor (XP/Doma/Breeding/Farm) com cálculo base×alvo assumindo servidor 5x (campos inversos de breeding/farm corrigidos).",
            "Feat (Eventos Sazonais): broadcast periódico durante evento ativo (mensagem admin + intervalo em minutos).",
            "Feat (Nível do jogador): unificação base + rampa Game.ini + cap XP — Web Store exibe teto efetivo in-game; rampa via patch de chaves repetidas; engrams sincronizados com nível base.",
        ],
    },
    {
        "version": "1.10.8",
        "date": "2026-07-07",
        "changes": [
            "Fix (CustomDinoDeliver): /dinolab + alias /dinopoll; reinstale DLL nos mapas.",
            "Melhoria (Eventos Sazonais): rebrand de BUFFs/Rates Temporários para Eventos Sazonais na UI, logs, Discord e Web Store.",
        ],
    },
    {
        "version": "1.10.7",
        "date": "2026-07-06",
        "changes": [
            "Fix (CustomDinoDeliver): entrega falhava com type_error.302 em campos JSON null (saddle_blueprint, custom_name) — JsonStr com fallback seguro.",
            "Fix (CustomDinoDeliver): callback /delivered rejeitava quando todos os pedidos falhavam (order_ids vazio) — aceita failures sem order_ids.",
            "Fix (Dino Lab / Web): payload_json normaliza saddle_blueprint e custom_name null para string vazia.",
            "Fix (TEK): aba SQL Executar usa banco correto (arkland_shop para consultas em orders).",
            "Feature (Plugins): versões independentes por plugin (bump no compile); release sincroniza PluginInfo sem sobrescrever plugin_version.txt; TEK compara instalado vs esperado.",
        ],
    },
    {
        "version": "1.10.6",
        "date": "2026-07-06",
        "changes": [
            "Fix (TEK): sync de plugins agora copia CustomDinoDeliver.dll, não só config.json",
            "Feature (Plugins): versionamento independente por plugin (plugin_version.txt); TEK compara versão instalada vs bundle do app.",
        ],
    },
    {
        "version": "1.10.5",
        "date": "2026-07-06",
        "changes": [
            "Fix (CustomDinoDeliver): pedidos presos em ENTREGANDO — release/callback em falha, mutex anti-concorrência, mensagem /dinolab só após entrega real.",
            "Fix (CustomDinoDeliver): SpawnExact com fallback SpawnDino; logs detalhados por pedido; exceções capturadas no loop de entrega.",
            "Fix (Dino Lab / Web): recuperação automática de ENTREGANDO stale (custom_dino_stale_entregando_minutes, padrão 5 min).",
        ],
    },
    {
        "version": "1.10.4",
        "date": "2026-07-06",
        "changes": [
            "Fix (CustomDinoDeliver): crash fatal ao usar /dinolab — assinatura correta do handler de chat ArkApi.",
        ],
    },
    {
        "version": "1.10.3",
        "date": "2026-07-06",
        "changes": [
            'Feature (Dino Lab / SpawnExact): Fase 4 — stats por ponto (wild/tamed), nível calculado automaticamente e imprint na entrega administrativa.',
            'Feature (Dino Lab): teto total de nível configurável (custom_dino_level_max); padrão 0 = sem limite total; validação por stat 0-254.',
            'Fix (Web Store / UI): sidebar Minha Area — nick em destaque e SteamID sem quebra de linha (classes auth-profile).',
            'Fix (Plugin CustomDinoDeliver): comando de chat renomeado de /dinopoll para /dinolab; README e guia atualizados; DLL recompilada.',
            'Fix (Plugin CustomDinoDeliver): crash fatal ao usar /dinolab — assinatura correta do handler de chat (AShooterPlayerController*, EChatSendMode::Type); null-checks e try/catch defensivos.',
        ],
    },
    {
        "version": "1.10.2",
        "date": "2026-07-06",
        "changes": [
            "Fix (Web Store / MySQL): migração payload_json corrige resgate do catálogo e erro HTTP 500 no Dino Lab.",
            "Feature (Web Store / Sorteio): número fixo por jogador registrado, confirmação gratuita por campanha até 2h antes do sorteio e troca do número por 5000 Âmbares; APIs confirm-participation e change-fixed-number; UI Minha Área.",
        ],
    },
    {
        "version": "1.10.1",
        "date": "2026-07-06",
        "changes": [
            "Fix (Dino Lab): dropdown de especies falhava ao carregar — fallback de blueprint via catalogo "
            "CustomShop e rota /species sem exigir banco.",
            "Feature (Dino Lab): modo Blueprint manual na web — colar Blueprint'/Game/...' ou /Game/... "
            "para dinos de mod ou fora da lista homologada.",
        ],
    },
    {
        "version": "1.10.0",
        "date": "2026-07-06",
        "changes": [
            "Feature (Dino Lab): entrega administrativa de dinos customizados — menu admin na Web Store, "
            "fila item_type=custom_dino com payload_json (6 cores, nivel, sexo, motivo), historico e "
            "APIs /api/admin/custom-dino/* e /api/pending/custom-dino/*.",
            "Feature (Plugin CustomDinoDeliver): DLL separada do CustomShop — spawn, cores Obelisk, "
            "cryopod, poll HTTP, fallback inventario cheio; comandos DinoDeliver.Reload (RCON) e /dinolab (chat).",
            "Feature (TEK / Loja): botao Instalar Dino Lab em todos os servidores, sync WebApiUrl/WebApiKey, "
            "reload RCON conjunto Shop + Dino Lab; build.bat e ARKLAND-Multi.spec empacotam CustomDinoDeliver.dll.",
            "Docs: guia operacional docs/DINO_LAB_GUIA.md e spec DINO_LAB_SPEC.md atualizada para MVP operacional.",
        ],
    },
    {
        "version": "1.9.217",
        "date": "2026-07-05",
        "changes": [
            "Feature (Web Store / Sorteio admin): relatorio da campanha ativa com numeros usados/disponiveis, "
            "participantes e nicks Steam; botao Ver relatorio na administracao de sorteios; "
            "API GET /api/admin/lottery/campaigns/{id}/report.",
        ],
    },
    {
        "version": "1.9.216",
        "date": "2026-07-05",
        "changes": [
            "Fix (Web Store / Sorteio): pagina #/sorteio ainda retornava HTTP 500 ao listar participantes "
            "- get_participants_public usava assigned_at ausente em schema MySQL parcial; ordenacao via "
            "_table_has_column e fallback MAX(ln.id); _resolve_display_name tolera colunas ausentes em store_users.",
        ],
    },
    {
        "version": "1.9.215",
        "date": "2026-07-05",
        "changes": [
            "Fix (Web Store / Sorteio): página #/sorteio retornava HTTP 500 ao carregar campanha "
            "ativa — _campaign_public_dict acessava colunas ausentes em schema MySQL parcial "
            "(pré-migração); leitura segura via _row_val.",
        ],
    },
    {
        "version": "1.9.214",
        "date": "2026-07-05",
        "changes": [
            "Fix (CustomShop / Notas): /notas agora desbloqueia explicitamente as 200 runas de Fjordur "
            "(GiveExplorerNote 1000-1199) — GiveAllExplorerNotes sozinho concedia +10 niveis das notas "
            "globais mas nao creditava as runas no implante.",
        ],
    },
    {
        "version": "1.9.213",
        "date": "2026-07-05",
        "changes": [
            "Fix (CustomShop / Notas): /notas exige CustomShop.dll recompilado (>= 1.9.207) "
            "implantado em cada mapa — releases anteriores podiam empacotar DLL antiga se o "
            "build C++ falhasse; logging de diagnóstico em CmdNotas, ShopNotes e ShopConfig.",
            "Melhoria (CustomShop / Config): template config.json inclui EngramasCommandPrice, "
            "NotasCommandPrice (5000) e NotasCommandEnabled (true) em Settings.",
        ],
    },
    {
        "version": "1.9.212",
        "date": "2026-07-05",
        "changes": [
            "Fix (Web Store / Sorteio): reserva de número específico retornava HTTP 500 — "
            "reutiliza slots REVOKED, trata IntegrityError no commit, migra colunas ausentes "
            "do schema MySQL e isola falha de auditoria/ledger.",
            "Fix (Web Store / Sorteio): débito de Âmbares na reserva/compra passa a retornar "
            "402 (saldo insuficiente) em vez de permitir saldo zerado silenciosamente.",
        ],
    },
    {
        "version": "1.9.211",
        "date": "2026-07-05",
        "changes": [
            "Feature (Web Store / Sorteio de Doações): promoção vinculada a doações PIX/cartão "
            "e compra opcional de números com Âmbares — grade pública 100–999, sorteio automático "
            "com rollover +25% sem vencedor, divisão integral do prêmio entre titulares (spec v1.6), "
            "Área Pública #/sorteio, Minha Área, admin Sorteios, hook em _finalize_pix_payment.",
            "Feature (Web Store / Sorteio): regulamento publicado em static/lottery_regulamento_v1_5.html com link na area do sorteio.",
            "Fix (Web Store / Admin mercado): detalhe de auditoria usa _auditRow corretamente no modal.",
            "Fix (Testes arkshop_web): fixture autouse remove STEAM_API_KEY do ambiente para nao bater na API Steam em CI/local."
        ],
    },
    {
        "version": "1.9.210",
        "date": "2026-07-05",
        "changes": [
            "Melhoria (Web Store / Notificações): centro de notificações definitivo — painel "
            "480px no desktop e bottom sheet full-width no mobile; portal no body (corrige "
            "painel minúsculo preso à sidebar); ícones por tipo, subtítulo de não lidas, "
            "empty state, backdrop e scroll independente; tema dark/âmbar.",
        ],
    },
    {
        "version": "1.9.209",
        "date": "2026-07-05",
        "changes": [
            "Feature (Web Store / Mídias): página pública #/midias com vídeos YouTube em grid "
            "(tutoriais, informativos e geral); filtro por categoria; admin CRUD em /api/admin/media.",
        ],
    },
    {
        "version": "1.9.208",
        "date": "2026-07-05",
        "changes": [
            "Melhoria (Web Store / Home): removida barra fixa inferior «Conectar ao servidor» — "
            "conexão permanece no hero e na seção de servidores da página inicial.",
        ],
    },
    {
        "version": "1.9.207",
        "date": "2026-07-05",
        "changes": [
            "Feature (CustomShop / Notas): comando /notas desbloqueia todas as notas de explorador "
            "e as 200 runas de Fjordur via GiveAllExplorerNotes; custo configurável "
            "(Settings.NotasCommandPrice, padrão 5000) com confirmação /confirmar (TTL 2 min).",
            "Feature (CustomShop): Shop.UnlockAllExplorerNotes para RCON/console e entrega da loja.",
            "Melhoria (Web Store / Admin): campos Preço /notas e Ativar /notas nas configurações do CustomShop.",
        ],
    },
    {
        "version": "1.9.206",
        "date": "2026-07-05",
        "changes": [
            "Feature (Web Store / Sugestões): área Sugestões da Comunidade — jogadores enviam ideias de dinos, recursos e itens; "
            "admin avalia com status e nota; limite 3/dia; rota #/sugestoes.",
        ],
    },
    {
        "version": "1.9.205",
        "date": "2026-07-04",
        "changes": [
            "Fix (Web Store / Âmbarômetro): nota de cobertura lista apenas o que entra no total "
            "(doações, loja web, mercado P2P, ajustes admin e enquetes) — sem menção a /shop ou fase 2.",
        ],
    },
    {
        "version": "1.9.204",
        "date": "2026-07-04",
        "changes": [
            "Feature (TEK / Web Store): campo Chave Steam Web API (nicknames) no painel CustomShop → Web Store — "
            "persiste em config TEK e settings.json, repassa ao subprocesso (STEAM_API_KEY) sem editar .env.",
            "Fix (Web Store): nicknames Steam lidos de settings.json quando env vazio — GET /api/health → steam_api_configured; "
            "admin web pode salvar steam_api_key em /api/settings.",
        ],
    },
    {
        "version": "1.9.203",
        "date": "2026-07-04",
        "changes": [
            "Feature (Web Store / Doações): checkout com cartão sem CPF obrigatório — pagamento internacional com e-mail e nome; PIX mantém CPF e telefone brasileiro.",
            "Feature (Web Store / Doações): estimativa USD/EUR ao lado dos preços em R$ — GET /api/public/exchange-rates (Frankfurter, cache 1h, fallback estático).",
            "Melhoria (Web Store / Doações): formulários separados PIX vs cartão, texto internacional na UI e pacotes enriquecidos no catálogo/home.",
        ],
    },
    {
        "version": "1.9.202",
        "date": "2026-07-04",
        "changes": [
            "Fix (Web Store / Admin): Gerenciar Jogadores descartava nicks da Steam API — persistência em sessão isolada (evita conflito com SELECT admin) e lookup steam_id normalizado.",
            "Fix (Web Store / Admin): aviso visível quando STEAM_API_KEY ausente ou batch GetPlayerSummaries falha (steam_persona_warning).",
            "Fix (Web Store / Steam): STEAM_API_KEY carregada de .env persistente (TEK) e repassada ao subprocesso da Web Store.",
            "Melhoria (Web Store / Admin): Pedidos (admin) com paginação, total, filtro por SteamID/pedido, status e intervalo de datas — GET /api/admin/orders?offset&limit&q&status&date_from&date_to.",
        ],
    },
    {
        "version": "1.9.201",
        "date": "2026-07-04",
        "changes": [
            "Fix (Web Store / Âmbarômetro): GET /api/public/amber-stats com limite próprio (120/min) em vez do default global 50/h — evita 429 na home.",
            "Fix (Web Store / Âmbarômetro): em 429 ou falha de rede mantém último valor válido, mensagem discreta de retry e backoff exponencial no polling.",
        ],
    },
    {
        "version": "1.9.200",
        "date": "2026-07-04",
        "changes": [
            "Melhoria (Web Store / Notificações): painel redesenhado — 440px desktop, drawer full-width no mobile, tipografia e padding legíveis, botão Marcar todas lidas sem corte, tema dark/âmbar.",
        ],
    },
    {
        "version": "1.9.199",
        "date": "2026-07-04",
        "changes": [
            "Fix (Web Store): nick Steam único em todo o portal — steam_persona da API GetPlayerSummaries substitui nomes editáveis obsoletos (market_display_name / display-name-gate).",
            "Fix (Web Store / Admin): batch GetPlayerSummaries corrigido (vírgulas nos SteamIDs) e lista Gerenciar Jogadores sempre atualiza personas da API, nunca cache stale.",
            "Fix (Web Store / Login): a cada login Steam sobrescreve steam_persona no banco; /api/auth/me retorna nick atual.",
            "Fix (Web Store / Regulamento): HTML estático regulamento_v1_0.html gerado no build e empacotado no PyInstaller — página e gate exibem o texto completo em produção (TEK).",
            "Fix (TEK / INI): conteúdo extra Game.ini sem cabeçalho de seção grava em [/Script/ShooterGame.ShooterGameMode] em vez de ServerSettings.",
        ],
    },
    {
        "version": "1.9.198",
        "date": "2026-07-04",
        "changes": [
            "Fix (Web Store / Admin): lista Gerenciar Jogadores busca nick Steam em lote (GetPlayerSummaries), grava em store_users.display_name e exibe persona para todos — não só quem já fez login.",
            "Feature (Web Store / Regulamento): página dedicada, link no rodapé, gate de aceite no 1º login com versão 1.0 persistida por steam_id; guards em tickets e doações/resgates.",
        ],
    },
    {
        "version": "1.9.197",
        "date": "2026-07-04",
        "changes": [
            "Fix (Web Store): boot crash refreshNotificationsBadge.",
        ],
    },
    {
        "version": "1.9.196",
        "date": "2026-07-03",
        "changes": [
            "Feature (Web Store / Kits): na renova??o de licen?a (Alfa, Beta ou Gamma), os limites de resgate dos kits com DefaultAmount vinculados ao grupo da licen?a s?o resetados ao valor inicial do cat?logo.",
        ],
    },
{
        "version": "1.9.195",
        "date": "2026-07-03",
        "changes": [
            "Feature (Web Store / Âmbarômetro): painel público na home com volume acumulado de âmbares movimentados; API GET /api/public/amber-stats.",
            "Feature (Web Store / Âmbarômetro): ledger idempotente (amber_ledger) registrando doações, loja web, mercado P2P, recompensas de enquetes e ajustes administrativos.",
        ],
    },
    {
        "version": "1.9.194",
        "date": "2026-07-03",
        "changes": [
            "Feature (Web Store / Comércio): notificações in-app para staff (market_staff_alert / market_staff_critical) em flag e remoção de anúncios.",
            "Melhoria (Web Store / Comércio Admin): timeline de anúncio inclui amber_snapshot de movimentação de âmbares.",
            "Melhoria (Web Store / Kits): ao renovar licença, limites de kits vinculados à licença são restaurados automaticamente.",
        ],
    },
    {
        "version": "1.9.193",
        "date": "2026-07-03",
        "changes": [
            "Feature (Web Store / Comércio Admin): auditoria mercado com paginação, filtros (listing, severity, datas, busca q), detalhe por ID e labels PT-BR.",
            "Feature (Web Store / Comércio Admin): timeline por anúncio (GET /api/market/admin/listings/<id>/timeline) — listing, claims, transações, audit e tickets.",
            "Feature (Web Store / Comércio Admin): painel Listagens paginado com busca, preview cryo (stats, breakdown, blob_hash) e ações em lote (flag/pause/remove).",
            "Melhoria (Suporte): tickets aceitam listing_id/claim_id/market_trace_id; widget mercado no painel admin de tickets.",
            "Fix (Comércio Admin): rotas de remoção admin não duplicam mais evento na auditoria geral da loja.",
        ],
    },
    {
        "version": "1.9.192",
        "date": "2026-07-03",
        "changes": [
            "Fix (Web Store / Comércio): notificações in-app ao vendedor quando anúncio é vendido, resgatado pelo comprador, sinalizado ou removido pela moderação (web e /mercado_admin).",
            "Feature (Web Store / Comércio): registro da vitrine em Minha Loja — histórico de eventos (vendas, moderação, resgates) via /api/market/my/audit.",
            "Melhoria (Web Store): sininho abre Minha Loja ao clicar em notificação do Comércio (link_type market).",
        ],
    },
    {
        "version": "1.9.191",
        "date": "2026-07-03",
        "changes": [
            "Fix (Web Store / Auth): display_name de sistema importado da Steam (personaname) no login; market_display_name fica apenas na vitrine do Comércio.",
            "Fix (Web Store / Admin): lista Gerenciar Jogadores mostra nick Steam (display_name) e SteamID — não mais o nome de vitrine do mercado.",
            "Melhoria (Web Store / Health): /api/health expõe steam_api_configured para indicar se STEAM_API_KEY está configurada.",
        ],
    },
    {
        "version": "1.9.190",
        "date": "2026-07-03",
        "changes": [
            "Fix (CustomShop / Entregas): HttpClient trata resposta vazia ou HTTP falho no claim sem spam de notificacao; TryParseApiJson centraliza parse da API.",
            "Fix (Web Store / API): rotas /api/pending/* sempre retornam JSON valido (fila vazia com ok/items/orders); evita erro de parse no plugin.",
        ],
    },
    {
        "version": "1.9.189",
        "date": "2026-07-03",
        "changes": [
            "Fix (Web Store / Home): botões Jogar agora e Copiar IP na seção Conectar aos servidores — navegação steam:// nativa (sem return false), delegação de cliques e fallback com instruções se o browser bloquear o protocolo.",
        ],
    },
    {
        "version": "1.9.188",
        "date": "2026-07-03",
        "changes": [
            "Feature (Comercio): teto automatico de preco de anuncio — multiplicador por tier sobre valor sugerido (config _price_ceiling em market_species_defaults.json); bloqueio ao salvar/ativar na web.",
            "Feature (Comercio): /mercado_admin in-game (remover, preco, flag) para admins/moderacao; painel web com Remover e Flag em anuncios ACTIVE.",
            "Melhoria (Comercio): /enviar e /confirmar exibem teto maximo de preco no chat; preview e upload retornam price_ceiling.",
        ],
    },
    {
        "version": "1.9.187",
        "date": "2026-07-03",
        "changes": [
            "Feature (CustomShop / Mercado P2P): Settings.MarketAssignNewDinoId (padrao true) — gera ID novo ao spawnar dino do /mercado; retry automatico com blob regenerado em duped=true.",
            "Fix (CustomShop / Mercado P2P): crash BeginDestroy on None apos SpawnMarketDino ok — nao destruir cryopod transiente apos spawn bem-sucedido; ReleaseTransientCryopod com guards UObject.",
            "Fix (CustomShop): spawn probe off-map usa bGenerateNewDinoID e SafeDestroyProbeDino; clones CreateFromBytes liberados em CollectCryoCustomDataBlob e /confirmar probe.",
        ],
    },
    {
        "version": "1.9.186",
        "date": "2026-07-03",
        "changes": [
            "Fix (CustomShop / Mercado P2P): crash apos SpawnMarketDino ok — SafeDestroyTransientCryopod usa ConditionalBeginDestroy em vez de BeginDestroy direto na cryopod transiente do vault.",
            "Fix (CustomShop / Mercado P2P): validacao de cryopod no /mercado sem spawn probe; probe bloqueado em itens transientes (sem OwnerInventory) antes de SpawnMarketDinoFromCryopod.",
        ],
    },
    {
        "version": "1.9.185",
        "date": "2026-07-03",
        "changes": [
            "Fix (CustomShop / Mercado P2P): /mercado deixava de derrubar o mapa — validacao da cryopod em PrepareMarketCryopodForDelivery sem spawn probe (evita double-spawn antes de SpawnMarketDinoFromCryopod).",
            "Fix (CustomShop): TryParseViaSpawnProbe trata duped=true com seguranca (nao Destroy em dino ja existente no mapa).",
        ],
    },
    {
        "version": "1.9.184",
        "date": "2026-07-03",
        "changes": [
            "Fix (ASM / CustomShop): painel de item usa item_detail_source e merge_shop_item_entry para Blueprint/Armor em Items[0] (selas sela_*).",
            "Melhoria (CustomShop / sync): sync_all_plugins aplica apply_saddle_armor em sela_* antes de sincronizar o catalogo.",
            "Melhoria (tools): apply_saddle_armor.py — deteccao e aplicacao de Armor 350 em selas aninhadas; testes em test_apply_saddle_armor e test_shop_catalog_import.",
        ],
    },
    {
        "version": "1.9.183",
        "date": "2026-07-03",
        "changes": [
            "Feature (CustomShop / Mercado P2P): /mercado spawna o dino ao lado do comprador em vez de entregar cryopod no inventário; bônus de 1 Soul Trap vazia (DinoStorage2) configurável em Settings.MarketSpawnBonusSoulTrapBlueprint.",
            "Feature (CustomShop / Mercado P2P): Settings.MarketDeliverAsSpawn (padrão true) alterna entre spawn e entrega em cryopod; fluxo /enviar e /confirmar inalterado.",
            "Feature (CustomShop / Engramas): /engramas cobra âmbares configuráveis (Settings.EngramasCommandPrice, padrão 5000) na confirmação; saldo insuficiente exibe mensagem em português.",
            "Fix (Web Store / Home): conexão Steam usa steam://run/346110 com +connect na porta de jogo (substitui steam://connect quebrado no cliente).",
            "Melhoria (Web Store / Admin): campo Preço /engramas nas configurações gerais do CustomShop.",
        ],
    },
    {
        "version": "1.9.182",
        "date": "2026-07-03",
        "changes": [
            "Feature (CustomShop / Engramas): /engramas com aviso de overflow ao trocar mapa e confirmação via /confirmar (TTL 2 min); desbloqueio dinâmico de todos os engramas (vanilla + mods) via PrimalGameData sem consumir pontos de engrama.",
            "Feature (CustomShop / Engramas): /engramas cobra âmbares configuráveis (Settings.EngramasCommandPrice, padrão 5000) antes do desbloqueio via /confirmar; saldo insuficiente exibe mensagem em português.",
            "Feature (CustomShop): Shop.UnlockAllEngrams [TekOnly] para RCON, console e entrega da loja; item tekgrams do catálogo usa comando único em vez de 74 UnlockEngram individuais.",
            "Melhoria (CustomShop / Loja): ExecuteAsAdmin em comandos do catálogo — privilégio admin temporário na entrega.",
            "Fix (Web Store / Admin): cache de admins invalida quando admin_steamids.json muda — corrige Acesso negado intermitente após editar admins.",
        ],
    },
    {
        "version": "1.9.181",
        "date": "2026-07-02",
        "changes": [
            "Fix (Web Store / Mercado P2P): cryopod morta (DEAD/Carga 0s) — StripCryopodTimer em /confirmar, PrepareMarketCryopodForDelivery em /mercado, validação e liberação do claim em falha (ShopCryoReader.cpp, ShopMarket.cpp).",
            "Fix (Loja / Catálogo): correções de blueprint path — Hide→Leather, armadura Tek pasta TEK, estruturas tek em tek/; Nameless Venom; _KNOWN_BLUEPRINT_FIXES ampliado.",
        ],
    },
    {
        "version": "1.9.180",
        "date": "2026-07-02",
        "changes": [
            "Fix (CustomShop / Build): compilação do CustomShop.dll — TArray::IsEmpty substituído por Num(); ApplyItemStats (Armadura/Dano/Durabilidade in-game) incluído no binário da release.",
        ],
    },
    {
        "version": "1.9.179",
        "date": "2026-07-02",
        "changes": [
            "Fix (Web Store / Home): botões Conectar no hero e na barra fixa; seção reposicionada; diagnóstico de conexão; fallback de IP público global nas configurações.",
            "Fix (ASM / Sync): game_host e game_port a partir de shop.public_ip/machine_public_ip; public_ip em settings.json; descoberta local com game_host.",
            "Fix (Loja / Catálogo): Armadura/Dano/Durabilidade preservados na sanitização; ApplyItemStats no CustomShop.dll; campo Armadura % no ASM.",
            "Melhoria (Loja / Catálogo): Armadura 350 em massa em 132 selas; script tools/apply_saddle_armor.py.",
            "Fix (TEK / Jogador): persistência do multiplicador 5x de pontos de engrama e posicionamento correto no Game.ini.",
            "Melhoria (Loja / Catálogo): 74 comandos tekgrams com preço 5000.",
            "Fix (Web Store / Mercado): persistência de stat_weights (dietas) em APPDATA em vez do bundle somente leitura.",
            "Feature (Web Store / Mercado): menu admin Mercado, fluxo de pré-registro de espécies e painel de catálogo de dinos.",
        ],
    },
    {
        "version": "1.9.178",
        "date": "2026-07-02",
        "changes": [
            "Fix (Web Store / Resgates): desistência de pedido PENDENTE agora funciona mesmo quando o item/kit é grátis "
            "(sem Âmbares a reembolsar); ao cancelar, kits com limite voltam a ficar disponíveis para novo resgate.",
            "Fix (Web Store / Login Steam): sessão do portal passa a persistir entre fechamentos do navegador; "
            "cookie permanente com expiração configurável por ARKSHOP_SESSION_DAYS (padrão: 30 dias).",
        ],
    },
    {
        "version": "1.9.177",
        "date": "2026-07-02",
        "changes": [
            "Fix (Web Store / Licenças): pedido de licença ficava PENDENTE em loop após resgate web — "
            "claim/release marcam ENTREGUE quando o jogador já possui a licença ativa.",
            "Fix (CustomShop / Licenças): entrega de licenca_* sem LicenseGrant no config.json do mapa — "
            "fallback infere o grupo (Gamma/Beta/Alfa/VIP) a partir do item_id, alinhado à web store.",
        ],
    },
    {
        "version": "1.9.176",
        "date": "2026-07-01",
        "changes": [
            "Fix CRÍTICO (TEK / Jogador): seção «Configurações do Jogador» não abria — import quebrado em "
            "player_level_panel.py (IndentationError) corrigido.",
        ],
    },
    {
        "version": "1.9.175",
        "date": "2026-07-01",
        "changes": [
            "Fix CRÍTICO (Backup): snapshots ignoravam saves reais — backup buscava SavedArks/ em vez de "
            "ShooterGame/Saved/{AltSaveDirectoryName}/ (ex.: savegame); restauração devolve arquivos à pasta correta.",
            "Melhoria (Backup): saves do mundo passam a ser a prioridade (padrão); .ini opcional; Discord/log "
            "mostram quantos arquivos de save e config foram incluídos.",
            "Feature (TEK / Jogador): painel simplificado de nível máximo — nível base e total com ascensões "
            "γ/β/α, chibi, runas e notas; XP no INI calculado automaticamente.",
            "Feature (TEK / Jogador): multiplicador de pontos de engrama por nível (ex.: 5× → 40 pts/nível) "
            "gravado em OverridePlayerLevelEngramPoints no Game.ini.",
            "Feature (Web Store / Votações): enquetes com admin, prazo, percentuais, quorum e recompensa em Âmbares; "
            "voto único e múltipla escolha opcional; visível sem login.",
            "Feature (Web Store / Home): cards de mapa gerados automaticamente a partir de servers.json "
            "(show_on_home) — rates e conexão detectados pelo sync ASM.",
            "Fix (Web Store / Reembolso): pedido marcado REEMBOLSADO sem creditar Âmbares — crédito garantido "
            "com fallback na auditoria; bloqueio quando valor = 0.",
        ],
    },
    {
        "version": "1.9.174",
        "date": "2026-07-01",
        "changes": [
            "Fix CRÍTICO (TEK / Saves): painel «💾 Saves» travava em «Atualizando lista…» — callbacks da thread "
            "de listagem agora voltam corretamente para a UI; erros por servidor não bloqueiam a lista inteira; "
            "recarrega ao reabrir a aba.",
            "Fix (TEK / Dashboard): app deixava de responder após muito tempo aberto — refresh leve sem recriar "
            "todos os cards; mudança de status/visibilidade Steam atualiza só o card afetado; tick de status "
            "reagenda mesmo com worker anterior em andamento.",
        ],
    },
    {
        "version": "1.9.173",
        "date": "2026-07-01",
        "changes": [
            "Feature (TEK / Saves): painel global «💾 Saves» — lista todos os servidores e arquivos em "
            "ShooterGame/Saved/savegame; carregar backup datado, Anti Corruption ou New Launch como save "
            "ativo; backup manual e exclusão; bloqueio se o servidor não estiver parado.",
            "Feature (Web Store / Home): card «Conectar aos servidores» com botões Steam (steam://connect) "
            "e copiar IP — API /api/public/home expõe connect_url e join_address; sync ASM grava game_host/game_port.",
            "Feature (TEK / Reinício): reinício automático por dias da semana (checkboxes Seg–Dom) no painel "
            "do servidor; lista vazia desativa reinícios.",
            "Melhoria (TEK): barra FERRAMENTAS do card do servidor em duas linhas — botões não cortam em telas estreitas.",
            "Melhoria (Web Store / Catálogo): categorias ampliadas (Selas, Blueprints, Estruturas, Recursos, etc.) "
            "com contadores e inferência automática no catálogo público.",
        ],
    },
    {
        "version": "1.9.172",
        "date": "2026-07-01",
        "changes": [
            "Fix CRÍTICO (Web Store / RCON): Shop.Reload automático ao salvar catálogo na interface web "
            "agora atinge todos os mapas — descobre servidores via servers.json + ASM local, tenta "
            "127.0.0.1 antes do IP LAN, reload em paralelo; configurações gerais também recarregam.",
            "Feature (Loja / Permissions): reconciliação automática player_entitlements ↔ ark_permission "
            "ao iniciar a Web Store e o painel Banco de Dados; botão manual «Sync licenças→Permissions» "
            "no DB Manager e «Sync Permissions» em Gerenciar Jogadores.",
            "Fix (Loja / Permissions): sync de licenças grava direto em ark_permission.players (MySQL) "
            "além do RCON — corrige TimedPoints/Âmbares quando mapa offline ou sem senha RCON; "
            "preserva grupos manuais não gerenciados pela web.",
        ],
    },
    {
        "version": "1.9.171",
        "date": "2026-06-30",
        "changes": [
            "Feature (Web Store / Tickets): status automático — criado como «Aguardando suporte», "
            "resposta do suporte muda para «Aguardando jogador», resposta do jogador volta para "
            "«Aguardando suporte»; migração de Aberto/Em análise no banco.",
            "Feature (Web Store / Tickets): notificações in-app para o jogador e para toda a equipe "
            "de suporte (support_steamids + admins) sempre que o status do ticket é atualizado.",
            "Feature (Server Manager / Banco de Dados): modo emergência — filtro por SteamID, "
            "editar/excluir/novo registro, modelos SQL e atalhos para players, player_entitlements, "
            "player_cloud_inventory e player_cloud_items; visão geral do jogador.",
        ],
    },
    {
        "version": "1.9.170",
        "date": "2026-06-29",
        "changes": [
            "Fix CRÍTICO (CustomShop / TimedPoints / cargo MOD): bônus de 500 Âmbares por ciclo não "
            "aplicava — grupo Permissions «Moderacao» (UI MOD) não batia com «Mod» no config após sync; "
            "catalog_sync normaliza Mod/MOD → Moderacao; TimedPoints resolve aliases Moderacao/Mod/MOD; "
            "recompilar CustomShop.dll e rodar Sync TEK ou Shop.Reload nos mapas.",
        ],
    },
    {
        "version": "1.9.169",
        "date": "2026-06-29",
        "changes": [
            "Fix (Web Store / Tickets): card «Equipe de Suporte» visível para admins na página de Tickets "
            "(CSS admin-only em blocos dentro de páginas, não só menu e páginas ativas).",
        ],
    },
    {
        "version": "1.9.168",
        "date": "2026-06-29",
        "changes": [
            "Fix (CustomShop / Nuvem): upload de inventário deixa de bloquear itens com "
            "bPreventUpload (ex.: Apex / Element) — apenas engramas e implantes continuam excluídos.",
            "Feature (Web Store / Loja): barra de busca no catálogo de itens, dinos, kits e licenças "
            "(nome, descrição, categoria, blueprint) e na administração da loja.",
            "Feature (Web Store): notificações in-app para jogadores (sino no portal) — respostas, "
            "status e eventos de tickets; tabela user_notifications criada automaticamente no startup.",
            "Feature (Web Store / Tickets): alertas no Discord para equipe (canal staff) — novo ticket, "
            "respostas, status, prioridade e encerramento; config em settings.json ou variáveis "
            "ARKSHOP_TICKET_DISCORD_*.",
            "Feature (Web Store / Suporte): equipe de suporte com acesso à fila de tickets sem "
            "permissões de admin — support_steamids.json + tabela shop_support; papel «Suporte» no portal.",
            "Feature (TEK): seção «Todas as opções» — visão plana filtrável de todos os campos editáveis.",
            "Melhoria (TEK): busca global «Buscar configuração…» na barra lateral — atalho direto ao campo.",
            "Feature (TEK / Estruturas): card «Platform saddle / Tek Strider» — torretas em Stryder, "
            "multiplicadores de plataforma, limite de dinos e área de construção agrupados.",
            "Fix (TEK / Evento): ActiveEvent normaliza IDs legados (ARKEaster→Easter, LoveEvolved→vday, "
            "Anniversary→birthday, SummerBash→Summer) na leitura, gravação INI e parâmetro ?ActiveEvent=.",
            "Fix (TEK / INI): limite de torretas (LimitTurretsInRange/Range/Num) grava em Game.ini "
            "[/Script/ShooterGame.ShooterGameMode] em vez de GameUserSettings.",
            "Melhoria (TEK): auditoria de visibilidade — rótulos PT, palavras-chave de busca (tributo, "
            "Stryder, eventos sazonais), campo «Próximo evento (UTC)» na extinção e campos de "
            "transferência/tributo indexados corretamente.",
        ],
    },
    {
        "version": "1.9.167",
        "date": "2026-06-28",
        "changes": [
            "Melhoria (Sincronização): até 10 pastas por ciclo (antes 5).",
            "Feature (Sincronização): opção «Apenas config.json» por ciclo — propaga só arquivos "
            "com esse nome entre as pastas do ciclo.",
        ],
    },
    {
        "version": "1.9.166",
        "date": "2026-06-28",
        "changes": [
            "CrossChat integrado desativado — sync grava CrossChat.Enabled=false nos mapas; "
            "use plugin de terceiros. UI simplificada (removidos campos confusos de chat cluster).",
        ],
    },
    {
        "version": "1.9.165",
        "date": "2026-06-28",
        "changes": [
            "Fix (Loja): «Sync + Reload RCON (todos)» envia Shop.Reload a todos os mapas TEK — "
            "status via asm_server_manager, host 127.0.0.1, sem duplicar servidores legados.",
            "Fix (CrossChat): ServerId fixo por pasta MAPAS em mapas_cross_chat_ids.json "
            "(%APPDATA%\\ARKLAND-ServerManager) — fora do sync do catálogo (AL→ALPS, BR→BRIGHAMIA, …).",
            "Novo (Ferramentas): repair_cross_chat_server_ids.ps1 — corrige ServerId nos config.json dos mapas.",
        ],
    },
    {
        "version": "1.9.164",
        "date": "2026-06-28",
        "changes": [
            "Fix (Loja): «Sync + Reload RCON (todos)» passa a enviar Shop.Reload a todos os mapas TEK — "
            "status via asm_server_manager, host 127.0.0.1 (fallback server_ip), sem duplicar servidores legados.",
            "Fix (CrossChat): ServerId usa nome do mapa (ALPS, BRIGHAMIA, …) mapeado da pasta "
            "MAPAS\\ (AL, BR, …), não a sigla da pasta.",
        ],
    },
    {
        "version": "1.9.163",
        "date": "2026-06-28",
        "changes": [
            "Refactor (Loja / Catálogo): catalog_vip_pricing renomeado para catalog_sync — "
            "sync TEK mantém só sanitização de placeholders e tiers Gamma/Beta/Alfa; purge "
            "genérico de entradas obsoletas legadas no JSON (sem recriar licenças/kits).",
        ],
    },
    {
        "version": "1.9.162",
        "date": "2026-06-28",
        "changes": [
            "Fix CRÍTICO (Loja / Catálogo): sync TEK deixa de recriar licenças VIP (licenca_vip_*) "
            "e kits VIP (vip_bronze, prata, ouro, diamante) — apply_vip_pricing_to_catalog remove "
            "entradas VIP legadas e mantém só sanitização de placeholders e preços tier Gamma/Beta/Alfa.",
        ],
    },
    {
        "version": "1.9.161",
        "date": "2026-06-28",
        "changes": [
            "Fix CRÍTICO (Loja / Catálogo): sync TEK deixava de reinjetar Permissions VIPBronze em "
            "itens avulsos (Gerador Tek S+, Replicador S+, Transmissor S+, Stryder Rig, Soul Traps) — "
            "apply_vip_pricing_to_catalog atualiza preço/descrição sem exigir VIP; kits licenciados "
            "mantêm Permissions corretas.",
        ],
    },
    {
        "version": "1.9.160",
        "date": "2026-06-28",
        "changes": [
            "Fix (Loja / Web Store): colunas da lista «Servidores ARK deste app» cortadas após "
            "«Nome chat cluster» — layout em duas linhas (config.json abaixo), cabeçalhos e "
            "checkboxes Home/Loja com largura suficiente.",
        ],
    },
    {
        "version": "1.9.159",
        "date": "2026-06-28",
        "changes": [
            "Fix CRÍTICO (CrossChat): ServerId duplicado entre mapas impedia entrega de mensagens "
            "(poll ignora source_server == self); shop_server_id deixa de definir o rótulo do chat.",
            "Novo (CrossChat / TEK): campo «Nome chat cluster» por servidor na aba Loja — persiste em "
            "servers.json / AsmServerConfig; vazio = pasta install_dir ou mapa; sync valida IDs únicos.",
            "Novo (Web Store / Mapas do cluster): rates e níveis máximos sincronizados pelo TEK "
            "(startup e restart) — pills nos cards da home (XP, Doma, Coleta, nível máx. jogador/dino; BUFF ativo).",
        ],
    },
    {
        "version": "1.9.158",
        "date": "2026-06-28",
        "changes": [
            "Fix (BUFFs): multiplicadores empilham sobre as rates base do servidor (ex.: 44x × 10x = 440x) "
            "em vez de substituir por valores relativos ao vanilla 1x.",
            "Fix (BUFFs): botão Encerrar BUFF no card do evento ativo — restaura INI do backup e reinicia o servidor.",
        ],
    },
    {
        "version": "1.9.157",
        "date": "2026-06-28",
        "changes": [
            "Fix (Web Store / Header): card de usuário logado exibe nickname Steam ao lado do SteamID "
            "(via store_users, players.json ou Steam Web API com STEAM_API_KEY); papel Admin/Jogador em linha separada; "
            "pipe oculto quando nickname indisponível.",
        ],
    },
    {
        "version": "1.9.156",
        "date": "2026-06-28",
        "changes": [
            "Fix (Web Store / Auditoria): filtro por SteamID64 em Eventos Gerais enviava pedido como order_id "
            "(checava length >= 32 em vez do padrão 7656119…); busca por jogador volta a funcionar.",
        ],
    },
    {
        "version": "1.9.155",
        "date": "2026-06-28",
        "changes": [
            "Fix (Web Store / Tickets admin): badges de status com cores no tema escuro; botão Atender/Abrir "
            "abre o detalhe do ticket (lista não esconde mais o painel); tickets ENCERRADO visíveis na fila "
            "com botão Ver e histórico somente leitura.",
        ],
    },
    {
        "version": "1.9.154",
        "date": "2026-06-28",
        "changes": [
            "Fix (Web Store / Licença Nuvem): resgate concede keyvault em player_entitlements e "
            "sincroniza Permissions.AddTimed via RCON como as demais licenças; fallback para catálogo "
            "legado Type command; licenca_nuvem padronizada como Type license no config.",
            "Fix (TEK oBobonic): encerra instâncias órfãs antes do auto-start, grava PID, para o bot "
            "ao fechar o app (WM_DELETE_WINDOW) — evita múltiplos bots após restart do TEK.",
        ],
    },
    {
        "version": "1.9.153",
        "date": "2026-06-28",
        "changes": [
            "Melhoria (Web Store / Tickets): abas Abertos e Encerrados corrigidas — tickets em "
            "EM_ANALISE e AGUARDANDO_JOGADOR permanecem visíveis ao jogador; botão Encerrar no "
            "admin; atender muda status sem sumir da lista; jogador pode marcar como resolvido; "
            "histórico e permissões de resposta por status.",
        ],
    },
    {
        "version": "1.9.152",
        "date": "2026-06-28",
        "changes": [
            "Fix CRÍTICO (Web Store / DB): migração steam_id falhava com erro 1068 "
            "(Multiple primary key defined) em players — bloqueava tickets, tribe_name e market; "
            "ALTER MODIFY idempotente sem redeclarar PRIMARY KEY em colunas que já são PK.",
        ],
    },
    {
        "version": "1.9.151",
        "date": "2026-06-28",
        "changes": [
            "Fix CRÍTICO (Web Store): portal travado em «Carregando portal…» após v1.9.149 — "
            "bloco JavaScript duplicado em saveGeneralSettings quebrava o parse do index.html; "
            "fallback visual se o JS principal não iniciar.",
        ],
    },
    {
        "version": "1.9.150",
        "date": "2026-06-28",
        "changes": [
            "Fix (CustomShop / TimedPoints): notificacao de Ambares usa chat normal (SendChatMessage) "
            "em vez de mensagem grande verde do servidor (SendServerMessage); CustomShop.dll requer recompilacao.",
            "Fix (CrossChat): mensagens cluster via ClientChatMessage sem badges de admin (estrela/tribo) "
            "no nome do remetente; CustomShop.dll requer recompilacao.",
            "Fix (Loja / Sync Permissions): collect_groups inclui keyvault e LicenseGrant.Group de kits/itens "
            "para provisionar grupos no keyvault ao sincronizar.",
        ],
    },
    {
        "version": "1.9.149",
        "date": "2026-06-28",
        "changes": [
            "Novo (Web Store / Tickets): sistema de suporte com categorias, prioridade, status, "
            "historico de eventos, anexos e vinculo opcional a pedidos (API jogador + admin). "
            "Migracao automatica do schema na subida da Web Store.",
            "Removido (Web Store / Admin): aba Mensagens do Sistema no painel web "
            "(edicao de mensagens do plugin permanece no app TEK).",
        ],
    },
    {
        "version": "1.9.148",
        "date": "2026-06-28",
        "changes": [
            "Novo (Web Store / Admin): cargos MOD e STAFF na aba Gerenciar Jogadores — "
            "permanentes, bônus TimedPoints, sync Permissions via RCON e persistência em "
            "player_entitlements (não são licenças resgatáveis).",
            "Novo (Web Store / Chat Cluster): admin envia mensagens do site para todos os "
            "mapas via POST /api/admin/chat/send — aparece in-game como [ARKLAND].",
        ],
    },
    {
        "version": "1.9.147",
        "date": "2026-06-28",
        "changes": [
            "Fix CRÍTICO (CrossChat): ServerId no sync prioriza pasta install_dir sobre shop_server_id "
            "— corrige todos os mapas aparecendo como [amissa] quando o ID da loja é igual.",
            "Novo (CrossChat): nome da tribo do jogador nas mensagens cluster e no Discord "
            "([Mapa] [Tribo] Jogador: texto).",
            "Fix (CrossChat): Shop.Reload recarrega ServerId do CrossChat sem reiniciar o servidor.",
        ],
    },
    {
        "version": "1.9.146",
        "date": "2026-06-28",
        "changes": [
            "Fix CRÍTICO (Web Store / Doações): save de pacotes PIX persiste no catálogo completo "
            "(merge parcial não apaga Items/Kits) e atualiza cache WEBSTORE — evita revert após "
            "Recarregar ou sync TEK.",
            "Novo (Web Store / Doações): 10 pacotes padrão com notas de incentivo em PT-BR; "
            "campo note editável no admin e exibido na loja pública.",
        ],
    },
    {
        "version": "1.9.145",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (Web Store / Mercado Pago): checkout cartão e webhook usam URL pública "
            "(public_url) — evita back_urls localhost e falha no retorno/aprovação MP.",
            "Fix (Web Store / Doações): lista vazia de pacotes PIX respeitada "
            "(_load_point_packages não cai mais nos defaults quando admin zera o catálogo).",
            "Fix (Web Store / Mercado Pago): token MP prioriza settings.json sobre env vazio ou stale.",
            "Fix (Web Store / PIX): QR/copy-paste normalizados; log em falha de checkout DB.",
            "Fix (Web Store / Cartão MP): auto_return só com HTTPS; validação de URL de retorno.",
            "Fix (Loja / Sync): sync aborta se settings.json ilegível — não apaga mp_access_token.",
        ],
    },
    {
        "version": "1.9.144",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (Web Store / Doações): pacotes PIX/cartão editados no admin web "
            "persistem no catálogo mestre (PointPackages) — antes só gravavam em settings.json "
            "e o reload lia os defaults do config.json.",
        ],
    },
    {
        "version": "1.9.143",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (Loja / Sync): catálogo mestre propaga Kits/Items completos para todos os mapas — "
            "WEBSTORE desatualizada com mais entradas não sobrescreve mais o mestre; "
            "sync recarrega o mestre do disco após reconcile; log itens/kits antes→depois por mapa.",
            "Fix (Loja / Sync): CrossChat do mestre vence no sync (só ServerId permanece exclusivo por mapa).",
        ],
    },
    {
        "version": "1.9.142",
        "date": "2026-06-27",
        "changes": [
            "Novo (Loja / Kits): limite de resgates por DefaultAmount (web + /shop in-game) — "
            "contador persistente em players.kits; pedidos pendentes reservam slot; "
            "painel Gerenciar Jogadores com usado/limite e botão Resetar; "
            "API POST /api/admin/players/{steam_id}/kit-limits/{kit_id}/revoke.",
            "Fix CRÍTICO (CrossChat): sync do CustomShop define ServerId único por mapa "
            "(pasta install_dir / shop id) — corrige chat cluster com todos os mapas "
            "aparecendo com o mesmo nome.",
            "Fix CRÍTICO (CustomShop / Entrega web): HttpClient recarrega config.json e tenta "
            "GiveKit/GiveItem novamente quando o kit/item não está no catálogo em memória "
            "(kit_desconhecido / item_desconhecido) — corrige entregas após sync sem Shop.Reload.",
            "Fix (Loja / Import): normalize_blueprint corrige RawMeat em pasta Resources "
            "(kit recursos) para o caminho Consumables válido no ARK.",
            "Fix (CustomShop): kits com DefaultAmount=0 são ilimitados; mensagem PT-BR ao esgotar resgates.",
        ],
    },
    {
        "version": "1.9.141",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (CrossChat): sync do CustomShop define ServerId único por mapa "
            "(pasta install_dir / shop id) — corrige chat cluster com todos os mapas "
            "aparecendo com o mesmo nome.",
        ],
    },
    {
        "version": "1.9.140",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (CustomShop / Entrega web): HttpClient recarrega config.json e tenta "
            "GiveKit/GiveItem novamente quando o kit/item não está no catálogo em memória "
            "(kit_desconhecido / item_desconhecido) — corrige entregas após sync sem Shop.Reload.",
            "Fix (Loja / Import): normalize_blueprint corrige RawMeat em pasta Resources "
            "(kit recursos) para o caminho Consumables válido no ARK.",
        ],
    },
    {
        "version": "1.9.139",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (Loja / Sync): Sync + Reload RCON e Aplicar em todos os plugins gravam o catálogo "
            "da UI no mestre canônico antes de propagar — get_catalog não recarrega mais do disco e descarta "
            "edições não salvas.",
            "Fix (Loja / Sync): reconcile_catalog_before_sync só substitui o catálogo em memória quando o "
            "disco tem mais entradas (não mais em empate de contagem), preservando edições recém-persistidas.",
        ],
    },
    {
        "version": "1.9.138",
        "date": "2026-06-27",
        "changes": [
            "Fix (Web Store / Admin): dropdown de licenças em Gerenciar Jogadores lista todas as licenças "
            "do catálogo (Type license ou LicenseGrant) — Gamma/Beta/Alfa, Nuvem e VIP; usa o config mais "
            "completo quando o mestre local estiver truncado.",
            "Melhoria (Web Store / Admin): endpoint GET /api/admin/license-catalog; dias padrão sincronizam "
            "com a licença selecionada no painel de jogadores.",
        ],
    },
    {
        "version": "1.9.137",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (Loja / Sync): um único mestre de catálogo — ARKLAND SERVER/CustomShop/configs/config.json "
            "(ou APPDATA/plugin em dev); WEBSTORE/config.json deixa de ser mestre e vira só cache runtime.",
            "Fix (Loja / Admin web): settings.json config_path aponta para o mestre canônico; save web grava uma vez "
            "no mestre + mapas (removido segundo destino «Catálogo TEK»); reconcile migra edições legadas WEBSTORE → mestre.",
            "Melhoria (Ambiente): pasta CustomShop/configs/ criada no layout ARKLAND SERVER para o catálogo mestre.",
        ],
    },
    {
        "version": "1.9.136",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (CustomShop / Kits): ExtractBlueprintPath normaliza blueprints malformados; GiveKit falha com motivo claro quando nenhum item é entregue (sem_conteudo / items_falharam).",
            "Fix (Loja / Admin web): sanitize_catalog_blueprints ao salvar config no arkshop_web; editor de kits usa normalizeBlueprintPath no front.",
            "Melhoria (Loja / Import): sanitize_catalog_blueprints na importação de catálogo (shop_catalog_import); testes em tests/test_shop_catalog_import.py.",
        ],
    },
    {
        "version": "1.9.135",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (CustomShop / TimedPoints): timer de pontos por tempo online não duplica agendamento; "
            "Tick usa GetWorld e jogadores online corretamente; logs de diagnóstico (Enabled, Groups, Default) "
            "no boot e no Shop.Reload; ShopConfig recarrega TimedPointsReward.",
            "Fix (Web Store / Discord): ponte cross_chat_discord mais robusta (reconexão, heartbeat, encoding); "
            "ARKLAND-WebStore.spec inclui dependências do bridge.",
            "Melhoria (Web Store / Pagamentos): coluna payment_method em point_payments; badges PIX/cartão na "
            "fila admin e textos de UI; checkout cartão e PIX com rótulos mais claros.",
            "Fix (Web Store / Checkout cartão): rotas /api/* respondem JSON em erros HTTP (429/404/limiter) — "
            "fetchJson no front evita falha ao parsear HTML.",
            "Melhoria (Loja): shop_integration registra sync de settings; customshop_panel defaults alinhados "
            "ao TimedPointsReward.",
        ],
    },
    {
        "version": "1.9.134",
        "date": "2026-06-27",
        "changes": [
            "Fix CRÍTICO (Loja / Sync Settings): TimedPointsReward, ShopName, Messages, "
            "PointPackages, Downloads e demais Settings propagam corretamente entre mestre TEK, "
            "WEBSTORE/config.json e plugins — reconcile detecta mudanças sem alteração de itens; "
            "Salvar/Sync TEK força cópia ao WEBSTORE; admin web grava Settings do mestre nos mapas.",
        ],
    },
    {
        "version": "1.9.133",
        "date": "2026-06-26",
        "changes": [
            "Fix CRÍTICO (CustomShop / mesmo PC): sync normaliza orders_db_host para 127.0.0.1 "
            "quando MariaDB escuta só localhost e o host configurado é IP desta máquina — "
            "plugins e Permissions passam a conectar com senha do DB Manager.",
        ],
    },
    {
        "version": "1.9.132",
        "date": "2026-06-26",
        "changes": [
            "Fix CRÍTICO (Loja / Web Store): Sync + Reload não sobrescreve mais edições do admin web — "
            "reconcile_catalog_before_sync incorpora WEBSTORE/config.json quando mais recente; "
            "ensure_webstore respeita mtime; save do admin web grava também no mestre TEK persistente.",
        ],
    },
    {
        "version": "1.9.131",
        "date": "2026-06-26",
        "changes": [
            "Fix CRÍTICO (CustomShop / cluster): MariaDB bind LAN opt-in no DB Manager "
            "(get_bind_lan/set_bind_lan) — mapas remotos conectam ao MySQL do host quando "
            "orders_db_host aponta para IP da LAN.",
            "Fix (Loja): sync avisa quando MariaDB escuta só 127.0.0.1 mas plugins usam host LAN "
            "(warn_cluster_db_bind_mismatch).",
            "Fix (Web Store): ARKSHOP_WEB_SECRET gerada e persistida automaticamente "
            "(resolve_web_secret) ao iniciar a loja pelo app.",
            "Fix (Web Store / Mercado Pago): checkout cartão e webhook evitam deadlock de sessão "
            "SQLAlchemy; status inicial PENDENTE no checkout.",
        ],
    },
    {
        "version": "1.9.130",
        "date": "2026-06-26",
        "changes": [
            "Melhoria (Web Store / Admin): redesign da fila de pedidos com ações de reembolso, "
            "reenvio, cancelamento e detalhes do pedido.",
            "Fix (Web Store): collation steam_id em JOINs MySQL (Gerenciar Jogadores) — evita erro 1267.",
            "Melhoria (Loja): catálogo mod_catalog_verified.json e sync_mod_catalog_from_beacon.py "
            "para validar blueprints de mods via Beacon.",
            "Melhoria (Loja): preços IndoRaptor no catálogo mestre.",
            "Segurança (Web Store / DB — fase 1): logs sem credenciais; admin_steamids fora do repo "
            "(APPDATA); CORS restrito; ARKSHOP_WEB_SECRET obrigatória em produção/.exe; MariaDB bind "
            "127.0.0.1 e firewall com escopo localhost ou LAN sob opt-in.",
        ],
    },
    {
        "version": "1.9.129",
        "date": "2026-06-26",
        "changes": [
            "Fix CRÍTICO (Loja / Web Store): v1.9.128 priorizava WEBSTORE/config.json como catálogo "
            "mestre — stub com poucas licenças truncava /api/catalog e o Sync propagava só ~4 itens "
            "para todos os mapas. Mestre agora resolve pelo config mais completo (mapas/APPDATA); "
            "WEBSTORE é só cópia runtime; sync aborta se mestre << mapas.",
            "Fix (Loja): ensure_webstore_catalog_config recopia mestre para WEBSTORE quando o mestre "
            "tem muito mais itens (recuperação automática da cópia truncada).",
            "Melhoria (Web Store): catalog_meta expõe items_count e kits_count em /api/catalog.",
            "Melhoria (Loja): tools/fix_production_catalog.ps1 prioriza mapa com mais itens e "
            "restaura WEBSTORE\\config.json a partir do mestre.",
        ],
    },
    {
        "version": "1.9.128",
        "date": "2026-06-26",
        "changes": [
            "Fix (Web Store): ícones SVG por espécie no catálogo de dinos em produção (PyInstaller) — "
            "ark_species_registry resolve static/data a partir de _MEIPASS.",
            "Fix (Web Store): painel Gerenciar Jogadores tolera ausência de market_player_profile e garante "
            "migração de store_users; mensagens de erro mais claras no admin.",
            "Fix (Web Store / Loja): config_path e catalog_config_path não apontam mais para extração "
            "temporária PyInstaller (_MEIPASS/_MEI*) — migração automática no boot da Web Store e no load "
            "do config TEK; sync grava caminho persistente.",
            "Fix (Loja): Sync + Reload RCON e sync_arkshop_web_settings reescrevem config_path para catálogo "
            "em Program Files, ao lado do .exe ou APPDATA.",
            "Fix (Loja): tools/fix_production_catalog.ps1 aplica preços VIP no JSON mestre, atualiza "
            "config_path em settings.json e opcionalmente sincroniza mapas.",
            "Melhoria (Web Store): /api/catalog expõe catalog_meta.placeholder_kits_detected para diagnosticar "
            "catálogo com preços 99.999.999 sem adivinhar o arquivo.",
            "Fix (Web Store): _data_dir() alinhado com webstore_data_dir() — ARKSHOP_DATA_DIR, ambiente "
            "ARKLAND (WEBSTORE) e fallback APPDATA; evita settings em dois lugares.",
            "Fix (Loja): sync_arkshop_web_settings e sync TEK copiam config.json para WEBSTORE quando ausente "
            "e apontam config_path para lá no ambiente ARKLAND.",
        ],
    },
    {
        "version": "1.9.127",
        "date": "2026-06-26",
        "changes": [
            "Fix (Loja): tools/fix_production_catalog.ps1 aplica preços VIP no JSON mestre, "
            "atualiza config_path em settings.json e opcionalmente sincroniza mapas.",
            "Melhoria (Web Store): /api/catalog expõe catalog_meta.placeholder_kits_detected "
            "para diagnosticar catálogo com preços 99.999.999 sem adivinhar o arquivo.",
        ],
    },
    {
        "version": "1.9.126",
        "date": "2026-06-26",
        "changes": [
            "Fix (Web Store / Loja): config_path e catalog_config_path não apontam mais para "
            "extração temporária PyInstaller (_MEIPASS/_MEI*) — migração automática no boot da "
            "Web Store e no load do config TEK; sync grava caminho persistente.",
            "Fix (Loja): Sync + Reload RCON e sync_arkshop_web_settings reescrevem config_path "
            "para catálogo em Program Files, ao lado do .exe ou APPDATA.",
        ],
    },
    {
        "version": "1.9.125",
        "date": "2026-06-26",
        "changes": [
            "Fix (Web Store): ícones SVG por espécie no catálogo de dinos em produção (PyInstaller) — "
            "ark_species_registry resolve static/data a partir de _MEIPASS.",
            "Fix (Web Store): painel Gerenciar Jogadores tolera ausência de market_player_profile e "
            "garante migração de store_users; mensagens de erro mais claras no admin.",
        ],
    },
    {
        "version": "1.9.124",
        "date": "2026-06-26",
        "changes": [
            "Fix (Loja): tools/apply_vip_pricing.py varre todos os kits com Permissions (VIP, VISOUS "
            "Gamma/Beta/Alfa) — preço = 10% da licença, remove placeholders 99.999.999/1, corrige "
            "diamante para Permissions Admins,VIPDiamante (não Alfa) e preço 1.125.",
            "Fix (Loja): kits VIP Bronze/Prata/Ouro/Diamante fixados em 300/450/750/1.125 Âmbar; "
            "licenca_vip_* garantidas no catálogo (3k/4,5k/7,5k/11,25k).",
            "Feat (Loja): mapeamento explícito ouro→VIPOuro (evita confundir com licença Alfa) e "
            "sanitização automática de Price ≥ 1.000.000 em todos os kits.",
        ],
    },
    {
        "version": "1.9.123",
        "date": "2026-06-26",
        "changes": [
            "Feat (oBobonic): bot Discord inicia automaticamente com o TEK quando obobonic.auto_start "
            "está ativo (padrão true) — thread em background, status no painel e log global; pasta "
            "ausente não derruba o app.",
            "Feat (Broadcasts): scheduler_enabled padrão true — ciclo automático ativo no boot; Parar "
            "não persiste false na config (reinicia no próximo launch se estava habilitado).",
        ],
    },
    {
        "version": "1.9.122",
        "date": "2026-06-26",
        "changes": [
            "Fix (Comércio P2P): recursos, sementes e veículos (ex.: Lingote de Aço Endurecido, Alga, HoverSkiff) "
            "removidos da tabela market_species — Comércio aceita só dinos criopodáveis (_Character_BP); "
            "recursos permanecem no catálogo de resgates (Items).",
            "Fix (Comércio P2P): sync_registry_overlay_to_db e boot filtram is_cryopodable_dino_blueprint; "
            "cleanup automático desativa entradas não-dino já importadas; admin Espécies oficiais não lista recursos.",
            "Feat (Loja): tools/sync_market_species_to_shop_catalog.py — dinos homologados no Comércio entram no "
            "config.json como Type:dino Nível 200 com preço do tier/root_value.",
        ],
    },
    {
        "version": "1.9.121",
        "date": "2026-06-26",
        "changes": [
            "Feat (Web Store): área admin «Gerenciar Jogadores» — lista paginada de contas Steam "
            "(store_users), busca, saldo Âmbar, status ativo/bloqueado, licenças e painel lateral "
            "para ajustar pontos, bloquear acesso, conceder/revogar licenças e entregar kits.",
            "Feat (Web Store): APIs /api/admin/players/* com auditoria (audit_events) em todas as ações; "
            "conta criada no login Steam; bloqueio impede rotas de jogador autenticado.",
        ],
    },
    {
        "version": "1.9.120",
        "date": "2026-06-26",
        "changes": [
            "Fix (Web Store): ícones de espécie redesenhados — círculo limpo com anel de tier, "
            "badge S+/S/A/B/C e sigla de 2 letras (RX, WW, etc.) em vez de blobs procedurais; "
            "regenerar com tools/generate_species_icons.py.",
            "Fix (Loja): 40 itens/dinos/recursos Abyss sincronizados para config.json (aba Dinos/Itens) "
            "via tools/sync_abyss_shop_catalog.py — Seaweed, Manganese, Water Wyvern, HoverSkiff, etc.",
            "Fix (Loja): Replicador S+ incluído em todos os kits VIP (Bronze, Prata, Ouro, Diamante) "
            "com blueprint S+ corrigido; modal «ver conteúdo» exibe «Replicador S+».",
        ],
    },
    {
        "version": "1.9.119",
        "date": "2026-06-25",
        "changes": [
            "Feat (Web Store): ícones SVG originais ARKLAND por espécie (154 criaturas) — "
            "silhuetas procedurais em static/species/icons/; catálogo e Comércio P2P "
            "usam registro com fallback por tier; sem wiki/Dododex/arkids.",
            "Docs: ATTRIBUTION.md com pesquisa legal (Fandom CC BY-NC-SA, Fan Content Guidelines, "
            "arkids.net) e guia admin; tools/generate_species_icons.py para regenerar bundle.",
        ],
    },
    {
        "version": "1.9.118",
        "date": "2026-06-25",
        "changes": [
            "Feat (Web Store): overhaul do Catálogo — busca com debounce (nome, descrição, blueprint, "
            "categoria, kit), chips de categoria, ordenação por preço/nome, contador de resultados, "
            "cards horizontais com mais informação e estado vazio com sugestões.",
            "Feat (Web Store): thumbnails no catálogo (Itens, Dinos, Kits, Licenças) — dinos via "
            "registro de espécies com silhuetas SVG por tier (sem Dododex); itens por categoria; "
            "kits com badge de tier; licenças com ícone dedicado.",
            "Feat (Web Store): /api/catalog enriquecido com display_category, thumbnail_url, "
            "search_text, item_count/kit_contents, license_days e tier_icon_urls.",
            "Feat (Web Store): modal «ver conteúdo» nos kits listando itens incluídos sem poluir o grid.",
        ],
    },
    {
        "version": "1.9.117",
        "date": "2026-06-25",
        "changes": [
            "Feat (Loja): Estratégia de preços VIP — licenças VIP Bronze/Prata/Ouro/Diamante "
            "(3k/4,5k/7,5k/11,25k Âmbar) e kits a 10% da licença (300/450/750/1.125); "
            "itens avulsos do kit com markup 1,5× para o bundle valer mais.",
            "Feat (Loja): Pacote PIX R$75 = 8.250 Âmbares — suficiente para Licença VIP Ouro + "
            "Kit Ouro (kit alfa); VIP Diamante somente Âmbar, nunca em doação PIX.",
            "Feat (Loja): Itens avulsos VIP — struct_transmitter, struct_generatortek, "
            "item_soultraps_20, struct_tekreplicator_vip (90 Âmbar c/ VIP Bronze); "
            "struct_tekreplicator premium 52.500; Tek Forge mantém mínimo 50.000.",
        ],
    },
    {
        "version": "1.9.114",
        "date": "2026-06-25",
        "changes": [
            "Fix (Web Store): resgate da Licença Nuvem não esgota mais o pool MySQL — "
            "CREATE TABLE deixou de rodar a cada request, débito+grant em transação única, "
            "teardown do scoped_session e pool ampliado; saldo Âmbar de todos os jogadores "
            "permanece visível após resgate.",
            "Fix (CustomShop): entrega web/Nuvem (pedidos pendentes) ignora Permissions em "
            "GiveKit/GiveItem — pedido já pago; /shop com pontos continua exigindo Alga, "
            "VIPDiamante ou qualquer grupo configurado no kit.",
            "Fix (CustomShop): kit diamante sem VIPDiamante em Permissions (só Admins) — "
            "evita dependência circular no primeiro resgate de VIP comprado na web.",
            "Melhoria (Loja): Sincronizar plugins registra no log e no resumo cada "
            "kit/item cujo campo Permissions mudou por mapa (catálogo TEK → config.json).",
            "Melhoria (CustomShop): mensagens in-game específicas ao falhar entrega "
            "pendente (catálogo, licença, spawn de dino) em vez de só «Contate admin».",
        ],
    },
    {
        "version": "1.9.113",
        "date": "2026-06-25",
        "changes": [
            "Fix (CustomShop): WebsiteUrl com IP legado é corrigido automaticamente ao "
            "abrir o TEK/Manager — migração em todos os mapas + log ao sincronizar; "
            "resolve_plugin_website_url usa sempre o domínio público (nunca IP:27199).",
            "Fix (Comércio P2P): espécies do overlay ark_species_registry.json (40 Abyss) "
            "sincronizam para market_species no boot e no «Sync catálogo» — visíveis no admin "
            "Espécies oficiais; ative para tabela pública e browse.",
            "Fix (Web Store): resgate de kit/item exibe mensagem clara em PT-BR (saldo, licença, "
            "pendência na Nuvem, erro de entrega) no toast e em Minha Área; falhas auditadas.",
            "Feat (Loja): script tools/sync_abyss_shop_catalog.py adiciona 40 itens Abyss ao "
            "config.json da loja (aba Dinos/Itens) — execute antes de Sincronizar plugins.",
        ],
    },
    {
        "version": "1.9.112",
        "date": "2026-06-25",
        "changes": [
            "Feat (Comércio P2P): thumbnails por tier (silhuetas SVG S+/S/A/B/C) nos cards "
            "de browse, vitrine, tabela oficial e admin; suporte a image_url/icon_path no "
            "registro de espécies para arte licenciada futura — sem uso de imagens Dododex.",
        ],
    },
    {
        "version": "1.9.111",
        "date": "2026-06-25",
        "changes": [
            "Fix (CustomShop): resumo «Loja (jogadores)» na aba Web Store mostra só o domínio "
            "público — IP:porta fica em linha de diagnóstico separada; rótulos clarificam "
            "domínio (chat), API LAN (plugins) e IP público (DNS).",
        ],
    },
    {
        "version": "1.9.110",
        "date": "2026-06-25",
        "changes": [
            "Fix (CustomShop): /shop e mensagens Nuvem voltam a exibir o domínio público "
            "(WebsiteUrl) em vez de http://IP:porta — configure em CustomShop → Loja → "
            "«Domínio público da loja» e clique Sincronizar plugins.",
        ],
    },
    {
        "version": "1.9.109",
        "date": "2026-06-25",
        "changes": [
            "Fix (Comércio P2P): classificação admin — listings não promovem mais para DRAFT "
            "automaticamente ao ativar espécie ou reconciliar; fila e endpoint /classify aceitam "
            "DRAFT sem aprovação (flag admin_classification_approved); badge AGUARDANDO alinhado "
            "ao estado real.",
        ],
    },
    {
        "version": "1.9.108",
        "date": "2026-06-25",
        "changes": [
            "Fix (Web Store): navegação por abas — CSS boot-admin forçava display:block em "
            "todas as páginas admin-only ao mesmo tempo; agora só o menu admin e a página "
            ".page.admin-only.active ficam visíveis.",
            "Feat (Web Store): nome de exibição obrigatório após login Steam — modal "
            "bloqueante, navegação e ações (resgate, PIX, Comércio) bloqueadas até salvar; "
            "validação API em /api/player/purchase, PIX e pedidos.",
        ],
    },
    {
        "version": "1.9.107",
        "date": "2026-06-25",
        "changes": [
            "Feat (Comércio P2P): registro Abyss em ark_species_registry.json — 40 blueprints "
            "(recursos, sementes, dinos nativos, variantes abissais e veículos Thalassian) com "
            "nome PT-BR, tier, papel e preço base sugerido em Âmbar para auto-categorização no depósito.",
        ],
    },
    {
        "version": "1.9.106",
        "date": "2026-06-25",
        "changes": [
            "Feat (Comércio P2P): categorização automática de dinos por registro ARK "
            "(blueprint → nome PT-BR, tier, papel e preço base sugerido) com fila admin "
            "de confirmação antes de liberar anúncios na vitrine.",
            "Feat (Comércio P2P): API admin POST /listings/classify e bulk, cards com nome "
            "amigável (sem blueprint cru), sugestão em destaque e mensagem "
            "«Aguardando aprovação da equipe»; browse continua só ACTIVE.",
        ],
    },
    {
        "version": "1.9.105",
        "date": "2026-06-25",
        "changes": [
            "Feat (Web Store): aba Tutoriais no menu Jogador — guias detalhados em português "
            "(primeiros passos, catálogo, Comércio P2P, comandos in-game, Nuvem e FAQ) com "
            "acordeão, índice e busca.",
        ],
    },
    {
        "version": "1.9.104",
        "date": "2026-06-25",
        "changes": [
            "Feat (Chat cluster): captura automática do chat global — sem comando /c; "
            "rotulação [Mapa] Jogador nos servidores.",
            "Feat (Chat cluster): ponte Discord bidirecional na Web Store (discord.py) — "
            "jogo→Discord e Discord→todos os mapas, com prevenção de eco.",
            "Melhoria (Chat cluster): config AutoCapture, IgnoreCommands, GlobalChatOnly no "
            "CustomShop; painel Discord no admin da loja web. CustomShop.dll requer recompilação.",
        ],
    },
    {
        "version": "1.9.103",
        "date": "2026-06-25",
        "changes": [
            "Feat (Comércio P2P): anúncios personalizáveis — nome customizado (até 80 chars), "
            "categoria/tier em destaque, descrição do vendedor (até 280 chars) e badge do "
            "nome de exibição na vitrine e no Mercado.",
            "Feat (Comércio P2P): migração automática das colunas custom_name, category e "
            "custom_description; validação server-side (strip HTML, limites) e formulário na Minha Loja.",
        ],
    },
    {
        "version": "1.9.102",
        "date": "2026-06-25",
        "changes": [
            "Feat (Comércio P2P): reserva de resgate com janela de 24h após compra ou retirada — "
            "/mercado só funciona dentro do prazo; expiração cancela e reembolsa o comprador "
            "(preço integral + taxas=0) com devolução do dino ao vendedor.",
            "Feat (Comércio P2P): worker periódico idempotente para claims expirados, countdown na "
            "Minha Loja/histórico, auditoria MARKET_CLAIM_EXPIRED_REFUND e migração automática do schema.",
        ],
    },
    {
        "version": "1.9.101",
        "date": "2026-06-25",
        "changes": [
            "Feat (TEK oBobonic): auditoria de cobertura — editor .env por seções (Discord, XP, ARK, "
            "Twitch/TikTok, tickets), backup/restauração .env, gerenciador de cogs em config.py.",
            "Feat (TEK oBobonic): status Discord inferido dos logs, links Dev Portal/convite, "
            "atalhos .bancos/ e data/; honestidade sobre limites (latência, dados JSON, UI Discord).",
            "Melhoria (Comércio P2P): comando de resgate renomeado de /resgatarmercado para /mercado "
            "(plugin CustomShop, web store e docs).",
        ],
    },
    {
        "version": "1.9.100",
        "date": "2026-06-25",
        "changes": [
            "Fix (TEK oBobonic): painel vazio/preto — grid row 0 sem weight=0, frame vazio cacheado "
            "antes do build; layout alinhado ao CustomShop e cache só após sucesso.",
            "Fix (Web Store): portal travado em «Conectando…» — sintaxe TypeScript inválida "
            "(const tail: Promise<unknown>[]) impedia o boot JS; corrigido para JS puro.",
            "Fix (Web Store): boot paralelo (health + auth + catálogo/home), watchdog 8s com "
            "botão Tentar novamente, before_request leve em / e /api/health, Cache-Control no index.",
        ],
    },
    {
        "version": "1.9.99",
        "date": "2026-06-25",
        "changes": [
            "Feat (TEK oBobonic): sync TEK → .env (RCON, query, senha admin e host dos mapas ARKLAND), "
            "health check RCON/A2S antes de iniciar, status online/offline com contagem de jogadores.",
            "Feat (TEK oBobonic): validação DISCORD_TOKEN, criação automática de .venv, reinício ao crash "
            "(toggle), subprocess Windows com .env carregado e Python do ambiente virtual.",
        ],
    },
    {
        "version": "1.9.98",
        "date": "2026-06-25",
        "changes": [
            "Feat (TEK): Painel oBobonic — gerencia o bot Discord oBobonicClean externo: "
            "iniciar/parar/reiniciar, configurar salas (mapas ARK no .env), logs e dependências.",
        ],
    },
    {
        "version": "1.9.97",
        "date": "2026-06-25",
        "changes": [
            "Feat (Dashboard TEK): Agendar desligamento no card do servidor — avisos RCON em 5/3/1 min, "
            "countdown em tempo real e cancelamento.",
        ],
    },
    {
        "version": "1.9.96",
        "date": "2026-06-25",
        "changes": [
            "Fix (Web Store): before_request não bloqueia mais em MySQL — DB sobe só em background; "
            "/api/health e /api/auth/me respondem sem esperar migrate/conexão.",
            "Fix (Web Store): portal não fica em «Inicializando» — boot JS imediato, admin oculto no HTML, "
            "redeem_docs.js defer e ping MariaDB em cache com timeout 2s.",
            "Fix (Broadcasts): ciclo automático envia de fato — Iniciar ciclo não desativava scheduler_enabled; "
            "persiste ao reiniciar o app, countdown em tempo real (1s) e ordem aleatória no loop.",
        ],
    },
    {
        "version": "1.9.95",
        "date": "2026-06-25",
        "changes": [
            "Fix (Web Store): portal admin não trava mais — admins do arquivo, cache MySQL com backoff, "
            "/api/health e boot com timeout; config.json antes de abrir Itens da Loja.",
            "Fix (DB): painel Banco de Dados não congela ao abrir tabelas — lock na conexão, "
            "consultas em background e grade em lotes.",
        ],
    },
    {
        "version": "1.9.94",
        "date": "2026-06-24",
        "changes": [
            "Remove (Caddy): integração Caddy removida — HTTPS público via Cloudflare Tunnel ou proxy externo.",
            "Fix (Web Store): diagnóstico testa HTTPS no domínio real; status sem referências a Caddy/modem.",
            "Fix (DB): painel Banco de Dados rolável — browser 720px sem cortar backup/ações.",
            "Feat (Jogo): upar speed em voadores (bAllowFlyerSpeedLeveling) e recolher estruturas (AlwaysAllowStructurePickup).",
        ],
    },
    {
        "version": "1.9.93",
        "date": "2026-06-24",
        "changes": [
            "Fix (Web Store): primeira carga não trava mais — migrate MySQL em background, "
            "timeout de conexão 5s, cache do config.json.",
            "Fix (Web Store): boot honesto — status mostra erro real (loja offline, catálogo, banco) "
            "em vez de ficar em «Inicializando».",
            "Fix (CustomShop): /shop e WebsiteUrl usam IP público; WebApiUrl usa LAN (v1.9.91–92).",
        ],
    },
    {
        "version": "1.9.92",
        "date": "2026-06-24",
        "changes": [
            "Fix (CustomShop): /shop mostra link http://IP:27199 que funciona hoje — "
            "WebsiteUrl do plugin não depende mais do domínio público fora do ar.",
        ],
    },
    {
        "version": "1.9.91",
        "date": "2026-06-20",
        "changes": [
            "Fix (CustomShop): WebApiUrl dos plugins usa IP LAN da loja (ex.: :27199) — "
            "resgates entregam no jogo mesmo com domínio público fora do ar.",
        ],
    },
    {
        "version": "1.9.90",
        "date": "2026-06-24",
        "changes": [
            "Fix (Web Store): diagnóstico não marca mais «jogadores» por hairpin do modem — "
            "testa Caddy em 127.0.0.1:443, www e porta 443 na internet.",
            "Fix (Caddy): ao iniciar, libera automaticamente firewall Windows 80/443.",
        ],
    },
    {
        "version": "1.9.89",
        "date": "2026-06-24",
        "changes": [
            "Fix (Web Store): painel Loja deixa de mostrar «Online» só com localhost — "
            "diagnóstico testa LAN, domínio público, DNS e Caddy; status honesto.",
            "Fix (Caddy): «HTTPS Online» só quando o domínio responde, não só porta 443 aberta.",
            "Melhoria (Loja): textos de rede corrigidos (sem referência a VPS); IP público no diagnóstico.",
        ],
    },
    {
        "version": "1.9.88",
        "date": "2026-06-24",
        "changes": [
            "Fix definitivo (TEK Dashboard): shell estável — bulk bar fora do scroll, "
            "cards_host permanente; rebuild só dos cards no status (sem destruir o scroll).",
        ],
    },
    {
        "version": "1.9.87",
        "date": "2026-06-24",
        "changes": [
            "Fix (CustomShop): /download após desconectar — leitura binária dos blobs (sem HEX), "
            "lock da nuvem liberado no login e purge completo do cofre.",
        ],
    },
    {
        "version": "1.9.86",
        "date": "2026-06-24",
        "changes": [
            "Fix (TEK Dashboard): cards sumiam com servidor online — revertido para "
            "CTkScrollableFrame nativo; scrollregion mínima por grade + refresh de stats.",
        ],
    },
    {
        "version": "1.9.85",
        "date": "2026-06-24",
        "changes": [
            "Fix (TEK Dashboard): grade de cards permanece visível ao iniciar/parar servidores — "
            "scrollregion recalcula altura real após layout dos widgets CTk (sem mudar o visual).",
        ],
    },
    {
        "version": "1.9.84",
        "date": "2026-06-24",
        "changes": [
            "Fix (TEK Dashboard): servidores sumiam ao iniciar um mapa — CTkScrollableFrame "
            "recalculava mal a área rolável após refresh; dashboard migrado para FastScrollFrame.",
        ],
    },
    {
        "version": "1.9.83",
        "date": "2026-06-24",
        "changes": [
            "Fix (TEK Dashboard): ao iniciar um servidor os demais cards sumiam da lista — "
            "cards agora ficam direto no scroll (sem frame aninhado) e scrollregion corrigido.",
        ],
    },
    {
        "version": "1.9.82",
        "date": "2026-06-24",
        "changes": [
            "Novo (Chat cluster): chat entre mapas via /c — sync automático de ServerId por servidor, "
            "aba no CustomShop, painel admin na loja web (log, filtros, silenciar jogadores) e CustomShop.dll recompilado.",
            "Novo (Auditoria PIX): log completo de doações na loja web — tentativas, concluídas, abandonadas e canceladas "
            "com SteamID, payment_id, MP ID e filtros para suporte.",
        ],
    },
    {
        "version": "1.9.81",
        "date": "2026-06-24",
        "changes": [
            "Fix (SteamCMD): botão «Baixar SteamCMD» falhava com name 'urllib' is not defined — "
            "import ausente em download_steamcmd.py; URL do instalador definida no módulo.",
        ],
    },
    {
        "version": "1.9.80",
        "date": "2026-06-24",
        "changes": [
            "Fix (TEK): páginas vazias no painel do servidor — valores numéricos inválidos no perfil "
            "interrompiam o carregamento assíncrono das seções; estado travado corrigido e mensagem de erro.",
            "Melhoria (Loja web): Crystal Isles e Genesis 2 na seção Mapas do Cluster — 6 mapas no total.",
        ],
    },
    {
        "version": "1.9.79",
        "date": "2026-06-24",
        "changes": [
            "Fix (TEK): botão «Novo Servidor» não abria o diálogo — erro de sintaxe em "
            "asm_add_server_dialog.py (string de caminho padrão C:\\ARK\\); mensagem de erro "
            "exibida se o diálogo falhar ao carregar.",
        ],
    },
    {
        "version": "1.9.78",
        "date": "2026-06-24",
        "changes": [
            "Novo (Configurações globais): ambiente ARKLAND SERVER — criação padronizada de pastas "
            "(MAPAS, CLUSTER, BACKUP, CACHE, LOGS, STEAMCMD, WEBSTORE, MARIADB) com aplicação automática "
            "dos caminhos no gerenciador.",
            "Melhoria: backups, SteamCMD, logs do manager, MariaDB portable e loja web usam o ambiente "
            "quando ativo; novos servidores sugerem instalação em MAPAS/.",
            "Melhoria (Loja web): seção Mapas do Cluster redesenhada — destaque visual para mapas MOD "
            "como diferencial do cluster (showcase, cards por bioma e contador dinâmico).",
        ],
    },
    {
        "version": "1.9.77",
        "date": "2026-06-20",
        "changes": [
            "Novo (Loja web): gestão de servidores do cluster — ocultar na home, excluir do sync, prune de "
            "duplicatas e edição pelo admin (Servidores + flags Home/Loja na aba Loja TEK).",
            "Novo (Loja web): seção Mapas da Home editável (admin) com Brighamia, Alps, The Volcano e Amissa; "
            "título e texto introdutório configuráveis no config.json.",
            "Melhoria (Loja): sync remoto de servidores por máquina (API /api/servers/sync) para cluster multi-host.",
            "Melhoria (Mods): linha copiável com IDs do Workshop separados por vírgula (TEK e classic).",
        ],
    },
    {
        "version": "1.9.76",
        "date": "2026-06-23",
        "changes": [
            "Novo (TEK — Broadcasts): reenvio automático por intervalo, ordem aleatória ou sequencial, "
            "seleção de servidores destino e mensagens no ciclo; export/import inclui configurações.",
            "Melhoria (Broadcasts): painel com scheduler, checkboxes por servidor/mensagem e envio da próxima mensagem.",
            "UI (Broadcasts): legendas nos campos Rótulo e Mensagem ao cadastrar nova entrada.",
        ],
    },
    {
        "version": "1.9.75",
        "date": "2026-06-22",
        "changes": [
            "Novo (TEK — Broadcasts): aba global para cadastrar mensagens, enviar via RCON a todos os "
            "servidores gerenciados e exportar/importar biblioteca (.arkbroadcast) entre máquinas.",
            "UI (Broadcasts): envio rápido, biblioteca com rótulo/mensagem e mesclagem por ID na importação.",
        ],
    },
    {
        "version": "1.9.74",
        "date": "2026-06-20",
        "changes": [
            "Novo (TEK — Disponibilidade): status de listagem paridade ASM — A2S local, query no IP público "
            "e fallback Steam; badges ONLINE · Steam, Aguardando publicação, LAN, Defina IP público.",
            "Config: campo machine_public_ip em config.json (paridade ASM MachinePublicIP) para detectar publicação na lista.",
            "Fix (Clusters): aviso quando cluster_dir aponta para raiz C:\\ em modo rede+sync; diagnóstico no detalhe do perfil.",
            "Fix (Comércio/Nuvem): mensagens in-game no chat normal (SendChatMessage) em vez de banner SERVER.",
        ],
    },
    {
        "version": "1.9.73",
        "date": "2026-06-20",
        "changes": [
            "Fix (Presets TEK): todas as 22 categorias de configuração disponíveis ao salvar preset — "
            "mesma lista do Importar/Sincronizar INI (engramas, subs, custom INI, PGM, etc.).",
            "Melhoria (Presets TEK): rótulos em português, selecionar tudo e lista rolável no diálogo.",
        ],
    },
    {
        "version": "1.9.72",
        "date": "2026-06-20",
        "changes": [
            "Novo (Clusters): exportar e importar perfil Cross-ARK (.arkcluster) entre PCs sem pasta compartilhada — "
            "mesmo Cluster ID, restrições e hints dos mapas vinculados na máquina de origem.",
            "UI (Clusters): botão «Exportar perfil» no detalhe do cluster; «Importar perfil» na lista lateral.",
        ],
    },
    {
        "version": "1.9.71",
        "date": "2026-06-22",
        "changes": [
            "Novo (Clusters): botão 'Testar viagem' simula listagem do obelisco/terminal antes de iniciar — "
            "valida Cluster ID, pasta compartilhada, escrita UNC, mapas vinculados e uploads existentes.",
            "UI (Clusters): perfil único com lista de mapas, pré-visualização do que será aplicado e aviso se mapa já está em outro cluster.",
            "UI (Servidor): painel do mapa só escolhe o perfil — configuração completa fica em Clusters.",
            "Fix (Clusters): criação automática de pastas locais ao salvar perfil (modo rede+sync e local).",
        ],
    },
    {
        "version": "1.9.70",
        "date": "2026-06-22",
        "changes": [
            "Fix (Cluster rede): Cross-ARK entre máquinas na LAN — UNC normalizada (// e \\), "
            "-ClusterDirOverride com aspas em caminhos UNC, igual ao ASM.",
            "Fix (Cluster rede + sync): cada servidor usa pasta local ShooterGame\\Saved\\clusters; "
            "sync replica para UNC; inicia automaticamente ao salvar perfil ou no boot do Manager.",
            "UI (Clusters): orientações claras para modo rede (UNC direto vs sync por máquina).",
        ],
    },
    {
        "version": "1.9.69",
        "date": "2026-06-22",
        "changes": [
            "Novo (CustomShop): chat cluster entre mapas via /c e MySQL (poll + mute + API Web Store).",
            "Fix (Clusters): painel Cross-ARK abre detalhe do perfil e vincula servidores TEK (ASM).",
            "Fix (Clusters): servers_in_cluster, sync engine e perfil global na Administracao do servidor.",
        ],
    },
    {
        "version": "1.9.68",
        "date": "2026-06-20",
        "changes": [
            "Fix (Comercio): mensagens in-game no chat normal (SendChatMessage) em vez de banner grande (SERVER).",
            "Fix (TimedPoints): remover grupo na Web Store ou Manager apaga do JSON ao salvar (nao merge silencioso).",
        ],
    },
    {
        "version": "1.9.67",
        "date": "2026-06-21",
        "changes": [
            "Fix (Comercio): layout alinhado do simulador na pagina Economia Comercio (grid HP/DM/WE/ST/SP).",
        ],
    },
    {
        "version": "1.9.66",
        "date": "2026-06-21",
        "changes": [
            "Comercio: economia proporcional (piso loja + espaco bonus por porte) — formula pts/254 com pesos por dieta.",
            "Comercio: admin Economia Comercio (tetos, pesos, simulador, editor por especie, recalcular DRAFT).",
            "Comercio: breakdown in-game no /enviar e /confirmar; points_base via plugin (spawn probe).",
            "Comercio: tabela publica com piso/porte/teto, export CSV, modo custom rate_per_point.",
            "Fix: notificacao Discord de backup exibe tamanho correto (B/KB/MB/GB, nao mais 0.0 MB).",
        ],
    },
    {
        "version": "1.9.65",
        "date": "2026-06-21",
        "changes": [
            "Novo (Comercio): breakdown economico no /enviar via API plugin/preview.",
            "Novo (Comercio): modo custom com rate_per_point no editor; barra piso/bonus/teto; export CSV.",
            "Limpeza: removido modal legado de multiplicadores; script sync_market_economy.py.",
        ],
    },
    {
        "version": "1.9.64",
        "date": "2026-06-21",
        "changes": [
            "Novo (Comercio): editor por especie com override de peso e modo legacy_multipliers.",
            "Novo (Comercio): Comercio admin — botao Economia substitui Mult.; link direto ao editor.",
            "Docs: secao 5.8.2 modos de preco e weight_override.",
        ],
    },
    {
        "version": "1.9.63",
        "date": "2026-06-21",
        "changes": [
            "Novo (Comercio): editor por especie na Economia Comercio (dieta, porte, stats enabled).",
            "Novo (Comercio): tabela publica mostra piso, porte, teto e stats — breakdown com espaco bonus.",
            "Docs: PROJETO_MERCADO_CRYOPOD secao 5.7–5.8 atualizada para modelo proporcional.",
        ],
    },
    {
        "version": "1.9.62",
        "date": "2026-06-21",
        "changes": [
            "Novo (Comercio): economia proporcional — piso (root loja) + espaco bonus por porte "
            "(100k/250k/300k) preenchido por stats base (pts/254) com pesos por dieta.",
            "Novo (Comercio): admin Economia Comercio — tetos, pesos, simulador e recalcular DRAFT.",
            "Fix (Comercio): pontos base (wild+mut) separados de level manual; 26 especies classificadas.",
        ],
    },
    {
        "version": "1.9.61",
        "date": "2026-06-21",
        "changes": [
            "Fix (Comercio): preco sugerido nao usa valor bruto da cryo como pontos (ex. HP 30470).",
            "Fix (Comercio): teto sugerido de 150k Âmbar; reconcile recalcula anuncios DRAFT/PAUSED.",
            "Fix (CustomShop): leitura melee/speed da cryo tenta indice atual se max+12 vier zero.",
        ],
    },
    {
        "version": "1.9.60",
        "date": "2026-06-21",
        "changes": [
            "Fix (Comercio): resolve_species reconhece blueprint da cryo (sufixo _C e "
            "BlueprintGeneratedClass) — listings ficavam PENDING com especie ACTIVE.",
            "Fix (Comercio): sync/ativar promove listings pendentes; botao Promover pendentes no admin.",
        ],
    },
    {
        "version": "1.9.59",
        "date": "2026-06-21",
        "changes": [
            "Novo (TEK): painel CustomShop — ativar/desativar timer minimo do Comercio "
            "(MarketCryoRequireMinDays) e dias minimos na aba Configuracoes.",
            "Fix (CustomShop): leitura timer cryogun — ignora saved<=3600 quando "
            "ItemDurability tem os segundos restantes (corrige 0 dias com max~29d).",
        ],
    },
    {
        "version": "1.9.58",
        "date": "2026-06-21",
        "changes": [
            "Novo (CustomShop): MarketCryoRequireMinDays no config — desativa verificacao de "
            "timer minimo em /enviar e /confirmar (default false por enquanto).",
        ],
    },
    {
        "version": "1.9.57",
        "date": "2026-06-21",
        "changes": [
            "Fix (CustomShop): timer cryogun — segundos restantes em ItemDurability quando "
            "BPGetItemDurabilityPercentage retorna 0; /enviar mostrava 0 dias com 29d na UI.",
        ],
    },
    {
        "version": "1.9.56",
        "date": "2026-06-21",
        "changes": [
            "Fix (CustomShop): leitura do timer de cryopods capturadas — SavedDurability "
            "em segundos (ex. 29d no jogo) nao era reconhecido; /enviar falhava com 0 dias.",
            "Fix (TEK): dashboard contava linhas do ListPlayers em vez de jogadores — "
            "'No Players Connected' aparecia como 1 online; versao ARK lida do ShooterGame.log.",
        ],
    },
    {
        "version": "1.9.55",
        "date": "2026-06-21",
        "changes": [
            "Novo (Web Store): secao de marketing do Comercio P2P na pagina inicial — "
            "beneficios, fluxo in-game e CTAs para mercado e tabela oficial.",
            "Novo (Comercio): legenda de tiers (S+, S, A, B, C) nas tabelas publica e admin.",
        ],
    },
    {
        "version": "1.9.54",
        "date": "2026-06-21",
        "changes": [
            "Fix (CustomShop): /enviar ignora cryopods corrompidas (timer sem dados legiveis) "
            "e seleciona a primeira cryo parseavel no inventario — corrige falha pos-dinowipe.",
        ],
    },
    {
        "version": "1.9.53",
        "date": "2026-06-21",
        "changes": [
            "Novo (Comercio): tabela economica com 26 grupos — vanilla, ARK Additions, "
            "Grand Hunt e Brighamia (Dread/Ancient Wyvern separados); sync de referencia "
            "e aliases de blueprint no upload P2P.",
            "Novo (Comercio): grupos Rex, Giga, Acro e Indominus (Domination Rex = mesma "
            "tabela); nomes do Comercio editaveis no admin sem alterar a loja.",
            "Novo (CustomShop): MarketCryoMinDaysRemaining (default 20 dias) — /enviar e "
            "/confirmar exigem timer minimo; cryo congela no vault ate resgate.",
        ],
    },
    {
        "version": "1.9.52",
        "date": "2026-06-21",
        "changes": [
            "Fix (CustomShop): StripCryopodTimer em cryos capturadas (timer ~30d) — "
            "restaura teto 3600s e SavedDurability; /confirmar no Comercio deixa de falhar.",
        ],
    },
    {
        "version": "1.9.51",
        "date": "2026-06-21",
        "changes": [
            "Fix (CustomShop): leitura de cryopods capturadas no Comercio — init forcado do item, "
            "scan CustomItemDatas, fallback SpawnFromDinoDataEx para metadata/imprint.",
            "Novo (CustomShop): /enviardebug + MarketCryoDebug no config — diagnostico de cryopod "
            "no chat e log ao falhar /enviar.",
        ],
    },
    {
        "version": "1.9.50",
        "date": "2026-06-20",
        "changes": [
            "Novo (Web Store): editor admin de multiplicadores por stat (7 stats, antes de ativar) "
            "+ botão Carregar sugeridos do market_species_defaults.json.",
            "Fix (Web Store): market_species_defaults.json incluído no bundle PyInstaller — "
            "sync catálogo aplica tiers e multiplicadores corretos em produção.",
        ],
    },
    {
        "version": "1.9.49",
        "date": "2026-06-20",
        "changes": [
            "Fix (Web Store): rotas /api/market/* retornavam 500 HTML — session_factory "
            "capturava _SessionLocal=None na importação; Comércio P2P inoperante.",
            "Fix (TEK): Gerenciador de Banco de Dados — scrollbars e treeviews com tema "
            "correto, layout da aba Dados e faixa branca na base.",
        ],
    },
    {
        "version": "1.9.48",
        "date": "2026-06-20",
        "changes": [
            "Fix (CustomShop): build_cl.bat inclui ShopCryoReader/ShopMarket; APIs Ark "
            "corrigidas para compilar o módulo Comércio P2P.",
        ],
    },
    {
        "version": "1.9.47",
        "date": "2026-06-20",
        "changes": [
            "Novo (Comércio P2P): Mercado de dinos via cryopod — upload /enviar e /confirmar, "
            "vault, anúncios, compra em Âmbares e resgate /resgatarmercado.",
            "Novo (Web Store): API mercado (economia, listings, claims, auditoria, migração "
            "automática market_*), UI Comércio e admin (espécies, classificação, vitrine).",
            "Novo (CustomShop): ShopCryoReader + ShopMarket — parse cryopod, strip timer no "
            "upload, anti-duplicação, claim/release seguro e validação de perfil in-game.",
        ],
    },
    {
        "version": "1.9.46",
        "date": "2026-06-20",
        "changes": [
            "Fix (CustomShop): ShopEntitlements::Grant — SQL alinhado com a web (sem subquery "
            "em player_entitlements), corrige erro MySQL 1093 e licenças Gamma/Beta/Alfa.",
            "Fix (CustomShop): GiveItem/GiveKit falham se LicenseGrant não gravar; claim atômico "
            "de pedidos pendentes; alias Gamma→licenca_gamma na entrega.",
            "Fix (Web Store): repair-license para pedidos entregues sem grant; claim/release "
            "de pedidos PENDENTE/ENTREGANDO.",
        ],
    },
    {
        "version": "1.9.45",
        "date": "2026-06-20",
        "changes": [
            "Fix (Web Store): desistencia de resgate PENDENTE reembolsa Âmbares corretamente "
            "e elimina erro SQLAlchemy ao cancelar pedido.",
        ],
    },
    {
        "version": "1.9.44",
        "date": "2026-06-20",
        "changes": [
            "Melhoria (Dashboard TEK): metricas do servidor (jogadores, uptime, RAM, versao) "
            "com fonte maior, chips destacados e melhor contraste nos cards.",
        ],
    },
    {
        "version": "1.9.43",
        "date": "2026-06-19",
        "changes": [
            "Fix (CustomShop): /upload sincroniza inventario no cliente apos remover itens "
            "(ClientRemoveActorItem + handshake completo) — corrige itens fantasmas na UI.",
            "Fix (CustomShop): Specimen Implant (PrimalItem_StartingNote) excluido da nuvem "
            "no upload e download — evita duplicar o implante no inventario.",
        ],
    },
    {
        "version": "1.9.42",
        "date": "2026-06-19",
        "changes": [
            "Fix (CustomShop): nuvem reescrita com segurança transacional — remove itens "
            "antes do banco, rollback automático do inventário em qualquer falha.",
            "Fix (CustomShop): /download conta pilhas reais (não slots internos ARK) e "
            "reverte itens já adicionados se a restauração falhar no meio.",
            "Melhoria (CustomShop): /nuvem mostra pilhas locais, slots livres e aviso "
            "se não há espaço para /download; lock anti-operação simultânea.",
            "Melhoria (DB Manager): área de dados/SQL expandida — seções Servidor Local e "
            "Backup colapsáveis; resultados SQL e tabelas ocupam o espaço disponível.",
        ],
    },
    {
        "version": "1.9.41",
        "date": "2026-06-19",
        "changes": [
            "Fix (CustomShop): dinos da loja web entregues em cryopod — AddItemObject "
            "(padrão ArkShop), cryo ativo por padrão e logs de diagnóstico no boot.",
            "Fix (CustomShop): /upload ignora slots internos do ARK (cores, craft, tributo) — "
            "contagem real de pilhas no inventário do jogador.",
            "Novo (TEK): tradução PT-BR completa das opções de servidor — 322 campos, "
            "tooltips em todos os campos e auditoria de qualidade (check_field_labels).",
            "Melhoria (CustomShop): recompensa por tempo online avisa no chat do jogo — "
            "valor creditado e saldo total de Âmbares (Default + licenças com StackRewards).",
        ],
    },
    {
        "version": "1.9.40",
        "date": "2026-06-19",
        "changes": [
            "Fix (Web Store): modal de resgate com scroll — botão Confirmar Resgate "
            "sempre visível em licenças com documentação longa (ex.: Licença Nuvem).",
            "Fix (CustomShop): /upload conta apenas itens válidos serializáveis — "
            "corrige falso limite de 250 itens quando o inventário tinha poucos itens reais.",
            "Melhoria (CustomShop): mensagens de /upload e /nuvem mais claras "
            "(contagem real de itens e orientação de uso).",
        ],
    },
    {
        "version": "1.9.39",
        "date": "2026-06-19",
        "changes": [
            "Fix (CustomShop): comandos /upload /download /nuvem funcionam no chat LOCAL "
            "(AddOnChatMessageCallback) — antes só respondiam no chat global.",
            "Fix (CustomShop): build.bat recompila CustomShop.dll antes do instalador — releases "
            "incluem plugin com inventário na nuvem.",
            "Melhoria (CustomShop): comandos console Shop.Upload, Shop.Download e Shop.Nuvem para teste via RCON.",
        ],
    },
    {
        "version": "1.9.38",
        "date": "2026-06-19",
        "changes": [
            "Novo (CustomShop): entrega de dinos em cryopods — módulo ShopCryoDino com cryopod vanilla "
            "(Extinction) direto no inventário do jogador.",
            "Melhoria (CustomShop): Settings.DeliverDinosInCryopods, CryoItemPath e CryoLimitedTime; "
            "por dino Cryopod/PreventCryo sobrescreve o padrão global.",
            "Melhoria (Web Store): painel Entrega de Dinos nas configurações gerais e seletor de "
            "entrega (padrão / cryopod / spawn) no editor de dinos.",
        ],
    },
    {
        "version": "1.9.37",
        "date": "2026-06-19",
        "changes": [
            "Melhoria (Web Store): editor de itens e kits com LicenseGrant — Group, Days, Redeemable "
            "e TimedPointsBonus sem editar config.json manualmente.",
            "Melhoria (Web Store): presets rápidos Nuvem (keyvault), Gamma, Beta e Alfa — inclui "
            "comando Permissions.AddTimed e modalidade correta no catálogo.",
            "Melhoria (Web Store): modalidade Licença VIP (Type license) e badge do grupo na lista admin.",
        ],
    },
    {
        "version": "1.9.36",
        "date": "2026-06-19",
        "changes": [
            "Novo (CustomShop): Inventário na Nuvem — /upload (até 250 itens), /download e /nuvem "
            "(alias /cloud) em qualquer mapa do cluster.",
            "Novo (CustomShop): módulo ShopCloudInventory — serialização GetItemBytes/CreateFromBytes, "
            "tabelas player_cloud_inventory e player_cloud_items.",
            "Novo (CustomShop): exige Licença Nuvem (keyvault) no upload; download liberado após expirar.",
            "Melhoria (Web Store): documentação automática da Licença Nuvem em redeem_docs.js.",
            "Melhoria (config): LicenseGrant em licenca_nuvem; CloudMaxItems=250, cooldown 30s.",
        ],
    },
    {
        "version": "1.9.35",
        "date": "2026-06-18",
        "changes": [
            "Fix (CustomShop / DB): sync não usa mais senha do root para o usuário arkland — evita gravar "
            "123456/changeme no config.json do plugin.",
            "Fix (Loja): validate_plugin_database_settings testa MySQL antes do sync; falha com mensagem "
            "clara em vez de propagar credencial inválida.",
            "Fix (DB): probe_mysql_host — detecta host correto (127.0.0.1 vs localhost) para MariaDB no Windows.",
            "Novo (DB Manager): botão «Arkland localhost+%» recria arkland@localhost e arkland@% com a mesma senha.",
            "Melhoria (CustomShop.dll): conexão MySQL tenta múltiplos hosts e registra pw_len no log para diagnóstico.",
        ],
    },
    {
        "version": "1.9.34",
        "date": "2026-06-18",
        "changes": [
            "Fix (CustomShop / DB): senha MySQL não é mais gravada no catálogo nem sobrescrita com "
            "placeholder changeme ao salvar ou sincronizar plugins.",
            "Fix (Loja): resolve_shop_db_password — senha efetiva vem do DB Manager / Banco de Pedidos; "
            "placeholders (changeme, SUA_SENHA_AQUI) são ignorados.",
            "Melhoria (CustomShop): sync preserva senha válida já no config.json do servidor quando o "
            "app ainda não tem credencial configurada.",
            "Docs: projeto Inventário na Nuvem (upload/download) documentado para discussão antes da implementação.",
        ],
    },
    {
        "version": "1.9.33",
        "date": "2026-06-18",
        "changes": [
            "Novo (Web Store): Sistema de Documentação Automática do Sistema de Resgates — painéis "
            "explicativos por categoria (Itens, Kits, Dinos, Licenças, Disponível, Doação).",
            "Novo (Web Store): documentação gerada automaticamente por item — descrição curta/detalhada, "
            "requisitos, licença necessária, avisos e texto de confirmação no modal de resgate.",
            "Melhoria (Web Store): grid de licenças Gamma/Beta/Alfa com duração e bônus de Âmbar documentados.",
        ],
    },
    {
        "version": "1.9.32",
        "date": "2026-06-18",
        "changes": [
            "Fix (Web Store): card de saldo de Âmbares — valor inteiro completo em cima, rótulo Âmbar/Âmbares "
            "abaixo; fonte reduz automaticamente para caber em saldos altos (sidebar, catálogo, recarga e mobile).",
        ],
    },
    {
        "version": "1.9.31",
        "date": "2026-06-12",
        "changes": [
            "Melhoria (Web Store): RCON ASE unificado — RconClient + ThreadPoolExecutor, retry no Shop.Reload "
            "(até 5 tentativas) e GET /api/rcon/status para teste de conectividade.",
            "Melhoria (Web Store): Console do Servidor — log append-only, histórico ↑/↓, Enter para enviar, "
            "loading nos botões e rate limit ajustado (60/min).",
            "Melhoria (Web Store): pontos e entregas 100% via banco/fila plugin — RCON bloqueado para "
            "Shop.AddPoints, Shop.SetPoints, Shop.GetPoints e Shop.Deliver.",
            "Melhoria (TEK): asm_rcon_window com auto-reconnect, send_command_with_retry e ping keep-alive.",
            "Melhoria (TEK + classic): módulos rcon_*.py ligados — auto-reconnect, retry e status no Console RCON.",
            "Fix (TEK): remote_agent usa connect() + send_command_safe() em vez de API inexistente do RconClient.",
            "Melhoria (TEK): reload CustomShop unificado em Shop.Reload (alinhado ao plugin e Web Store).",
            "Novo (TEK ASE): pasta custom de INI (user_config_folder) — lê/grava fora do install_dir e "
            "sincroniza para WindowsServer no start.",
            "Novo (TEK + classic): toggle EnableCryoSicknessPVP (Cryo Sickness em PvP).",
            "Fix (RCON): sanitização de senhas corrompidas com sufixo ?ServerPassword= (TEK, Web Store e RconClient).",
        ],
    },
    {
        "version": "1.9.30",
        "date": "2026-06-17",
        "changes": [
            "Novo (Web Store + CustomShop): sistema de licenças Gamma/Beta/Alfa — "
            "player_entitlements, TimedPoints empilhado (Default + licenças), preços 50k/75k/100k.",
            "Novo (Web Store): Desistência — cancelar resgate PENDENTE com reembolso de Âmbar.",
            "Melhoria (Web Store): resgate valida preço server-side e licenças exigidas (Permissions); "
            "Minha Área exibe licenças ativas; catálogo com cadeado.",
            "Novo (CustomShop): ShopEntitlements — grant/revoke, CanRedeem em Buy/Give kit e item.",
            "Fix (Web Store): moeda Âmbar na home sem sobreposição em mobile — animação só em desktop (901px+).",
        ],
    },
    {
        "version": "1.9.29",
        "date": "2026-06-17",
        "changes": [
            "Melhoria (Web Store): editor de itens com menu Modalidade no catálogo — Item, Dino, "
            "Licença, Comando e subcategorias; define Type e Category automaticamente.",
        ],
    },
    {
        "version": "1.9.28",
        "date": "2026-06-17",
        "changes": [
            "Novo (Web Store): moeda oficial Âmbar/Âmbares com ícone, lore completa na home "
            "(A Lenda do Âmbar de Arkland) e frase oficial da moeda.",
            "Novo (Web Store): aba Licenças no catálogo — permissões, nuvem e benefícios por comando.",
            "Melhoria (Web Store): interface pública sem a palavra Shop — ARKLAND Donations; "
            "normalização automática do nome exibido.",
            "Fix (TEK): MOTD visível em Detalhes do Servidor — card em largura total no topo "
            "(antes era coberto por BanList/Branch).",
            "Fix (TEK): painel CustomShop — padrão ARKLAND Donations em vez de ARKLAND Shop.",
            "Melhoria (Web Store): licenca_nuvem categorizada como Licenças no config.",
        ],
    },
    {
        "version": "1.9.27",
        "date": "2026-06-17",
        "changes": [
            "Novo (Web Store): página inicial completa — hero, servidores do cluster, estatísticas do "
            "catálogo, pacotes PIX, utilidades e FAQ focados no jogador.",
            "Novo (Web Store): seção Eventos Sazonais — rates ajustados periodicamente em todos os mapas, "
            "no estilo dos servidores oficiais.",
            "Novo (Web Store): destaque dos mapas mod Brighamia e Alps na home.",
            "Novo (Web Store): catálogo público (Itens, Dinos, Kits) sem login; Steam só para doar, "
            "resgatar e Minha Área.",
            "Melhoria (Web Store): menu Downloads renomeado para Utilidades; removidos cards automáticos "
            "do instalador/releases do painel admin.",
            "Melhoria (Web Store): home sem versão do app nem changelog do projeto — foco nos servidores.",
            "Fix (Web Store): grade de dinos no catálogo desktop; saldo de pontos via /api/player/points.",
            "Fix (Web Store): auditoria admin com modal formatado em vez de JSON cru; boot não exige login.",
        ],
    },
    {
        "version": "1.9.26",
        "date": "2026-06-12",
        "changes": [
            "Novo (Configurações): backup automático global de todos os servidores — pasta "
            "centralizada, ZIP compactado (nível 9), retenção por quantidade e botão executar agora.",
            "Novo (Banco de Dados): backup automático do MariaDB (arkland_shop / ark_permission) "
            "com intervalo configurável, restauração e retenção por quantidade.",
            "Fix (CustomShop): GiveItem entrega Dinos e Commands na fila web — resgates de "
            "carcharodontosaurus e itens similares passam a spawnar no jogo.",
            "Fix (CustomShop): GiveKit/GiveItem só marcam sucesso quando o spawn do dino realmente "
            "ocorre; /shop deixa de reportar entrega falsa.",
            "Novo (Web Store): sistema de auditoria completo — tabela audit_events, timeline por "
            "pedido e página Admin Auditoria.",
            "Novo (Web Store): reemissão só por admin com motivo e registro de qual admin reemitiu.",
            "Fix (TEK Mods): textos e ícones da aba Mods (Workshop) corrigidos (encoding UTF-8).",
        ],
    },
    {
        "version": "1.9.25",
        "date": "2026-06-16",
        "changes": [
            "Fix (CustomShop): GiveItem entrega Dinos e Commands na fila web — resgates de "
            "carcharodontosaurus e itens similares passam a spawnar no jogo.",
            "Fix (CustomShop): GiveKit/GiveItem só marcam sucesso quando o spawn do dino realmente "
            "ocorre; /shop deixa de reportar entrega falsa.",
            "Novo (Web Store): sistema de auditoria completo — tabela audit_events, timeline por "
            "pedido e página Admin Auditoria.",
            "Novo (Web Store): reemissão só por admin com motivo e registro de qual admin reemitiu.",
            "Fix (TEK Mods): textos e ícones da aba Mods (Workshop) corrigidos (encoding UTF-8).",
        ],
    },
    {
        "version": "1.9.24",
        "date": "2026-06-12",
        "changes": [
            "Fix (Discord): DiscordNotifier nunca era inicializado no app TEK — webhooks globais "
            "(start/stop/crash, backup, mods, BUFFs) voltam a funcionar.",
            "Fix (Discord TEK): notificações por servidor via webhook em Gerenciamento Automático + "
            "Detalhes do Discord Bot (start/stop e join/leave via ListPlayers).",
            "Melhoria (Discord): erros de webhook passam a aparecer no log com corpo da resposta HTTP.",
        ],
    },
    {
        "version": "1.9.23",
        "date": "2026-06-12",
        "changes": [
            "Fix (TEK): nova seção Mods (Workshop) na barra lateral do painel do servidor — "
            "lista de mods e atualização automática Workshop deixam de ficar escondidas em Administração.",
            "Fix (TEK): conflito de layout entre lista de mods e Branch SteamCMD corrigido "
            "(widgets sobrepostos na mesma linha do grid).",
        ],
    },
    {
        "version": "1.9.22",
        "date": "2026-06-12",
        "changes": [
            "Fix (BUFFs TEK): scheduler inicia ao abrir o app; reinício aplica rates nos INIs "
            "e só marca ativo quando o servidor volta online; UI mostra estado ATIVANDO.",
            "Fix (BUFFs TEK): RCON usa admin_password; parada/início via asm_server_manager "
            "sem diálogos que bloqueavam a thread em background.",
            "Fix (ModAutoUpdater TEK): ponte unificada para servidores TEK; card na aba Mods "
            "com ativar/parar, intervalo e log; Steam API Key repassada ao salvar config global.",
            "Fix (AutoUpdate servidor TEK): verificação agendada aguarda SteamCMD, compara "
            "build ID e registra log; reinício opcional após update (config global).",
            "Fix (Web Store): resgate confirmBuy não quebra toast após fechar modal.",
            "Novo (Web Store): editor estruturado de itens + Salvar & Aplicar grava disco e "
            "recarrega CustomShop em todos os servidores cadastrados.",
            "Melhoria (Web Store): save_config sincroniza catálogo em cada plugin_config_path "
            "e Shop.Reload via RCON em todos os servidores registrados.",
        ],
    },
    {
        "version": "1.9.21",
        "date": "2026-06-12",
        "changes": [
            "Novo (Web Store): editor estruturado de kits — itens (Amount/Quality), dinos "
            "(Level/Gender/ForceTame) e comandos com quantidade, sem perder campos ao salvar.",
            "Fix (Web Store): edição de kits preserva Dinos, Items, Commands e VipLicense "
            "existentes (merge com o JSON do config).",
            "Fix (CustomShop): Commands aceita string ou objeto { Command, ExecuteAsAdmin }; "
            "placeholder {steamid} além de {SteamID}.",
        ],
    },
    {
        "version": "1.9.20",
        "date": "2026-06-16",
        "changes": [
            "Novo (Web Store): layout responsivo para mobile e tablet — menu hambúrguer, sidebar "
            "deslizante, tabelas com scroll e modais adaptados.",
            "Melhoria (Web Store): barra mobile com saldo de pontos; catálogo e formulários "
            "empilhados em telas estreitas.",
        ],
    },
    {
        "version": "1.9.19",
        "date": "2026-06-16",
        "changes": [
            "Fix (PIX): impede crédito duplicado de pontos — webhook e polling na mesma transação "
            "com trava no banco.",
            "Fix (CustomShop/TimedPoints): Default (+25 etc.) só para jogadores conectados; "
            "sem acúmulo offline.",
            "Novo (CustomShop): licença VIP ao entregar kit — campo VipLicense (tier + até 30 dias) "
            "registra vip_players na entrega web.",
            "Melhoria (TimedPoints): bônus VIP por licença web resgatada ou permissão in-game; "
            "Stack configurável.",
        ],
    },
    {
        "version": "1.9.18",
        "date": "2026-06-16",
        "changes": [
            "Fix (PIX): rate limit 429 no polling de status — limite dedicado ao endpoint e "
            "consultas mais espaçadas com backoff automático.",
            "Novo (Web Store): Histórico de Doações em Minha Área — pontos creditados, data/hora, "
            "valor PIX e status de cada doação.",
            "Melhoria (Web Store): resumo de Minha Área separa doações creditadas e resgates de itens.",
        ],
    },
    {
        "version": "1.9.17",
        "date": "2026-06-12",
        "changes": [
            "Novo (Web Store/PIX): formulário do pagador antes do PIX — e-mail, nome, CPF e telefone "
            "(exigidos pelo Mercado Pago); dados repassados ao MP, sem e-mail fictício.",
            "Melhoria (Web Store): transparência sobre dados na doação — política, modal e hints "
            "deixam claro que o MP solicita os dados e a ARKLAND não usa para marketing.",
            "Fix (PIX): crédito automático de pontos após confirmação (poll 3s + webhook); "
            "payer_email gravado em point_payments.",
            "Fix (DB Manager): não sobrescreve mais usuário/senha com root@localhost quando MariaDB "
            "local está rodando; prioriza shop_db e config da Web Store.",
            "Melhoria (Loja): salvar Web Store grava credenciais MySQL em shop_db (prefs do DB Manager).",
        ],
    },
    {
        "version": "1.9.16",
        "date": "2026-06-12",
        "changes": [
            "Novo (Web Store): ARKLAND Donations — política de doações com modal, banner e aceite "
            "obrigatório antes de doar via PIX ou resgatar com pontos.",
            "Melhoria (Web Store): linguagem de doação/resgate em toda a UI (sem termos de compra/venda); "
            "aba Doação PIX; resgates com pontos no catálogo.",
            "Novo (Web Store): admin Doações PIX — pacotes, token Mercado Pago e tabela de gestão.",
            "Fix (Web Store): saldo de pontos na sidebar, statusbar e catálogo; retorno 0 se jogador "
            "não existe no banco.",
            "Fix (PIX): e-mail válido no checkout Mercado Pago (player{steamid}@arkland.com.br).",
            "Fix (Web Store): aba Disponível — migração orders.id para schema SQLAlchemy; "
            "setup_db.sql atualizado.",
        ],
    },
    {
        "version": "1.9.15",
        "date": "2026-06-12",
        "changes": [
            "Fix (HTTPS/Caddy): botões Instalar/Iniciar/Parar/Reiniciar não respondiam — "
            "_save_shop_from_ui() acessava campos do banco ainda não criados (NameError silencioso).",
            "Fix (HTTPS/Caddy): status Caddy atualiza ao final da aba Web Store; erros exibidos em messagebox.",
        ],
    },
    {
        "version": "1.9.14",
        "date": "2026-06-12",
        "changes": [
            "Novo (HTTPS): integração Caddy no app — instalar, iniciar, parar, reiniciar, "
            "firewall 80/443 e boot automático no Windows (modo Host, aba Web Store).",
            "Melhoria (HTTPS): Caddyfile gerado automaticamente (domínio → localhost:porta da loja); "
            "auto-start do Caddy após subir a web store.",
            "Fix (DB): ao reiniciar o app, o Gerenciador de DB mantém a última conexão remota "
            "(ex.: arkland@192.168.15.51) em vez de sobrescrever com root@127.0.0.1 quando o "
            "MariaDB local está rodando.",
            "Fix (DB): auto-connect local como root não grava prefs quando shop_db aponta para "
            "servidor remoto da loja.",
        ],
    },
    {
        "version": "1.9.13",
        "date": "2026-06-12",
        "changes": [
            "Fix (TEK/Admins): AllowedCheaterSteamIDs.txt passa a ser gravado em "
            "ShooterGame/Saved/ ao salvar ou iniciar o servidor (modo TEK não escrevia o arquivo).",
            "Fix (Admins): gravação centralizada em ark_server_files.py; promoção de jogador a admin "
            "atualiza o arquivo imediatamente.",
            "Melhoria (TEK): hint na seção Administradores indica caminho e momento da gravação.",
        ],
    },
    {
        "version": "1.9.12",
        "date": "2026-06-12",
        "changes": [
            "Novo (Web Store): abas Catálogo — Itens, Kits, Disponível (resgate) e Recarga PIX.",
            "Novo (Web Store): recarga PIX via Mercado Pago (MP_ACCESS_TOKEN) com QR code e webhook.",
            "Melhoria (Loja): domínio padrão arkland.com.br; modo Cliente para loja/banco em servidor remoto.",
            "Melhoria (Loja): defaults do servidor remoto — LAN 192.168.15.51, IP público 179.185.19.88, "
            "porta 27199; MySQL de pedidos aponta para o host remoto.",
            "Melhoria (Loja): UI Web Store exibe URLs do servidor remoto (LAN, internet e domínio para jogadores).",
            "Fix (Loja): abas Itens/Kits do painel CustomShop não duplicam conteúdo após importar catálogo.",
            "Novo (API): /api/player/available — resgate de entregas pendentes na web store.",
        ],
    },
    {
        "version": "1.9.11",
        "date": "2026-06-12",
        "changes": [
            "Novo (Loja): botão «Importar JSON» no painel CustomShop — carrega catálogo ArkShop "
            "(ShopItems/Kits) com conversão automática para formato CustomShop.",
            "Novo (Loja): importação normaliza Blueprints, Amount→Quantity, itens dino (Dinos) e "
            "command (Commands); opção mesclar/substituir e importar TimedPointsReward.",
            "Fix (CustomShop): BuyItem entrega dinos e executa comandos na compra; bundles aceitam "
            "Amount como alias de Quantity.",
        ],
    },
    {
        "version": "1.9.10",
        "date": "2026-06-15",
        "changes": [
            "Fix (BUFFs/TEK): sistema de rates temporários funciona em servidores TEK — "
            "start/stop, INI e combo unificado (TEK + legado).",
            "Novo (TEK): remover servidores legados (modo primitivo) em Configurações → "
            "Servidores legados, sem precisar abrir o modo primitivo.",
            "Fix (DB): botão «Sync jogadores» — recria arkland_shop.players com schema CustomShop "
            "e importa SteamId de ark_permission.players.",
            "Fix (DB): botão «Recarregar» na barra de conexão e na aba Dados; aviso se "
            "players tiver schema do Permissions.",
        ],
    },
    {
        "version": "1.9.9",
        "date": "2026-06-15",
        "changes": [
            "Fix (mods): descompressão UE4 de arquivos .z na instalação de mods — paridade "
            "ModUtils.CopyMod do ASM; PrimalGameData e mapas mod passam a carregar corretamente.",
            "Fix (mods): reparo automático antes do start se PrimalGameData ainda estiver "
            "comprimido (.uasset.z sem .uasset).",
            "Fix (mods): geração de .mod via WriteModFile (mod.info + modmeta.info) na cópia.",
        ],
    },
    {
        "version": "1.9.8",
        "date": "2026-06-15",
        "changes": [
            "Fix (TEK/mods): reparo de arquivos .mod antes do start — paridade modo primitivo "
            "(Steam Client oficial ou geração via mod.info).",
            "Fix (TEK/mods): ActiveMods no GUS inclui o ID do map mod (como no modo primitivo).",
            "Fix (TEK/mods): «Baixar Mods» usa +force_install_dir na pasta do servidor e validate, "
            "igual ao modo primitivo.",
        ],
    },
    {
        "version": "1.9.7",
        "date": "2026-06-15",
        "changes": [
            "Fix (ASM/mods): paridade mapa mod — CLI usa nome interno (não /Game/Mods/...), "
            "-TotalConversionMod= na launch, map mod baixado via workshop ID do ServerMap.",
            "Fix (ASM/mods): ActiveMods no GUS exclui o ID do map mod (como ASM); "
            "«Baixar Mods» inclui map mod + total conversion automaticamente.",
            "Fix (ASM/mods): aviso ao iniciar se Content/Mods/{id}/ ou {id}.mod estiver ausente.",
        ],
    },
    {
        "version": "1.9.6",
        "date": "2026-06-15",
        "changes": [
            "Fix (INI): GameUserSettings.ini garante as 7 seções canônicas do servidor ASE "
            "(mesmo vazias) — ScalabilityGroups, SessionSettings, ServerSettings, GameSession, etc.",
            "Fix (INI): ordem estável de seções na gravação GUS (template hosting/ASM).",
            "Fix (INI): apenas Version=5 injetado automaticamente; sem defaults inventados em seções vazias.",
        ],
    },
    {
        "version": "1.9.5",
        "date": "2026-06-15",
        "changes": [
            "Fix crítico (INI): GameUserSettings.ini agora preserva [/Script/ShooterGame.ShooterGameUserSettings] "
            "com Version=5 — sem isso o ARK regravava o arquivo inteiro com defaults no boot.",
            "Fix (INI): MaxPlayers espelhado em SessionSettings/GameSession além de [/Script/Engine.GameSession].",
            "Fix (INI): normalização de case das seções GUS evita duplicatas que invalidam o arquivo.",
        ],
    },
    {
        "version": "1.9.4",
        "date": "2026-06-15",
        "changes": [
            "Fix (DB Manager): layout da aba Banco de Dados restaurado — NameError interrompia a montagem do painel na v1.9.3.",
            "Fix (DB Manager): status arkland_shop/ark_permission integrado na barra de conexão sem quebrar o grid.",
        ],
    },
    {
        "version": "1.9.3",
        "date": "2026-06-12",
        "changes": [
            "Novo (DB): setup_db.sql e wizard criam ark_permission além de arkland_shop — banco vazio para o Permissions.dll.",
            "Novo (Permissions): template plugin/Permissions/configs/config.json incluído no bundle do app.",
            "Novo (Loja): sync/instalação CustomShop grava Permissions/config.json com credenciais do DB Manager (MysqlDB: ark_permission).",
            "Novo (DB Manager): status dos bancos arkland_shop e ark_permission, atalhos e aviso se Permissions.dll sem banco.",
            "Novo (Loja): botão «Provisionar grupos (RCON)» — Permissions.AddGroup a partir do catálogo CustomShop.",
            "Melhoria (Plugins): ASE Permissions marcado como obrigatório com grupos na stack CustomShop.",
        ],
    },
    {
        "version": "1.9.2",
        "date": "2026-06-12",
        "changes": [
            "Fix (TEK/paridade primitiva): novo _asm_persist_server — Iniciar, Reiniciar e Instalar agora seguem o mesmo fluxo do modo primitivo (widgets → JSON → INI → ação).",
            "Fix (TEK/SessionName): nome da sessão vazio usa automaticamente o nome do gerenciador, igual ao server_name do modo primitivo.",
            "Fix (TEK): caminhos duplicados de start consolidados; SteamCMD usa persistência completa antes de rodar.",
        ],
    },
    {
        "version": "1.9.1",
        "date": "2026-06-12",
        "changes": [
            "Fix (SteamCMD/TEK): branch vazio agora usa -beta public no AsmSteamCmd (caminho real do TEK) — a v1.9.0 só corrigia o ModManager legado.",
            "Fix (SteamCMD): ao trocar de preaquatica para estável, remove appmanifest antigo e força validate — corrigia instalação presa na v358.24.",
            "Fix (SteamCMD): Instalar/Atualizar sincroniza o painel aberto antes de rodar (branch_name não ficava vazio se não salvasse).",
            "Fix (ASM/SessionName): INI gravado antes de iniciar; ?SessionName= na CLI para nomes simples; aviso ao reconectar servidor já em execução.",
        ],
    },
    {
        "version": "1.9.0",
        "date": "2026-06-12",
        "changes": [
            "Nova funcionalidade (TEK): menu suspenso para eventos oficiais ARK (ActiveEvent) em Administração → Evento sazonal ARK — FearEvolved, WinterWonderland, TurkeyTrial, etc.",
            "Melhoria (Web Store): redesign da loja — hero, chips de categoria e cards com thumbnail.",
            "Melhoria (CustomShop): botão para recarregar plugin via RCON em todos os servidores elegíveis.",
            "Fix (SteamCMD): branch vazio agora usa -beta public explicitamente na instalação/atualização do servidor.",
        ],
    },
    {
        "version": "1.8.11",
        "date": "2026-06-14",
        "changes": [
            "Fix (CustomShop): ShopPoints::Exec agora trata ER_DUP_FIELDNAME (1060) como migração idempotente, evitando erro em runtime 'Duplicate column name kits'.",
            "Build (CustomShop): plugin recompilado e empacotado com CustomShop.dll corrigida.",
        ],
    },
    {
        "version": "1.8.10",
        "date": "2026-06-13",
        "changes": [
            "Fix (ASM/launch): SessionName removido da CLI em todos os casos; o nome da sessão "
            "agora é persistido somente no GameUserSettings.ini para evitar parsing inconsistente no Windows.",
            "Docs: ARK_SERVER_CONFIG_REFERENCE.md alinhado ao comportamento atual de launch "
            "(SessionName apenas no INI, AltSaveDirectoryName e -clusterid corrigidos no mapeamento).",
        ],
    },
    {
        "version": "1.8.9",
        "date": "2026-06-13",
        "changes": [
            "Fix (ASM/launch): SessionName com colchetes/espaços não vai mais na CLI com "
            "%5B/%20 — o ARK exibia o encoding literal; nome fica só no GUS.ini (aspas + UTF-16).",
            "Fix (ASM/launch): ?SessionName= na CLI restrito a nomes simples (A-Za-z0-9_-) "
            "para evitar 'ARK #NNNNNN' sem corromper nomes complexos.",
            "Fix (CustomShop): migração kits com ADD COLUMN IF NOT EXISTS e tolerância a "
            "ER_DUP_FIELDNAME (1060).",
        ],
    },
    {
        "version": "1.8.8",
        "date": "2026-06-13",
        "changes": [
            "Fix (Updater): encerra ARKLAND-WebStore.exe antes de instalar — corrigia erro "
            "'DeleteFile falhou; código 5 / Acesso negado' ao atualizar.",
            "Fix (Updater/TEK): app fecha corretamente após iniciar o agente de atualização.",
            "Fix (TEK): verificação automática de atualização ao iniciar o app (regressão do app_tek).",
            "Fix (Web Store): auto_start_webstore usava variável shop antes de defini-la.",
        ],
    },
    {
        "version": "1.8.7",
        "date": "2026-06-13",
        "changes": [
            "Fix (ASM/launch): restaurado ?SessionName= na travel URL com percent-encoding — "
            "regressão da v1.7.6 causava nome genérico 'ARK #NNNNNN' na listagem.",
            "Fix (ASM/INI): SessionName gravado por último no GUS.ini — INI customizado/raw "
            "não pode mais sobrescrever o nome efetivo do servidor.",
            "Fix (CustomShop): migração da coluna kits idempotente (sem erro Duplicate column).",
        ],
    },
    {
        "version": "1.8.6",
        "date": "2026-06-12",
        "changes": [
            "Fix (CustomShop): Error 126 — libmariadb.dll e z.dll copiadas para Win64/ além de "
            "Plugins/CustomShop/; diagnóstico de instalação incompleta.",
            "Fix (CustomShop): SSL/TLS ao conectar em 127.0.0.1:3306 — MariaDB portable não usa "
            "TLS; plugin recompilado com MYSQL_OPT_SSL_ENFORCE=0.",
            "Melhoria (CustomShop): instalar/sincronizar grava WebApiUrl, API Key e credenciais "
            "Database (arkland_shop) do DB Manager no config.json do plugin.",
            "Melhoria (Web Store): IP público + URLs LAN/internet na aba; botão Firewall Windows; "
            "detecção automática de IP público; diagnóstico LAN vs localhost.",
        ],
    },
    {
        "version": "1.8.5",
        "date": "2026-06-12",
        "changes": [
            "Fix (Web Store): ARKLAND-WebStore.exe falhava com «No module named dotenv» — "
            "python-dotenv adicionado às dependências e empacotado no build PyInstaller.",
        ],
    },
    {
        "version": "1.8.4",
        "date": "2026-06-12",
        "changes": [
            "Fix (Web Store): no instalador, a loja não iniciava — o app tentava rodar app.py com "
            "ARKLAND-ServerManager.exe (não é Python). Novo ARKLAND-WebStore.exe dedicado no "
            "instalador; dados persistentes em %APPDATA%\\ARKLAND-ServerManager\\arkshop_web.",
            "Melhoria (Web Store): diagnóstico ao falhar (tail do webstore.log), espera pela porta "
            "e MariaDB antes de subir o Flask.",
        ],
    },
    {
        "version": "1.8.3",
        "date": "2026-06-12",
        "changes": [
            "Fix (DB): conexão travava em «Conectando...» quando o login funcionava na primeira "
            "tentativa — finalização da conexão (state.conn + status Conectado) estava só no "
            "retry do erro 1049; corrigido para qualquer conexão bem-sucedida.",
        ],
    },
    {
        "version": "1.8.2",
        "date": "2026-06-13",
        "changes": [
            "Novo (DB): Assistente guiado de instalação do banco arkland_shop — wizard em 3 passos "
            "(MariaDB → root → senha arkland) com setup automático e prefs salvas para a Loja.",
            "Fix (DB): setup_db.sql incluído no executável PyInstaller e no instalador; cópia em "
            "%APPDATA%\\ARKLAND-ServerManager — corrige «Arquivo não encontrado» no Setup limpo.",
            "Fix (DB): conexão retenta sem database quando arkland_shop ainda não existe (erro 1049).",
            "Performance: projeto UI concluído — chunking Engramas/Meio Ambiente/Estruturas, "
            "cache de busca, tail de Administração adiado, docs/UI_PATTERNS.md.",
        ],
    },
    {
        "version": "1.8.1",
        "date": "2026-06-12",
        "changes": [
            "Fix (Sidebar): título 'ARK Manager' cortado na barra lateral — renomeado para "
            "'ARKLAND / Server Manager', logo reduzida (54×36 px), padding ajustado e "
            "sidebar ampliada para 240 px; nenhum texto é truncado.",
            "Novo (WebStore — Downloads): página pública de Downloads e painel admin "
            "'Gerenciar Links' — links manuais via config.json + injeção automática do "
            "instalador e GitHub Releases a partir do version.json.",
            "Novo (WebStore — /api/version): endpoint público que expõe versão, data e "
            "URL de download atual do projeto.",
            "Fix (WebStore — Catálogo): nomes de produtos exibidos como ID interno — "
            "campo Name adicionado ao config.json; fallback formatKey() converte "
            "'metal_ingot_100' → 'Metal Ingot 100' automaticamente.",
            "Fix (WebStore — DB): MariaDB não iniciava antes do Flask em reinicializações "
            "— _ensure_mariadb_running() aguarda porta ativa antes de subir o processo "
            "Flask; _start_db_reconnect_watcher() reativa a conexão em background.",
            "Fix (WebStore — Visual): redesign 'Primitive+TEK' — paleta âmbar/fogo, "
            "textura de pedra no fundo, logo em medallion com fundo branco visível, "
            "acentos ciano substituídos por âmbar em nav, botões, cards e modais.",
        ],
    },
    {
        "version": "1.8.0",
        "date": "2026-06-11",
        "changes": [
            "Novo (TEK v2 — Interface): layout híbrido D completo em todas as 24+ seções — "
            "cards duplos, dual-label PT+EN, slider condicional (≥1200px), checkboxes em grid.",
            "Novo (TEK v2 — i18n): 100% dos campos com tradução PT-BR — 320 entradas no catálogo, "
            "0 pendências; hints/tooltips por campo com exibição por clique.",
            "Novo (TEK v2 — Modified+Reset): badge ● ciano e botão ↺ em todos os campos que "
            "diferem do padrão ARK — cobertura nos helpers legados e nos cards novos.",
            "Novo (TEK v2 — Fase 3 CLI): seção 'Avançado — Linha de comando' em Administração "
            "com 7 grupos de cards: Inicialização, Rede/plataformas, Segurança, Performance, "
            "Gameplay CLI, Logs de admin, Web Alarm.",
            "Novo (TEK v2 — Fase 4 Agregados): editores estruturados para "
            "HarvestResourceItemAmountClassMultipliers, DinoClassDamage/Resistance, "
            "TamedDinoClassDamage/Resistance, DinoSpawnWeightMultipliers, "
            "PreventDinoTameClassNames — grupo 'Agregados' na navegação.",
            "Novo (TEK v2 — Fase 5 SM): seção 'Extensões SM' com ItemStackSizeMultiplier, "
            "SpoilingTimeMultiplier, MaxTributeDinos/Items, BabyImprintAmountMultiplier, "
            "EnableCreativeMode — grupo 'SM / Avançado' na navegação.",
            "Novo (TEK v2 — SpawnExact): gerador completo de SpawnExactDino compatível com "
            "ArkUtils — species search via Obelisk ASB, 7 stats wild/tamed, 6 regiões de cor, "
            "imprint %, blueprints favoritos, histórico, presets, copiar e enviar via RCON.",
            "Novo (TEK v2 — Obelisk): cliente Python para o manifest ArkUtils Obelisk "
            "(values.json) com cache local, deduplicação e exibição de variantes (Alpha, Boss…).",
            "Novo (TEK v2 — Arquivos do Servidor): cards individuais para Administradores, "
            "Whitelist e Exclusive Join com contador dinâmico de IDs e botão 'Colar ID(s)'.",
            "Novo (SpawnExact — CustomShop): botão 'Adicionar ao Kit' exporta o comando "
            "SpawnExactDino diretamente para um kit do config.json da loja.",
            "Fix (Loja/WebStore): aba Web Store carregava incompleta — NameError em "
            "_save_shop_from_ui (acesso a _port_var antes de sua criação); CTkEntry não "
            "aceita command= (ValueError); ambos corrigidos.",
            "Fix (Loja/WebStore): URL central agora populada diretamente de resolve_central_url(shop) "
            "na inicialização, sem chamar _save_shop_from_ui antes de todos os widgets existirem.",
        ],
    },
    {
        "version": "1.7.6",
        "date": "2026-06-10",
        "changes": [
            "Fix (ASM/launch): SessionName removido da CLI — RunServer.cmd passa pelo cmd.exe "
            "que expandia %20/%5B e corrompia nomes (ex: BBRDBARKLANDDBPVEDB5X…). Nome só no INI.",
            "Fix (ASM/launch): RunServer.cmd escapa % como %% para evitar corrupção de argumentos.",
            "Fix (SteamCMD): Instalar/Atualizar usa validate automaticamente quando a pasta já "
            "tem servidor — força manifest e arquivos atualizados.",
            "Melhoria (Start): aviso ao iniciar servidor em v358.x (fora do branch preaquatica) "
            "com opção de atualizar via SteamCMD antes do start.",
        ],
    },
    {
        "version": "1.7.5",
        "date": "2026-06-09",
        "changes": [
            "Novo (Loja): botão 📦 Instalar CustomShop — copia DLLs embutidas do app para "
            "ArkApi/Plugins/CustomShop/ em todos os servidores (config.json existente preservado).",
            "Novo (Loja): suporte TEK — painel Web Store lista servidores asm_config_manager "
            "e config_manager com indicador de instalação do plugin.",
            "Melhoria (Loja): Aplicar em todos os plugins e registro arkshop_web incluem "
            "servidores TEK; AsmServerConfig ganha shop_server_id e customshop_config_path.",
        ],
    },
    {
        "version": "1.7.4",
        "date": "2026-06-10",
        "changes": [
            "Fix (SteamCMD/TEK): +force_install_dir agora vem ANTES de +login — ordem exigida "
            "pela Valve; ordem errada fazia servidor instalar/atualizar na versão antiga (ex: 358.24).",
            "Fix (SteamCMD/TEK): instalação ao criar servidor usa validate e verifica "
            "appmanifest_376030.acf na pasta configurada.",
            "Melhoria (SteamCMD): aviso quando a pasta de instalação já contém servidor antigo; "
            "log exibe build Steam ao concluir.",
        ],
    },
    {
        "version": "1.7.3",
        "date": "2026-06-10",
        "changes": [
            "Fix (ASM/SessionName): fallback automático — se 'Nome da sessão' estiver vazio, "
            "usa o nome do servidor no gerenciador (card/sidebar) para INI e CLI.",
            "Fix (ASM/import): corrigida leitura de SessionName ao importar servidor existente "
            "(bug lia MaxPlayers em vez de SessionName e podia zerar o nome).",
        ],
    },
    {
        "version": "1.7.2",
        "date": "2026-06-10",
        "changes": [
            "Fix (ASM/INI): SessionName com colchetes/espaços agora gravado entre aspas — "
            "valores como [ARKLAND] Teste quebravam o parser do ARK e geravam 'ARK #NNNNNN'.",
            "Fix (ASM/INI): SessionName duplicado em [SessionSettings] e [ServerSettings]; "
            "escrita UTF-16 nativa (sem configparser.write).",
            "Fix (ASM/launch): ?SessionName= na CLI com percent-encoding (%20, %5B…) — "
            "funciona com espaços e caracteres especiais sem quebrar o cmd.exe.",
        ],
    },
    {
        "version": "1.7.1",
        "date": "2026-06-10",
        "changes": [
            "Fix (ASM/launch): restaurado ?SessionName= na CLI para nomes sem espaços — "
            "regressão da v1.7.0 causava nome genérico 'ARK #NNNNNN' na listagem.",
            "Fix (ASM/INI): MaxPlayers gravado em [/Script/Engine.GameSession] (seção correta do ASM).",
            "Fix (ASM/start): Iniciar/Restart pelo dashboard ou card agora sincroniza o painel "
            "aberto antes de gravar INI e lançar o servidor.",
            "Melhoria (SteamCMD): log imediato e janela visível ao baixar servidor/mods — "
            "feedback antes da auto-atualização do SteamCMD (1–2 min).",
            "Melhoria (Mods): um único SteamCMD para todos os mods da lista (antes: 1 por mod).",
            "Melhoria (TEK): botão 📁 na pasta de instalação ao criar servidor; pergunta se "
            "deseja instalar o servidor agora após criar.",
        ],
    },
    {
        "version": "1.7.0",
        "date": "2026-06-10",
        "changes": [
            "Novo (Loja): arquitetura multi-máquina — uma loja web central (host) e apps "
            "cliente na LAN apontando para o mesmo arkshop_web e API key.",
            "Novo (Loja): entrega in-game via plugin CustomShop — compras ficam PENDENTES "
            "na web e são entregues automaticamente ao jogador (GiveItem/GiveKit), sem mod "
            "MX-E Ark Shop UI nem dependência do ArkShop original.",
            "Novo (Loja): painel 🛒 Loja reformado — aba Web Store (modo Host/Cliente), "
            "teste de conexão, sync de catálogo e botão Aplicar em todos os plugins.",
            "Melhoria (Plugin): CustomShop recompilável — HttpClient, build_cl.bat e "
            "CustomShop.vcxproj alinhados; DLL embutida no instalador do app.",
            "Fix (Loja): API /api/pending e /api/pending/delivered corrigidas para "
            "entrega via fila do plugin (delivery_mode=plugin por padrão).",
            "Fix (ASM/launch): SessionName removido permanentemente da CLI — nome do "
            "servidor fica somente no GameUserSettings.ini ([SessionSettings]/SessionName).",
            "Fix (ASM/INI): DifficultyOffset gravado apenas quando enable_difficulty_override=True.",
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
    {
        "version": "1.3.21",
        "date": "2026-05-21",
        "changes": [
            "Feat (Paridade ASM — ServerGameSettings): ~35 novos campos GUS [ServerSettings]: tamed_dino_damage/resistance_multiplier, dino_character_stamina_drain_multiplier, dino_turret_damage_multiplier, max_personal_tamed_dinos, day/night cycle speed scales, disable_weather_fog, allow_pvp/pve_gamma, allow_hit_markers, disable_imprint_dino_buff, allow_anyone_baby_imprint_cuddle, allow_flying_stamina_recovery, prevent_mate_boost, allow_multiple_attached_c4, estruturas/decay (auto_destroy_decayed_dinos, pve_dino_decay_period_multiplier, disable_dino_decay_pvp, pvp_structure_decay, max_structures_visible, max_platform_saddle_structure_limit, etc.), allow_cave_building_pve, enable_diseases, allow_tribe_alliances, override_npc_network_stasis_range_scale.",
            "Feat (Paridade ASM — ServerAdvancedSettings): ~40 novos campos Game.ini [ShooterGameMode]: passive_tame_interval_multiplier, wild/tamed dino food/torpor drain multipliers, base_temperature_multiplier, disable_dino_riding/taming, disable_friendly_fire_pvp/pve, disable_loot_crates, increase_pvp_respawn_interval, prevent_offline_pvp_connection_invincible_interval, allow_tribe_war_pve/cancel, max_alliances/tribes_per_tribe/alliance, allow_custom_recipes, use_corpse_locator, supply_crate_loot_quality_multiplier, global_corpse_decomposition/battery_durability multipliers, poop/hair/resource multipliers, disable_structure_placement_collision, pvp_zone_structure_damage_multiplier, limit_turrets_in_range, fast_decay_interval.",
            "Feat (Paridade ASM — ServerConfig): ~35 novos campos: server_ip (MultiHome), use_raw_sockets, no/force_net_threading, public_ip_for_epic, spectator_password, enable_ban_list_url, rcon_server_game_log_buffer, admin_logging, enable_extinction_event, disable_vac, disable_anti_speed_hack, speed_hack_bias, use_cache, use_old_save_format, use_no_memory_bias, stasis_keep_controllers, use_no_hang_detection, server_allow_ansel, no_dinos, force_dx10/shader_model4/low_memory, enable_allow_cave_flyers, enable_auto_destroy_structures, enable_web_alarm, enable_server_admin_logs, max_tribe_logs, tribute_*_expiration_seconds, minimum_dino_reupload_interval, cross_ark_allow_foreign_dino_downloads, branch_name/password.",
            "Feat (ark_ini.py): _GUS_SERVER_SETTINGS expandido para 95 entradas; save_game_user_settings() grava inversões booleanas (PreventDiseases, PreventTribeAlliances, DisablePvEGamma, PvPDinoDecay) e todos os novos campos ServerConfig; save_game_ini() escreve ~40 novos campos [ShooterGameMode]; populate_config_from_gus/game_ini() lêem todos os novos campos.",
            "Feat (build_launch_args): novos URL params ?MultiHome= e ?bRawSockets; novas flags -insecure, -noantispeedhack, -speedhackbias=, -nocombineclientmoves, -nonetthreading, -forcenetthreading, -PublicIPForEpic=, -ForceAllowCaveFlyers, -AutoDestroyStructures, -nofishloot, -usecache, -oldsaveformat, -nomemorybias, -StasisKeepControllers, -NoHangDetection, -ServerAllowAnsel, -NoDinos, -d3d10, -sm4, -lowmemory, -servergamelog, -servergamelogincludetribelogs, -ServerRCONOutputTribeLogs, -NotifyAdminCommandsInChat, -webalarm.",
            "Feat (ModManager): suporte a branch SteamCMD via -beta <name> e -betapassword <pwd> usando campos branch_name/branch_password do ServerConfig.",
            "Feat (Acesso Remoto): novo painel Remoto na barra lateral — código de identidade base64, RemoteAgent com rotas GET /servers e POST /server/{id}/start|stop|restart|rcon, RemoteClient HTTP, janela de controle remoto com polling a cada 3s, console RCON embutido, regenerar token, lista de máquinas remotas salvas.",
        ],
    },
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
