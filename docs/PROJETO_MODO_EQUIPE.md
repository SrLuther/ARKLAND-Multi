# PROJETO_MODO_EQUIPE.md — Sistema de Equipes (substituição do modelo complexo de Tribo)

| Campo | Valor |
|-------|-------|
| **Status** | 🟢 Produto web: só Equipes (Tribos ocultas ao jogador) |
| **Versão** | 0.7 (`/marco` → preview → `/confirmar`; sem reembolso de depósitos) |
| **Data** | 18 de julho de 2026 |
| **Escopo** | Sistema **web-first** de Equipes: fundação, recrutamento, banco, marcos, XP, rankings, sorteio e papéis |
| **Fora de escopo (nesta fase)** | Sincronização obrigatória com tribo in-game (TribeID), guerras, aliança entre equipes, recompensas individuais de ranking (futuro) |
| **Documentos relacionados** | [`PROJETO_AREA_TRIBO.md`](PROJETO_AREA_TRIBO.md) *(legado)*, [`TRIBO_REPARTICAO_MERCADO.md`](TRIBO_REPARTICAO_MERCADO.md), [`REGULAMENTO_SEASON_PASS.md`](REGULAMENTO_SEASON_PASS.md), [`SORTEIO_DOACOES_SPEC.md`](SORTEIO_DOACOES_SPEC.md), [`ECONOMIA_ARKLAND.md`](ECONOMIA_ARKLAND.md) |

---

## 0. Resumo executivo

Substituir a lógica atual centrada em **presença in-game / TribeSync / Principal+Fob** por um sistema de **Equipe** gerido quase integralmente na Web Store.

| Antes (Área de Tribo) | Depois (Modo Equipe) |
|----------------------|----------------------|
| Identidade amarrada a `TribeID` por mapa | Identidade **global na web**, independente do mapa |
| Sync plugin → MySQL de quem está na tribo | Membros entram/saem **só pela web** (convite/pedido) |
| Dono = owner in-game (com proteções) | Dono = **fundador** da equipe (staff pode intervir) |
| Split de mercado na Principal | Split de mercado **da equipe** (opt-in) |
| Sem progressão coletiva | **Marcos + XP conjunto** (estilo SeasonLand) |
| Sem ranking de tribo | Ranking de equipes + ranking de jogadores (XP cumulativo) |
| Sorteio só individual | Equipe pode participar com **2 números por membro** |

> **Princípio:** a equipe **pode** coincidir com a tribo do jogo, mas **não precisa**. É uma organização social/econômica do portal — não um espelho do engine.

---

## 1. Visão e princípios de produto

### 1.1 Objetivo

Dar aos jogadores uma **casa social na web** onde:

1. Fundam e nomeiam uma equipe.
2. Recrutam e gerem membros com papéis.
3. Partilham ganhos do mercado (opt-in).
4. Guardam recursos e Âmbares num **banco da equipe**.
5. Evoluem juntos por **marcos** (objetivos staff-configurados) + **XP conjunto**.
6. Competem em rankings e participam do sorteio como bloco.

### 1.2 Princípios

| # | Princípio | Implicação |
|---|-----------|------------|
| P1 | **Web-first** | Fundação, convites, papéis, doações, marcos, rankings e sorteio vivem na UI web |
| P2 | **Fundador soberano** | Quem cria decide quem entra/sai e quem tem papéis (salvo intervenção staff) |
| P3 | **Staff como árbitro** | Staff define marcos, limites, e pode remover qualquer um (inclusive o fundador) |
| P4 | **Progressão cooperativa** | Marcos exigem esforço conjunto (recursos + Âmbares + XP) |
| P5 | **XP de jogador nunca reseta** | Diferente do SeasonLand (seasonal); ranking pessoal é acumulativo |
| P6 | **Economia auditável** | Banco, doações e payouts com ledger/idempotência (padrão ARKBANK/amber_ledger) |
| P7 | **Desacoplamento do TribeID** | Equipe ≠ tribo in-game; vínculo opcional/cosmético no futuro |

### 1.3 Relação com a Área de Tribo atual

| Opção | Descrição | Nota |
|-------|-----------|------|
| **A — Substituir** | Área de Tribo deixa de ser o produto social; Equipe assume split/gestão | Recomendado a médio prazo |
| **B — Coexistir** | Tribo continua só como painel de logs/presença; Equipe é a camada social/econômica | Migração suave |
| **C — Congelar Tribo** | Manter TribeSync/logs; desligar split de tribo e migrar split para Equipe | Provável caminho de implementação |

**Pergunta aberta Q1:** ~~Na v1, a Equipe **substitui** o split de tribo ou coexistem temporariamente?~~

**Decisão Q1 — SUBSTITUIR:** com `teams_enabled` (padrão **ligado** se a chave estiver ausente), novos payouts de mercado usam **só split de Equipe**; split de tribo é ignorado (código de tribo mantido como fallback quando a flag está off).

**Decisão produto (18/jul/2026) — Tribos saem da web para jogadores:**
- UI jogador: **sem** “Minha Tribo”, nav de tribo ou split de tribo.
- Área social = **Minha Equipe** + **Equipes** (diretório global) + rankings.
- Admin pode manter **Tribos (legado)** para sync/logs; não é fluxo do jogador.
- Copy de split: “repartição da equipe”, não da tribo.

---

## 2. Entidades e ciclo de vida

### 2.1 Equipe

| Campo | Descrição |
|-------|-----------|
| `team_id` | ID interno |
| `name` | Nome público (único no cluster, regras de moderação) |
| `tag` *(opcional)* | Prefixo curto 2–5 chars (ex.: `[ARK]`) — **discutir** |
| `founder_steam_id` | Criador original (imutável para histórico) |
| `owner_steam_id` | Proprietário atual (pode mudar por staff / transferência) |
| `max_members` | Cap vigente (vem da config staff; ver §6) |
| `milestone_index` | Marco atual conquistado / em progresso |
| `team_xp` / `team_xp_lifetime` | XP conjunto **lifetime** (não zera ao concluir marco). `team_honor` = lifetime |
| `auto_kick_inactive` / `auto_kick_inactive_hours` | Config Owner: auto-expulsão por inatividade (Q4) |
| `bank_*` | Saldos do banco (§5) |
| `created_at` / `status` | ACTIVE / DISBANDED / SUSPENDED |

