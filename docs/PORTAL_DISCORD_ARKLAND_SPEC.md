# Portal Discord ARKLAND — Extensão do ecossistema Web Store (especificação para discussão)

> **⚠️ Direção atualizada (jul/2026):** A UI principal do portal jogador é a **Web Store (Minha Área)**, não o bot Discord. Este documento permanece como referência histórica para integrações Discord **opcionais** (notificações, espelho de status).  
> **→ Especificação canônica:** [`PORTAL_JOGADOR_SPEC.md`](PORTAL_JOGADOR_SPEC.md)

| Campo | Valor |
|-------|-------|
| **Status** | 📋 **Superseded** — ver [`PORTAL_JOGADOR_SPEC.md`](PORTAL_JOGADOR_SPEC.md) |
| **Versão do documento** | 1.0 (arquivado) |
| **Data** | 05 de julho de 2026 |
| **Escopo** | Painel de botões Discord integrado ao portal ARKLAND (CustomShop + Web Store + TEK) |
| **Fora de escopo** | Código, deploy, substituição do oBobonicClean genérico |

> **Ver também:** [`REGULAMENTO_SITE_IMPLEMENTACAO.md`](REGULAMENTO_SITE_IMPLEMENTACAO.md), [`PROJETO_MERCADO_CRYOPOD.md`](PROJETO_MERCADO_CRYOPOD.md), [`GENOMA_ARKLAND_SPEC.md`](GENOMA_ARKLAND_SPEC.md), [`DINO_LAB_SPEC.md`](DINO_LAB_SPEC.md), [`ambarmeter_spec.md`](ambarmeter_spec.md), [`src/obobonic_bot.py`](../src/obobonic_bot.py), [`plugin/arkshop_web/app.py`](../plugin/arkshop_web/app.py).

---

## Sumário executivo

O plugin de terceiros visto no screenshot (Link Ark-Discord, Auto-Kick, Daily Points, VIP Daily, Steam ID) resolve dores reais com **poucos botões** — mas assume **ArkShop/VIP** e um fluxo de pontos diários desacoplado do ecossistema ARKLAND.

A proposta deste documento é um **Portal Discord ARKLAND**: não um bot genérico de comunidade, e sim uma **extensão do portal web** com funções simples de alto valor, reutilizando Steam OpenID, licenças **Alfa / Beta / Gamma / Nuvem**, Âmbares, tickets, mercado e RCON já existentes.

**Decisão de arquitetura sugerida:** cog novo no **oBobonicClean** (`portal_arkland`) + API REST dedicada na Web Store (`/api/portal/discord/*`) autenticada por Discord OAuth2 + vínculo Steam↔Discord persistido — **separada** do bot fino de cross-chat/tickets em `arkshop_web`.

---

## 1. Visão

### 1.1 O que é

Um **painel persistente** (embed + botões) em canal fixo do Discord ARKLAND — por exemplo `#portal-jogador` ou integrado ao painel de tickets existente (`CANAL_PAINEL_ID`) — que oferece atalhos **read-mostly** e **ações seguras** para quem já joga no cluster:

| Princípio | Descrição |
|-----------|-----------|
| **Portal, não bot** | Cada botão abre ou executa algo que **já existe** na Web Store ou no CustomShop |
| **Simples** | 3–5 botões no MVP; expansão por fases |
| **Identidade ARKLAND** | Licenças Alfa/Beta/Gamma/Nuvem, Âmbares, regulamento — **nunca VIP/ArkShop** |
| **Steam como fonte da verdade** | Conta de jogo = SteamID64; Discord é identidade de canal |

### 1.2 O que já existe (baseline técnico)

#### oBobonic / TEK (`src/obobonic_bot.py`, `src/pages/obobonic_panel.py`)

- Gerenciador de subprocesso do **oBobonicClean** (projeto externo em `oBobonicClean/`).
- Sincroniza mapas TEK → variáveis `ARK_MAP*` no `.env` do bot.
- Health check RCON/A2S por mapa; catálogo de **cogs** já carregáveis: `rcon_monitor`, `ark`, `ark_a2s`, `tickets`, `voting`, `xp`, `referrals`, `vip`, etc.
- **Não** implementa hoje integração com Web Store — apenas orquestração e configuração via painel TEK.

