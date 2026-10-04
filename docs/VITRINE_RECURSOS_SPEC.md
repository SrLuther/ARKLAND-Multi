# Vitrine de Recursos — Mercado P2P de recursos (somente Âmbar)

Status: implementado no repositório (Web Store + plugin CustomShop). **Nada foi implantado em servidor.**
Plugin C++ só chega aos mapas numa release futura do app; Web Store precisa de reinício para criar as tabelas/rotas.

## 1. Visão geral

Jogadores enviam recursos comuns do inventário pessoal para uma **vitrine pessoal** (estoque), definem na web o
**tamanho do lote** e o **preço do lote em Âmbares**, e outros jogadores compram **lotes inteiros**. O comprador resgata
em jogo pelo `/mercado` (o mesmo comando do comércio de dinos).

```
 JOGO (CustomShop)                       WEB STORE (arkshop_web)
 /vitrine  ──► lê inventário pessoal      GET  plugin/config
            ──► preview no chat           GET  plugin/stock/<steam>
 /confirmar ─► journal ► remove itens ──► POST plugin/upload (upload_id idempotente)
                       └ falhou? ───────► POST plugin/upload/cancel  ► devolve itens
 (web) Minha vitrine: define lote/preço ► PUT  my/stock/<rid>/listing
 (web) Explorar ► comprar lotes ────────► POST listings/<stock_id>/purchase (débito+crédito+claim)
 /mercado ──► claim ► dá itens (stacks) ► POST plugin/claims/claim | delivered | release
 expiração 24h (scheduler) ► reembolsa comprador + devolve recurso ao estoque do dono
 retirar estoque (web) ► claim WITHDRAW ► resgatado pelo /mercado (sem Âmbar)
```

## 2. Decisões de projeto (pontos abertos do pedido)

| Tema | Decisão |
| --- | --- |
| Onde persistir "Recursos autorizados" e limite de tipos | **Fonte:** bloco `ResourceVitrine` no `catalog.json` partilhado (o mesmo arquivo que a Web Store grava e que o CustomShop abre na subida via `SharedCatalogPath`). **Cópia:** tabelas `market_resource_catalog` / `market_resource_settings`. Na subida da Web Store e ao ler a lista, o arquivo atualiza o MySQL; linha que saiu do arquivo não volta só porque sobrou no banco. O plugin consulta `GET plugin/config` primeiro e, se a lista vier vazia ou a chamada falhar, lê o mesmo bloco no catalog local. |
| Chave de recurso | Blueprint normalizado: `/Game/.../Nome.Nome` (sem `Blueprint'...'`, sem sufixo `_C`); comparação sempre em minúsculas (`blueprint_key`). O plugin normaliza o nome completo da classe do item da mesma forma. |
| "Preço mín/máx por lote" do admin | Aplicado ao **preço do lote** definido pelo jogador (independe do tamanho do lote). Opcional (NULL = livre). Risco conhecido: como o jogador escolhe o tamanho do lote, a faixa não limita preço por unidade — se o admin precisar disso, usar lote fixo no futuro. |
| Comissão (`fee_amount`) | Constante única em `market_fee.py` (`MARKET_FEE_PERCENT = 0`). A Vitrine de Recursos já usa; o comércio de dinos hoje grava `fee_amount=0` fixo (mesmo valor). Se a comissão deixar de ser 0, mudar `market_fee.py` **e** ligar `purchase_listing` ao helper. |
| Estoque < 1 lote com anúncio ativo | O anúncio **continua ativo** (configuração preservada) mas fica **oculto em "Explorar"** (`lots_available = 0`) e aparece na "Minha vitrine" como *"Sem lote completo"*. Volta sozinho quando o estoque voltar (novo upload/estorno de expiração). Nada é pausado/apagado automaticamente. |
| Limite de tipos por jogador | Conta tipos com `quantity > 0`. Padrão **5** (1–50, ajustável). Upload que exceda é **rejeitado inteiro** pelo backend (`type_limit`); o plugin faz pré-checagem, **trunca** o preview aos tipos que cabem e avisa no chat quais ficam de fora (nada removido). Estornos de expiração/devolução ao estoque **nunca** são bloqueados pelo limite. |
| Retirada | Gera claim `WITHDRAW` (quantidade total ou parcial) para o próprio dono, resgatado no `/mercado`; expira em 24 h e, ao expirar, **volta ao estoque** (sem Âmbar). |
| `claim` x expiração | `CLAIMED` só expira após uma folga de 15 min desde o `claimed_at` (evita reembolso enquanto o plugin ainda está entregando). `delivered` é aceito em `CLAIMED` mesmo após a expiração, desde que o scheduler não o tenha processado. |
| Itens aceitos no `/vitrine` | Inventário **pessoal** (inventário + hotbar). Exclui: equipados, engramas, blueprints, qualquer item com durabilidade (equipamentos, perecíveis) e itens não empilháveis (`maxStack <= 1`). Cofres/criaturas não são lidos. |
| Entrega em stacks | `quantity` do claim é partido em stacks do `stack_size` cadastrado pelo admin (último stack = resto). O admin deve cadastrar o stack **real** do jogo. |