### 2.2 Membro

| Campo | Descrição |
|-------|-----------|
| `steam_id` | Jogador |
| `role` | `OWNER` + papéis especiais (§11) |
| `joined_at` | Entrada |
| `status` | ACTIVE / INVITED / PENDING / KICKED / LEFT |
| `player_xp` | XP pessoal acumulativo (global, não só da equipe) |

### 2.3 Regras de filiação

| Regra | Proposta |
|-------|----------|
| Um jogador em quantas equipes? | **1 equipe ACTIVE** por jogador (Q2) |
| Pode fundar sem estar numa? | Sim — ao fundar, torna-se OWNER |
| Pode sair? | Sim — perde papéis; banco/doações **não** são reembolsáveis |
| Kick pelo owner | Sim — **imediato** (Q4). Auto-kick por inatividade é opcional (Owner) |
| Kick pela staff | Sim — inclusive OWNER |

**Decisão Q4:** kick manual sempre imediato. Owner pode ligar `auto_kick_inactive` + `auto_kick_inactive_hours` (24–720).
Inatividade = sem `last_activity_at` atualizado por: doar Â, depositar recurso, commit ao marco, crédito XP TimedPoints, ou heartbeat `GET /api/teams/my`. Owner nunca é auto-expulsado. Job: `process_team_inactive_kicks` no retry scheduler.

**Decisão Q2 — 1 equipe ACTIVE:** um jogador só pode estar em **uma** equipe com membership ACTIVE. Após leave/disband pode fundar outra (ver Q5).

---

## 3. Fundação e nome

### 3.1 Fluxo

1. Jogador autenticado na Web Store → **Fundar equipe**.
2. Escolhe **nome** (e opcionalmente tag).
3. Confirma regulamento curto da Equipe.
4. Sistema cria equipe; jogador vira `OWNER`.
5. Equipe aparece em **Minha Equipe** + ranking (posição inicial).

### 3.2 Regras de nome

| Tema | Proposta |
|------|----------|
| Unicidade | Nome único (case-insensitive) |
| Comprimento | 3–32 caracteres |
| Conteúdo | Filtro de termos ofensivos + revisão staff |
| Mudança | Owner pode renomear com cooldown (ex.: 7 dias) ou custo em Â (discutir) |
| “É a tribo do jogo?” | Checkbox cosmético *“Esta equipe representa minha tribo in-game”* — **sem** sync automático na v1 |

### 3.3 Custo de fundação

**Decisão Q5:**
| Situação | Custo |
|----------|-------|
| **1ª fundação** de sempre (`founder_steam_id` nunca usado) | **Grátis** |
| Fundar de novo após leave/disband (ou qualquer create com histórico de fundação) | **2500 Âmbares** |

Regra prática: se `COUNT(teams WHERE founder_steam_id = jogador) >= 1` antes do create → debitar 2500. Config opcional: `teams_founding_fee` (default 2500). Com Q2=1 não podem estar em duas ao mesmo tempo.

---

## 4. Sistema de recrutamento (completo)

### 4.1 Canais

| Canal | Quem inicia | Fluxo |
|-------|-------------|-------|
| **Convite direto** | Owner / papel autorizado | Gera link/código → jogador aceita na web |
| **Pedido de entrada** | Candidato | Pedido PENDING → Owner aprova/recusa |
| **Recrutamento público** | Owner | Equipe marcada como “aberta a pedidos” no ranking / lista |
| **Convite in-game** *(fase 2)* | Chat `/equipe.CODE` | Espelha o padrão `/tribe.CODE` atual |

### 4.2 Estados do pedido

```
INVITED ──aceita──► ACTIVE
   └──recusa/expira──► CLOSED

PENDING ──aprova──► ACTIVE
   └──recusa/expira──► CLOSED
```

### 4.3 Capacidade

- Entrada só se `members_active < max_members`.
- `max_members` definido pela staff (§6); pode subir com marcos futuros (opcional).

### 4.4 Política justa (governança)

| Ator | Poder |
|------|-------|
| **Owner** | Convidar, aprovar, recusar, kickar, atribuir/remover papéis, config de split, confirmar sorteio, escolher modo do banco |
| **Staff** | Remover qualquer membro; remover/substituir Owner; suspender equipe; forçar transferência de ownership |
| **Equipe (após staff remover Owner)** | Membros ACTIVE votam ou Owner interino (staff) designa até a equipe eleger o novo Owner |

**Fluxo quando staff remove o fundador/owner:**

1. Staff remove `owner_steam_id` da equipe (ou marca SUSPENDED temporário).
2. Staff assume **custódia** (não joga como membro; painel admin).
3. Equipe tem prazo (ex.: 72h) para indicar novo Owner (voto simples ou consenso no painel).
4. Staff confirma transferência → novo `owner_steam_id`.
5. Se ninguém assume → equipe DISBANDED ou fica sem recrutamento até resolução.

**Decisão Q6 — Sim:** Owner pode transferir ownership voluntariamente (passar o bastão) sem staff. Staff também pode forçar transferência.

---

## 5. Banco da equipe e armazém

### 5.1 O que guarda

| Tipo | Origem | Uso típico |
|------|--------|------------|
| **Âmbares** | Doação no painel web (débito da carteira do jogador) | Requisitos de marco (Â), split futuro |
| **Armazém (recursos raros)** | Envio in-game via `/marco` (e API plugin) | Stock da equipe; Owner/Tesoureiro **aplica** ao marco |

### 5.2 Catálogo curado (~10 recursos raros)

A staff **não** digita blueprints livres. Existe um catálogo fixo de **10 recursos raros** (chaves estáveis + nomes PT). O admin escolhe um **subconjunto** e define **quantidades** por marco (ou aplica defaults do sistema).

