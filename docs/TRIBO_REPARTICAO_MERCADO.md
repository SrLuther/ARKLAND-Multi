# §18 Repartição de ganhos do mercado (tribe revenue share)

> **Tipo:** Especificação + implementação MVP.  
> **Relacionado a:** [`PROJETO_AREA_TRIBO.md`](PROJETO_AREA_TRIBO.md) §17 (Tribo Principal + Fobs), [`ECONOMIA_ARKLAND.md`](ECONOMIA_ARKLAND.md) (mercado P2P).  
> **Última atualização:** 2026-07-12  

---

## 18.0 Decisões finais (admin + refinamentos 2026-07-12)

### Regras de produto (fonte de verdade do utilizador)

| # | Tema | Decisão |
|---|------|---------|
| **U1** | **Plugin → DB** | CustomShop (TribeSync) identifica Proprietário e mapas com tribo; grava **nome, mapa, dono, membros** em MySQL (`tribe_presences`, `tribe_members`, `tribe_map_links`). A web **lê a DB** — sync não depende de RCON (RCON só atalho). |
| **U2** | **Dono não é sobrescrito** | Se a web **já tiver** alguém como proprietário da tribo `(server_id, tribe_id)`, quem sincronizar noutro mapa / como membro (mesmo como owner in-game) é tratado como **membro** — não rouba `tribe_map_links`. |
| **U3** | **Opt-in por jogador** | Cada jogador, isolado, **aceita ou não** o ganho partilhado. **Não aceitar / sair** → recebe **100%** do que comercializa. **Aceitar** → dinos que enviar (≥ R8) seguem a repartição. |
| **U4** | **Default 60/40** | **60%** para quem envia; **40%** dividido **por igual** entre os **demais participantes do pool** (quem optou-in). |
| **U5** | **Maior parcela = quem envia** | Sempre. O proprietário pode **redefinir as %** (validação: soma 100%, remetente estritamente maior + gap ≥ 10 p.p.). |
| **U6** | **Pool = opt-in** | «Demais» = outros no pool partilhado (não todos os membros da tribo automaticamente). |

### Decisões administrativas anteriores (2026-07-10) — mantidas

| # | Tema | Decisão registrada |
|---|------|--------------------|
| D1 | **Floor mínimo do vendedor** | Regra relativa — percentual **estritamente maior** + **gap mínimo de 10 p.p.** (sem piso fixo absoluto; o *default* de produto é 60/40). |
| D2 | **Cooldown de 48h** | Só em **alterações** de taxas/membros na config. Não aplica a opt-out nem disable. |
| D3 | **Opt-out e reentrada** | Pode retornar: **45h** após opt-out + **aprovação do owner**. |
| D4 | **Visibilidade** | Só integrantes da tribo. |
| D5 | **Limite** | Máx. **10** membros na config. |
| D6 | **Fobs** | Sem split próprio — só tribo principal. |
| D7 | **Mínimo de venda** | **1.000 Âmbares**. |
| D8 | **Discord** | Fase 2+. |
| D9 | **Encomendas** | Sem vínculo. |
| D10 | **Cross-cluster** | Split só na principal; fobs sem repartição. |

---

## 18.0.1 O que o plugin grava vs o que a web mostra

| Camada | Dados |
|--------|--------|
| **Plugin (TribeSync → MySQL)** | `steam_id`, `server_id`, `tribe_id`, `tribe_name`, `is_owner` / rank, lista de membros; pedidos `tribe_sync_requests`; auto-link do dono em `tribe_map_links` **só se** ainda não houver outro dono web para aquela tribo/mapa. |
| **Web — Minha Tribo** | Mapas do dono, membros por mapa, regulamento, **Divisão de Ganhos** (estado do split, % template, **Aceitar / Sair** do pool, efeito no payout). |
| **Web — Mercado** | Ao **ativar** anúncio: se o vendedor está no pool e split ACTIVE e preço ≥ 1000 → congela `split_snapshot`; na compra distribui Âmbares. Sem opt-in → crédito 100% ao vendedor. |

---

## 18.0 Decisões administrativas registradas (2026-07-10)

> Histórico: as questões do §18.12 foram respondidas em 10/07/2026. Em 12/07/2026 o utilizador fechou U1–U6 (opt-in por jogador, default 60/40, proteção de dono). As seções abaixo foram alinhadas.