## 3. Banco de dados (migração versionada)

Módulo `resource_vitrine_migrate.py` (`RESOURCE_VITRINE_SCHEMA_VERSION = "1.0.0"`), chamado ao final de
`market_migrate.ensure_market_schema` (boot + watcher de reconexão). `CREATE TABLE IF NOT EXISTS` (SQLite e MySQL),
idempotente. Limites MySQL respeitados (índices únicos com `VARCHAR` ≤ 191 caracteres úteis; chaves compostas ≤ 3072 bytes
em utf8mb4; `steam_id` = `VARCHAR(32)`).

| Tabela | Colunas principais | Índices/únicos |
| --- | --- | --- |
| `market_resource_catalog` | `id`, `blueprint_key` (191), `blueprint` (255), `name` (80), `stack_size`, `min_lot_price`, `max_lot_price`, `enabled`, timestamps | UNIQUE `blueprint_key` |
| `market_resource_settings` | `setting_key` (64) PK, `setting_value` (255), `updated_at` | PK |
| `market_resource_stock` | `id`, `steam_id`, `resource_id`, `quantity`, `lot_size`, `lot_price`, `active`, timestamps | UNIQUE (`steam_id`,`resource_id`); IDX `resource_id` |
| `market_resource_uploads` | `id`, `upload_id` (64), `steam_id`, `status` (`APPLIED`/`CANCELLED`), `lines_json`, `total_quantity`, timestamps | UNIQUE `upload_id` |
| `market_resource_claims` | `id`, `kind` (`BUY`/`WITHDRAW`), `recipient_steam_id`, `seller_steam_id`, `resource_id`, `blueprint`, `resource_name`, `stack_size`, `quantity`, `tx_id`, `status`, `request_id`, `claim_reserved_at`, `claim_expires_at`, `claimed_at`, `delivered_at`, timestamps | IDX (`recipient_steam_id`,`status`); IDX `claim_expires_at`; UNIQUE (`recipient_steam_id`,`request_id`) |
| `market_resource_transactions` | `id`, `request_id`, `stock_id`, `resource_id`, `seller_steam_id`, `buyer_steam_id`, `blueprint`, `resource_name`, `lots`, `lot_size`, `lot_price`, `quantity`, `price_paid`, `fee_amount`, `seller_credit`, `buyer_points_before/after`, `seller_points_before/after`, `status` (`COMPLETED`/`REFUNDED`), `refund_amount`, `seller_reversal`, `refunded_at`, `market_trace_id`, `created_at` | UNIQUE (`buyer_steam_id`,`request_id`); IDX seller / buyer |

Estados de claim: `PENDENTE → CLAIMED → DELIVERED`; `CLAIMED → PENDENTE` (release); expiração: `BUY → REEMBOLSADO`,
`WITHDRAW → EXPIRADO` (volta ao estoque). Transições monetárias usam `UPDATE ... WHERE status IN (...)` com `rowcount`
(guarda atômica independente de `FOR UPDATE`, que o SQLite ignora).

## 4. Contrato da API

Respostas: `{"ok": true, ...}` ou `{"ok": false, "error": "<mensagem PT>", "code": "<codigo>"}` (HTTP 400/401/403/404/409/503).
Códigos: `invalid_input`, `not_authorized_resource`, `type_limit`, `stock_cap`, `upload_cancelled`, `insufficient_stock`,
`insufficient_balance`, `self_purchase`, `not_found`, `price_out_of_range`, `claim_expired`, `price_changed`.

