# Especificação: Sistema de Promoções e Descontos do Catálogo

**Projeto:** ARKLAND Multi — Web Store (`arkshop_web`) + CustomShop  
**Versão do documento:** 1.0 (rascunho para discussão)  
**Data:** 03/07/2026  
**Status:** Especificação — **sem implementação**

---

## 1. Resumo executivo

O ARKLAND Multi opera uma loja web (`plugin/arkshop_web`) integrada ao plugin in-game **CustomShop** (`plugin/CustomShop`). O catálogo vive em `config.json` com seções `Items` e `Kits`, cada entrada tendo campo `Price` em Âmbares (pontos). Hoje **não existe mecanismo de promoção**: o preço exibido e cobrado é sempre `Price` do config, tanto na web (`_catalog_price` → `player_purchase`) quanto in-game (`BuyItem` / `BuyKit` em `ShopStore.cpp`).

Este documento propõe um **sistema de promoções temporárias** aplicável a itens e kits selecionados, com agendamento, regras de escopo, exibição na UI web e cobrança correta no checkout — **sem alterar o `Price` base do catálogo** (desconto calculado em runtime).

**Decisão arquitetural central:** as promoções devem ser resolvidas **no servidor web** (`arkshop_web`) como fonte de verdade para compras via site. O plugin in-game pode, numa fase posterior, consumir as mesmas regras para paridade no `/shop`, mas o MVP prioriza a loja web onde já ocorre a maior parte dos resgates pagos.

**Padrão de referência existente:** `FeaturedMaps` — seção top-level em `config.json`, editável via admin web, sincronizada pelo ASM em `SHARED_SYNC_TOP_LEVEL_KEYS` (`src/shop_integration.py`). Promoções seguirão modelo similar.

---

## 2. Objetivos e não-objetivos

### Objetivos

| # | Objetivo |
|---|----------|
| O1 | Permitir que admins criem promoções com desconto sobre itens e/ou kits do catálogo |
| O2 | Definir período de vigência (início/fim) configurável |
| O3 | Exibir preço original riscado + preço promocional + badge na loja web |
| O4 | Cobrar o preço promocional no checkout (`/api/player/purchase`) e registrar metadados no pedido |
| O5 | Garantir reembolso correto (valor efetivamente pago, não o preço de tabela) |
| O6 | Auditar criação/edição de promoções e compras com desconto |
| O7 | Sincronizar definições de promoção via `config.json` mestre (ASM → webstore → plugins) |
| O8 | Suportar escopo flexível: IDs específicos, categorias, kits, ou loja inteira |

### Não-objetivos (v1 / fora de escopo inicial)

| # | Não-objetivo | Motivo |
|---|--------------|--------|
| N1 | Cupons de uso único por jogador (códigos digitáveis) | Complexidade adicional; fase 2 |
| N2 | Desconto em pacotes PIX (`PointPackages`) | São doações em BRL, não catálogo de resgate |
| N3 | Desconto no mercado P2P (`market_listings`) | Economia separada com regras próprias |
| N4 | Alterar `Price` permanentemente no config durante promoção | Promoção deve ser overlay reversível |
| N5 | Promoções por servidor/mapa individual | Cluster compartilha catálogo mestre hoje |
| N6 | Buy-X-get-Y com entrega parcial automática | Avaliar na fase 2; MVP foca % e preço fixo |
| N7 | Notificações push/e-mail de promoção | Pode ser adicionado depois |

---

## 3. Histórias de usuário

### Admin / operador

| ID | Como… | Quero… | Para… |
|----|-------|--------|-------|
| A1 | admin da loja | criar uma promoção de 25% em todos os kits de dinos | impulsionar vendas de fim de semana |
| A2 | admin | selecionar itens específicos por ID e aplicar preço fixo promocional | liquidar estoque simbólico de itens antigos |
| A3 | admin | definir data/hora de início e fim com fuso horário explícito | alinhar com eventos sazonais do cluster |
| A4 | admin | ver preview de quantos itens/kits serão afetados antes de publicar | evitar erros de escopo |
| A5 | admin | desativar uma promoção imediatamente sem apagar o histórico | encerrar campanha antecipada |
| A6 | admin | ver relatório de vendas com desconto por promoção | medir ROI da campanha |
| A7 | admin | editar promoções no painel ASM ou na web admin | usar a ferramenta que já utilizo |
| A8 | admin | duplicar uma promoção passada para reutilizar configuração | agilizar campanhas recorrentes |

### Jogador

| ID | Como… | Quero… | Para… |
|----|-------|--------|-------|
| P1 | jogador logado | ver claramente o preço original e o preço com desconto | entender a economia antes de resgatar |
| P2 | jogador | filtrar ou identificar itens em promoção (badge, aba) | encontrar ofertas rapidamente |
| P3 | jogador | pagar o preço promocional ao confirmar resgate | não ser cobrado pelo preço cheio |
| P4 | jogador | receber reembolso integral do valor pago se cancelar pedido pendente | confiar no sistema |
| P5 | jogador | ver contagem regressiva até o fim da promoção (opcional) | decidir antes que expire |

---

## 4. Modelo de dados