| # | Tema | Decisão registrada |
|---|------|--------------------|
| D1 | **Floor mínimo do vendedor** | Regra relativa — o vendedor (lister) deve ter percentual **estritamente maior** que qualquer outro membro individual, com **gap mínimo de 10 pontos percentuais** acima do próximo maior. Não há piso fixo em % absoluta. Ver R1 para algoritmo de validação. |
| D2 | **Cooldown de 48h** | Aplica-se somente a **alterações** na tabela/configuração do split (mudança de percentuais ou de membros). **Não** se aplica a opt-out individual nem a desativação do split. |
| D3 | **Opt-out e reentrada** | Um membro que fez opt-out **pode** retornar ao split. Condições obrigatórias: aguardar **45 horas** após o opt-out e obter **aprovação explícita do owner**. |
| D4 | **Visibilidade pública** | Apenas **integrantes confirmados da tribo** têm acesso à configuração de split e ao regulamento. Detalhes de percentuais e divisão não são exibidos publicamente para jogadores fora da tribo. |
| D5 | **Limite de membros no split** | Máximo de **10 membros** por configuração de split (incluindo o vendedor/lister). |
| D6 | **Fobs e split** | **Não** — fob não possui configuração de split própria. Split é recurso exclusivo da **tribo principal** (mapa âncora). Membro que pertence a uma fob em determinado mapa **não pode participar de split de outra tribo no mesmo mapa**. |
| D7 | **Mínimo de venda para split** | **1.000 Âmbares** (substituindo o valor provisório de 500). Vendas abaixo deste limiar seguem fluxo integral ao vendedor. |
| D8 | **Notificação Discord** | **Adiada — Fase 2+** (baixa prioridade). Não faz parte do MVP nem da v1.1. |
| D9 | **Split + encomendas** | **Nenhum vínculo.** O sistema de encomendas (`ENCOMENDA_DINO_SPEC.md`) é ferramenta exclusiva do admin — zero integração com split de tribo. |
| D10 | **Cross-cluster** | Após o mapa principal ser definido, todas as tribos do grupo em outros mapas devem ser **fobs**. Split é configurado somente na tribo principal. Fob não possui configuração de split — fob é posto avançado de suporte, sem repartição de receita própria. |

---

## 18.1 Contexto técnico — fluxo de venda P2P

Em `market_listings.py`, na ativação do anúncio congela-se `split_snapshot` se o vendedor está no pool; em `purchase_listing()`:

```
_debit_points(db, buyer_steam_id, price)
se split_snapshot: apply_split_payout(...)  # pool
senão: _credit_points(db, seller, price)     # 100%
```

O mercado P2P **não tem `server_id`** — é cross-cluster; o split resolve-se pelo `tribe_owner` / membership do vendedor.

---

## 18.2 Princípios do sistema

| # | Princípio | Detalhes |
|---|-----------|----------|
| P1 | **Vendedor sempre é o maior beneficiário** | O membro que lista/envia a criatura é considerado o mais dedicado ao breeding. O sistema garante que sua porcentagem seja **estritamente maior** que a de qualquer outro membro individual. Isso é exibido explicitamente na UI e documentado na política. |
| P2 | **Todos os valores em percentuais** | A configuração é feita em `%` inteiros. A soma **deve ser exatamente 100%**. Valores decimais não são aceitos. |
| P3 | **Transparência total** | Cada membro da tribo pode ver a configuração de split ativa, o histórico de versões e o log de auditoria de todas as vendas com split. Nenhum valor é ocultado. |
| P4 | **Recurso opt-in e desativável** | O split da tribo é configurado pelo owner (desativado por omissão). Cada **jogador** opta individualmente pelo pool. Sem opt-in pessoal → 100% nas vendas próprias. Owner pode desativar o split da tribo (cluster-wide). |
| P5 | **Opt-out individual** | Sair do pool = 100% do que comercializa; deixa de receber fatia das vendas dos outros. |
| P6 | **Não retroativo** | Snapshot fixado na **ativação** do anúncio. |

---

## 18.3 Regras automáticas (hardcoded no sistema)