### 4.1 Plugin (header `X-API-Key`)

| Método e rota | Corpo / retorno |
| --- | --- |
| `GET /api/market/resources/plugin/config` | `{ok, max_types_per_player, resources:[{id, blueprint, key, name, name_ascii, stack_size}]}` (só `enabled`) |
| `GET /api/market/resources/plugin/stock/<steam_id>` | `{ok, max_types, type_count, types:[resource_id...]}` (tipos com `quantity>0`) |
| `POST /api/market/resources/plugin/upload` | `{steam_id, upload_id, items:[{blueprint, quantity}]}` → `{ok, status:"APPLIED", duplicate, credited:[{resource_id, name, quantity, stock_quantity}]}`. Idempotente por `upload_id` (re-POST devolve o mesmo resultado com `duplicate:true`; se o upload foi cancelado → 409 `upload_cancelled`). Valida: SteamID64, `upload_id` `[A-Za-z0-9_-]{8,64}`, ≤ 64 linhas, `1 ≤ quantity ≤ 1.000.000`, blueprint autorizado/ativo, estoque final ≤ 100.000.000, limite de tipos. |
| `GET /api/market/resources/plugin/upload/<upload_id>` | `{ok, status:"APPLIED"|"CANCELLED"|"UNKNOWN"}` |
| `POST /api/market/resources/plugin/upload/cancel` | `{steam_id, upload_id}` → se `APPLIED`: `{ok, status:"APPLIED"}` (**não devolver itens**); se inexistente: grava tombstone `CANCELLED` e retorna `{ok, status:"CANCELLED"}` (re-POST do upload passa a falhar). Idempotente. |
| `GET /api/market/resources/plugin/pending/<steam_id>` | `{ok, claims:[{claim_id, kind, blueprint, name, name_ascii, quantity, stack_size, hours_remaining}]}` (só `PENDENTE` não expirados) |
| `POST /api/market/resources/plugin/claims/claim` | `{steam_id, claim_ids}` → `{ok, claimed:[{claim_id,...}]}` (`PENDENTE→CLAIMED`) |
| `POST /api/market/resources/plugin/claims/release` | `{steam_id, claim_ids}` → `{ok, released:[...]}` (`CLAIMED→PENDENTE`) |
| `POST /api/market/resources/plugin/claims/delivered` | `{steam_id, claim_id}` → `{ok, claim_id, status:"DELIVERED"}` (idempotente se já entregue) |

### 4.2 Web — jogador (sessão Steam)

| Rota | Descrição |
| --- | --- |
| `GET /api/market/resources/catalog` (público) | recursos ativos + `max_types_per_player` |
| `GET /api/market/resources/listings?seller_steam_id=&resource_id=&q=&limit=&offset=` (público) | anúncios ativos com `lots_available ≥ 1`: `{stock_id, seller_steam_id, seller_display_name, resource{...}, lot_size, lot_price, lots_available, stock_quantity}` |
| `GET /api/market/resources/my` | `{ok, stock:[...], type_count, max_types, pending_claims:[...], history:[...], catalog:[...]}` (formatos em 4.4) |
| `PUT /api/market/resources/my/stock/<resource_id>/listing` | `{lot_size, lot_price, active}` — valida mín/máx do admin |
| `POST /api/market/resources/my/withdraw` | `{resource_id?, quantity?, request_id?}` — sem `resource_id` retira tudo; cria claims `WITHDRAW` |
| `POST /api/market/resources/listings/<stock_id>/purchase` | `{lots, request_id?, expected_price?}` — transação atômica; rate-limit 10/min |

### 4.3 Web — admin (`@admin_required`)

| Rota | Descrição |
| --- | --- |
| `GET /api/market/resources/admin/catalog` | todos os recursos (inclusive desativados) + settings + estatísticas |
| `PUT /api/market/resources/admin/catalog` | upsert: `{id?, blueprint, name, stack_size, min_lot_price?, max_lot_price?, enabled}` |
| `DELETE /api/market/resources/admin/catalog/<id>` | desativa (`enabled=0`); nunca apaga se houver estoque/claims |
| `PUT /api/market/resources/admin/settings` | `{max_types_per_player}` |
| `POST /api/market/resources/admin/claims/expire-stale` | força o processamento de expirados |