| Key | Nome PT | Nota / shop |
|-----|---------|-------------|
| `element_ore` | Minério de Elemento | Shop `rec_elementore` |
| `black_pearl` | Pérola Negra | Shop `rec_pnegra` |
| `hard_polymer` | Polímero Duro | Shop `rec_polymer` |
| `sand` | Areia | Shop `rec_sand` |
| `substrate_absorbent` | Substrato Absorvente | Blueprint ARK (`PrimalItemResource_SubstrateAbsorbent`); alias legado `absorbent_polymer` |
| `silica_pearls` | Pérolas de Sílica | Shop `rec_silicon` |
| `deathworm_horn` | Chifre de Deathworm | Scorched Earth |
| `organic_polymer` | Polímero Orgânico | Shop `rec_organicpolymer` |
| `ammonite_bile` | Bílis de Amonite | Apex / craft |
| `element_dust` | Pó de Elemento | Extinction |

Depósitos (`/marco` e API) **só** aceitam estas keys. Qualquer outra key é rejeitada.

### 5.3 Fluxo: depósito → armazém → commit → marco

```
/marco → preview → /confirmar (qualquer dos 10) ──► ARMAZÉM da equipe
                                                          │
                                      Owner / Tesoureiro “Aplicar ao marco”
                                                          │
                                                          ▼
                                               Progresso do marco (committed)
                                                          │
                                               (Â doados + XP TimedPoints)
                                                          │
                                                          ▼
                                                    Concluir marco
```

| Passo | Quem | Efeito |
|-------|------|--------|
| Depositar recurso | Qualquer membro ACTIVE via `/marco` → `/confirmar` / API | Credita **armazém** (`resources`) — **não** conta sozinho como progresso do marco; depósitos **sem reembolso** |
| Doar Âmbares | Qualquer membro ACTIVE (web) | Credita `amber_balance` (igual hoje) |
| Aplicar ao marco (commit) | Owner ou Tesoureiro (Guardião do Cofre) | Debita armazém → credita `committed` do marco atual |
| Concluir marco | Membro (quando requisitos OK) | Consome `committed` + Â; **não** zera XP (lifetime cumulativo — Q3) |

### 5.4 Modo do banco (escolha do Owner)

O Owner escolhe **como** o banco opera (config na UI):

| Modo | Comportamento | Sugestão |
|------|---------------|----------|
| **Cofre fechado** | Só Owner (e Tesoureiro) aplicam ao marco / veem ledger completo; todos doam | Default seguro |
| **Cofre aberto a papéis** | Papéis autorizados doam e veem saldo; commit restrito | Recomendado |
| **Transparência total** | Todos os membros veem saldos e histórico | Bom para confiança |

**Saque de Âmbares para carteira pessoal:** por padrão **desligado** (anti-abuse). Só Staff ou regra futura com quorum.

### 5.5 Comando `/marco` → `/confirmar` (plugin)

Fluxo in-game (CustomShop). API web: `POST /api/teams/bank/deposit-resource` + `GET /api/teams/plugin/membership/<steam_id>`. Implementado em `ShopTeams` (`/marco` registado; ramo em `CmdConfirmar`).

**Decisão de produto (travada):** `/marco` **não** deposita de imediato. Mostra preview, avisa que **não há reembolso**, e só após `/confirmar` (dentro do TTL) consome inventário e credita o armazém. Objetivo: evitar envios acidentais.

#### 5.5.1 Fluxo passo a passo

```
/marco
  │
  ├─ Sem equipe ACTIVE ──► "[-] Não pertences a nenhuma equipe."
  ├─ Sem recursos do catálogo no inventário ──► "Sem recursos válidos necessários para sua equipe"
  │
  ▼
Scaneia inventário (só as 10 keys) → guarda PendingMarco (steam_id, lista qty+key, expires)
  │
  ▼
Mensagem de PREVIEW (pendente — ainda não consumiu nada)
  │
  ├─ Jogador ignora / TTL passa ──► pending limpo; itens intactos
  │
  ▼
/confirmar (kind=marco, dentro do TTL)
  │
  ├─ Sem pending ──► "[-] Nenhum envio /marco pendente."
  ├─ Expirado ──► "[-] O envio expirou. Usa /marco de novo."
  ├─ Inventário já não bate com o preview ──► cancela; pede /marco de novo
  ├─ API falha após consumo ──► "[-] Falha ao creditar o armazém. Tenta de novo."
  │                              (itens já removidos → recovery staff / ledger; ver §5.5.5)
  │
  ▼
Consome stacks → POST deposit-resource (por key, com idempotency_key) → mensagem de sucesso
```

| Passo | Quem / o quê | Efeito |
|-------|--------------|--------|
| 1. `/marco` | Qualquer membro ACTIVE | Scan inventário ∩ catálogo; **não** remove itens; cria pending |
| 2. Preview | Plugin → chat | Lista + aviso sem reembolso + pedido de `/confirmar` |
| 3. `/confirmar` | Mesmo steam_id, TTL ativo | Revalida → consome → API armazém |
| 4. Ledger web | `DEPOSIT_RESOURCE` | Histórico no painel (“João depositou N Pérola Negra no armazém”) |

**Importante:**
- `/marco` **não** escreve no progresso do marco. Só alimenta o **armazém**. Owner/Tesoureiro aplica stock ao marco na web (`commit-resource`).
- Uso do armazém permanece **exclusivo para marcos** nesta fase (sem saque de recursos para inventário pessoal).
- Argumento opcional `/marco <recurso>`: **fora do MVP** — v1 envia **todos** os recursos do catálogo encontrados no inventário.

#### 5.5.2 Timeout e estado pendente

| Campo | Valor |
|-------|-------|
| **TTL default** | **60 segundos** (`steady_clock` no plugin, por `steam_id`) |
| **Pending kind** | `marco` (ver coexistência com `/confirmar` abaixo) |
| **Payload** | Lista `{ resource_key, label_pt, amount }` + `expires` + opcional snapshot de stacks |
| **Novo `/marco`** | Substitui pending anterior do mesmo jogador (mesmo kind) |
| **Expiração** | Silenciosa até o jogador digitar `/confirmar` (aí mensagem de expirado) |