#### Web Store (`plugin/arkshop_web`)

| Área | Estado | Referência |
|------|--------|------------|
| Login Steam OpenID | ✅ Produção | `app.py` — fluxo `/login/steam` |
| Saldo Âmbares | ✅ `GET /api/player/points`, `/api/player/summary` | |
| Licenças (entitlements) | ✅ `GET /api/player/entitlements` — Alfa/Beta/Gamma/Nuvem | `player_entitlements` |
| Vínculo Discord | ⚠️ Manual (ID/username) para tickets | `ticket_routes.py` — `oauth_available: False` |
| Enquetes + recompensa | ✅ `poll_routes.py`, `poll_service.py` | |
| Tickets jogador | ✅ `ticket_routes.py` + notif. staff Discord | `ticket_discord.py` |
| Regulamento + aceite | ✅ `regulamento_service.py` | |
| Notificações in-app | ✅ mercado, tickets, etc. | `notification_routes.py` |
| Status cluster / join | ✅ `GET /api/public/home` — servidores + `connect_url` | `server_connect.py` |
| Âmbarômetro público | ✅ `GET /api/public/amber-stats` | `amber_ledger.py` |
| Pontos “diários” 24h | ❌ **Não existe** | Recompensa = Timed Points in-game + enquetes |
| Cross-chat Discord | ✅ Bot fino em `cross_chat_discord.py` | Token separado |
| API interna CustomShop | ✅ `X-API-Key` | `app.py` — rotas internas |

#### CustomShop in-game (`plugin/CustomShop/src/Commands.cpp`)

| Comando jogador | Função |
|-----------------|--------|
| `/shop` | URL da loja web |
| `/upload`, `/download`, `/nuvem`, `/cloud` | Inventário Nuvem (exige licença Nuvem) |
| `/engramas` | Desbloqueio pago de engramas |
| `/mercado` | Mercado P2P cryopod (Genoma futuro) |

**Timed Points** (`TimedPoints.cpp`): recompensa **periódica enquanto online** (intervalo em minutos, grupos Default/Gamma/Beta/Alfa) — **não** claim único a cada 24h.

**RCON admin:** `KickPlayer`, `ListPlayers`, `Shop.GetPoints`, entitlements via web — TEK já expõe kick em `src/pages/player_kick.py`.

### 1.3 Lacunas vs. objetivo “portal Discord”

| Lacuna | Impacto |
|--------|---------|
| Sem OAuth Discord ↔ Steam | Botões personalizados exigem vínculo confiável |
| Sem API pública bot→portal | oBobonic não consulta saldo/licenças hoje |
| “Daily Points” do screenshot | Modelo diferente do Timed Points ARKLAND |
| VIP Daily Points | Anti-pattern explícito para ARKLAND |
| Auto-kick self-service | TEK tem kick admin; falta fluxo jogador + confirmação |
| Genoma / Dino Lab | Sem superfície Discord hoje (correto — ver §9) |

---

## 2. Comparação com o screenshot (terceiros)

| Feature do screenshot | Adaptar? | Proposta ARKLAND |
|----------------------|----------|------------------|
| **Link Ark-Discord** (código in-game) | ✅ Sim | **Vincular Steam↔Discord** via OAuth2 Discord + sessão web (substituir entrada manual de ID) |
| **Auto-Kick** (desbloqueio / stuck) | ✅ Sim | **Auto-kick assistido**: confirma Steam vinculado → `KickPlayer` via RCON no mapa onde está online |
| **Daily Points** (claim 24h) | ⚠️ Parcial | **Não clonar** — mostrar status Timed Points + link enquete ativa; claim real continua in-game/web |
| **VIP Daily Points** | ❌ Não | Substituir por **status licença** (Alfa/Beta/Gamma/Nuvem) + bônus Timed Points já configurados |
| **Steam ID** (botão) | ✅ Sim | Perfil Steam + estado vínculo + atalho Minha Área web |

**O que descartar de propósito:** qualquer nomenclatura VIP/ArkShop, economia paralela de pontos Discord, código in-game digitado no chat (frágil e spamável) — preferir OAuth + botões efêmeros (modal/select).

---

## 3. Funções candidatas (ranking valor × viabilidade)

Escala: **Valor** (1–5) × **Viabilidade** (1–5) = **Score**. Ordenado do maior score.