### 4.4 Formatos de resposta (implementados — fonte para a UI)

* **`resource`** (catálogo): `{id, blueprint, key, name, name_ascii, stack_size, min_lot_price|null, max_lot_price|null, enabled}`;
  no `admin/catalog` cada item ganha também `owners` e `quantity` (estatística de estoque).
* **`GET listings`** → `{ok, listings:[{stock_id, seller_steam_id, seller_display_name, resource, lot_size, lot_price,
  unit_price, lots_available, stock_quantity}], limit, offset, has_more}`. `limit` 1–100 (padrão 25).
* **`stock` item** (em `my` e na resposta do `PUT .../listing` como `stock`): `{stock_id, resource_id, resource, quantity,
  lot_size|null, lot_price|null, active, lots_available, leftover, state, updated_at}`. `state` ∈ `active`, `paused`,
  `no_lot_defined`, `no_full_lot` (estoque < 1 lote: oculto em Explorar), `resource_disabled`.
* **`PUT .../listing`**: aceita `lot_size`, `lot_price`, `active` (parcial: omitidos mantêm o valor atual). Para ativar
  é obrigatório ter lote e preço. Erros: `price_out_of_range` (mín/máx do admin), `invalid_input`, `not_found`.
* **`pending_claims` item**: `{claim_id, kind:"BUY"|"WITHDRAW", resource_id, blueprint, name, name_ascii, quantity, stack_size,
  status, expires_at, hours_remaining}`.
* **`history` item**: `{type:"upload"|"sale"|"purchase"|"refund"|"withdraw", at, resource, lots?, quantity, amount?, status?}`
  (mais recentes primeiro, máx. 50).
* **`POST purchase`** → `{ok, duplicate, tx_id, claim_id, stock_id, lots, quantity, price_paid, buyer_balance,
  claim_expires_at, message}`. Reenvio com o mesmo `request_id` devolve o mesmo resultado com `duplicate:true` e **não**
  cobra de novo. Erros: `insufficient_balance`, `insufficient_stock` (com `available`), `self_purchase`, `price_changed`
  (`expected_price` diferente do atual), `not_found`.
* **`POST my/withdraw`** → `{ok, duplicate, claims:[...], withdrawn:[{resource_id,name,quantity}], message}`. Com
  `request_id`, cada recurso usa o sub-id `<request_id>:<resource_id>` (reenvio não duplica). O estoque sai na hora e fica
  reservado no claim; se o claim expira, volta ao estoque.
* **`POST plugin/upload`** → `{ok, status:"APPLIED", duplicate, credited:[{resource_id, name, quantity, stock_quantity}]}`.
* **`admin/claims/expire-stale`** → `{ok, processed, buyer_refunds:[...], returned_to_stock:[...]}`.
* **Erros**: `{ok:false, error, code, ...extra}`; falhas inesperadas → HTTP 500 `{code:"internal"}` sem detalhes.

## 5. Regras de negócio (backend)

* **Upload**: tudo numa transação: insere `market_resource_uploads` (UNIQUE `upload_id`) → soma no estoque (cria linha se
  necessário). Duplicado → devolve o resultado original sem somar de novo.
* **Compra**: 1) idempotência por (`buyer`,`request_id`); 2) valida anúncio ativo, recurso ativo, lote definido, vendedor ≠
  comprador, `1 ≤ lots ≤ 1000`, `lots ≤ floor(quantity/lot_size)`; 3) `UPDATE stock SET quantity = quantity - q WHERE id=? AND
  quantity >= q AND active=1 AND lot_size=? AND lot_price=?` (guarda atômica — mudança de preço/lote entre listar e comprar
  → `price_changed`); 4) débito do comprador (`players.points >= preço`, senão `insufficient_balance`), crédito do vendedor
  (`preço − fee`); 5) cria transação + claim `BUY` (24 h); 6) auditoria `MARKET_RESOURCE_PURCHASE` + `amber_ledger`
  (`market_resource_purchase_buyer/seller`, chave idempotente `market:restx:<id>:...`). Qualquer falha → rollback total.