#### 5.5.3 Mensagens de chat (travadas)

Prefixo de sucesso/preview da equipe: `[+Equipe]`. Erros com `[-]`.

**Preview** (depois de `/marco`, antes de confirmar) — deixa claro que ainda é pendente (“prestes a”) e que **não há reembolso**:

```
[+Equipe] Você está prestes a alimentar o armazém com:
• 120 Pérola Negra
• 45 Minério de Elemento
Atenção: não há reembolso de depósitos de recursos.
Digite /confirmar para enviar (expira em 60s).
```

**Sucesso** (depois de `/confirmar` OK):

```
[+Equipe] Você alimentou o armazém de sua equipe com:
• 120 Pérola Negra
• 45 Minério de Elemento
```

**Sem recursos válidos:**

```
Sem recursos válidos necessários para sua equipe
```

| Situação | Mensagem |
|----------|----------|
| Sem equipe ACTIVE | `[-] Não pertences a nenhuma equipe.` |
| API de crédito falhou | `[-] Falha ao creditar o armazém. Tenta de novo.` |
| `/confirmar` sem pending `/marco` | `[-] Nenhum envio /marco pendente.` |
| Pending expirado | `[-] O envio expirou. Usa /marco de novo.` |

#### 5.5.4 Coexistência de `/confirmar` (mercado / engramas / notas / marco)

`/confirmar` **já existe** no CustomShop — um único `AddChatCommand("/confirmar", …)` em `ShopMarket::CmdConfirmar`, que despacha por pending por `steam_id`:

| Prioridade atual (C++) | Origem | Pending |
|------------------------|--------|---------|
| 1 | `/engramas` | `Engrams::HasPendingUnlock` |
| 2 | `/notas` | `Notes::HasPendingUnlock` |
| 3 *(novo)* | `/marco` | `Teams::HasPendingDeposit` (kind `marco`) |
| 4 | `/enviar` (Comércio) | `g_pending` market upload |

**Estratégia (obrigatória):**
1. **Um pending “ativo” por kind e por steam_id** — maps separados (como Engrams/Notes vs Market hoje).
2. **Despacho por prioridade** em `CmdConfirmar`: se houver pending `marco` válido, tratar marco e **return** (não cair no fluxo de mercado).
3. Se o jogador tiver pending de mercado **e** de marco ao mesmo tempo (raro): a ordem da tabela decide; ao criar pending `marco`, **não** apagar pending de mercado (e vice-versa). O preview de cada fluxo já diz o contexto (“Comercio” vs “armazém”).
4. Mensagens de “nenhum pendente” devem ser **específicas do kind** quando o despacho chega ao ramo errado — ex.: ramo marco → `Nenhum envio /marco pendente.`; ramo mercado continua `Nenhum envio pendente. Use /enviar primeiro.`
5. Stub de desenho: `plugin/CustomShop/src/ShopTeams.h` + `ShopTeams.cpp`.

#### 5.5.5 API e idempotência

- Endpoint: `POST /api/teams/bank/deposit-resource` (`api_key`, body: `steam_id`, `resource_key`, `amount`, `idempotency_key`, `note`).
- Um POST **por** `resource_key` na lista confirmada.
- `idempotency_key` sugerida: `marco:{steam_id}:{map}:{unix_ts}:{resource_key}` (ou UUID por sessão de pending).
- Ordem no confirm: **revalidar inventário → consumir stacks → POST(s)**. Se o HTTP falhar após consumo, mensagem de falha; staff usa ledger / inventário para recovery (não há reembolso automático ao jogador — alinhado ao aviso do preview e a §5.7).

#### 5.5.6 Ficheiros

| Ficheiro | Papel |
|----------|--------|
| `plugin/CustomShop/src/ShopTeams.h` / `.cpp` | Catálogo BP↔key, scan, pending, `/marco`, confirm |
| `plugin/CustomShop/src/ShopMarket.cpp` | Extender `CmdConfirmar` com ramo `Teams::HasPendingDeposit` |
| `plugin/arkshop_web/team_routes.py` | API já existente |
| `plugin/arkshop_web/team_service.py` | `deposit_resource` → armazém (catálogo) |

### 5.6 Painel web do banco / marco

- Saldos: Âmbares + **armazém** (cada um dos 10, qty > 0) + **aplicado ao marco** (committed).
- Histórico: doações Â, depósitos `/marco`, commits ao marco, gastos de conclusão.
- Progresso do marco: barras = committed vs required (não o stock bruto do armazém).
- Botão **Doar Âmbares**; botão **Aplicar ao marco** (Owner/Tesoureiro).

### 5.7 Propriedade dos depósitos

| Tema | Proposta |
|------|----------|
| Reembolso ao sair/kick | **Não** |
| Reembolso de depósito `/marco` | **Não** — aviso explícito no preview antes de `/confirmar` |
| Dissolução da equipe | Saldo de Â → ARKBANK ou burn; recursos do armazém → perdidos / staff decide |
| Abuse (alt depositando) | Cap diário por steam_id; staff audit; só catálogo fixo |

---

## 6. Marcos e progressão da equipe

### 6.1 Conceito

Um **Marco** é um objetivo coletivo configurado pela staff. Não há limite de quantidade: a staff libera o próximo quando quiser.

Cada marco exige **duas frentes** (ambas obrigatórias para “construir” / concluir):

1. **Contribuição material** — recursos do catálogo **já aplicados (committed)** ao marco + Âmbares no banco.
2. **Progresso de XP conjunto** — igual à lógica SeasonLand: cada ganho de Âmbar in-game (TimedPoints) também gera XP para a equipe (e para o jogador — §9).

O armazém é só o “estoque”; o marco só conta o que o Owner/Tesoureiro **aplicou**.

### 6.2 Exemplo ilustrativo (não normativo)

| Marco | Recursos (catálogo) | Âmbares | XP conjunto alvo |
|-------|---------------------|---------|------------------|
| 1 | 500 Minério de Elemento + 200 Pérola Negra | 5.000 Â | 2.500 XP |
| 2 | 300 Polímero Duro + 1.000 Areia + 100 Chifre de Deathworm | 12.000 Â | 6.000 XP |
| 3 | … (subset do catálogo + qty) | … | … |