| # | Função | V | F | Score | Nota |
|---|--------|---|---|-------|------|
| 1 | **Vincular Steam ↔ Discord** | 5 | 4 | 20 | Desbloqueia todas as ações personalizadas |
| 2 | **Minha conta** (saldo + licenças) | 5 | 5 | 25 | APIs já existem; só agregar |
| 3 | **Status do cluster** | 4 | 5 | 20 | `GET /api/public/home` + opcional A2S do cog `ark_a2s` |
| 4 | **Abrir loja / Minha Área** | 4 | 5 | 20 | Link autenticado ou deep link web |
| 5 | **Auto-kick (stuck)** | 4 | 3 | 12 | RCON + ListPlayers; exige rate limit forte |
| 6 | **Ticket rápido** | 4 | 4 | 16 | Criar ticket pré-preenchido com Discord no corpo |
| 7 | **Enquete ativa** | 3 | 4 | 12 | `GET /api/polls` — votar no web (bot só alerta) |
| 8 | **Regulamento / aceite pendente** | 3 | 4 | 12 | Aviso se `needs_regulamento_accept` |
| 9 | **Alertas mercado** (resumo) | 3 | 3 | 9 | Últimas notificações `market_*` — espelho do sino web |
| 10 | **Recompensa Timed Points** (info) | 3 | 5 | 15 | Somente leitura: intervalo + tier; **sem botão “claim”** |
| 11 | **Conectar ao servidor** | 3 | 5 | 15 | Botão por mapa com `steam://run/346110//+connect%20host:port` |
| 12 | **Âmbarômetro** (curiosidade) | 2 | 5 | 10 | Número público — engajamento leve |

---

## 4. Detalhamento por função

### 4.1 Vincular Steam ↔ Discord

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como jogador, quero vincular meu Discord à minha conta Steam ARKLAND para usar botões personalizados sem digitar IDs. |
| **Tech path** | Botão **Vincular conta** → OAuth2 Discord (`identify`) → redirect web `/portal/discord/callback` → usuário faz login Steam se necessário → grava `support_ticket_discord_links` (ou tabela `portal_discord_links`) → resposta ephemeral “Vinculado como {nick}”. |
| **Permissões** | Qualquer membro do guild; 1 Discord ↔ 1 Steam (unique constraint); staff pode desvincular no admin web. |
| **Reuse** | Estender `save_discord_link` / schema existente; hoje `oauth_available: False` em `ticket_routes.py`. |

### 4.2 Minha conta (saldo + licenças)

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como jogador vinculado, quero ver meus Âmbares e licenças ativas sem abrir o navegador completo. |
| **Tech path** | Botão **Minha conta** → `GET /api/portal/discord/me` (API key bot + header `X-Discord-User-Id`) → embed: saldo (`/api/player/points`), entitlements (`/api/player/entitlements`), timed_points_total. |
| **Permissões** | Requer vínculo; resposta **ephemeral** (privada). |
| **Terminologia** | Exibir **Licença Alfa** (expira em …), **Nuvem** — nunca VIP. |

### 4.3 Status do cluster

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como visitante do Discord, quero saber quais mapas estão online e quantos jogadores. |
| **Tech path** | Botão **Status** → agregação: (a) `GET /api/public/home` + (b) opcional poll RCON via TEK/oBobonic `health_check_maps` cacheado 60s → embed por mapa. |
| **Permissões** | Público (sem vínculo). |
| **Reuse** | `obobonic_bot.MapHealthResult`, `server_connect.public_server_connect_view`. |

### 4.4 Abrir loja / Minha Área

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como jogador, quero ir direto ao portal para resgatar, doar ou ver pedidos. |
| **Tech path** | Botões link: **Loja** → `website_url`; **Minha Área** → `{public_url}/#/area` (login Steam se sessão expirada). |
| **Permissões** | Público / autenticado web (fora do Discord). |