### R1 — Mínimo do vendedor (regra relativa) ✅ DECIDIDO D1
O vendedor (quem lista a criatura) deve satisfazer **duas condições simultâneas**. Não existe piso fixo em percentual absoluto — a regra é inteiramente relativa à configuração escolhida:

1. Seu percentual deve ser **estritamente maior** que o de qualquer outro membro individual.
2. A diferença entre seu percentual e o do próximo membro mais alto deve ser de **no mínimo 10 pontos percentuais (p.p.)**.

Se qualquer condição falhar, o sistema bloqueia o salvamento com mensagem clara.

**Algoritmo de validação (R1):**
```
pct_vendedor = percentual atribuído ao lister
pct_outros   = percentuais de todos os demais membros ativos no split
max_outro    = max(pct_outros)

Condição 1: pct_vendedor > max_outro           → lister é o maior (estrito)
Condição 2: pct_vendedor - max_outro >= 10     → gap mínimo de 10 p.p.

Se qualquer condição falhar → BLOQUEADO
```

> **Exemplo válido:** Vendedor 40%, Membro A 30%, Membro B 30%.  
> Gap = 40 − 30 = 10 p.p. ✓ (exatamente no limite — aceito).  
>
> **Exemplo válido:** Vendedor 55%, Membro A 25%, Membro B 20%.  
> Gap = 55 − 25 = 30 p.p. ✓  
>
> **Exemplo inválido:** Vendedor 38%, Membro A 32%, Membro B 30%.  
> Gap = 38 − 32 = 6 p.p. < 10 p.p. → BLOQUEADO.  
>
> **Exemplo inválido:** Vendedor 35%, Membro A 35%, Membro B 30%.  
> Empate no topo → BLOQUEADO.

### R2 — Soma obrigatória = 100%
O sistema valida que a soma de todos os percentuais configurados seja exatamente 100% antes de salvar. Não é permitido salvar configuração com soma diferente.

### R3 — Cooldown obrigatório de 48h (somente em alterações) ✅ DECIDIDO D2
Após **alterações** na configuração do split (mudança de percentuais ou adição/remoção de membros pelo owner), o split entra em status `PENDING_COOLDOWN` por 48 horas antes de entrar em vigor. Durante o cooldown, listagens novas não podem usar o split em transição; listagens existentes com o split anterior continuam com as regras antigas.

**Escopo do cooldown:**
- ✅ Aplica-se: mudança de percentuais, adição ou remoção de membro pelo owner, reativação do split após desativação.
- ❌ Não se aplica: opt-out individual de membro (R4 — imediato), desativação total do split pelo owner (R5 — imediata).

**Justificativa:** impede alterações oportunistas feitas imediatamente antes de uma venda de alto valor. Opt-out e desativação são ações defensivas — não exigem carência.

### R4 — Recálculo proporcional no opt-out e política de reentrada ✅ DECIDIDO D2/D3
Quando um membro faz opt-out do split, sua porcentagem é redistribuída proporcionalmente entre os membros restantes (incluindo o vendedor). O recálculo ocorre **imediatamente** para futuras listagens (sem cooldown de 48h — ver R3); listagens já ativas com aquele membro incluído mantêm as regras originais (ver P6).

**Algoritmo de recálculo:**
```
percentual_liberado = percentual_do_membro_que_saiu
para cada membro_restante:
    membro_restante.pct += round(percentual_liberado * membro_restante.pct / soma_restante)
ajustar_arredondamento_para_soma_100()  # atribuir remainder ao vendedor
```

**Política de reentrada:** Um membro que fez opt-out **pode** retornar ao split, mas deve cumprir **ambas** as condições:
1. Aguardar **45 horas** a partir do timestamp do opt-out.
2. Obter **aprovação explícita do owner** da tribo no site (via botão "Aprovar reentrada").

Após a reentrada, o owner precisa redefinir os percentuais (a configuração anterior não é restaurada automaticamente). A nova configuração entra em cooldown de 48h normalmente (R3), pois trata-se de uma alteração de configuração.

### R5 — Disable total = sem split
Quando o owner desativa o split da tribo (`status = DISABLED`), todas as novas listagens voltam ao fluxo atual (100% ao vendedor). Listagens com split ativo antes da desativação seguem suas regras congeladas até expiração ou venda.