### 4.1 Seção `Promotions` em `config.json`

Nova seção top-level, lista ordenada de objetos promoção. O `Price` em `Items`/`Kits` permanece inalterado.

```json
{
  "Promotions": [ /* ver seção 14 */ ],
  "PromotionSettings": {
    "timezone": "America/Sao_Paulo",
    "default_stacking": "best_for_customer",
    "show_countdown": true,
    "badge_label": "PROMO"
  }
}
```

### 4.2 Schema de uma promoção

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `id` | string (slug UUID curto) | sim | Identificador estável (`promo_black_friday_2026`) |
| `name` | string | sim | Nome interno/admin |
| `title` | string | não | Título público (banner, badge estendido) |
| `description` | string | não | Texto explicativo na UI |
| `enabled` | boolean | sim | Interruptor manual (além do schedule) |
| `priority` | integer | sim | Maior vence em conflito (default: 0) |
| `type` | enum | sim | `percentage`, `fixed_price`, `fixed_discount` |
| `value` | number | sim | % (0–100), preço fixo em Âmbar, ou desconto fixo em Âmbar |
| `scope` | object | sim | Regras de aplicação (ver seção 6) |
| `schedule` | object | sim | Vigência (ver seção 7) |
| `limits` | object | não | Limites globais ou por jogador (fase 2) |
| `display` | object | não | Badge, cor, banner, ordenação em destaque |
| `created_at` | ISO8601 | não | Auditoria |
| `updated_at` | ISO8601 | não | Auditoria |
| `created_by` | steam_id | não | Admin criador |

### 4.3 Campos derivados (runtime, não persistidos no config)

Calculados por `resolve_promotion_price(catalog_kind, item_id, entry, now)`:

| Campo derivado | Descrição |
|----------------|-----------|
| `base_price` | `entry.Price` (ou `Price * amount` para itens com quantidade) |
| `promo_price` | Preço após desconto (inteiro, mínimo 0) |
| `discount_amount` | `base_price - promo_price` |
| `discount_percent` | Arredondado para exibição |
| `applied_promotion_id` | ID da promoção vencedora |
| `applied_promotion_name` | Para UI e auditoria |

### 4.4 Extensão opcional em banco de dados (recomendada para relatórios)

Tabela `promotion_redemptions` (MySQL/SQLite via SQLAlchemy):

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | PK | Auto |
| `promotion_id` | string | FK lógica ao config |
| `order_id` | string | FK `orders.order_id` |
| `steam_id` | string | Comprador |
| `catalog_kind` | enum | `shop` \| `kit` |
| `item_id` | string | ID no catálogo |
| `base_price` | int | Preço de tabela |
| `promo_price` | int | Preço cobrado |
| `discount_amount` | int | Diferença |
| `created_at` | datetime | Momento da compra |

**Extensão em `orders` (opcional, recomendada):**

| Coluna nova | Tipo | Descrição |
|-------------|------|-----------|
| `base_price` | int nullable | Preço de tabela no momento da compra |
| `promotion_id` | string nullable | Promoção aplicada |
| `promotion_snapshot` | text nullable | JSON com tipo/valor/nome para histórico imutável |

> **Nota:** Mesmo sem colunas novas, `points_spent` + `payload_json` em `audit_events` podem registrar promoção; colunas dedicadas simplificam relatórios e reembolsos.

### 4.5 Integração com catálogo existente

**Itens** (`Items` / `ShopItems`):

```json
"abyss_aqualyrium": {
  "Blueprint": "/Game/...",
  "Category": "Recursos",
  "Name": "Aqualyrium (mod Abyss)",
  "Price": 1000,
  "Quantity": 10,
  "Type": "item"
}
```

**Kits** (`Kits`):

```json
"acro_pack10": {
  "Description": "10x Acrocantossauro Fêmea Nível 1",
  "Price": 60000,
  "DefaultAmount": 0,
  "Dinos": [ /* ... */ ]
}
```

Campos relevantes para promoções: `Price`, `Category`, `Type`, `Permissions`, `DefaultAmount` (limite de resgates — independente do desconto).

---

## 5. Tipos de promoção

### 5.1 `percentage` — Desconto percentual

- **value:** 1–100 (ex.: `25` = 25% off)
- **Fórmula:** `promo_price = floor(base_price * (100 - value) / 100)`
- **Arredondamento:** sempre para baixo (`floor`), mínimo 0
- **Exemplo:** item `Price: 1000`, 25% → `750` Âmbares

### 5.2 `fixed_price` — Preço promocional fixo

- **value:** preço final em Âmbares (ex.: `500`)
- **Fórmula:** `promo_price = min(value, base_price)` (nunca cobrar mais que o preço base)
- **Uso:** liquidação com preço psicológico definido

### 5.3 `fixed_discount` — Desconto absoluto em Âmbares

- **value:** quantidade a subtrair (ex.: `200`)
- **Fórmula:** `promo_price = max(0, base_price - value)`
- **Uso:** campanhas tipo "200 Âmbares off em qualquer dino tier B"

### 5.4 `buy_x_get_y` — Compre X leve Y (fase 2, especificado para discussão)