Quantidades: staff na admin, ou **defaults do sistema** por recurso ao montar o marco.

### 6.3 Interface staff (única tela de config)

Na admin, para o **próximo marco a liberar / em edição**:

| Campo | Descrição |
|-------|-----------|
| Índice do marco | `N` (1, 2, 3… sem teto) |
| Título / descrição | Texto jogador-facing |
| Requisitos de recurso | Subset do catálogo: `{ key, quantity }` — **sem** freeform de blueprint; multi-recurso permitido |
| Defaults | Botão opcional “sugerir qty” a partir de defaults do sistema |
| Âmbares necessários | Inteiro ≥ 0 |
| XP conjunto necessário | Inteiro ≥ 0 |
| `max_members` vigente a partir deste marco | Opcional: subir cap ao concluir |
| Estado | DRAFT / ACTIVE / COMPLETED / RETIRED |
| Liberar marco | Botão: torna ACTIVE quando a staff quiser |

Catálogo exposto em `GET /api/admin/teams/warehouse-catalog` (e em meta/status).

**Decisão Q16 — cursor por equipe:** trilha global publicada pela staff; cada equipe avança no seu `milestone_index` (não sincronizado com outras).

| Modelo | Prós | Contras |
|--------|------|---------|
| **Trilha global** | Staff equilibrada; ranking justo | Equipes rápidas esperam liberação |
| **Cursor por equipe** | Cada uma avança no seu ritmo na sequência publicada | Staff precisa publicar N marcos à frente |

**Implementado:** cursor por equipe na trilha staff (marcos 1..K; equipe no índice `i` trabalha o marco `i+1` via `get_current_milestone_for_team`).

### 6.4 Conclusão de um marco

Quando **todos** os requisitos (recursos **committed** + Âmbares + XP) estão satisfeitos:

1. Sistema marca marco COMPLETED para aquela equipe.
2. Consome as quantidades exigidas de `committed` (excesso committed volta ao armazém) e os Â do banco.
3. Incrementa `milestone_index`.
4. Mantém XP lifetime (threshold do próximo marco = soma incremental — Q3).
5. Desbloqueia o próximo da trilha (se já publicado); senão, equipe fica em “aguardando staff”.
6. Evento no ranking + log público opcional.

### 6.5 Bônus de Âmbar por marcos (TimedPoints)

Pedido do produto: *“ganho de âmbar adicional de acordo com o nível da equipe”*.

**Clarificação Q7:** o bônus **não** é um percentual solto automático genérico. É um **benefício desbloqueado / avançado pela trilha de marcos** da equipe (cursor por equipe, Q16).

| Conceito | Regra |
|----------|-------|
| Origem | Cada marco concluído pode conceder `amber_bonus_pp` (pontos percentuais) definido pela staff no editor do marco |
| Acumulação | Soma dos `amber_bonus_pp` dos marcos 1..`milestone_index` (já concluídos) |
| Default por marco | Se o campo do marco estiver vazio, usa `teams_amber_bonus_pp` (default **2**) |
| Soft cap | `teams_amber_bonus_cap` (default **20**) aplica-se ao total acumulado |
| Modo × licença | **ADITIVO** com bônus da licença TimedPoints (não exclusivo, não multiplicativo) |
| Quem recebe | Só membros **ACTIVE** no momento do tick |
| Exposição web | `amber_bonus_pct` / `amber_bonus_mode=additive` — C++ TimedPoints pode aplicar depois |

**Exemplo:** Marco 1 = +2 pp, Marco 2 = +3 pp, Marco 3 = +2 pp → após concluir 3 marcos: +7% (se cap ≥ 7).

### 6.6 XP conjunto (espelho SeasonLand)

| Tema | Proposta |
|------|----------|
| Fonte | Mesmo pipeline TimedPoints → outbox → crédito web |
| Conversão | `1 Â creditado = 1 XP` (igual SeasonLand), mas destino = `team_xp` + `player_xp` |
| Escopo multi-mapa | Soma de todos os mapas do cluster |
| Idle / offline | Sem XP (só ticks online) |
| Alts | Mesmas regras anti-abuse do SeasonLand / TimedPoints |

Diferença vs SeasonLand:

| SeasonLand | Equipe |
|------------|--------|
| XP reseta por season | XP de **jogador** não reseta |
| Pass Free/Premium | Sem pass — só progresso de marco |
| Meta coletiva = cofre ARKBANK | Meta = requisitos do marco |

**Decisão Q3 — lifetime cumulativo:** ao concluir um marco, o XP da equipe **não zera**.
`xp_required` no admin é **incremental**; o limiar do marco N = soma dos `xp_required` dos marcos 1..N.
Ex.: Marco 1 = 2500 → completa com `team_xp_lifetime >= 2500`; Marco 2 = +6000 → completa com lifetime >= 8500.
**Honra da equipe** (`team_honor`) = `team_xp_lifetime`. Ranking: `milestone_index` DESC, depois lifetime DESC.

---

## 7. Capacidade máxima de membros

- **Base produto:** `teams_max_members` = **5** (default em settings + `DEFAULT_MAX_MEMBERS`).
- Pode subir com marcos via `max_members_unlock` ao concluir (só aumenta se o valor for maior que o cap atual).
- Staff também pode forçar `max_members` por equipe no admin.
- Diretório global: `accepting_members` / `recruiting_open` = `recruitment_open` **e** `member_count < max_members`.

**Recomendação:** base global 5 + opcional `max_members_unlock` por marco concluído.

---

## 8. Ganhos partilhados do mercado

Reaproveitar o espírito de [`TRIBO_REPARTICAO_MERCADO.md`](TRIBO_REPARTICAO_MERCADO.md), migrado para Equipe:

| Tema | Proposta v1 Equipe |
|------|--------------------|
| Escopo | Equipe global (não por mapa) |
| Opt-in | Por jogador (como hoje) |
| Default | 60% vendedor / 40% pool |
| Mínimo de venda | 1.000 Â |
| Quem configura % | Owner (com floor relativo + gap) |
| Fobs / Principal | **Irrelevante** — não há Principal |
| Encomendas | Fora (igual hoje) |