### R6 — Opt-in por jogador (não por anúncio) ✅ U3
O split aplica-se automaticamente às listagens do vendedor **se** ele está no pool (aceitou). Sem aceitar → 100% ao vendedor, mesmo com split ACTIVE na tribo. Não há checkbox por anúncio no MVP.

### R6b — Default 60/40 ✅ U4
Na ausência de taxas customizadas do owner (ou ao usar «Aplicar default 60/40»): **60%** quem envia, **40%** igual entre os outros do pool.

### R7 — Vinculação ao vendedor, não à tribo
O split é configurado **por steam_id do owner**, não por mapa. Como o mercado P2P é cross-cluster (sem `server_id`), o vendedor escolhe qual configuração de split aplicar ao criar o anúncio (caso pertença a mais de uma tribo configurada).

### R8 — Mínimo de venda para split ✅ DECIDIDO D7
O split só se aplica a vendas com preço ≥ **1.000 Âmbares**. Abaixo deste valor, o fluxo é integral ao vendedor, independentemente do split configurado.

### R9 — Membro banido ou suspenso
Se um membro do split estiver com conta suspensa no momento da venda, sua parcela **não é creditada** e é redirecionada ao vendedor, registrada no ledger com flag `suspended_redirect: true`. O admin pode redistribuir manualmente após resolução.

### R10 — Identidade do split no ledger
Cada venda com split gera entradas separadas no `amber_ledger` com `event_type` específico para cada participante, vinculadas ao mesmo `split_id` e `listing_id`. Nenhum valor é agrupado.

### R11 — Limite de membros no split ✅ DECIDIDO D5
A configuração de split pode ter no máximo **10 membros** (incluindo o vendedor/lister). Tentativas de adicionar um 11º membro são bloqueadas com mensagem clara. O valor mínimo continua sendo 2 participantes (vendedor + ao menos 1 membro).

### R12 — Visibilidade: integrantes da tribo apenas ✅ DECIDIDO D4
A configuração de split (percentuais, membros, histórico de versões) é visível exclusivamente para **integrantes confirmados da tribo** no site. Jogadores externos, visitantes e compradores não têm acesso aos detalhes de divisão. O audit log completo é acessível ao owner e ao admin ARKLAND.

### R13 — Split exclusivo da tribo principal; fobs sem split ✅ DECIDIDO D6/D10
O split de receita é configurado somente na **tribo principal** (mapa âncora do cluster group). Fobs (tribos em mapas secundários) **não possuem** configuração de split própria — fob é posto avançado de suporte, sem repartição de receita. Adicionalmente, um membro que pertença a uma fob em determinado mapa **não pode participar do split de outra tribo neste mesmo mapa**.

### R14 — Sem integração com encomendas ✅ DECIDIDO D9
O sistema de split de tribo **não tem nenhum vínculo** com o sistema de encomendas (`ENCOMENDA_DINO_SPEC.md`). Encomendas são ferramenta exclusiva do admin — transações de encomenda não geram split, não são contabilizadas no histórico de split e não afetam os percentuais configurados.

---

## 18.4 Fluxo completo

### Fluxo A — Configuração inicial do split

```
Owner acessa Minha Área → Minha Tribo → aba "Divisão de Ganhos"
  └─ Clica "Ativar divisão de ganhos"
       └─ Define até 10 membros participantes e percentuais (R11)
            └─ Sistema valida R1 (lister maior + gap ≥ 10 p.p.) e R2 (soma = 100%)
                 └─ Owner confirma → split entra em PENDING_COOLDOWN (48h — R3)
                      └─ Após 48h → status ACTIVE
                           └─ [Fase 2+] Notificação Discord para membros participantes (D8 — adiado)
```

### Fluxo B — Criação de listagem com split

```
Membro lista criatura no mercado
  └─ Se split ACTIVE existe: sistema pergunta "Aplicar divisão de ganhos neste anúncio?"
       └─ Preview exibido:
            ┌──────────────────────────────────────────────────────┐
            │ Divisão de ganhos para este anúncio                  │
            │ Venda por: 10.000 Âmbares                            │
            │                                                       │
            │ Você (vendedor / breeder)    50%  = 5.000 Âmbares    │
            │ JogadorB (membro)            30%  = 3.000 Âmbares    │
            │ JogadorC (membro)            20%  = 2.000 Âmbares    │
            │                                                       │
            │  [ Confirmar com split ]  [ Listar sem split ]        │
            └──────────────────────────────────────────────────────┘
       └─ Confirma → listing salvo com tribe_split_id + split_snapshot (JSON)
```