### 4.5 Auto-kick (desbloqueio / stuck)

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como jogador preso (mesh, bed bug, loading infinito), quero me kickar com segurança para reconectar. |
| **Tech path** | Botão **Desbloquear (kick)** → modal confirmação “Digite KICK” → API portal valida vínculo → `ListPlayers` em mapas do cluster → encontra SteamID → `KickPlayer {steam_id}` no mapa correto → log auditoria. |
| **Permissões** | Apenas Steam vinculado ao Discord caller; cooldown 5 min; máx. 3/dia. |
| **Riscos** | Abuso em PvE (evitar kick durante combate?) — opcional: só se jogador detectado online > X min sem movimento (fase 2). |
| **Reuse** | `src/pages/player_kick.py` pattern; mapas/senhas RCON do `.env` oBobonic sincronizado via TEK. |

### 4.6 Ticket rápido

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como jogador, quero abrir suporte a partir do Discord com meus dados já preenchidos. |
| **Tech path** | Botão **Suporte** → link `{public_url}/#/tickets/new?discord={user_id}` ou modal categoria → `POST /api/tickets` com token portal + regulamento guard. |
| **Permissões** | Vínculo Steam+Discord; aceite regulamento obrigatório (gate web ou API). |
| **Reuse** | `ticket_service.create_ticket`, staff notificado via `ticket_discord.py` existente. |

### 4.7 Enquete ativa

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como jogador, quero saber se há enquete com recompensa em Âmbares. |
| **Tech path** | Botão **Enquetes** → `GET /api/polls?include_closed=0` → embed com título + link votar na web (voto exige Steam session). |
| **Permissões** | Alerta público; voto = login web. |
| **Anti-pattern** | Não implementar voto nativo Discord (duplicaria fraude / contas alt). |

### 4.8 Regulamento / aceite pendente

| Campo | Conteúdo |
|-------|----------|
| **User story** | Se o regulamento mudou, quero ser avisado no Discord ao usar o portal. |
| **Tech path** | Após vínculo, `GET /api/regulamento/status` → se pendente, botão **Aceitar regulamento** → link web gate. |
| **Permissões** | Vinculado; leitura livre do HTML público. |
| **Reuse** | `regulamento_service.needs_regulamento_accept`. |

### 4.9 Alertas mercado (resumo)

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como vendedor/comprador, quero ver no Discord se vendi um dino ou se há claim pendente. |
| **Tech path** | Botão **Mercado** → `GET /api/notifications?unread_only=1` via portal API → top 3 + link Minha Área mercado. |
| **Permissões** | Vinculado; ephemeral. |
| **Nota Genoma** | Fase futura: incluir “certificado emitido” quando Genoma existir — hoje só tipos `market_*`. |

### 4.10 Recompensa Timed Points (somente informação)

| Campo | Conteúdo |
|-------|----------|
| **User story** | Quero entender quantos Âmbares ganho por tempo online conforme minha licença. |
| **Tech path** | Incluído em **Minha conta**: `timed_points_total`, `timed_points_interval_min` de `/api/player/entitlements`; texto explicativo do regulamento §8. |
| **Permissões** | Vinculado. |
| **Anti-pattern** | **Sem** botão “Resgatar diário” — economia diferente do screenshot. |

### 4.11 Conectar ao servidor

| Campo | Conteúdo |
|-------|----------|
| **User story** | Quero entrar no mapa X com um clique. |
| **Tech path** | Select menu de mapas → URL `steam://run/346110//+connect%20{host}:{port}` de `server_connect.build_steam_connect_url`. |
| **Permissões** | Público. |

### 4.12 Âmbarômetro (curiosidade)

| Campo | Conteúdo |
|-------|----------|
| **User story** | Como membro da comunidade, quero ver o volume total de Âmbares circulando. |
| **Tech path** | Rodapé do embed Status ou botão secundário → `GET /api/public/amber-stats`. |
| **Permissões** | Público. |

---

## 5. MVP sugerido (3–5 botões)

Prioridade para **máximo valor com mínimo risco**:

| Botão | Função | Motivo |
|-------|--------|--------|
| 1 | **Vincular conta** | Pré-requisito de personalização |
| 2 | **Minha conta** | Saldo + licenças — diferencial ARKLAND imediato |
| 3 | **Status cluster** | Útil para todos, zero risco |
| 4 | **Loja web** | Conversão / resgate — já existe |
| 5 | **Desbloquear (kick)** | Diferencial do screenshot; alto valor operacional |

**Fase 1.1 (rápida):** trocar botão 5 por **Suporte** se auto-kick gerar receio de abuso antes dos rate limits.