| Variante | Comportamento |
|----------|---------------|
| BxGy quantidade | Comprar `amount >= X` entrega bônus ou desconto na N-ésima unidade |
| BxGy kit | Comprar kit A dá desconto no kit B |

**Complexidade:** exige mudanças em entrega (`GiveItem` quantidade), UI de carrinho (hoje `amount` é fixo em 1 na web), e validação de kit limits. **Recomendação:** documentar agora, implementar após MVP.

### 5.5 Tipos excluídos

- Desconto em `EngramasCommandPrice` (Settings) — configuração separada
- Desconto em `TimedPointsReward` — não é catálogo de resgate

---

## 6. Regras de escopo

Objeto `scope` em cada promoção:

```json
"scope": {
  "mode": "include",
  "targets": {
    "items": ["abyss_aqualyrium", "abyss_barnacle"],
    "kits": ["acro_pack10", "kit_alfa"],
    "categories": ["Recursos", "Dinos"],
    "types": ["dino", "item"],
    "tags": ["mod_abyss"],
    "all_shop": false,
    "all_kits": false
  },
  "exclude": {
    "items": ["licenca_nuvem"],
    "kits": ["vip_diamante"],
    "categories": ["Licenças"]
  }
}
```

### 6.1 Modos de escopo

| `scope.mode` | Semântica |
|--------------|-----------|
| `include` | Aplica somente se o item/kit casar com **qualquer** critério em `targets` |
| `exclude` | Aplica a **tudo** exceto entradas em `exclude` (requer `all_shop: true` ou `all_kits: true`) |

### 6.2 Resolução de categoria

- Usar `Category` explícita do config
- Fallback: inferência de `catalog_enrich._resolve_display_category` (mesma lógica da web)
- Normalização: case-insensitive, sem acentos (`_norm_cat`)

### 6.3 Tags (fase 1.5)

Hoje **não existe** campo `Tags` no config. Opções:

1. **Fase 1:** escopo só por ID, categoria, type, `all_shop`/`all_kits`
2. **Fase 1.5:** adicionar `Tags: ["evento_verao"]` opcional em itens/kits para campanhas amplas sem listar centenas de IDs

### 6.4 Itens com `Price: 0`

- Promoção **não reduz** abaixo de 0; itens/kits gratuitos permanecem gratuitos
- Badge opcional "Incluído na promoção" mesmo sem alteração de preço (display only)

### 6.5 Licenças e itens `AdminOnly`

- Promoções podem incluir licenças, mas `player_purchase` já bloqueia `AdminOnly` / `Redeemable: false`
- Admin deve ver aviso no preview se escopo inclui itens não resgatáveis

### 6.6 Kits com `DefaultAmount > 0`

- Desconto aplica ao **preço de compra** do kit, não ao limite de usos
- Limite de resgates (`kit_limits.py`) permanece independente

---

## 7. Agendamento (schedule)

```json
"schedule": {
  "start": "2026-07-04T00:00:00",
  "end": "2026-07-06T23:59:59",
  "timezone": "America/Sao_Paulo",
  "recurring": null
}
```

### 7.1 Vigência

| Estado | Condição |
|--------|----------|
| `scheduled` | `now < start` |
| `active` | `enabled && start <= now <= end` |
| `expired` | `now > end` |
| `disabled` | `enabled == false` |

- Comparar sempre em UTC internamente; converter usando `timezone` da promoção ou `PromotionSettings.timezone`
- **Servidor:** usar `datetime.now(timezone.utc)` (padrão já usado em `Order.created_at`)

### 7.2 Recorrência (fase 2)

```json
"recurring": {
  "pattern": "weekly",
  "days_of_week": [5, 6],
  "start_time": "18:00",
  "end_time": "23:59"
}
```

Casos de uso: "toda sexta e sábado, 18h–23h59". Requer motor de recorrência; MVP usa apenas intervalo fixo.

### 7.3 Sincronização de relógio

- Web store é autoridade temporal
- Plugin in-game (se implementar promoções) deve confiar na API web ou usar UTC no config reload

---

## 8. Regras de empilhamento (stacking)

### 8.1 Princípio padrão: uma promoção vencedora por item

Quando múltiplas promoções ativas cobrem o mesmo item/kit:

1. Filtrar promoções `active` que casam com escopo
2. Calcular `promo_price` de cada uma
3. Aplicar política de stacking

### 8.2 Políticas (`PromotionSettings.default_stacking`)

| Política | Comportamento |
|----------|---------------|
| `best_for_customer` **(default)** | Menor `promo_price` vence |
| `highest_priority` | Maior `priority` vence; empate → menor preço |
| `first_match` | Primeira na lista `Promotions` (ordem do config) |
| `no_stack` | Apenas uma promoção por campanha — admin deve garantir escopos disjuntos |

### 8.3 Promoções sobrepostas intencionais

- Admin pode definir `priority` explícita (ex.: promo flash `priority: 100` sobre promo geral `priority: 10`)
- **Nunca** somar percentuais (25% + 10% = 35%) no MVP — risco de preço negativo e abuso

### 8.4 Exclusões

- `exclude` em promoção de escopo amplo previne desconto em itens sensíveis (licenças VIP, itens admin)