### Fluxo C — Venda e distribuição de pontos

```
Comprador clica "Comprar"
  └─ Sistema debita price do comprador
       └─ Lê split_snapshot do listing
            └─ Para cada membro no snapshot:
                 └─ Verifica conta ativa (R9)
                      └─ Credita parcela proporcional
                           └─ Registra no amber_ledger (event_type específico)
                                └─ Notifica cada beneficiário ("Você recebeu X Âmbares")
```

**Entradas no amber_ledger para venda de 10.000 Âmbares com split 50/30/20:**

| `steam_id` | `event_type` | `signed_delta` | `metadata_json` |
|------------|--------------|----------------|-----------------|
| buyer | `market_purchase_buyer` | −10.000 | `{listing_id, split_id}` |
| vendedor | `market_split_seller` | +5.000 | `{listing_id, split_id, pct:50, leg:"seller"}` |
| JogadorB | `market_split_member` | +3.000 | `{listing_id, split_id, pct:30, leg:"member"}` |
| JogadorC | `market_split_member` | +2.000 | `{listing_id, split_id, pct:20, leg:"member"}` |

---

## 18.5 Opt-out de membro

### Cenário: JogadorB decide não participar mais do split

**Opt-out para futuras listagens (imediato, sem cooldown):**
1. JogadorB acessa Minha Tribo → Divisão de Ganhos → "Sair do split".
2. O sistema marca `tribe_split_members.opted_out = true` para JogadorB e registra `opted_out_at`.
3. Recálculo proporcional (R4): os 30% de JogadorB são redistribuídos imediatamente → Vendedor 62%, JogadorC 38% (exemplo arredondado).
4. **Nenhum cooldown** aplica-se ao opt-out — a redistribuição é efetiva de imediato para futuras listagens (D2).
5. Listagens existentes com JogadorB incluído **não são alteradas** — o snapshot original é honrado.
6. Para reentrar no split, JogadorB deve aguardar **45 horas** a partir do `opted_out_at` e solicitar aprovação do owner (D3 / R4).

**Opt-out durante listagem ativa (mais delicado):**

| Situação | Comportamento |
|----------|---------------|
| Comprador ainda não comprou | Listing continua com snapshot original; se JogadorB não tem conta ativa no momento da compra, R9 aplica |
| Comprador comprou antes do opt-out | Nada muda — transação já concluída |
| Opt-out e membro removido da tribo | Equivalente — snapshot congela; R9 aplica no momento da compra |

---

## 18.6 UI copy PT-BR — Textos de interface

### Página "Divisão de Ganhos" (Minha Tribo)

```
──────────────────────────────────────────────────────────────────
 Divisão de Ganhos do Mercado
──────────────────────────────────────────────────────────────────
 ⭐ IMPORTANTE: Quem lista a criatura sempre recebe a maior parte.
    Isso reconhece o trabalho de breeding e cuidado com os dinos.

 Status: ● ATIVO (vigente desde 08/07/2026)

 Configuração atual:
  - Você (vendedor/breeder)     50%   ← mínimo garantido ao lister
  - JogadorB                    30%
  - JogadorC                    20%

  [ Editar configuração ]  [ Desativar divisão ]

 Próxima alteração entra em vigor após 48h de carência.
──────────────────────────────────────────────────────────────────
 Transparência: todos os membros da tribo podem ver esta tela.
 Auditoria completa disponível em "Ver histórico de divisões".
──────────────────────────────────────────────────────────────────
```

### Modal de opt-in por listagem

```
 Divisão de ganhos disponível para este anúncio
 ──────────────────────────────────────────────
 Preço do anúncio:       10.000 Âmbares
 Sua parte (breeder):     5.000 Âmbares (50%)
 JogadorB receberá:       3.000 Âmbares (30%)
 JogadorC receberá:       2.000 Âmbares (20%)

 ⚠ Ao confirmar, estes valores ficam fixados para este anúncio.
   Alterações futuras no split não afetam este anúncio.

  [ ✓ Confirmar com divisão ]    [ Listar sem divisão (100% para mim) ]
```

