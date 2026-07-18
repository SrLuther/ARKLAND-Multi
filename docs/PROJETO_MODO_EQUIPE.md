# PROJETO_MODO_EQUIPE.md — Sistema de Equipes (substituição do modelo complexo de Tribo)

| Campo | Valor |
|-------|-------|
| **Status** | 🟢 MVP+ implementado na Web Store (`teams_enabled`) — ajustes de produto depois |
| **Versão** | 0.3 (armazém + catálogo curado) |
| **Data** | 18 de julho de 2026 |
| **Escopo** | Novo sistema **web-first** de Equipes: fundação, recrutamento, banco, marcos, XP, rankings, sorteio e papéis |
| **Fora de escopo (nesta fase)** | Sincronização obrigatória com tribo in-game (TribeID), guerras, aliança entre equipes, recompensas individuais de ranking (futuro) |
| **Documentos relacionados** | [`PROJETO_AREA_TRIBO.md`](PROJETO_AREA_TRIBO.md), [`TRIBO_REPARTICAO_MERCADO.md`](TRIBO_REPARTICAO_MERCADO.md), [`REGULAMENTO_SEASON_PASS.md`](REGULAMENTO_SEASON_PASS.md), [`SORTEIO_DOACOES_SPEC.md`](SORTEIO_DOACOES_SPEC.md), [`ECONOMIA_ARKLAND.md`](ECONOMIA_ARKLAND.md) |

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

**Decisão Q1 — SUBSTITUIR:** com `teams_enabled=true`, novos payouts de mercado usam **só split de Equipe**; split de tribo é ignorado (código de tribo mantido como fallback quando a flag está off). UI da tribo mostra mensagem de migração.

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
| Um jogador em quantas equipes? | **1 equipe ativa** por jogador (simplesidade, anti-abuse) |
| Pode fundar sem estar numa? | Sim — ao fundar, torna-se OWNER |
| Pode sair? | Sim — perde papéis; banco/doações **não** são reembolsáveis |
| Kick pelo owner | Sim — **imediato** (Q4). Auto-kick por inatividade é opcional (Owner) |
| Kick pela staff | Sim — inclusive OWNER |

**Decisão Q4:** kick manual sempre imediato. Owner pode ligar `auto_kick_inactive` + `auto_kick_inactive_hours` (24–720).
Inatividade = sem `last_activity_at` atualizado por: doar Â, depositar recurso, commit ao marco, crédito XP TimedPoints, ou heartbeat `GET /api/teams/my`. Owner nunca é auto-expulsado. Job: `process_team_inactive_kicks` no retry scheduler.

**Pergunta aberta Q2:** Permitir **1** ou **N** equipes por jogador?

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

**Pergunta aberta Q5:** Fundação gratuita, custo fixo em Âmbares, ou taxa simbólica para evitar spam?

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

**Pergunta aberta Q6:** Transferência de ownership voluntária pelo Owner (passar o bastão) sem staff — sim ou não?

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
| `absorbent_polymer` | Polímero Absorvente | Sem pack na loja — blueprint ARK |
| `silica_pearls` | Pérolas de Sílica | Shop `rec_silicon` |
| `deathworm_horn` | Chifre de Deathworm | Scorched Earth |
| `organic_polymer` | Polímero Orgânico | Shop `rec_organicpolymer` |
| `ammonite_bile` | Bílis de Amonite | Apex / craft |
| `element_dust` | Poeira de Elemento | Extinction |

Depósitos (`/marco` e API) **só** aceitam estas keys. Qualquer outra key é rejeitada.

### 5.3 Fluxo: depósito → armazém → commit → marco

