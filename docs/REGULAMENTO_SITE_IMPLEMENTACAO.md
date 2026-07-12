# Implementação do Regulamento na Web Store ARKLAND

| Campo | Valor |
|-------|-------|
| **Documento** | Especificação de implementação — Regulamento no site |
| **Versão do spec** | 1.0 |
| **Data** | 04 de julho de 2026 |
| **Regulamento de referência** | [`REGULAMENTO_SERVIDOR.md`](./REGULAMENTO_SERVIDOR.md) v1.1 |
| **Escopo** | Web Store (`plugin/arkshop_web`) — frontend SPA + backend Flask |
| **Fora de escopo (v1)** | Plugin C++ in-game, Discord bot, notificações push externas |

---

## Sumário

1. [Objetivo e escopo](#1-objetivo-e-escopo)
2. [UX — onde o jogador vê o regulamento](#2-ux--onde-o-jogador-vê-o-regulamento)
3. [Aceite obrigatório](#3-aceite-obrigatório)
4. [API e backend](#4-api-e-backend)
5. [Frontend](#5-frontend)
6. [Integração com tickets](#6-integração-com-tickets)
7. [Admin — painel e re-aceite](#7-admin--painel-e-re-aceite)
8. [Fases de implementação](#8-fases-de-implementação)
9. [Checklist de arquivos](#9-checklist-de-arquivos)
10. [Critérios de aceite e testes](#10-critérios-de-aceite-e-testes)

---

## 1. Objetivo e escopo

### 1.1 Objetivo

Publicar o **Regulamento Oficial do Cluster ARKLAND** na Web Store de forma acessível, versionada e auditável, e exigir **aceite explícito** vinculado ao **SteamID64** antes que o jogador utilize funcionalidades que dependem de conta (tickets, resgates, doações, mercado P2P, Minha Área).

O regulamento em [`REGULAMENTO_SERVIDOR.md`](./REGULAMENTO_SERVIDOR.md) já define:

- Regras PvE, conduta, exploits e punições (Seções 4–9);
- Uso do site, Âmbares, licenças **Gamma / Beta / Alfa / Nuvem** — sem nomenclatura VIP (Seção 8.5);
- Canal oficial de denúncias via tickets com **prova obrigatória** (Seção 10);
- Versionamento e comunicação de alterações (Seção 12).

Este spec descreve **como** espelhar isso na interface e no backend, reutilizando padrões existentes do portal.

### 1.2 Escopo funcional

| Incluído | Excluído (futuro) |
|----------|-------------------|
| Página/modal de leitura do regulamento | Bloqueio in-game no plugin CustomShop |
| Gate de aceite no 1º login (após Steam OpenID) | Aceite por mapa/servidor separado |
| Persistência de versão aceita por `steam_id` | Assinatura digital / e-mail |
| Re-aceite forçado quando `REGULAMENTO_VERSION` sobe | Tradução para outros idiomas |
| Categoria de ticket para denúncias + validação de prova | OCR / moderação automática de imagens |
| Painel admin: status de aceite e bump de versão | Publicação automática no Discord |

### 1.3 Princípios de design (alinhados ao repo)

- **SPA monolítica** em `static/index.html` — mesmo padrão de `openPolicyModal`, `display-name-gate` e `data-page` navigation.
- **Política de Doações** permanece documento **separado** (aceite em `localStorage`, chave `arkland_donation_policy_v1`). O regulamento é mais amplo; o aceite do regulamento **não substitui** o aceite da política de doação no fluxo PIX/resgate.
- Terminologia pública: **ARKLAND**, **Âmbares**, licenças **Alfa / Beta / Gamma / Nuvem** — nunca VIP.
- Auditoria via `audit_events` quando aplicável (re-aceite forçado, bump de versão).

---

## 2. UX — onde o jogador vê o regulamento

### 2.1 Mapa de superfícies

```
┌─────────────────────────────────────────────────────────────────┐
│  Visitante (sem login)                                          │
│  · Home → link "Regulamento do servidor"                        │
│  · Footer global → Regulamento | Política de Doações            │
│  · Página dedicada regulamento (leitura livre)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    Login Steam OpenID
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Jogador autenticado — 1º acesso ou versão desatualizada       │
│  · Modal gate regulamento (bloqueante, z-index > display-name)  │
│  · Checkbox + "Li e aceito o Regulamento vX.Y"                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    Aceite registrado no servidor
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Uso normal                                                     │
│  · Catálogo / Mercado / Tickets / Minha Área                    │
│  · Tickets → banner "Denúncias exigem prova" + link regulamento │
│  · Modal regulamento reaberto sob demanda (sem bloquear)        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Footer global (novo)

Hoje o site **não possui** rodapé legal fixo; a Política de Doações aparece no catálogo (`donation-policy-banner`) e na home (`openPolicyModal`).

**Proposta:** bloco `site-footer` fixo no final do `#main` (ou abaixo do conteúdo em todas as páginas), visível para logado e anônimo:

| Link | Ação |
|------|------|
| **Regulamento do servidor** | `goToPage('regulamento')` ou `openRegulamentoModal(false)` |
| **Política de Doações** | `openPolicyModal(false)` (existente) |
| **Suporte / Tickets** | `goToPage('tickets')` (login se necessário) |

Estilo: reutilizar tokens CSS existentes (`--border`, `--text2`, fonte 12px) — consistente com `home-commerce__footer`.

### 2.3 Página dedicada `regulamento`

Nova página SPA: `data-page="regulamento"` → `#page-regulamento`.

Conteúdo:

- Cabeçalho com versão e data (`REGULAMENTO_VERSION`, `REGULAMENTO_UPDATED_AT`);
- Corpo: HTML renderizado do regulamento (ver §5.3);
- Sumário âncora (links internos `#1-introdução`, etc.) espelhando o markdown fonte;
- CTA inferior: "Abrir ticket de suporte" → tickets; "Voltar à loja" → home.

**URL amigável (opcional fase 2):** `https://arkland.com.br/#/regulamento` ou rota Flask `GET /regulamento` que serve o mesmo `index.html` com hash — útil para compartilhar fora do portal.

### 2.4 Modal no primeiro login (gate)

Espelhar o padrão de `#display-name-gate` e `#modal-policy`:

| Elemento | Referência atual | Regulamento |
|----------|------------------|-------------|
| Overlay bloqueante | `#display-name-gate` (z-index 10050) | `#regulamento-gate` (z-index **10060**) |
| Aceite com checkbox | `#policy-accept-row` + `acceptDonationPolicy()` | Checkbox obrigatório + botão desabilitado até marcar |
| Persistência | `localStorage` (doações) | **Servidor** (`store_users` / API) |
| Momento de exibição | Após `bootPortal` → `playerNeedsDisplayName()` | Após auth OK; **antes ou depois** do nome de exibição (ver §3.2) |

Texto do gate (resumo, não substitui leitura):

> Ao usar a Web Store ARKLAND você concorda com o Regulamento do Servidor (PvE, conduta, mercado em Âmbares, licenças Gamma/Beta/Alfa/Nuvem e sistema de tickets). Menores de 16 anos não podem utilizar o ecossistema.

Botão secundário: "Ler regulamento completo" → expande scroll na mesma modal ou navega para `#page-regulamento`.

### 2.5 Integração no fluxo de tickets

Na página `#page-tickets`, painel **Novo ticket**:

1. **Banner informativo** (estilo `donation-policy-banner`) no topo:
   - Título: "Denúncias e disputas — regras do regulamento"
   - Texto: prova visual obrigatória (imagem ou vídeo/link); denúncias sem prova podem ser arquivadas (Seção 10.2).
   - Link: "Ler Seção 10 do regulamento" → `goToPage('regulamento')` com âncora `#10-denúncias-e-tickets-de-suporte`.

2. Ao selecionar categoria **Denúncia / conduta** (nova, ver §6): destacar campo de anexos e links como **obrigatórios** (validação client + server).

### 2.6 Outros pontos de descoberta

| Local | Ação |
|-------|------|
| Home — pilar "Transparência" | Adicionar menção ao regulamento + link |
| Catálogo — ao lado de "Política" | Botão "📋 Regulamento" |
| Mercado P2P — banner de regras | Link "Regras completas no regulamento §8.7" (solteiros, casal M+F, contribuição 40% ao prêmio do Sorteio — ver §8.7.3–8.7.4) |
| Minha Área | Linha "Regulamento aceito: v1.1 em DD/MM/AAAA" |

---

## 3. Aceite obrigatório

### 3.1 Regra de negócio

| Condição | Comportamento |
|----------|---------------|
| Visitante não autenticado | Pode ler regulamento; não grava aceite |
| Login Steam, `regulamento_accepted_version` **nulo** ou **< `REGULAMENTO_VERSION`** | Exibir gate bloqueante |
| Admin / support com versão desatualizada | **Mesma regra** (staff também aceita; evita ambiguidade legal) |
| Versão aceita == versão vigente | Acesso normal; `needs_regulamento_accept: false` em `/api/auth/me` |
| Admin incrementa `REGULAMENTO_VERSION` | Todos os jogadores com versão anterior precisam re-aceitar no próximo login |

**Não** usar apenas `localStorage` para o regulamento (diferente da política de doações): aceite deve ser **provável em auditoria** e sobreviver a troca de dispositivo.

### 3.2 Ordem dos gates no boot

Sequência recomendada em `bootPortal()` após `loadAuth()`:

1. **Regulamento** (se `needs_regulamento_accept`) — gate legal cluster-wide;
2. **Nome de exibição** (`needs_display_name`) — requisito do mercado;
3. Restante do boot (catálogo, home, etc.).

Justificativa: o aceite do regulamento é pré-requisito de **qualquer** uso autenticado; o nome de exibição é requisito de comércio mas não de tickets de suporte genérico — porém manter regulamento primeiro simplifica a UX (um modal legal antes de cadastros).

### 3.3 UI do aceite

```
┌──────────────────────────────────────────────┐
│  📋 Regulamento ARKLAND — versão 1.0         │
│  [área scroll com texto ou resumo + link]    │
│                                              │
│  ☐ Declaro ter 16 anos ou mais e li/aceito   │
│    o Regulamento do Servidor ARKLAND (v1.0)  │
│                                              │
│  [Cancelar / Sair]  [Aceitar e continuar]    │
└──────────────────────────────────────────────┘
```

- **Cancelar:** logout (`/api/auth/logout`) ou permanece bloqueado (não fecha overlay sem aceitar).
- **Aceitar:** `POST /api/regulamento/accept` com `{ "version": "1.0" }`.
- Registrar `ip_address` e `user_agent` no aceite (auditoria).

### 3.4 Versionamento — `REGULAMENTO_VERSION`

Constante única no backend (e espelhada no frontend para exibição):

```python
# plugin/arkshop_web/regulamento_config.py (novo)
REGULAMENTO_VERSION = "1.1"
REGULAMENTO_UPDATED_AT = "2026-07-12"
REGULAMENTO_SOURCE_DOC = "docs/REGULAMENTO_SERVIDOR.md"
```

| Evento | Ação |
|--------|------|
| Edição editorial sem mudança de regras | Manter versão; atualizar só `REGULAMENTO_UPDATED_AT` (opcional) |
| Mudança material de regras | Incrementar versão minor (`1.0` → `1.1`) |
| Reestruturação maior | Major (`1.x` → `2.0`) |
| Publicação | Sincronizar cabeçalho de `REGULAMENTO_SERVIDOR.md` + comunicado (notificação in-app fase 2) |

**Fonte de verdade:** o markdown em `docs/REGULAMENTO_SERVIDOR.md`; a constante Python deve ser bumpada **no mesmo commit** que altera o regulamento.

---

## 4. API e backend

### 4.1 Modelo de dados

**Opção recomendada:** colunas em `store_users` (já existe por SteamID no primeiro login).

```sql
ALTER TABLE store_users
  ADD COLUMN regulamento_accepted_version VARCHAR(16) NULL,
  ADD COLUMN regulamento_accepted_at DATETIME NULL;
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `regulamento_accepted_version` | `VARCHAR(16) NULL` | Ex.: `"1.0"` — última versão aceita |
| `regulamento_accepted_at` | `DATETIME NULL` | Timestamp UTC do aceite |

Migração: seguir padrão `_ensure_store_users_schema()` em `app.py` (ALTER incremental MySQL).

**Tabela opcional de histórico (fase 3):**

```sql
CREATE TABLE regulamento_acceptance_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  steam_id VARCHAR(32) NOT NULL,
  version VARCHAR(16) NOT NULL,
  accepted_at DATETIME NOT NULL,
  ip_address VARCHAR(45) NULL,
  user_agent VARCHAR(512) NULL,
  INDEX idx_steam (steam_id),
  INDEX idx_accepted (accepted_at)
);
```

Cada aceite (incluindo re-aceites) insere uma linha; `store_users` mantém o estado atual.

### 4.2 Endpoints sugeridos

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/api/regulamento/meta` | Público | `{ version, updated_at, title, sections[] }` |
| `GET` | `/api/regulamento/content` | Público | HTML ou markdown do regulamento vigente |
| `GET` | `/api/regulamento/status` | Jogador | `{ current_version, accepted_version, needs_accept }` |
| `POST` | `/api/regulamento/accept` | Jogador | Body: `{ "version": "1.0" }` — valida == vigente |
| `GET` | `/api/admin/regulamento/acceptances` | Admin | Lista paginada + filtros (versão, pendente) |
| `POST` | `/api/admin/regulamento/bump-version` | Admin | Body: `{ "version": "1.1", "notify": true }` — só metadado; bump manual da constante no deploy |

**Extensão de `/api/auth/me`:**

```json
{
  "authenticated": true,
  "steam_id": "7656119…",
  "needs_regulamento_accept": true,
  "regulamento_version_current": "1.0",
  "regulamento_version_accepted": null
}
```

Helpers em `app.py` (espelhar `_auth_display_name_fields`, `_guard_player_display_name`):

- `_auth_regulamento_fields(steam_id) -> dict`
- `_guard_regulamento_accepted(steam_id) -> Response | None` — retorna 403 JSON se pendente

### 4.3 Guards em rotas sensíveis

Aplicar `_guard_regulamento_accepted` nas mesmas rotas que já usam `_guard_player_display_name` **ou** em camada mais ampla:

| Área | Guard regulamento | Guard display name |
|------|-------------------|-------------------|
| `POST /api/tickets` | Sim | Não (tickets após regulamento) |
| Resgates / doações / mercado | Sim | Sim |
| `GET /api/regulamento/*` | Não | Não |
| Admin | Não (admin bypass opcional apenas para `bump-version`) | Não |

Ordem dos guards: **regulamento → display name → site_access_blocked**.

### 4.4 Entrega do conteúdo

| Abordagem | MVP | Completo |
|-----------|-----|----------|
| HTML estático embutido em `regulamento_content.html` | ✓ | |
| Cópia gerada de `REGULAMENTO_SERVIDOR.md` no build | | ✓ |
| Render markdown runtime (`markdown` lib) | | opcional |

**MVP:** arquivo `static/regulamento_v1_0.html` (fragmento body) servido por `GET /api/regulamento/content` ou `/static/regulamento_v1_0.html`.

**Completo:** script `scripts/build_regulamento_html.py` que converte o `.md` → HTML no CI/release, garantindo que site e repo não divergem.

### 4.5 Auditoria

Em `POST /api/regulamento/accept`:

```python
_audit(
    event_type="regulamento_accepted",
    actor_steam_id=steam_id,
    message=f"Regulamento v{version}",
    payload_json={"version": version},
)
```

Em admin bump / re-aceite forçado:

```python
event_type="regulamento_version_bumped"
```

---

## 5. Frontend

### 5.1 Componentes (dentro de `index.html`)

| ID / função | Descrição |
|-------------|-----------|
| `#page-regulamento` | Página SPA com conteúdo completo |
| `#regulamento-gate` | Modal bloqueante pós-login |
| `openRegulamentoModal(readOnly)` | Igual `openPolicyModal` |
| `acceptRegulamento()` | POST accept + fecha gate + refresh `_auth` |
| `playerNeedsRegulamentoAccept()` | `needs_regulamento_accept` do `_auth` |
| `guardRegulamento(context)` | Toast + abre gate; usado em `nav()` e ações críticas |
| `loadRegulamentoContent()` | Fetch HTML e injeta em `#regulamento-body` |

CSS: reutilizar `.policy-modal-body`, `.modal-backdrop`, `.donation-policy-banner`.

### 5.2 Navegação

Adicionar item de menu **opcional** (pode ser só footer para não poluir sidebar):

```html
<div class="nav-item" data-page="regulamento" onclick="nav(this)">
  <span class="nav-icon">📋</span> Regulamento
</div>
```

Em `nav(el)`:

```javascript
if (page === "regulamento") loadRegulamentoPage();
```

Em `bootPortal()` — após `loadAuth()`:

```javascript
if (playerNeedsRegulamentoAccept()) {
  showRegulamentoGate();
  return; // adia catálogo até aceitar (ou carrega catálogo em paralelo somente leitura)
}
```

### 5.3 Render: markdown vs HTML estático

| Critério | HTML estático | Markdown runtime |
|----------|---------------|------------------|
| Consistência com `REGULAMENTO_SERVIDOR.md` | Requer build/sync | Automática se ler .md |
| Performance | Melhor | Parse no servidor |
| Padrão atual do site | **Igual Política de Doações** (HTML inline) | Novo |
| SEO / âncoras | Controle total | Depende do renderer |

**Recomendação:** MVP com HTML estático gerado manualmente do v1.0; fase 2 com script de build a partir do markdown fonte.

### 5.4 Estado `_auth`

Estender objeto global:

```javascript
let _auth = {
  // …existente…
  needs_regulamento_accept: false,
  regulamento_version_current: null,
  regulamento_version_accepted: null,
};
```

Atualizar em `loadAuth()` e após `acceptRegulamento()`.

### 5.5 Separação Política de Doações × Regulamento

| Documento | Escopo | Aceite |
|-----------|--------|--------|
| Política de Doações | PIX, cartão, sem reembolso, dados MP | `localStorage` + modal no checkout |
| Regulamento | Cluster PvE, conduta, mercado, licenças, tickets | Servidor por `steam_id` |

Fluxo doação/resgate: **ambos** podem ser exigidos (regulamento no login; política no primeiro PIX/resgate).

---

## 6. Integração com tickets

### 6.1 Nova categoria `denuncia`

Alinhar [`REGULAMENTO_SERVIDOR.md` §10.3](./REGULAMENTO_SERVIDOR.md) com `ticket_service.py`:

```python
TICKET_CATEGORIES = frozenset({
    # …existentes…
    "denuncia",  # Denúncia de jogador / conduta
})
TICKET_CATEGORY_LABELS = {
    # …
    "denuncia": "Denúncia de conduta",
}
```

Posição no `<select id="tickets-new-category">`: após "Suporte", antes de "Bug".

### 6.2 Validação de prova obrigatória

Categorias que exigem prova (Seção 10.2):

| Categoria | Prova obrigatória |
|-----------|-------------------|
| `denuncia` | Sim — anexo imagem/PDF **ou** link de vídeo |
| `recurso_ban` | Recomendado; regulamento pede provas ao alegar erro |
| `mercado` | Se disputa P2P — anexo ou link |
| `suporte`, `bug`, `doacao`, etc. | Opcional (comportamento atual) |

**Backend** (`create_ticket` em `ticket_service.py`):

```python
_PROOF_REQUIRED_CATEGORIES = frozenset({"denuncia"})

def _validate_ticket_proof(category, attachments, links) -> str | None:
    if category not in _PROOF_REQUIRED_CATEGORIES:
        return None
    has_file = bool(attachments)
    has_video_link = any(_looks_like_video_url(u) for u in links)
    if not has_file and not has_video_link:
        return "Denúncias exigem imagem/PDF anexo ou link de vídeo (YouTube, Medal, etc.)."
    return None
```

**Frontend** (`ticketsCreateNew`): mesma validação antes do POST; exibir hint dinâmico ao mudar categoria.

### 6.3 UX no formulário

Quando `category === "denuncia"`:

- Borda destacada no campo anexos;
- Placeholder da mensagem: "Descreva o que, quando, onde (mapa) e quem (SteamID ou nick)…";
- Checkbox: "Confirmo que as provas são autênticas" (opcional fase 2);
- Link para regulamento §10.

### 6.4 Staff

No painel `tickets-admin`, filtro por categoria já suporta novas entradas via `ticket_meta()`.

Badge visual: denúncias sem anexo no momento da criação **não devem ocorrer** se validação estiver ativa; tickets legados permanecem.

---

## 7. Admin — painel e re-aceite

### 7.1 Visão em Jogadores (players-admin)

Na ficha do jogador (`selectPlayerAdmin`), nova seção:

| Campo | Exemplo |
|-------|---------|
| Regulamento aceito | v1.0 em 04/07/2026 14:32 UTC |
| Status | ✓ Em dia / ⚠ Pendente (v1.1) |

Ações admin (fase 2):

- **Forçar re-aceite:** zera `regulamento_accepted_version` para o jogador (próximo login exige gate).
- **Registrar aceite manual:** apenas com motivo auditado (caso excepcional).

### 7.2 Relatório global (fase 2)

Nova subpágina admin ou card em `general`:

- Total de contas com aceite na versão vigente;
- Lista de pendências (login recente mas versão nula);
- Botão "Exigir re-aceite de todos" → zera coluna + dispara notificação in-app (`notification_service`).

### 7.3 Bump de versão (processo operacional)

1. Editar `docs/REGULAMENTO_SERVIDOR.md` (cabeçalho versão);
2. Bump `REGULAMENTO_VERSION` em `regulamento_config.py`;
3. Regenerar HTML estático (se aplicável);
4. Deploy Web Store;
5. (Fase 2) `POST /api/admin/regulamento/notify-bump` — notificação: "Regulamento atualizado para v1.1 — aceite na próxima visita";
6. Comunicado Discord / aviso in-game conforme Seção 12.1.

**Não** apagar aceites antigos no log — apenas invalidar comparando versão.

---

## 8. Fases de implementação

### Fase 1 — MVP (leitura + aceite básico)

- [ ] `regulamento_config.py` com `REGULAMENTO_VERSION = "1.0"`
- [ ] Migração `store_users` (duas colunas)
- [ ] `GET /api/regulamento/meta`, `POST /api/regulamento/accept`
- [ ] Extensão `/api/auth/me` com `needs_regulamento_accept`
- [ ] `#page-regulamento` com HTML estático v1.0
- [ ] `#regulamento-gate` no boot (autenticados)
- [ ] Link no footer + catálogo
- [ ] Testes unitários aceite + auth

**Entregável:** jogador autenticado não usa tickets/resgates sem aceitar v1.0.

### Fase 2 — Tickets e guards completos

- [ ] Categoria `denuncia` + validação prova
- [ ] Banner regulamento na página tickets
- [ ] `_guard_regulamento_accepted` em rotas de resgate, mercado, doação
- [ ] Minha Área: status do aceite
- [ ] Painel players-admin: exibir versão aceita
- [ ] Testes `test_tickets.py` para prova obrigatória

### Fase 3 — Admin, re-aceite e sync markdown

- [ ] `regulamento_acceptance_log` + relatório admin
- [ ] Forçar re-aceite individual / em massa
- [ ] Script build markdown → HTML
- [ ] Notificação in-app em bump de versão
- [ ] URL pública `/#/regulamento` ou rota dedicada

### Fase 4 — Polimento (opcional)

- [ ] Aceite de idade (16+) como campo separado auditável
- [ ] Export CSV aceites para compliance
- [ ] Integração changelog (`CHANGELOG.md` / `version.json`)

---

## 9. Checklist de arquivos

| Arquivo | Alteração |
|---------|-----------|
| `docs/REGULAMENTO_SITE_IMPLEMENTACAO.md` | Este spec |
| `docs/REGULAMENTO_SERVIDOR.md` | Fonte de conteúdo; bump versão quando mudar regras |
| `plugin/arkshop_web/regulamento_config.py` | **Novo** — constantes de versão |
| `plugin/arkshop_web/regulamento_service.py` | **Novo** — lógica aceite, meta, guards |
| `plugin/arkshop_web/regulamento_routes.py` | **Novo** — blueprint Flask (ou rotas em `app.py`) |
| `plugin/arkshop_web/app.py` | Modelo `StoreUser`, `_ensure_store_users_schema`, `auth_me`, guards, register blueprint |
| `plugin/arkshop_web/ticket_service.py` | Categoria `denuncia`, `_validate_ticket_proof` |
| `plugin/arkshop_web/ticket_routes.py` | Passar validação no POST create |
| `plugin/arkshop_web/static/index.html` | Página, gate, footer, JS, guards UI, tickets banner |
| `plugin/arkshop_web/static/regulamento_v1_0.html` | **Novo** — fragmento HTML (MVP) |
| `plugin/arkshop_web/tests/test_regulamento.py` | **Novo** — aceite, auth, guards |
| `plugin/arkshop_web/tests/test_tickets.py` | Casos denúncia sem prova |
| `scripts/build_regulamento_html.py` | **Novo** (fase 3) — md → html |
| `CHANGELOG.md` | Entrada por release |
| `version.json` / `src/version.py` | Versão do app quando publicar feature |

**Não alterar nesta feature:** `plugin/CustomShop/*` (in-game), política de doações existente (salvo links cruzados).

---

## 10. Critérios de aceite e testes

### 10.1 Critérios de aceite (produto)

1. Visitante anônimo abre regulamento completo sem login.
2. Jogador no primeiro login Steam vê gate bloqueante até aceitar v1.0.
3. Aceite persiste no banco; novo dispositivo não reexige se versão vigente já aceita.
4. Admin sobe `REGULAMENTO_VERSION` → jogador existente vê gate no próximo `loadAuth`.
5. Ticket categoria `denuncia` sem anexo e sem link de vídeo é **rejeitado** (400) com mensagem em PT-BR citando regulamento.
6. Ticket `denuncia` com imagem anexa é criado com sucesso.
7. Política de Doações continua funcionando independentemente (`openPolicyModal`, PIX).
8. Textos públicos usam **Gamma/Beta/Alfa/Nuvem** — sem VIP.
9. `/api/auth/me` retorna `needs_regulamento_accept` coerente com o banco.

### 10.2 Testes automatizados sugeridos

```python
# test_regulamento.py
def test_meta_public():
    r = client.get("/api/regulamento/meta")
    assert r.json["version"] == "1.0"

def test_accept_requires_login():
    assert client.post("/api/regulamento/accept", json={"version": "1.0"}).status_code == 401

def test_accept_persists(client_logged_in):
    client_logged_in.post("/api/regulamento/accept", json={"version": "1.0"})
    me = client_logged_in.get("/api/auth/me").json
    assert me["needs_regulamento_accept"] is False

def test_guard_blocks_ticket_if_pending(client_logged_in_no_accept):
    r = client_logged_in_no_accept.post("/api/tickets", json={...})
    assert r.status_code == 403

# test_tickets.py
def test_denuncia_without_proof_rejected():
    r = client.post("/api/tickets", json={"category": "denuncia", "subject": "x", "body": "y"})
    assert "prova" in r.json["error"].lower()
```

### 10.3 Testes manuais (QA)

| # | Passo | Resultado esperado |
|---|-------|-------------------|
| 1 | Abrir site sem login → Regulamento | Conteúdo visível, sem gate |
| 2 | Login conta nova | Gate regulamento aparece |
| 3 | Aceitar → navegar Tickets | Formulário acessível |
| 4 | Novo ticket → Denúncia, sem anexo | Erro client + server |
| 5 | Denúncia com screenshot | Ticket criado |
| 6 | Doar PIX (1ª vez) | Política de doações **ainda** exigida |
| 7 | Admin: ver jogador | Versão aceita exibida |
| 8 | Bump versão em dev | Gate reaparece |

### 10.4 Regressão

- `display-name-gate` continua após regulamento aceito;
- Staff `tickets-admin` acessível com regulamento aceito;
- `site_access_blocked` ainda prevalece sobre tudo;
- Boot público (home/catálogo sem DB) não quebra — endpoints de regulamento meta/content estáticos não dependem de MariaDB.

---

## Referências cruzadas

| Documento | Relação |
|-----------|---------|
| [`REGULAMENTO_SERVIDOR.md`](./REGULAMENTO_SERVIDOR.md) | Conteúdo legal fonte |
| [`PROJETO_ARKLAND_MASTER.md`](./PROJETO_ARKLAND_MASTER.md) | Visão do ecossistema |
| `plugin/arkshop_web/static/index.html` | Padrões UI (`openPolicyModal`, `display-name-gate`, tickets) |
| `plugin/arkshop_web/ticket_service.py` | Categorias e anexos atuais |

---

*ARKLAND — Comunidade PvE. Este spec não substitui o regulamento; em caso de conflito prevalece `REGULAMENTO_SERVIDOR.md`.*

**Fim do spec — v1.0**