---

## 18.7 Auditoria — esquema do log

### Tabela `tribe_split_audit`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | BIGINT PK | |
| `split_id` | BIGINT FK | Referência ao split |
| `action` | ENUM | `CREATED`, `UPDATED`, `MEMBER_ADDED`, `MEMBER_REMOVED`, `OPTED_OUT`, `ACTIVATED`, `PAUSED`, `FROZEN`, `DISABLED` |
| `actor_steam_id` | VARCHAR(32) | Quem realizou a ação |
| `target_steam_id` | VARCHAR(32) NULL | Membro afetado (se aplicável) |
| `old_value_json` | TEXT | Configuração anterior (snapshot) |
| `new_value_json` | TEXT | Nova configuração (snapshot) |
| `created_at` | DATETIME(6) | Timestamp UTC |
| `ip_address` | VARCHAR(45) NULL | IP do ator (para disputas) |

### Visibilidade do audit log

| Perfil | O que vê |
|--------|----------|
| **Owner da tribo** | Todo o histórico do split da sua tribo |
| **Membro participante** | Seu próprio histórico de entradas/saídas no split |
| **Todos os membros da tribo** | Configuração atual + histórico de versões (sem IPs) |
| **Admin ARKLAND** | Tudo, incluindo IPs e flags de suspeita |

---

## 18.8 Suporte e intervenção administrativa

### Ferramentas do suporte

| Ferramenta | Descrição |
|-----------|-----------|
| **Freeze de split** | Admin suspende o split (`status = FROZEN`). Novas vendas com aquele split ficam como se split estivesse desativado (100% ao vendedor) até descongelamento. |
| **Override manual** | Em disputa pós-venda, admin pode registrar transferência manual via `record_admin_adjust()` para realocar pontos entre membros. `idempotency_key` impede duplicação. |
| **Visualização completa** | Admin vê todo o histórico, todas as vendas com split e total acumulado por membro. Não pode editar a configuração — apenas freezar/descongelar. |
| **Ticket vinculado** | Quando membro abre ticket de disputa de split, sistema vincula automaticamente o `split_id` e `listing_id` ao ticket. |
| **Relatório CSV** | Admin exporta todas as vendas com split de uma tribo em período determinado. |
| **Estorno de split** | Se venda for estornada (claim expirado), o estorno credita de volta ao comprador e **debita de cada beneficiário do split** proporcionalmente (até o saldo disponível; admin registra diferença manualmente). |

### Quando o admin pode editar a configuração do split
O admin **não edita** diretamente a configuração de split de uma tribo. O admin pode:
- Freezar o split (bloqueio temporário de novos splits).
- Registrar ajuste manual de pontos via painel administrativo em caso de disputa comprovada.
- Remover membro da tribo no jogo (o que dispara R9 automaticamente).

---

## 18.9 Tabela de edge cases