* **Expiração** (`expire_resource_claims`, mesmo tick do scheduler que chama `expire_stale_claims`): `BUY` →
  claim `REEMBOLSADO`, comprador recebe 100% do pago, vendedor devolve o crédito **até o saldo disponível** (mesma política do
  comércio de dinos), recurso volta ao estoque do dono, transação `REFUNDED`. `WITHDRAW` → `EXPIRADO`, recurso volta ao
  estoque. Tudo com guarda atômica de status (idempotente).
* **Auditoria**: `market_audit_events` com `MARKET_RESOURCE_*` (`UPLOAD`, `UPLOAD_CANCELLED`, `LISTING_SET`, `PURCHASE`,
  `CLAIM_CLAIMED`, `CLAIM_DELIVERED`, `CLAIM_RELEASED`, `WITHDRAW`, `CLAIM_EXPIRED_REFUND`, `CLAIM_EXPIRED_RETURN`,
  `ADMIN_CATALOG`, `ADMIN_SETTINGS`). Sem segredos nos logs.

## 6. Plugin CustomShop (C++)

Novo módulo `ShopVitrine.cpp/.h` (namespace `CustomShop::Vitrine`).

* `/vitrine` (configurável: `Settings.VitrineCommandEnabled`, `Settings.VitrinePreviewTtlSeconds` 30–120, padrão 120 como o `/enviar`):
  consulta `plugin/config` (MySQL) e, se a lista vier vazia ou a web falhar, lê `ResourceVitrine` no `catalog.json`
  (`SharedCatalogPath`, senão o `config.json` local); varre o inventário pessoal (dedup por ponteiro; sem equipados,
  engramas, blueprints, durabilidade; quantidade acima do stack vanilla não descarta o item); casa path **ou** nome curto
  sem `_C`; soma por recurso; aplica o limite de tipos (trunca e avisa); lista no
  chat (`nome: quantidade`) e grava o **pending** (um por jogador, TTL).
  Log em `logs/arkland_debug.log`: `origem`, quantidade de recursos, itens lidos e a chave do item.
* **Um pending por jogador**: `/vitrine` recusa-se (mensagem clara) se houver pending de engramas, notas, marco ou
  `/enviar`; e `/engramas`, `/notas`, `/marco`, `/enviar` (via `Vitrine::HasPending`) avisam se houver `/vitrine` pendente
  em vez de sobrescrever (nos fluxos onde isso é viável sem reescrevê-los — ver §6.3).
* **Ordem de despacho do `/confirmar`**: `engramas → notas → marco → vitrine → mercado (/enviar de dino)`.
* **Journal** (`ArkApi/Plugins/CustomShop/vitrine_journal/<upload_id>.json`, escrita atômica `tmp + MoveFileEx`):
  1. `state=planned` (linhas intencionadas) → 2. remove itens → 3. `state=removed` (com quantidades realmente removidas)
  → 4. `POST plugin/upload` (mesmo `upload_id`) → 5. sucesso: apaga journal.
  * Falha na remoção (parcial): devolve o que já removeu (stacks) e apaga o journal.
  * POST falhou: `POST upload/cancel`; resposta `CANCELLED` → **devolve os itens** e apaga o journal; `APPLIED` → trata
    como sucesso (não duplica); sem resposta (web fora) → **mantém o journal** (`state=removed`) para recuperação.
  * **Recuperação** (`Vitrine::RecoverForPlayer`, chamada no login — `HandleNewPlayer`, em `/vitrine` e `/mercado`):
    `planned` → descartado (nada comprovadamente removido); `removed` → consulta `GET upload/<id>`: `APPLIED` → apaga;
    caso contrário reenvia o POST (mesmo `upload_id`); erro **definitivo** de validação (HTTP 400/409 com `code`) →
    `cancel` + devolve itens; erro transitório → mantém.
* **`/mercado`**: depois dos claims de dinos, busca `plugin/pending/<steam>` de recursos: `claim` → checa slots livres →
  entrega em stacks (`Store::GiveResourceStacks`) → confere delta no inventário → `delivered`. Sem espaço/falha →
  `release` (nada se perde; resgate liberado).
* **Compilação**: `plugin/CustomShop/build_cl.bat` (MSVC + SDK em `plugin/CustomShop/ArkServerAPI`) compilou e linkou o
  CustomShop 1.10.41 sem erros (DLL em `plugin/CustomShop/bin/`). **Não** testado em servidor/jogo.