**Layout sugerido:**

```
┌─────────────────────────────────────────────┐
│  🌐 Portal ARKLAND                          │
│  Cluster PvE · Âmbares · Licenças Nuvem     │
│  ─────────────────────────────────────────  │
│  [ Vincular conta ] [ Minha conta ]         │
│  [ Status ] [ Loja ] [ Desbloquear ]        │
└─────────────────────────────────────────────┘
```

---

## 6. Integração com o painel TEK oBobonic

### 6.1 Divisão de responsabilidades

| Componente | Papel |
|------------|------|
| **oBobonicClean** (`portal_arkland` cog) | UI Discord (embed, botões, OAuth redirect handler leve ou proxy URL) |
| **Web Store** | Fonte da verdade: Steam, pontos, licenças, tickets, polls |
| **TEK** (`obobonic_panel.py`) | Ligar/desligar cog, canal do painel, URL da loja, sync RCON |
| **cross_chat / ticket_discord** | Mantidos separados — tokens diferentes, escopo staff/broadcast |

### 6.2 Novas chaves `.env` sugeridas (TEK → oBobonic)

| Chave | Descrição |
|-------|-----------|
| `PORTAL_CHANNEL_ID` | Canal do painel portal |
| `PORTAL_WEB_URL` | URL pública da loja (fallback `WebsiteUrl`) |
| `PORTAL_API_KEY` | Segredo compartilhado bot ↔ `arkshop_web` |
| `PORTAL_DISCORD_CLIENT_ID` / `SECRET` | OAuth2 app Discord (pode ser mesma application do bot) |
| `PORTAL_AUTO_KICK_ENABLED` | `true/false` |
| `PORTAL_AUTO_KICK_COOLDOWN_SEC` | Default 300 |

### 6.3 Painel TEK — bloco “Portal ARKLAND”

Espelhar padrão existente (cogs, health maps):

- Toggle cog `portal_arkland` na lista `COG_CATALOG`.
- Campo canal + botão **Publicar / atualizar painel**.
- Status: vínculos ativos (contagem via API), último kick self-service, erros RCON.
- Link teste **Sincronizar TEK** (já existe para RCON maps).

### 6.4 API portal proposta (Web Store)

Prefixo: `/api/portal/discord/` — autenticação: `Authorization: Bearer {PORTAL_API_KEY}` + `X-Discord-User-Id`.

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/me` | Saldo, entitlements, regulamento pendente, discord link |
| POST | `/link/complete` | Finaliza OAuth (chamado pelo callback web) |
| POST | `/self-kick` | Executa kick após checks |
| GET | `/cluster-status` | Proxy home + cache opcional |

**Não** reutilizar `X-API-Key` do CustomShop — escopo e rotação diferentes.

---

## 7. Anti-patterns (não fazer)

| Anti-pattern | Por quê |
|--------------|---------|
| **VIP Daily Points** / tier ArkShop | ARKLAND usa licenças nomeadas; Timed Points já cobre bônus por tier |
| **Claim 24h exclusivo Discord** | Duplicaria emissão de Âmbares; conflito com Timed Points + enquetes + doações |
| **Código in-game no chat** (`!link ABC123`) | Spam, spoofing, moderação — OAuth é superior |
| **Bot genérico duplicando oBobonic** | Tickets, XP, voz, Twitch já existem nos cogs atuais |
| **Voto de enquete só pelo Discord** | Um Discord ≠ uma conta Steam; fraude |
| **Saldo / kick sem vínculo** | Vazamento de PII e abuso de kick |
| **RCON password no cog** | Senha só no `.env` TEK-sincronizado; nunca log |
| **Renomear VIP no código CustomShop** | `ShopVip` é legado interno; UI sempre **Licença {tier}** |

---

## 8. Perguntas abertas para Ciano

1. **OAuth Discord:** mesma application do bot oBobonic ou app OAuth separado só para vínculo?
2. **Canal do painel:** canal dedicado `#portal` ou reutilizar `CANAL_PAINEL_ID` (tickets)?
3. **Auto-kick:** liberar no MVP ou esperar rate limits + auditoria? Cooldown 5 min é suficiente?
4. **Timed Points:** botão só informativo basta, ou deseja **notificação Discord** quando o tick in-game creditar (webhook)?
5. **Claim diário web:** existe intenção futura de recompensa 24h **fora** do Timed Points, ou descartamos permanentemente?
6. **Idioma:** embeds só PT-BR ou preparar i18n?
7. **Staff:** botão admin extra no mesmo painel (RCON rápido) ou manter staff só no TEK / cog `ark`?
8. **Mercado:** alertas Discord push para vendedor (além do sino web) entram no portal ou ficam só in-app?
9. **Regulamento:** aceite obrigatório antes de **qual** botão Discord — todos os vinculados ou só kick/ticket?
10. **Hosting callback OAuth:** mesmo domínio da loja (`public_url`) — confirma HTTPS e path `/portal/discord/callback`?