---

## 9. Exibição na UI web

### 9.1 Endpoint `/api/catalog` (público)

Hoje retorna itens/kits enriquecidos via `catalog_enrich.enrich_catalog_payload` com `Price` bruto. **Mudança proposta:** mesclar campos de promoção em cada entrada:

```json
{
  "abyss_aqualyrium": {
    "Price": 1000,
    "Name": "Aqualyrium (mod Abyss)",
    "display_category": "Recursos",
    "promotion": {
      "active": true,
      "promo_price": 750,
      "base_price": 1000,
      "discount_percent": 25,
      "promotion_id": "promo_verao_recursos",
      "badge": "PROMO",
      "ends_at": "2026-07-06T23:59:59-03:00"
    }
  }
}
```

Se sem promoção: omitir `promotion` ou `"active": false`.

### 9.2 Cards do catálogo (`index.html`)

Padrões visuais propostos (alinhados a `.dl-card--featured` existente):

| Elemento | Comportamento |
|----------|---------------|
| Badge | Canto superior: `PROMO` ou `-25%` (configurável em `display.badge`) |
| Preço | `<s>1.000</s>` + preço promocional em âmbar destacado |
| Borda/card | Variante `.item-card--promo` (similar a featured maps) |
| Countdown | Opcional: "Termina em 2d 5h" se `PromotionSettings.show_countdown` |
| Filtro | Chip "Em promoção" na barra de categorias |
| Ordenação | Pin opcional: promoções com `display.featured: true` sobem na lista |

### 9.3 Modal de compra

- Exibir `base_price`, `promo_price`, economia (`Você economiza 250 Âmbares`)
- `confirmBuy()` já envia `item_id` + `item_type`; **não** enviar preço do cliente (servidor recalcula)

### 9.4 Home pública (`/api/public/home`)

- Bloco opcional `active_promotions_banner` com título/descrição da campanha principal
- Link para catálogo filtrado

### 9.5 Admin preview

- Tabela: item/kit, preço base, preço promo, % desconto, conflitos de stacking

---

## 10. Mudanças no fluxo de compra

### 10.1 Fluxo atual (referência)

```
POST /api/player/purchase
  → _catalog_entry(item_type, item_id)
  → validações (licença, kit limit, saldo)
  → price = _catalog_price(entry, amount)    # Price * amount
  → _create_order(..., points_spent=price)
  → débito atômico em players.points
  → entitlements (licença)
  → _process_order_delivery → fila plugin
  → _audit_event("purchase_created", price=...)
```

### 10.2 Fluxo proposto

```
POST /api/player/purchase
  → _catalog_entry(...)
  → validações (inalteradas)
  → pricing = resolve_catalog_pricing(item_type, item_id, entry, amount, steam_id, now)
       ├── base_price
       ├── promo_price
       ├── promotion_id
       └── promotion_snapshot
  → price = pricing.promo_price
  → validar saldo >= price
  → _create_order(..., points_spent=price, base_price=..., promotion_id=...)
  → débito atômico (price promocional)
  → registrar promotion_redemption (se DB)
  → ... (restante igual)
  → _audit_event(..., price=price, base_price=..., promotion_id=...)
```

### 10.3 Validação server-side (obrigatória)

- **Nunca** confiar em preço enviado pelo frontend
- Recalcular promoção no momento exato do POST
- Se promoção expirou entre abrir modal e confirmar: retornar `409` com mensagem clara e preço atualizado

### 10.4 Idempotência

- `idempotency_key` existente permanece
- Em retry com mesma key, retornar resultado original (incluindo preço promocional gravado)

### 10.5 Resposta enriquecida

```json
{
  "ok": true,
  "order_id": "...",
  "points_spent": 750,
  "base_price": 1000,
  "discount_amount": 250,
  "promotion_id": "promo_verao_recursos",
  "new_balance": 4250,
  "user_message": "Resgate solicitado com desconto promocional (-25%)."
}
```

### 10.6 Compras admin / RCON

- `rcon_purchase_admin` e reissue devem usar flag `skip_promotion: true` por padrão (admin paga preço de tabela ou zero conforme fluxo atual)

---

## 11. Entrega in-game (CustomShop.dll)

### 11.1 Arquitetura atual

| Canal | Cobrança | Entrega |
|-------|----------|---------|
| **Web** | `player_purchase` debita `players.points` | Plugin poll `GET /api/pending/<steam_id>` → `GiveItem`/`GiveKit` **sem cobrar** |
| **In-game `/shop`** | `BuyItem`/`BuyKit` em `ShopStore.cpp` lê `Price` do config e chama `ShopPoints::SpendPoints` | Entrega direta |

### 11.2 Implicação crítica

**No MVP, promoções aplicam-se apenas à loja web.** O jogador que comprar via UI in-game pagará `Price` integral do `config.json`.

`GiveItem` (linha ~688 `ShopStore.cpp`) **não deduz pontos** — correto para pedidos web já pagos.

### 11.3 Opções para paridade in-game (fase 2+)