| # | Cenário | Comportamento |
|---|---------|---------------|
| 1 | Vendedor faz opt-out de si mesmo | Bloqueado — vendedor não pode sair do próprio split sem desativar o recurso |
| 2 | Membro faz opt-out após listing estar ativa mas antes da venda | Snapshot do listing não muda; se conta inativa no momento da venda, R9 aplica |
| 3 | Owner altera % após criar listing | Listing tem snapshot congelado; nova % vale para próximas listings (após cooldown R3) |
| 4 | Membro removido da tribo in-game enquanto listing ativa | Snapshot honrado; se conta inativa no momento da venda, parcela vai ao vendedor (R9) |
| 5 | Dois membros de mesma tribo com splits diferentes | Impossível — há um split ativo por configuração de tribo. Vendedor escolhe qual split usa ao criar listing (se elegível por múltiplas tribos) |
| 6 | Comprador pertence ao mesmo split que o vendedor | Permitido — comprador paga integral, recebe split como qualquer membro. Não é wash trading automático pois preço mínimo de mercado é enforced |
| 7 | Venda abaixo de R8 (< 1.000 Âmbares) com split ativado | Split ignorado — 100% ao vendedor; ledger registra `split_ignored: min_price` |
| 8 | Split com apenas 2 membros (vendedor + 1) | Válido — vendedor deve ter gap ≥ 10 p.p. acima do membro (ex: vendedor 60%, membro 40% — válido; vendedor 54%, membro 46% — BLOQUEADO por R1) |
| 9 | Split com 1 membro (só o vendedor) | Inválido — split exige ao menos 2 participantes. Com apenas o vendedor, desativar o split é o caminho correto |
| 10 | Owner da tribo sai da tribo in-game | Split fica ativo mas em estado `ORPHANED`; admin deve reassinar ownership ou o split é congelado automaticamente após 7 dias |
| 11 | Fob owner quer split só para a fob | **Não suportado (D6/R13).** Fob não possui configuração de split — split é exclusivo da tribo principal. Owner da fob que queira split deve configurá-lo na tribo principal (se for membro dela) |
| 12 | Membro banido recebe split antes do ban ser processado | Parcela é creditada; admin pode registrar estorno manual. R9 é verificado no momento exato da execução de `purchase_listing()` |
| 13 | Cooldown ativo e vendedor quer listar com split | Listagem bloqueada com split novo; pode listar sem split ou esperar o cooldown (R3) |
| 14 | Split percentual com arredondamento que não fecha em 100% | Sistema atribui remainder (±1 ponto de % por arredondamento) sempre ao vendedor |
| 15 | Vendor faz listing, depois é expulso da tribo antes da venda | Snapshot congelado; vendedor recebe sua parte no momento da venda (já que a listing é sua) |
| 16 | Mercado pausado pelo admin — listagem com split expira | No processo de expiração/estorno, o estorno segue o caminho inverso do split (ver §18.8 estorno) |
| 17 | Membro de fob quer participar do split de outra tribo no mesmo mapa | **Bloqueado (D6/R13).** Membro que pertence a uma fob em determinado mapa não pode participar do split de outra tribo nesse mesmo mapa. Split cross-cluster só é possível se o membro for integrante confirmado da tribo principal |
| 18 | Owner tenta criar split com membro de outra tribo | Bloqueado — só membros confirmados da tribo (ou cluster group) podem ser incluídos no split |
| 19 | "Wash trading" coordenado (membro A lista barato, membro B compra, split redistribui) | Mitigado por: preço mínimo de mercado enforced em `validate_listing_price_ceiling()`; alerta admin quando buyer aparece no mesmo split que o seller |
| 20 | Split ativo, tribo dissolvida in-game | Split recebe flag `TRIBE_DISSOLVED`; novas listings não podem usá-lo; listings existentes executam normalmente pelo snapshot |
| 21 | Owner desativa split, reativa em < 48h | Nova ativação reinicia cooldown de 48h do zero |
| 22 | Membro com saldo insuficiente recebe split | O crédito nunca falha — é apenas um incremento no saldo. Não há "saldo mínimo" para receber |
| 23 | Split ativo durante manutenção do site | Listagens com split ativo são pausadas durante manutenção; retomam automaticamente |
| 24 | Admin força venda sem split (ordem judicial/regra do servidor) | Admin pode freezar split antes da venda + registrar override manual pós-venda |
| 25 | Split referenciado em regulamento interno da tribo (§19) | O regulamento pode mencionar a política de split, mas a **configuração** do split é separada (este §18). As duas são independentes. |

---

## 18.10 Modelo de dados

### Tabelas novas

```sql
-- Configuração de split por tribo
CREATE TABLE tribe_splits (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  tribe_owner_id   BIGINT NOT NULL REFERENCES tribe_owners(id),
  tribe_id         INT NOT NULL,
  server_id        VARCHAR(64) NOT NULL,    -- contexto de referência (tribo principal)
  tribe_name       VARCHAR(128) NULL,
  status           ENUM('DRAFT','PENDING_COOLDOWN','ACTIVE','PAUSED','FROZEN','DISABLED','ORPHANED') DEFAULT 'DRAFT',
  cooldown_hours   INT NOT NULL DEFAULT 48,
  valid_from       DATETIME(6) NULL,
  created_at       DATETIME(6) NOT NULL,
  updated_at       DATETIME(6) NOT NULL,
  updated_by       VARCHAR(32) NULL,
  KEY idx_tribe (server_id, tribe_id),
  KEY idx_owner (tribe_owner_id)
);

-- Membros do split
CREATE TABLE tribe_split_members (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  split_id     BIGINT NOT NULL REFERENCES tribe_splits(id),
  steam_id     VARCHAR(32) NOT NULL,
  display_name VARCHAR(128) NULL,
  percentage   TINYINT UNSIGNED NOT NULL,   -- 1..99; soma deve ser 100 validado na camada de app
  is_seller    TINYINT(1) NOT NULL DEFAULT 0,  -- flag para o vendedor default
  opted_out    TINYINT(1) NOT NULL DEFAULT 0,
  opted_out_at DATETIME(6) NULL,
  added_at     DATETIME(6) NOT NULL,
  UNIQUE KEY uq_member (split_id, steam_id),
  KEY idx_steam (steam_id)
);
```