### 6.1 Novas chaves em `Settings` (opcionais)

```json
"VitrineCommandEnabled": true,
"VitrinePreviewTtlSeconds": 120
```

### 6.2 Arquivos

`ShopVitrine.cpp/.h` (novo), `ShopMarket.cpp` (ramo do `/confirmar`, extensão do `/mercado`, bloqueio de pending),
`ShopStore.cpp/.h` (`Store::GiveResourceStacks`), `ShopConfig.*` (2 chaves), `Main.cpp` (registro + recuperação no login),
`Commands.cpp` (registro + bloqueio inverso em `/engramas` e `/notas`), `ShopTeams.cpp` (bloqueio inverso em
`/marco`, 1 guarda em `RequestDepositPreview`), `ShopEngrams.cpp`/`ShopNotes.cpp` não são alterados, `CMakeLists.txt`,
`CustomShop.vcxproj`, `build_cl.bat`.

### 6.3 Pending único — cobertura

* `/vitrine` → verifica `Engrams::HasPendingUnlock`, `Notes::HasPendingUnlock`, `Teams::HasPendingDeposit` e o pending
  de `/enviar` (`ShopMarket::HasPendingEnviar`). Se houver → recusa com mensagem.
* `/enviar` → verifica `Vitrine::HasPending` antes de gravar o próprio pending.
* `/engramas` (`CmdEngramas`), `/notas` (`CmdNotas`) e `/marco` (`Teams::RequestDepositPreview`): ganharam uma guarda
  `Vitrine::HasPending` **antes** de criar o pending (recusam com `Vitrine::kMsgPendingBlocks`). Os módulos
  `ShopEngrams`/`ShopNotes` em si não mudam. Resta só uma janela teórica de corrida (comandos no mesmo tick), coberta pelo
  TTL sem perda de itens. Risco em §8.

## 7. Web (UI)

* **Comércio → nova aba "💎 Vitrine de Recursos"** (`#market-panel-resources`) separada da vitrine de dinos, com sub-abas
  *Explorar* e *Minha vitrine* (código em `static/resource_vitrine.js`, estilos prefixados `rv-`).
* **Admin → Mercado → "Recursos (vitrine)"** (`#page-market-resources-admin`).
* **Removido**: item de menu "Venda in-game (legado)", `#page-sell`, `#modal-sell` e o JS morto (`renderSell`,
  `openSellModal`, `confirmSell`, `deleteSell`). `Settings.DisableSellButton` e `SellItems` continuam no config
  (leitores existentes não quebram).
* **Tutorial**: bloco curto em *Tutoriais* ("Vitrine de Recursos").

## 8. Riscos e limites conhecidos

1. **Rollback de save do jogo**: se o servidor cair entre a remoção e o próximo save do mundo, o inventário volta ao estado
   anterior mesmo que o upload tenha sido aplicado (duplicação possível). Mitigação: journal + POST imediato (janela de
   segundos). Não há como detectar do plugin.
2. **Chamadas HTTP síncronas na game thread** (padrão do plugin; `/enviar` já faz isso).
3. Exclusão de itens no plugin: durabilidade (`bUseItemDurability`), `ItemRating > 0`, blueprint, engrama, equipado e
   `maxStack<=1`. O mesmo predicado vale para listar **e** remover (nunca consome outro item da mesma classe).
4. Stack do admin maior que o stack real do jogo pode gerar stacks inválidos — cadastrar o valor real.
5. Pending de outros comandos criado depois do `/vitrine` (ver §6.3).
6. Preço mín/máx por lote não limita preço por unidade (ver §2).

## 9. Rollout (produção)

1. Release do app (inclui `plugin/arkshop_web` + `CustomShop.dll` 1.10.41 + `PluginInfo.json`).
2. **Reiniciar a Web Store**: cria as 6 tabelas (`ensure_market_schema`) e registra as rotas. Migração é aditiva (não toca
   dados existentes). Aba nasce vazia: admin cadastra os recursos e o limite de tipos.
3. Plugin: só **depois** da Web Store atualizada (o plugin antigo ignora a feature; o plugin novo com web antiga recebe 404
   e responde "Vitrine indisponivel" sem remover nada). Atualizar mapa a mapa fora do pico (reinício do mapa necessário).