| Opção | Prós | Contras |
|-------|------|---------|
| **A — Só web (MVP)** | Zero mudança C++; simples | Divergência de preço in-game vs web |
| **B — C++ lê promoções do config** | Offline; reload com `Shop.Reload` | Duplicar lógica de schedule/stacking em C++ |
| **C — C++ consulta API** | Fonte única de verdade | Latência; dependência HTTP in-game |
| **D — Desabilitar compra paga in-game** | Força uso da web | Mudança de UX grande |

**Recomendação:** MVP = **Opção A** + mensagem in-game "Promoções disponíveis em {WebsiteUrl}" quando promo ativa. Fase 2 = **Opção B** com subset da lógica (percentage + fixed_price, schedule UTC, `best_for_customer`).

### 11.4 Entrega de pedidos web com desconto

- Plugin recebe `item_id`, `amount`, `item_type` — **não precisa saber do desconto**
- `points_spent` já reflete promoção; entrega é idêntica
- Kit limits: `_effective_kit_remaining` conta pedidos `PENDENTE`/`ENTREGANDO` — inalterado

### 11.5 Sincronização de config

Adicionar `"Promotions"` e `"PromotionSettings"` a `SHARED_SYNC_TOP_LEVEL_KEYS` em `shop_integration.py` para propagar ASM → webstore → plugins.

---

## 12. Proposta de UI admin

### 12.1 Web admin (`plugin/arkshop_web/static/index.html`)

Nova página **"Promoções"** (nav admin-only), espelhando padrão de Featured Maps:

| Funcionalidade | Detalhe |
|----------------|---------|
| Listagem | Cards com nome, status (agendada/ativa/expirada), período, # itens afetados |
| Criar/editar | Modal com formulário: tipo, valor, escopo (multi-select IDs, categorias), schedule |
| Preview | Botão "Simular" chama `GET /api/promotions/preview` |
| Toggle | Ativar/desativar sem apagar |
| Duplicar | Clonar promoção com novo ID e datas |
| Salvar | `PUT /api/promotions` → grava em `config.json` + `push_catalog_to_webstore` |

### 12.2 ASM (`src/pages/customshop_panel.py`)

Nova aba **"🏷️ Promoções"** no painel CustomShop:

- Leitura/escrita no mesmo `config.json` mestre
- `_save_config` já chama `push_catalog_to_webstore`
- `_reload()` via RCON `Shop.Reload` após salvar
- Seletor de itens/kits reutilizando listas das abas existentes (🛒 Itens / 🎁 Kits)
- Validação local antes de salvar (datas, value range, escopo não vazio)

### 12.3 Permissões

- Mesmo gate de admin: `_is_admin_steamid` / sessão admin
- Auditoria com `actor_steam_id` em toda mutação

---

## 13. Endpoints de API necessários

### 13.1 Públicos

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/catalog` | **Estender:** incluir `promotion` em cada item/kit; adicionar `promotions_summary` global |
| GET | `/api/promotions/active` | Lista promoções ativas (banner home, countdown) |

### 13.2 Jogador (autenticado)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/player/purchase` | **Estender:** pricing promocional server-side |
| GET | `/api/player/pricing?item_id=&item_type=` | Preview de preço antes do modal (opcional) |