### Extensão na tabela existente

```sql
ALTER TABLE market_listings
  ADD COLUMN tribe_split_id   BIGINT NULL REFERENCES tribe_splits(id),
  ADD COLUMN split_snapshot   TEXT NULL;   -- JSON das % no momento da ativação do anúncio
```

---

## 18.11 MVP vs. fases futuras

### MVP (implementado)

- [x] Tabelas `tribe_splits` e `tribe_split_members`
- [x] API `POST/GET /api/tribe/split` — criar/editar (owner) + consultar
- [x] API `POST /api/tribe/split/optin` e `/optout` — opt-in por jogador
- [x] `purchase_listing()` + snapshot na ativação do anúncio
- [x] Default 60/40 + validação R1/R2; proteção de dono no TribeSync/web
- [x] UI Minha Tribo — Aceitar/Sair + editar % (dono)
- [x] Audit log `tribe_split_audit` (básico)
- [x] Cooldown R3 (PENDING_COOLDOWN 48h)
- [ ] ~~Notificação Discord~~ **→ Fase 2+ (D8)**

### v1.1 (após estabilização do MVP)

- [ ] UI de countdown do cooldown R3
- [ ] Recálculo proporcional completo (R4) com UI de preview
- [ ] R9 (conta suspensa — redirecionamento ao vendedor)
- [ ] Estorno proporcional quando venda é revertida
- [ ] Freeze de split pelo suporte (painel admin)
- [ ] Relatório CSV de splits por tribo
- [ ] Edge cases 10, 11, 13–17 documentados acima

### v2.0 (long-term)

- [ ] Consentimento de membros via site (fluxo de aprovação antes do split entrar em vigor)
- [ ] Escrow para membros banidos (parcela fica em quarentena)
- [ ] Detecção automática de wash trading com alerta admin
- [ ] Histórico visual de versões do split com diff
- [ ] Split baseado em contribuição de breeding (tracker integrado ao genoma — ver `docs/GENOMA_ARKLAND_SPEC.md`)

---

## 18.12 Status das decisões administrativas

> **Todas as questões abertas foram respondidas pelo admin em 10/07/2026.** Esta seção substitui o antigo §18.12 "Perguntas abertas". As decisões estão formalizadas em §18.0 e aplicadas em cada regra (R1–R14) com marcação ✅ DECIDIDO.

### Resumo por regra

| Regra | Decisão aplicada | Ref. decisão |
|-------|-----------------|--------------|
| R1 | Gap mínimo de 10 p.p. acima do próximo membro; sem piso fixo em % absoluta | D1 |
| R3 | Cooldown 48h somente em alterações de config; opt-out e disable são imediatos | D2 |
| R4 | Reentrada permitida: 45h de espera + aprovação do owner | D3 |
| R8 | Mínimo de venda: 1.000 Âmbares | D7 |
| R11 | Limite: 10 membros por split | D5 |
| R12 | Visibilidade: integrantes da tribo apenas | D4 |
| R13 | Split exclusivo da tribo principal; fobs sem split; restrição same-map | D6/D10 |
| R14 | Sem integração com encomendas | D9 |
| MVP | Notificação Discord adiada para Fase 2+ | D8 |

### Próximas etapas

MVP alinhado a U1–U6 implementado no código web + TribeSync (proteção de dono). Pendências v1.1: countdown UI, ledger event types dedicados, freeze admin.

---

> Spec + implementação MVP. Alterações de regras de produto devem atualizar §18.0 (U*) antes de mudar código.