---

## 9. Relação com Genoma e Dino Lab (mínimo)

| Sistema | Relação com Portal Discord |
|---------|---------------------------|
| **Genoma** (mercado P2P verificado) | **Fase 2+.** Botão Mercado pode linkar `#/mercado` e, no futuro, alertar “certificado Genoma pronto”. Não misturar com Dino Lab. |
| **Dino Lab** (entrega admin staff) | **Fora do portal jogador.** Staff usa web admin; zero botões Discord para entrega custom. |
| **Nuvem** (`/upload`, `/download`) | Portal pode **mostrar** status licença Nuvem em Minha conta; comandos permanecem in-game. |

---

## 10. Fases e esforço estimado

Estimativas para **1 dev familiarizado** com o repo; incluem testes básicos, não deploy prod.

| Fase | Entregável | Esforço |
|------|------------|---------|
| **F0 — Design** | Aprovar MVP, respostas §8, registrar cog no `COG_CATALOG` | 0,5–1 dia |
| **F1 — Vínculo OAuth** | Tabela/link, callback web, API `/portal/discord/me`, botão Vincular | 2–3 dias |
| **F2 — Painel MVP** | Embed + 5 botões, Minha conta + Status + Loja link | 1–2 dias |
| **F3 — Auto-kick** | API self-kick, ListPlayers multi-mapa, cooldown, audit log | 2–3 dias |
| **F4 — TEK** | Campos `.env`, seção painel oBobonic, publicar painel | 1 dia |
| **F5 — Extras** | Ticket rápido, enquete, mercado notif., regulamento gate | 2–4 dias |
| **F6 — Hardening** | Rate limits, testes integração, docs operador | 1–2 dias |

**Total MVP (F0–F4):** ~**7–10 dias**.  
**Portal completo (F0–F6):** ~**10–15 dias**.

### 10.1 Dependências

```
F1 (OAuth) ──► F2 (painel personalizado)
F1 ──► F3 (auto-kick)
TEK sync RCON (existente) ──► F3
F2 ──► F5 (extras)
```

### 10.2 Critérios de aceite MVP

- [ ] Jogador vincula Discord↔Steam sem digitar IDs manualmente.
- [ ] **Minha conta** mostra Âmbares e licenças Alfa/Beta/Gamma/Nuvem (sem VIP).
- [ ] **Status** lista mapas com online/offline coerente com TEK.
- [ ] **Loja** abre URL correta do cluster.
- [ ] **Desbloquear** kicka apenas o Steam vinculado, com cooldown e log.
- [ ] Cog desligável no painel TEK sem quebrar tickets/XP existentes.

---

## 11. Referências de código

| Arquivo | Relevância |
|---------|------------|
| `src/obobonic_bot.py` | Cogs, env ARK_MAP, health RCON |
| `src/pages/obobonic_panel.py` | UI TEK bot |
| `plugin/arkshop_web/app.py` | Steam auth, player APIs, home pública |
| `plugin/arkshop_web/ticket_routes.py` | Discord link manual + stub OAuth |
| `plugin/arkshop_web/cross_chat_discord.py` | Bot fino existente (não confundir) |
| `plugin/arkshop_web/server_connect.py` | URLs Steam connect |
| `plugin/CustomShop/src/Commands.cpp` | Comandos jogador |
| `plugin/CustomShop/src/TimedPoints.cpp` | Recompensa por tempo online |
| `src/pages/player_kick.py` | Padrão KickPlayer RCON |

---

*Documento para discussão interna. Nenhuma linha de código deve ser implementada até aprovação do MVP e respostas às perguntas abertas.*