### 13.3 Admin

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/promotions/admin` | Lista completa (inclui expiradas/desabilitadas) |
| POST | `/api/promotions` | Criar promoção |
| PUT | `/api/promotions/<id>` | Atualizar |
| DELETE | `/api/promotions/<id>` | Remover (ou soft-delete com `enabled: false`) |
| PUT | `/api/promotions/settings` | `PromotionSettings` global |
| GET | `/api/promotions/preview?id=` | Itens/kits afetados com preços calculados |
| GET | `/api/promotions/<id>/stats` | Vendas, desconto total, pedidos (requer DB) |

### 13.4 Plugin (inalterado para MVP)

| Método | Rota | Nota |
|--------|------|------|
| GET | `/api/pending/<steam_id>` | Sem mudança |
| POST | `/api/pending/claim` | Sem mudança |
| POST | `/api/pending/delivered` | Sem mudança |

---

## 14. Exemplo completo de bloco `config.json`

```json
{
  "PromotionSettings": {
    "timezone": "America/Sao_Paulo",
    "default_stacking": "best_for_customer",
    "show_countdown": true,
    "badge_label": "PROMO",
    "in_game_parity": false
  },
  "Promotions": [
    {
      "id": "promo_verao_recursos_2026",
      "name": "Verão — Recursos Abyss",
      "title": "🔥 Verão Abyss: 25% OFF",
      "description": "Desconto em todos os recursos do mod Abyss até domingo.",
      "enabled": true,
      "priority": 10,
      "type": "percentage",
      "value": 25,
      "scope": {
        "mode": "include",
        "targets": {
          "categories": ["Recursos"],
          "items": [],
          "kits": [],
          "types": [],
          "tags": [],
          "all_shop": false,
          "all_kits": false
        },
        "exclude": {
          "items": [],
          "kits": [],
          "categories": []
        }
      },
      "schedule": {
        "start": "2026-07-04T00:00:00",
        "end": "2026-07-06T23:59:59",
        "timezone": "America/Sao_Paulo",
        "recurring": null
      },
      "limits": {
        "max_redemptions_global": null,
        "max_redemptions_per_player": null
      },
      "display": {
        "badge": "-25%",
        "badge_color": "#e87820",
        "featured": true,
        "banner_image_url": ""
      },
      "created_at": "2026-07-01T12:00:00Z",
      "updated_at": "2026-07-01T12:00:00Z",
      "created_by": "76561198000000000"
    },
    {
      "id": "promo_pack_acro_flash",
      "name": "Flash — Pack Acro",
      "title": "Pack Acro 10x por 45.000",
      "description": "Preço especial no kit acro_pack10 por 48 horas.",
      "enabled": true,
      "priority": 100,
      "type": "fixed_price",
      "value": 45000,
      "scope": {
        "mode": "include",
        "targets": {
          "items": [],
          "kits": ["acro_pack10"],
          "categories": [],
          "types": [],
          "tags": [],
          "all_shop": false,
          "all_kits": false
        },
        "exclude": {
          "items": [],
          "kits": [],
          "categories": []
        }
      },
      "schedule": {
        "start": "2026-07-05T20:00:00",
        "end": "2026-07-07T20:00:00",
        "timezone": "America/Sao_Paulo",
        "recurring": null
      },
      "limits": null,
      "display": {
        "badge": "FLASH",
        "badge_color": "#f04050",
        "featured": true
      },
      "created_at": "2026-07-01T12:00:00Z",
      "updated_at": "2026-07-01T12:00:00Z",
      "created_by": "76561198000000000"
    },
    {
      "id": "promo_black_friday_geral",
      "name": "Black Friday — Loja inteira",
      "title": "BLACK FRIDAY: 15% em tudo",
      "description": "Desconto geral exceto licenças e VIP.",
      "enabled": false,
      "priority": 5,
      "type": "percentage",
      "value": 15,
      "scope": {
        "mode": "exclude",
        "targets": {
          "all_shop": true,
          "all_kits": true,
          "items": [],
          "kits": [],
          "categories": [],
          "types": [],
          "tags": []
        },
        "exclude": {
          "items": ["licenca_nuvem", "licenca_gamma"],
          "kits": ["vip_bronze", "vip_prata", "vip_ouro", "vip_diamante"],
          "categories": ["Licenças"]
        }
      },
      "schedule": {
        "start": "2026-11-28T00:00:00",
        "end": "2026-11-30T23:59:59",
        "timezone": "America/Sao_Paulo",
        "recurring": null
      },
      "limits": null,
      "display": {
        "badge": "BLACK FRIDAY",
        "featured": false
      },
      "created_at": "2026-07-01T12:00:00Z",
      "updated_at": "2026-07-01T12:00:00Z",
      "created_by": "76561198000000000"
    }
  ]
}
```

---

## 15. Casos de borda

### 15.1 Promoção expira durante checkout

| Momento | Comportamento |
|---------|---------------|
| Modal aberto, promo ativa | Exibe preço promocional |
| Jogador confirma após `end` | Servidor recalcula → preço cheio ou erro `409 promo_expired` |
| Saldo insuficiente ao preço cheio | `402` com mensagem explicativa |

**Política recomendada:** honrar preço promocional se confirmação ocorrer dentro de **grace period de 60 segundos** após `end`? → **Decisão em aberto (ver seção 18).** Default: sem grace — preço cheio.

### 15.2 Pedido pendente quando promoção termina

- Pedido já criado com `points_spent` promocional → **mantém** preço pago
- Cancelamento reembolsa `points_spent` (já implementado em `player_cancel_order`)
- Entrega in-game ocorre normalmente

### 15.3 Kit com limite parcial (`DefaultAmount`)

- Jogador com 1 resgate restante compra kit em promoção → OK
- Desconto não altera contagem de usos
- Pedidos pendentes reservam slot (`_count_pending_kit_orders`) — inalterado

### 15.4 Item com `amount > 1` (futuro)

- Hoje web envia `amount: 1` sempre
- Quando suportado: `base_price = Price * amount`; promoção aplica sobre total

### 15.5 Stacking conflitante

- Duas promoções ativas no mesmo item → `best_for_customer` escolhe menor preço
- Log em `payload_json`: `candidates: [...]` para debug admin

### 15.6 Preço promocional zero

- Permitido? (`100% off` ou `fixed_price: 0`)
- **Risco:** abuso de resgates gratuitos
- **Recomendação:** permitir apenas com `limits.max_redemptions_per_player` ou flag admin `allow_zero_price: true`

### 15.7 Reembolso admin pós-entrega

- `_order_refund_amount` usa `points_spent` → reembolsa valor promocional correto
- Fallback para `_catalog_price` só se `points_spent == 0` (legado)

### 15.8 Edição de promoção com pedidos em andamento

- Pedidos antigos conservam `promotion_snapshot` no pedido
- Alterar promoção não altera pedidos já criados

### 15.9 Catálogo desatualizado no frontend

- `loadCatalog()` deve incluir `promotions_version` ou hash para refetch periódico
- Countdown no cliente é indicativo; servidor é autoridade

### 15.10 Item removido do catálogo mas em promoção

- Preview admin mostra "órfãos"
- Na compra: `404 Item não encontrado` (comportamento atual)

### 15.11 Licença com desconto

- Entitlement grant inalterado; apenas valor debitado muda
- Revogação em cancelamento via `_revoke_entitlement_for_order` — inalterado

---

## 16. Auditoria e relatórios

### 16.1 Eventos de auditoria (`audit_events`)

| event_type | Quando | payload sugerido |
|------------|--------|------------------|
| `promotion_created` | Nova promoção | `promotion_id`, snapshot |
| `promotion_updated` | Edição | `diff`, `promotion_id` |
| `promotion_deleted` | Remoção | `promotion_id` |
| `promotion_activated` | `enabled: true` + dentro do schedule | `promotion_id` |
| `promotion_deactivated` | Desligada manualmente | `promotion_id` |
| `purchase_created` | **Estender** | `price`, `base_price`, `promotion_id`, `discount_amount` |
| `promotion_redemption` | Compra com desconto | todos os campos de pricing |

### 16.2 Relatórios admin

| Relatório | Métricas |
|-----------|----------|
| Por promoção | pedidos, `sum(discount_amount)`, `sum(points_spent)`, jogadores únicos |
| Por item | top itens vendidos com desconto |
| Timeline | vendas ao longo da vigência |
| Export CSV | `promotion_redemptions` join `orders` |

### 16.3 Integração com auditoria existente

- Filtro em admin já suporta `purchase_created` — adicionar `promotion_id` no payload
- `market_audit_events` permanece separado (P2P)

### 16.4 Logs de arquivo

- `_log("promo_price_resolved", item_id, promotion_id, base, promo)` em debug

---

## 17. Plano de migração e rollout

### Fase 0 — Preparação (sem impacto em produção)

1. Adicionar seções vazias ao config mestre: `"Promotions": []`, `"PromotionSettings": {...}`
2. Incluir chaves em `SHARED_SYNC_TOP_LEVEL_KEYS`
3. Deploy código com feature flag `PROMOTIONS_ENABLED=false`

### Fase 1 — MVP web-only

1. Módulo `promotions.py` com resolução de preço + testes unitários
2. Estender `/api/catalog` e `player_purchase`
3. UI admin web + cards com badge
4. Colunas opcionais em `orders` + tabela `promotion_redemptions`
5. Ativar flag em staging; campanha piloto com 3–5 itens

### Fase 2 — ASM + relatórios

1. Aba Promoções no `customshop_panel.py`
2. Dashboard de stats
3. Preview e duplicar promoção

### Fase 3 — Paridade in-game (opcional)

1. `ShopStore.cpp` / `ShopConfig` lê `Promotions`
2. UI in-game mostra preço riscado
3. `BuyItem`/`BuyKit` aplicam `resolve_promotion_price`

### Rollback

- `PROMOTIONS_ENABLED=false` → ignora seção, preços voltam ao normal
- Remover `"Promotions"` do config → comportamento legado
- Pedidos históricos com `promotion_id` permanecem válidos

### Compatibilidade

- Config sem `Promotions` → zero mudança de comportamento
- Plugins antigos ignoram chave desconhecida no JSON

---

## 18. Questões em aberto para discussão

1. **Paridade in-game:** Aceitamos MVP só na web (preço cheio no `/shop` in-game) ou paridade in-game é requisito do dia 1?

2. **Grace period no checkout:** Se a promoção expira enquanto o jogador está no modal, honramos o preço promocional por N segundos ou cobramos preço cheio imediatamente?

3. **Desconto 100% / preço zero:** Permitimos promoções que zeram o preço? Com quais limites (`max_redemptions_per_player`, aprovação manual)?

4. **Empilhamento:** Confirmamos `best_for_customer` (menor preço) como padrão, ou preferem `highest_priority` estrito para controle total do admin?

5. **Escopo por tags:** Implementamos `Tags` nos itens/kits na v1 ou apenas IDs + categorias + `all_shop`?

6. **Recorrência:** Campanhas semanais (ex.: "sexta de desconto") são necessárias na v1 ou intervalo fixo basta?

7. **Colunas em `orders`:** Preferem migration DB com `base_price`/`promotion_id` ou apenas auditoria em `payload_json`?

8. **Pacotes com bônus de Âmbar:** Futuramente estender promoções a `PointPackages` (ex.: +10% Âmbar na doação) ou manter estritamente catálogo de resgate?

9. **Exibição de itens a 0 Âmbar:** Mostrar badge "PROMO" em itens já gratuitos ou ocultar?

10. **Limite global de resgates:** Necessário teto tipo "primeiros 100 resgates da promoção" (scarcity marketing)?

---

## 19. Fases de implementação (MVP vs completo)

### MVP (estimativa: 1 sprint)

| Componente | Entregável |
|------------|------------|
| Backend | `promotions.py`: resolve price, schedule, stacking |
| API | Estender `/api/catalog`, `/api/player/purchase` |
| API admin | CRUD básico `/api/promotions/*` |
| Config | `Promotions` + `PromotionSettings` em config.json |
| Sync | Chave em `SHARED_SYNC_TOP_LEVEL_KEYS` |
| UI web | Badge + preço riscado + filtro "Em promoção" |
| UI admin web | Lista + modal criar/editar |
| DB | `promotion_id` + `base_price` em `orders` (migration) |
| Testes | Unitários de pricing, schedule, stacking |
| Docs | CHANGELOG + este spec atualizado |

**Fora do MVP:** ASM panel, in-game, recorrência, buy-x-get-y, cupons, limits per player, stats dashboard.

### Versão completa (estimativa: +2 sprints)

| Componente | Entregável |
|------------|------------|
| ASM | Aba Promoções em `customshop_panel.py` |
| Relatórios | Stats, CSV, gráficos |
| In-game | C++ promo parity |
| Avançado | Recorrência, tags, limits, cupons |
| Home | Banner promocional |
| Countdown | Timer live no card |
| Buy-X-Get-Y | Se aprovado |

---

## 20. Plano de testes (outline)

### 20.1 Testes unitários (`promotions.py`)

| Caso | Assert |
|------|--------|
| `percentage` 25% em Price 1000 | promo_price == 750 |
| `fixed_price` 500 em Price 1000 | promo_price == 500 |
| `fixed_discount` 200 em Price 1000 | promo_price == 800 |
| Preço mínimo 0 | nunca negativo |
| Promoção expirada | promo não aplica |
| Promoção agendada (futuro) | promo não aplica |
| `disabled: false` | promo não aplica |
| Escopo por `categories` | só itens da categoria |
| Escopo `all_shop` + exclude licenças | licenças excluídas |
| Stacking duas promos | menor preço vence |
| Item Price 0 | permanece 0 |
| Kit acro_pack10 fixed_price | preço correto |

### 20.2 Testes de integração (`test_app.py`)

| Caso | Assert |
|------|--------|
| GET `/api/catalog` com promo ativa | campo `promotion.active` |
| POST purchase com promo | `points_spent` == promo_price |
| Purchase sem saldo (preço promo) | 402 |
| Cancel pending com promo | reembolso == points_spent promocional |
| Admin refund ENTREGUE | reembolso valor promocional |
| Promo expira entre catalog e purchase | 409 ou preço cheio |
| Idempotency retry | mesmo resultado |
| Kit limit + promo | limite respeitado, preço promocional |

### 20.3 Testes E2E manuais

1. Admin cria promo 20% → aparece no catálogo web
2. Jogador compra → saldo debitado corretamente
3. Pedido pendente → entrega in-game → status ENTREGUE
4. Desistência → reembolso promocional
5. Desativar promo → preços voltam após reload catalog
6. ASM salva config → webstore recebe via sync

### 20.4 Testes de regressão

- Compra sem promoções no config → idêntico ao comportamento atual
- FeaturedMaps, PointPackages, mercado P2P → inalterados
- Plugin pending/claim/delivered → inalterados

### 20.5 Testes de carga (opcional)

- Resolver preço para 5000 itens < 50ms
- Cache de promoções ativas em memória com invalidação no reload config

---

## Apêndice A — Mapa de arquivos afetados (implementação futura)

| Arquivo | Mudança prevista |
|---------|------------------|
| `plugin/arkshop_web/promotions.py` | **Novo** — motor de promoções |
| `plugin/arkshop_web/app.py` | Integrar pricing, CRUD, estender catalog/purchase |
| `plugin/arkshop_web/catalog_enrich.py` | Opcional: helper de display promo |
| `plugin/arkshop_web/static/index.html` | UI cards, admin, filtros |
| `plugin/arkshop_web/tests/test_promotions.py` | **Novo** |
| `plugin/arkshop_web/tests/test_app.py` | Casos de integração |
| `src/shop_integration.py` | `SHARED_SYNC_TOP_LEVEL_KEYS` |
| `src/pages/customshop_panel.py` | Aba admin (fase 2) |
| `plugin/CustomShop/configs/config.json` | Seção `Promotions` |
| `plugin/CustomShop/src/ShopStore.cpp` | Fase 3 in-game |
| `CHANGELOG.md` | Entrada na release |

## Apêndice B — Referências no código atual

| Conceito | Localização |
|----------|-------------|
| Preço catálogo | `app.py` → `_catalog_price()` |
| Compra web | `app.py` → `player_purchase()` |
| Catálogo público | `app.py` → `get_catalog()` |
| Enriquecimento UI | `catalog_enrich.py` → `enrich_catalog_payload()` |
| Limites de kit | `kit_limits.py` |
| Reembolso | `app.py` → `_order_refund_amount()`, `player_cancel_order()` |
| Pedidos plugin | `app.py` → `get_pending_deliveries()` |
| Compra in-game | `ShopStore.cpp` → `BuyItem()`, `BuyKit()` |
| Entrega web | `ShopStore.cpp` → `GiveItem()`, `GiveKit()` |
| Sync config | `shop_integration.py` → `SHARED_SYNC_TOP_LEVEL_KEYS` |
| Padrão admin CRUD | `app.py` → rotas `featured-maps` |
| Auditoria | `app.py` → `_audit_event()`, modelo `AuditEvent` |

---

*Documento gerado para discussão pré-implementação. Nenhuma alteração de código foi aplicada.*