4. Rollback: remover o plugin novo não perde dados (journal pendente é reaproveitado se o plugin voltar); tabelas novas
   podem permanecer.

## 10. Testes

`plugin/arkshop_web/tests/test_resource_vitrine.py` (serviço + HTTP + permissões + schema + UI/markup).
Execução: `python -m pytest plugin/arkshop_web/tests/test_resource_vitrine.py`.

Plugin (contrato estático C++ ↔ spec): `tests/test_customshop_vitrine_contract.py`.

## 11. Notas do plugin (CustomShop 1.10.41)

Decisões de implementação onde o spec era omisso/ambíguo (o backend **não** foi alterado; ajustar aqui se mudar):

1. **Journal** — `planned` é gravado **antes** de qualquer remoção e promovido a `removed` só depois de medir o que saiu do
   inventário (delta de `CountPlain` antes/depois, fonte de verdade). Falha ao gravar `planned` ⇒ nada é removido. Campo
   `abort=true` = upload confirmado `CANCELLED` ⇒ só devolver (nunca reenviar); `returned` por linha evita devolver duas vezes.
   Journals `kind=ack` guardam o `delivered` de um claim já entregue cuja web não respondeu (reenviado até 3x na hora e depois
   em cada recuperação).
2. **Qualquer** falha do `POST upload` (definitiva ou transitória) chama `POST upload/cancel` como árbitro atômico
   (tombstone): `CANCELLED` ⇒ devolve itens; `APPLIED` ⇒ sucesso; sem resposta ⇒ mantém o journal. Na recuperação, erro
   transitório do re-POST mantém o journal e só erro definitivo (`invalid_input`, `not_authorized_resource`, `type_limit`,
   `stock_cap`, `upload_cancelled`) dispara `cancel` + devolução.
3. **Recuperação sem jogador online**: `RecoverAll` (45 s após o mapa subir) conclui `APPLIED`/re-POST/`ack` sozinho; só a
   devolução de itens espera o login (`HandleNewPlayer` +12 s, `/vitrine`, `/mercado`).
4. **`HttpClient::Get`** devolve `""` para HTTP ≥ 400 (não expõe o corpo): `GET upload/<id>` com erro = "sem resposta" ⇒ journal
   mantido. `PostJson` devolve o corpo mesmo em 4xx, por isso o `code` do erro é lido ali.
5. **TTL do preview**: padrão **120 s** (igual ao `/enviar`, pedido do usuário), faixa 30–120. O texto anterior dizia 90.
6. **Chave de recurso**: o plugin compara `key` (minúsculo) vindo de `plugin/config` com o nome completo da classe do item
   normalizado como `normalize_blueprint` (`_C` removido). Itens de subclasses/skins diferentes **não** casam.
7. **Stack de entrega** = `min(stack_size do admin, stack real do jogo)` quando o real é > 1; stack do admin maior que o
   real é reduzido (nunca cria stack inválido). Devolução de upload cancelado usa o mesmo cálculo.
8. **Entrega no `/mercado`**: `claim` é feito **um por vez**; sem espaço (estimativa de slots livres) ⇒ `release` e para.
   Se o delta medido < `quantity`, desfaz o que entrou e faz `release`; se não conseguir desfazer, o claim fica `CLAIMED`
   (sem `release`/`delivered`) — o backend o expira após a folga de 15 min (risco residual: reembolso do comprador com
   entrega parcial já no inventário; logado como erro).
9. **Campos usados do backend** (precisam existir): `plugin/config.resources[].{id,blueprint,key,name,name_ascii,stack_size}`,
   `plugin/stock.{max_types,types}`, `plugin/pending.claims[].{claim_id,kind,blueprint,name_ascii,quantity,stack_size,hours_remaining}`
   e `claims/claim.claimed[].{claim_id,quantity,stack_size,blueprint,name_ascii}` — todos já presentes em `_claim_public`.
10. **`ItemRating`**: itens com `ItemRating > 0` são excluídos (qualidade especial); `bUseItemDurability` cobre durabilidade/perecíveis.
11. O limite de tipos é pré-checado com `plugin/stock`; tipos já no estoque sempre cabem, tipos novos só até
    `max_types − type_count`; linhas > 1.000.000 por recurso são cortadas em 1.000.000 (resto fica no inventário).