**Decisão Q8 — Reset limpo:** sem migração automática de quem tinha split de tribo ACTIVE. Owners criam equipe e convidam o roster manualmente (já era o caminho da §14).

---

## 9. Rankings

### 9.1 Ranking de equipes

**Chave de ordenação (proposta):**

1. `milestone_index` (desc)
2. `team_xp_lifetime` / honra (desc) — Q3 lifetime
3. `created_at` (asc) como tie-break estável

UI pública: `#/equipes` ou secção no portal — top N, posição da minha equipe, filtro por nome.

### 9.2 Ranking de jogadores (XP)

| Tema | Proposta |
|------|----------|
| Fonte de XP | Idêntica ao SeasonLand (TimedPoints → Â → XP) |
| Reset | **Nunca** (acumulativo) |
| Equipe | XP conta mesmo sem equipe; com equipe também alimenta o marco |
| Recompensas | **Futuro** — doc só reserva o ranking |
| Visibilidade | Público (top) + “minha posição” |

**Nota:** SeasonLand continua seasonal para o Pass; este ranking é **paralelo e permanente**.

---

## 10. Sorteio — participação da equipe

### 10.1 Regras propostas

| # | Regra |
|---|-------|
| R1 | Owner **confirma participação da equipe** na campanha ativa (1× por campanha) |
| R2 | Cada membro ACTIVE gera **2 números aleatórios** vinculados à **equipe** (não ao jogador individual desses slots) |
| R3 | Novos membros após a confirmação: **+2 números automáticos** — **sem** reconfirmação do Owner |
| R4 | **Q9:** Kick/saída após confirmação — números **permanecem** na equipe (não são queimados nem transferidos ao jogador) |
| R5 | Se a equipe for contemplada (um dos números da equipe sai): prêmio **só em Âmbares** |
| R6 | Itens de catálogo no sorteio: valor integral convertido em Â + somado ao pote da equipe contemplada |
| R7 | Total Â do prêmio da equipe ÷ número de membros ACTIVE no momento do draw → crédito igual |
| R8 | **Q11:** Participação individual (número fixo / compra) **e** números da equipe **permitidos** na mesma campanha |
| R9 | **Q12:** Anti-esgotamento **sempre ativo** — ver §10.3 |

### 10.2 Conversão de catálogo → Â e divisão (Q10)

```
amber_from_catalog = sum(catalog_amber_price(item) for item in campaign.extra_prizes)
team_prize_pool    = amber_share_of_draw + amber_from_catalog
per_member         = floor(team_prize_pool / active_members_at_draw)
remainder          = team_prize_pool % active_members_at_draw  → banco da equipe (Âmbares)
```

### 10.3 Anti-esgotamento da grade (Q12)

Ao atribuir números da equipe (2 por membro ACTIVE, na confirmação ou ao entrar membro pós-confirmação):

1. Tentar alocar quantos forem possíveis na grade 100–999.
2. Se não houver números livres suficientes: alocar o possível e **reembolsar o banco da equipe** `teams_lottery_shortfall_refund` Âmbares por cada número que faltou (default **5000**; constante `LOTTERY_SHORTFALL_REFUND_AMBER`).
3. Soft cap de membros (`max_members`) continua a limitar a pressão na grade, mas o reembolso é a garantia económica sempre activa.

---

## 11. Papéis especiais — sugestões

O Owner atribui papéis na UI da equipe. **Decisão Q13:** até **2 papéis especiais** (Guardião/Arauto/etc.) por membro; OWNER é separado e **não** conta no limite de 2. Owner também pode ter até 2 papéis especiais além de OWNER.

### 11.1 Catálogo sugerido

| Papel | Nome sugerido | O que faz | Não faz |
|-------|---------------|-----------|---------|
| **OWNER** | Proprietário | Tudo: kick, convites, papéis, split, sorteio, modo do banco, renomear | — |
| **BRAÇO-DIREITO** / **Guardião** | Segundo em comando | Aprovar/recusar pedidos, kickar (exceto Owner), atribuir papéis abaixo dele | Não dissolve; não transfere ownership; **não** confirma sorteio nem edita split (Q14 — só Owner) |
| **RECRUTADOR** | Recrutador | Criar convites, aprovar/recusar pedidos | Não kicka veteranos; não mexe no banco |
| **TESOUREIRO** | Tesoureiro | Vê ledger completo; opcionalmente move Â do banco → requisitos de marco (commit) | Não saca para si; não kicka |
| **MESTRE DE MARCO** | Mestre de Marco | Destaca requisitos; pode marcar “foco da semana”; vê depósitos por recurso | Não altera config staff |
| **DIPLOMATA** | Diplomata | Mensagem pública da equipe / recrutamento aberto on-off | Sem poder econômico |
| **CRONISTA** | Cronista | Edita regulamento interno / mural da equipe | Sem poder de membros |
| **MEMBRO** | Membro | Doar Â, `/marco`, ver progresso, opt-in split | Sem gestão |

### 11.2 Nomes alternativos (flavor ARKLAND)

| Sóbrio | Flavor |
|--------|--------|
| Braço-direito | **Guardião** |
| Recrutador | **Arauto** |
| Tesoureiro | **Guardião do Cofre** |
| Mestre de Marco | **Engenheiro de Marcos** |
| Diplomata | **Embaixador** |
| Cronista | **Arquivista** |

### 11.3 Matriz de permissões (proposta)

| Ação | Owner | Guardião | Arauto | Tesoureiro | Eng. Marco | Embaixador | Arquivista | Membro |
|------|:-----:|:--------:|:------:|:----------:|:----------:|:----------:|:----------:|:------:|
| Renomear equipe | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Confirmar sorteio | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Config split | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Kick membro | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Aprovar pedido | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Convidar | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Ver ledger banco | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ⚠️ |
| Doar Â / `/marco` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Aplicar armazém → marco | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Editar mural | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| Recrutamento público | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |

