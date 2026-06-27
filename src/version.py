"""
Versão e changelog do ARKLAND - Server Manager.
Este arquivo é a única fonte de verdade para a versão do aplicativo.
"""

APP_VERSION: str = "1.9.131"
BUILD_DATE: str = "2026-06-26"

# Cada entrada: version, date, changes (lista de strings)
CHANGELOG: list[dict] = [
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