```
/marco (qualquer dos 10) ──► ARMAZÉM da equipe
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
| Depositar recurso | Qualquer membro ACTIVE via `/marco` / API | Credita **armazém** (`resources`) — **não** conta sozinho como progresso do marco |
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

### 5.5 Comando `/marco` (plugin)

Novo fluxo in-game (CustomShop / bridge) — **ainda não implementado em C++**; API web pronta:

1. Jogador tem a equipe ACTIVE na web.
2. Digita `/marco` (ou `/marco <recurso>`) perto de inventário / dropbox definido.
3. Plugin valida: membro ACTIVE + recurso ∈ catálogo dos 10 (sempre — independente do marco atual).
4. Consome itens do inventário → crédito no **armazém** da equipe (API `POST /api/teams/bank/deposit-resource` com `api_key` + idempotência).
5. Feedback in-game + log no painel (“João depositou 200 Pérola Negra no armazém”).

**Importante:** `/marco` **não** escreve direto no progresso do marco. O Owner/Tesoureiro aplica stock do armazém ao marco na web.

### 5.6 Painel web do banco / marco

- Saldos: Âmbares + **armazém** (cada um dos 10, qty > 0) + **aplicado ao marco** (committed).
- Histórico: doações Â, depósitos `/marco`, commits ao marco, gastos de conclusão.
- Progresso do marco: barras = committed vs required (não o stock bruto do armazém).
- Botão **Doar Âmbares**; botão **Aplicar ao marco** (Owner/Tesoureiro).

### 5.7 Propriedade dos depósitos

| Tema | Proposta |
|------|----------|
| Reembolso ao sair/kick | **Não** |
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

**Regra:** só existe **um** marco ACTIVE por vez no catálogo global (todas as equipes avançam na mesma “trilha”), **ou** cada equipe tem seu próprio cursor na trilha (recomendado).

| Modelo | Prós | Contras |
|--------|------|---------|
| **Trilha global** | Staff equilibrada; ranking justo | Equipes rápidas esperam liberação |
| **Cursor por equipe** | Cada uma avança no seu ritmo na sequência publicada | Staff precisa publicar N marcos à frente |

**Recomendação:** **cursor por equipe** numa trilha ordenada publicada pela staff (marcos 1..K disponíveis; equipe no índice `i` só vê/trabalha o marco `i+1`).

### 6.4 Conclusão de um marco

Quando **todos** os requisitos (recursos **committed** + Âmbares + XP) estão satisfeitos:

1. Sistema marca marco COMPLETED para aquela equipe.
2. Consome as quantidades exigidas de `committed` (excesso committed volta ao armazém) e os Â do banco.
3. Incrementa `milestone_index`.
4. Mantém XP lifetime (threshold do próximo marco = soma incremental — Q3).
5. Desbloqueia o próximo da trilha (se já publicado); senão, equipe fica em “aguardando staff”.
6. Evento no ranking + log público opcional.

### 6.5 Bônus de Âmbar por nível da equipe

Pedido do produto: *“ganho de âmbar adicional de acordo com o nível da equipe”*.

**Proposta de progressão inteligente:**

| Marco concluído | Bônus TimedPoints (sugestão) | Notas |
|-----------------|------------------------------|-------|
| 0 | +0% | Base |
| 1 | +2% | Teto baixo no início |
| 2 | +4% | |
| 3 | +6% | |
| … | +2 p.p. por marco | Soft cap (ex.: máx +20% no marco 10) |

- Bônus aplica-se **só a membros ACTIVE** da equipe no momento do tick.
- Empilha (ou não) com licença — **Q7**.
- Valores % e soft cap: **staff-config**.

Alternativa mais “inteligente” (curva, não linear):

```
bonus_pct = min(soft_cap, round(a * log2(1 + milestone_index)))
```

Ex.: `a=4`, soft_cap=20 → crescimento rápido no início, desacelera depois.

**Pergunta aberta Q7:** Bônus acumula com licença TimedPoints? Só um dos dois? Multiplicativo ou aditivo?

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

- Definido pela staff na **mesma UI dos marcos**.
- Pode ser:
  - **Global fixo** (ex.: máx 10 para todas), ou
  - **Por marco** (ex.: Marco 1 → 6; Marco 3 → 8; Marco 5 → 10).

**Recomendação:** base global + opcional `max_members_unlock` por marco concluído.

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

**Pergunta aberta Q8:** Migrar automaticamente quem tinha split de tribo ACTIVE para a nova equipe, ou reset limpo?

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
| R4 | Saída/kick: números daquele membro **permanecem** na equipe **ou** são removidos? → ver Q9 |
| R5 | Se a equipe for contemplada (um dos números da equipe sai): prêmio **só em Âmbares** |
| R6 | Itens de catálogo no sorteio: valor integral convertido em Â + somado ao pote da equipe contemplada |
| R7 | Total Â do prêmio da equipe ÷ número de membros ACTIVE no momento do draw → crédito igual |
| R8 | Participação individual do jogador (número fixo / compra) **continua existindo** em paralelo |

### 10.2 Conversão de catálogo → Â

Fórmula proposta:

```
amber_from_catalog = sum(catalog_amber_price(item) for item in campaign.extra_prizes)
team_prize_pool    = amber_share_of_draw + amber_from_catalog
per_member         = floor(team_prize_pool / active_members_at_draw)
remainder          = team_prize_pool % active_members_at_draw  → Owner ou ARKBANK (Q10)
```

### 10.3 Perguntas abertas

| ID | Pergunta |
|----|----------|
| Q9 | Kick/saída após confirmação: números ficam na equipe ou são queimados? |
| Q10 | Resto da divisão inteira: Owner, banco da equipe, ou burn? |
| Q11 | Membro pode estar na equipe **e** ter números individuais na mesma campanha? (Recomendação: **sim**) |
| Q12 | Limite de números da equipe vs grade 100–999 — risco de esgotar pool? |

---

## 11. Papéis especiais — sugestões

O Owner atribui papéis na UI da equipe. Um membro pode ter **0..N** papéis (ou 1 slot — Q13).

### 11.1 Catálogo sugerido

| Papel | Nome sugerido | O que faz | Não faz |
|-------|---------------|-----------|---------|
| **OWNER** | Proprietário | Tudo: kick, convites, papéis, split, sorteio, modo do banco, renomear | — |
| **BRAÇO-DIREITO** | Segundo em comando | Aprovar/recusar pedidos, kickar (exceto Owner), atribuir papéis abaixo dele | Não dissolve; não transfere ownership; não confirma sorteio sozinho *(ou sim — Q14)* |
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
| Confirmar sorteio | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Config split | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Kick membro | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Aprovar pedido | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Convidar | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Ver ledger banco | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ⚠️ |
| Doar Â / `/marco` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Aplicar armazém → marco | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Editar mural | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| Recrutamento público | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |

⚠️ = configurável pelo Owner (“delegar”).

**Pergunta aberta Q13:** Um papel por pessoa ou múltiplos?  
**Pergunta aberta Q14:** Guardião pode confirmar sorteio e editar split?

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
| Esgotar números do sorteio | Soft cap de membros; pool de números dedicados à equipe; Q12 |
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
| Q5 | Custo de fundação? | Grátis / Â fixo | **Grátis** |
| Q6 | Transferência voluntária de Owner? | Sim / Só staff | **Sim** (+ staff) |
| Q7 | Bônus marco × licença TimedPoints | Aditivo / Mult / Exclusivo | **Aditivo** (`teams_amber_bonus_pp` / `teams_amber_bonus_cap`) — % exposto na equipe; aplicação no TimedPoints C++ pode vir depois |
| Q8 | Migração automática do split antigo? | Sim / Reset | **Reset limpo** (sem auto-migração) |
| Q9 | Números sorteio após kick | Ficam / Queimam | **Ficam na equipe** (quando lottery v1.1 ligar) |
| Q10 | Resto da divisão do prêmio | Owner / Banco / Burn | **Banco da equipe** |
| Q11 | Números individuais + equipe | Sim / Não | **Sim** (paralelo) |
| Q12 | Estratégia anti-esgotamento da grade | Soft cap / pool separado | **Soft cap via `max_members`** |
| Q13 | Papéis: 1 ou múltiplos | 1 / N | **N** (exceto OWNER único) |
| Q14 | Guardião confirma sorteio/split? | Sim / Não | **Não** — Guardião: approve/kick/invite; sorteio+split = Owner |
| Q15 | Nomes dos papéis | Sóbrio / Flavor ARKLAND | **Flavor** (Guardião, Arauto, …) |
| Q16 | Trilha de marcos | Cursor por equipe / Global | **Cursor por equipe** na trilha staff |

---

## 18. Implementação (código) — 18/jul/2026

### Como ativar

1. Admin → **Configurações** → marcar **Ativar Modo Equipe (`teams_enabled`)**.
2. Opcional: `teams_max_members`, `teams_amber_bonus_pp`, `teams_amber_bonus_cap`.
3. Publicar marcos em **Admin → Equipes**.
4. Jogadores veem **Minha Equipe** e **Ranking Equipes** no menu.

### Módulos

| Ficheiro | Função |
|----------|--------|
| `plugin/arkshop_web/team_service.py` | Schema + regras de negócio |
| `plugin/arkshop_web/team_routes.py` | APIs player / admin / plugin |
| `plugin/arkshop_web/tests/test_team_service.py` | Testes focados |
| `arkbank_service.process_timed_outbox` | Hook XP → `add_team_timed_xp` |
| `market_listings` ativação | Q1: `teams_enabled` → só team split; senão tribe fallback |

### O que funciona (MVP+)

- Fundação / rename / convite / pedido / leave / kick / papéis / transfer ownership
- Staff: listar, kick, transfer, suspend, CRUD+publish marcos, max_members
- Banco Â (doar da carteira) + armazém (catálogo 10) + ledger + depósito via API
- Commit armazém → marco (Owner/Tesoureiro); marcos: progresso por committed; conclusão consome committed+Â; **XP lifetime não zera** (limiar cumulativo)
- XP lifetime jogador + XP equipe (TimedPoints outbox); honra = lifetime
- Rankings APIs + UI tabelas
- Split mercado da equipe (60/40 default, opt-in; **substitui** tribo quando `teams_enabled`)
- Auto-kick inatividade (Owner settings + job no retry scheduler)

### Stubs / TODO

| Item | Estado |
|------|--------|
| Sorteio coletivo (2 nº/membro, payout Â, resto→banco) | Stub `POST /api/teams/lottery/confirm` — wiring em `lottery_service` **v1.1** |
| Comando in-game `/marco` (CustomShop C++) | **Não feito** — API pronta: `POST /api/teams/bank/deposit-resource` credita **armazém** (só as 10 keys do catálogo). `/marco` aceitará **todos** os 10 itens → warehouse. Commit ao marco: `POST /api/teams/bank/commit-resource` (Owner/Tesoureiro) |
| Aplicar `%` bônus Â da equipe no tick TimedPoints do plugin | Campo calculado na web; C++ ainda não lê |
| Convite chat `/equipe.CODE` | Fase 2 |
| Mural rico / eleição pós-custódia | Futuro |

---

## 19. Próximos passos sugeridos

1. Ativar `teams_enabled` em staging e validar fluxos de fundação/banco/marco.
2. Implementar `/marco` no CustomShop: mapear inventário → 10 keys do catálogo → API de depósito no armazém.
3. Ligar sorteio coletivo (v1.1) sem quebrar números individuais.
4. Decidir quando desligar UI de split de Tribo de vez (já ignorada com `teams_enabled`).

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
4. Membros doam Â no painel; depositam recursos do catálogo com `/marco` → **armazém**.
5. Carla (Tesoureira) aplica stock do armazém ao marco (“Aplicar ao marco”).
6. Jogando nos mapas, TimedPoints sobem XP da equipe e o ranking pessoal.
7. Ao completar committed + Â + XP, Marco 1 conclui → bônus +2% Â → Marco 2 abre.
8. Ana confirma a equipe no sorteio → 6×2 = 12 números; entra Diogo depois → +2 automáticos.
9. Número da equipe sai → prêmio só em Â, dividido igualmente; kit do catálogo vira Â e entra no bolo.

---

*Fim do rascunho v0.1 — aguarda decisões do checklist §17 para virar spec aprovada.*