**Decisão Q13:** máx. **2 papéis especiais** por membro (OWNER fora do contador).  
**Decisão Q14:** Guardião **não** confirma sorteio nem edita split — só Owner (`lottery_confirm` / `split_config`).

---

## 12. Interfaces (wireframe lógico)

### 12.1 Jogador — Minha Equipe

- Cabeçalho: nome, marco atual, XP, membros `n/max`
- Abas: **Membros** · **Banco** · **Marco** · **Split** · **Sorteio** · **Mural**
- CTA Owner: gerir papéis, convites, config

### 12.2 Público — Ranking

- Top equipes (marco + XP)
- Top jogadores (XP lifetime)
- Busca / página da equipe (roster público opcional)

### 12.3 Staff — Admin Equipes

- Trilha de marcos (CRUD requisitos, XP, Â, max_members)
- Bônus % por nível
- Lista de equipes / intervenção (kick, transfer ownership, suspend)
- Auditoria de banco e `/marco`

---

## 13. Arquitetura técnica (esboço)

### 13.1 Novos módulos web (padrão do repo)

| Módulo | Responsabilidade |
|--------|------------------|
| `team_service.py` | CRUD equipe, membros, papéis, banco lógico |
| `team_routes.py` | APIs player + admin |
| `team_milestone_service.py` | Trilha, progresso, conclusão |
| `team_lottery.py` | Confirmação, números, payout coletivo |
| Tabelas MySQL | `teams`, `team_members`, `team_bank_*`, `team_milestones`, `team_xp_events`, … |

### 13.2 Plugin

| Peça | Função |
|------|--------|
| Comando `/marco` | Depósito de recursos → API |
| Hook TimedPoints | Já alimenta outbox; estender crédito para `team_xp` + `player_xp` lifetime |
| (Opcional) `/equipe.CODE` | Convite chat fase 2 |

### 13.3 O que NÃO depende do TribeSync

Fundação, roster, banco Â, marcos, rankings, sorteio — **zero** dependência de `tribe_id`.

TribeSync pode permanecer só para **logs / painel legado**, se a opção B/C do §1.3 for escolhida.

---

## 14. Migração e convivência

| Passo | Ação |
|-------|------|
| 1 | Lançar Equipe em paralelo (feature flag `teams_enabled`) |
| 2 | Congelar novos splits de tribo; copy na UI: “Split migrou para Equipes” |
| 3 | Owner cria equipe e convida o antigo roster manualmente |
| 4 | (Opcional) ferramenta staff “importar membros da tribo Principal” 1× |
| 5 | Desligar split de tribo; manter logs se útil |

---

## 15. Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Spam de equipes | Custo de fundação / 1 equipe por jogador / nome único |
| Owner tóxico | Staff remove + custódia + eleição |
| Farm de XP com alts | Mesmas regras TimedPoints; cap de membros |
| Esgotar números do sorteio | Soft cap `max_members` + reembolso Q12 (`teams_lottery_shortfall_refund`) |
| Depósito `/marco` fraudulento | Whitelist de itens; rate limit; audit log |
| Confusão Equipe vs Tribo in-game | Copy clara na UI: “Equipe do portal ≠ tribo do ARK” |

---

## 16. Fases de entrega (sugestão)

| Fase | Entrega | Valor |
|------|---------|-------|
| **MVP** | Fundação, nome, membros, convites/pedidos, papéis básicos, staff kick/transfer | Casa social web |
| **MVP+** | Banco Â + doações web; split mercado; ranking equipes/jogadores | Economia social |
| **v1** | Marcos staff + XP conjunto + `/marco` recursos + bônus TimedPoints | Progressão cooperativa |
| **v1.1** | Sorteio coletivo (2 nº/membro) | Engajamento campanhas |
| **v2** | Convite chat, mural rico, recompensas de ranking jogador | Polish |

---

## 17. Checklist de decisões (para fechar a discussão)

| ID | Tema | Opções | Sua escolha |
|----|------|--------|-------------|
| Q1 | Split: substituir tribo ou coexistir? | A / B / C | **A — SUBSTITUIR** (`teams_enabled` ON → só split de equipe; OFF → tribe split fallback) |
| Q2 | 1 ou N equipes por jogador? | 1 / N | **1** equipe ACTIVE |
| Q3 | XP equipe ao concluir marco: zera ou lifetime? | Zera marco + lifetime / só lifetime | **Lifetime cumulativo** — não zera; `xp_required` incremental; limiar = soma 1..N; honra = lifetime |
| Q4 | Kick com cooldown? | Sim / Não | **Kick manual imediato**; auto-kick inatividade configurável pelo Owner (`auto_kick_inactive` + horas). Inatividade = sem XP/depósito/doação/commit/`GET /api/teams/my`. Owner nunca auto-kick. |
| Q5 | Custo de fundação? | Grátis / Â fixo | **1ª grátis**; depois **2500 Â** (`teams_founding_fee`; histórico via `founder_steam_id`) |
| Q6 | Transferência voluntária de Owner? | Sim / Só staff | **Sim** (+ staff) |
| Q7 | Bônus Â × licença TimedPoints | Aditivo / Mult / Exclusivo | **Aditivo** + bônus é **recompensa de marco** (`amber_bonus_pp` por marco; default `teams_amber_bonus_pp`; cap `teams_amber_bonus_cap`) |
| Q8 | Migração automática do split antigo? | Sim / Reset | **Reset limpo** (sem auto-migração) |
| Q9 | Números sorteio após kick | Ficam / Queimam | **Ficam na equipe** |
| Q10 | Resto da divisão do prêmio | Owner / Banco / Burn | **Banco da equipe** (Âmbares) |
| Q11 | Números individuais + equipe | Sim / Não | **Sim** (paralelo na mesma campanha) |
| Q12 | Estratégia anti-esgotamento da grade | Soft cap / pool / reembolso | **Sempre activo:** alocar o possível + reembolso `teams_lottery_shortfall_refund` (5000 Â/número em falta) |
| Q13 | Papéis: 1 ou múltiplos | 1 / N / máx 2 | **Máx. 2 papéis especiais** (OWNER separado, fora do limite) |
| Q14 | Guardião confirma sorteio/split? | Sim / Não | **Não** — Guardião: approve/kick/invite; sorteio+split = Owner |
| Q15 | Nomes dos papéis | Sóbrio / Flavor ARKLAND | **Flavor** (Guardião, Arauto, …) |
| Q16 | Trilha de marcos | Cursor por equipe / Global | **Cursor por equipe** na trilha staff |

---

## 18. Implementação (código) — 18/jul/2026

### Como ativar

1. Por omissão o Modo Equipe está **ligado** (`teams_enabled` ausente ⇒ true). Staff pode desligar em Configurações.
2. Default `teams_max_members` = **5**. Opcional: `teams_amber_bonus_pp` (default pp por marco se o campo do marco estiver vazio), `teams_amber_bonus_cap`, `teams_founding_fee` (2500), `teams_lottery_shortfall_refund` (5000).
3. Publicar marcos em **Admin → Equipes** (com `max_members_unlock` e `amber_bonus_pp` por marco).
4. Jogadores veem **Minha Equipe**, **Equipes** (lista global) e **Ranking Equipes** no menu — sem Tribo.

### Módulos

| Ficheiro | Função |
|----------|--------|
| `plugin/arkshop_web/team_service.py` | Schema + regras de negócio |
| `plugin/arkshop_web/team_routes.py` | APIs player / admin / plugin |
| `plugin/arkshop_web/tests/test_team_service.py` | Testes focados |
| `arkbank_service.process_timed_outbox` | Hook XP → `add_team_timed_xp` |
| `market_listings` ativação | Q1: `teams_enabled` → só team split; senão tribe fallback |

### O que funciona (MVP+ / v0.4)

- Fundação (1ª grátis; 2ª+ = 2500 Â) / rename / convite / pedido / leave / kick / papéis (máx. 2 especiais) / transfer ownership (Owner sem staff)
- **Diretório global** `GET /api/teams/public` + UI Equipes (regulamento, n/max, aceitando, Solicitar união)
- **Minha Área** mostra painel completo da equipe (igual Minha Equipe)
- Staff: listar, kick, transfer, suspend, CRUD+publish marcos, max_members
- Banco Â + armazém + ledger; marcos com XP lifetime; honra = lifetime
- Rankings + split de mercado da equipe (substitui tribo na web)
- Auto-kick inatividade; mural/regulamento (`POST /api/teams/mural`)
- Recrutamento: toggle owner + gate `members < max`

### Stubs / TODO

| Item | Estado |
|------|--------|
| Sorteio coletivo (2 nº/membro, payout Â, resto→banco, Q9–Q12) | **Feito** — `POST /api/teams/lottery/confirm` + alocação em `lottery_service` (source `TEAM`) |
| Comando in-game `/marco` → `/confirmar` (CustomShop C++) | **Feito** — `ShopTeams` regista `/marco`; preview 60s + aviso sem reembolso; `CmdConfirmar` ramo kind `marco`; consume + `POST /api/teams/bank/deposit-resource`. Membership: `GET /api/teams/plugin/membership/<sid>`. Commit ao marco: `POST /api/teams/bank/commit-resource` (Owner/Tesoureiro) |
| Aplicar `%` bônus Â da equipe no tick TimedPoints do plugin | Campo calculado na web (`amber_bonus_pct` via marcos); C++ ainda não lê |
| Convite chat `/equipe.CODE` | Fase 2 |
| Mural rico / eleição pós-custódia | Futuro |

---

## 19. Próximos passos sugeridos

1. Ativar `teams_enabled` em staging e validar fluxos de fundação/banco/marco.
2. Validar in-game: `/marco` → preview → `/confirmar` (CustomShop) e crédito no armazém web.
3. Validar sorteio coletivo em staging (confirmação Owner, join +2, draw com resto→banco, shortfall refund).
4. Decidir quando desligar UI de split de Tribo de vez (já ignorada com `teams_enabled`).
5. *(Futuro)* Aplicar `%` bônus Â da equipe no tick TimedPoints do plugin C++ (web já expõe `amber_bonus_pct`).
---


## Apêndice A — Glossário

| Termo | Significado |
|-------|-------------|
| **Equipe** | Organização social/econômica na Web Store |
| **Owner / Proprietário** | Gestor atual da equipe |
| **Fundador** | Quem criou (histórico; pode ≠ Owner) |
| **Marco** | Objetivo coletivo staff-configurado |
| **Banco / Armazém** | Cofre de Â + stock dos 10 recursos; commit aplica stock ao marco |
| **XP conjunto** | Progresso do marco alimentado por TimedPoints |
| **XP de jogador** | Acumulativo permanente para ranking pessoal |

## Apêndice B — Exemplo de jornada

1. Ana funda **“Lobos do Norte”**.
2. Convida 5 amigos; promove Bruno a **Guardião** e Carla a **Tesoureira**.
3. Staff publicou Marco 1: 500 Minério de Elemento + 200 Pérola Negra + 5k Â + 2.5k XP (subset do catálogo).
4. Membros doam Â no painel; depositam recursos do catálogo com `/marco` → preview (sem reembolso) → `/confirmar` → **armazém**.
5. Carla (Tesoureira) aplica stock do armazém ao marco (“Aplicar ao marco”).
6. Jogando nos mapas, TimedPoints sobem XP da equipe e o ranking pessoal.
7. Ao completar committed + Â + XP, Marco 1 conclui → desbloqueia `amber_bonus_pp` daquele marco (ex. +2%) → Marco 2 abre.
8. Ana confirma a equipe no sorteio → 6×2 = 12 números; entra Diogo depois → +2 automáticos (ou reembolso Q12 se a grade esgotar).
9. Número da equipe sai → prêmio só em Â, dividido igualmente; kit do catálogo vira Â e entra no bolo; resto da divisão → banco.

---

*Spec v0.7 — `/marco` com confirmação `/confirmar` (TTL 60s, aviso sem reembolso); coexistência de pending kinds documentada. Q7–Q12 fechados na web. C++ TimedPoints ainda não aplica `amber_bonus_pct`; comando `/marco` ainda em stub.*
