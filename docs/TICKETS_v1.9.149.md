# Sistema de Tickets — ARKLAND Web Store v1.9.149

Ecossistema de tickets que substitui **Mensagens do Sistema** no admin web. A edição de mensagens do plugin permanece apenas no app TEK (`customshop_panel`).

## Objetivo

Centralizar suporte jogador ↔ staff na loja web: abertura de ticket com categoria/prioridade, thread de mensagens, histórico de eventos, anexos, vínculo opcional com pedidos e Discord.

## Arquitetura

```
Jogador (Steam login)
    │
    ├─ GET  /api/tickets/meta          → categorias, prioridades, status (labels PT)
    ├─ POST /api/tickets               → cria ticket + 1ª mensagem (+ order_id opcional)
    ├─ GET  /api/tickets               → lista (abertos / encerrados)
    ├─ GET  /api/tickets/:id           → detalhe + thread + histórico + pedido
    ├─ GET  /api/tickets/:id/history   → histórico isolado
    ├─ POST /api/tickets/:id/reply     → resposta do jogador
    ├─ POST /api/tickets/:id/attachments
    └─ POST /api/tickets/discord-link  → vínculo manual

Admin (Steam admin)
    │
    ├─ GET  /api/admin/tickets              → fila (filtros: status, category, priority, q)
    ├─ GET  /api/admin/tickets/:id          → detalhe + histórico + resumo do pedido
    ├─ GET  /api/admin/tickets/:id/history
    ├─ POST /api/admin/tickets/:id/reply
    ├─ POST /api/admin/tickets/:id/status   → ABERTO | EM_ANALISE | AGUARDANDO_JOGADOR | ENCERRADO
    ├─ POST /api/admin/tickets/:id/priority → baixa | normal | urgente
    └─ POST /api/admin/tickets/:id/attachments
```

### Persistência (MySQL / SQLite)

| Tabela | Função |
|--------|--------|
| `support_tickets` | Cabeçalho: steam_id, nick, Discord, assunto, **categoria**, **prioridade**, **status**, **order_id**, admin atribuído |
| `support_ticket_messages` | Mensagens (player / admin / system), corpo, links JSON |
| `support_ticket_attachments` | Metadados de arquivo; binário em `{data}/ticket_uploads/{ticket_id}/` |
| `support_ticket_history` | Trilha de auditoria: criação, mudanças de status/prioridade, respostas, anexos, pedido vinculado |
| `support_ticket_discord_links` | Vínculo Steam ↔ Discord por jogador |

Modelos SQLAlchemy: `SupportTicket`, `SupportTicketMessage`, `SupportTicketAttachment`, `SupportTicketHistory`, `SupportTicketDiscordLink` em `app.py`.

Lógica de negócio: `ticket_service.py`  
Rotas HTTP: `ticket_routes.py`

### Categorias (UI em português)

| ID | Label |
|----|-------|
| `suporte` | Suporte |
| `bug` | Bug / erro |
| `doacao` | Doação |
| `recurso_ban` | Recurso de banimento |
| `resgate` | Resgate / entrega |
| `pagamento` | Pagamento |
| `mercado` | Mercado de dinos |
| `conta` | Conta / acesso |
| `geral` | Geral |
| `outro` | Outro |

### Prioridades

| ID | Label |
|----|-------|
| `baixa` | Baixa |
| `normal` | Normal (padrão) |
| `urgente` | Urgente |

### Status

| ID | Label |
|----|-------|
| `ABERTO` | Aberto |
| `EM_ANALISE` | Em análise |
| `AGUARDANDO_JOGADOR` | Aguardando jogador |
| `ENCERRADO` | Encerrado |

Status legados (`OPEN`, `IN_PROGRESS`, `CLOSED`) são migrados automaticamente na inicialização do schema.

### Histórico (`support_ticket_history`)

Eventos registrados:

- `created` — abertura do ticket
- `status_changed` — transição de status (admin)
- `priority_changed` — alteração de prioridade (admin)
- `reply_player` / `reply_admin` — novas mensagens
- `attachment_added` — upload de anexo
- `order_linked` — pedido vinculado na criação

Visível na UI do jogador (detalhe) e do admin (timeline acima da thread).

### Integração com pedidos

- Campo opcional `order_id` no `POST /api/tickets`
- Validação: pedido deve existir e pertencer ao `steam_id` do jogador
- Admin vê resumo (`item_id`, status, pontos, disputas) e link para detalhes completos do pedido

### Nick Steam

No create, `player_name` é resolvido via `_resolve_player_display_name` (store_users, mercado, players.json).

### Anexos

- Tipos: imagens (`image/*`) e PDF
- Tamanho máximo: 5 MB
- Links: até 10 URLs por mensagem (textarea, uma por linha)

## Frontend (`static/index.html`)

| Área | Página | Nav |
|------|--------|-----|
| Jogador | `#page-tickets` | Tickets (público, exige login) |
| Admin | `#page-tickets-admin` | Tickets (admin-only) |

Abas jogador: **Abertos**, **Encerrados**, **+ Novo ticket** (categoria, prioridade, pedido opcional).

Admin: filtros por status/categoria/prioridade, badges, timeline de histórico, painel de pedido vinculado, selects para status e prioridade.

## O que entra na 1.9.149

- [x] Schema + modelos + migrate idempotente (priority, order_id, history)
- [x] Categorias, prioridades e status estendidos
- [x] Histórico / audit trail por ticket
- [x] Vínculo opcional com pedidos da loja
- [x] CRUD básico (criar, listar, detalhe, responder, encerrar)
- [x] Upload de anexos (disco local)
- [x] Links em mensagens
- [x] Vínculo Discord manual
- [x] UI jogador + admin (fila + atendimento + histórico)
- [x] Testes unitários/HTTP (`tests/test_tickets.py`)
- [x] SQLite local por padrão (sem MariaDB obrigatório para dev)

## Fora de escopo (versões futuras)

- OAuth Discord (rotas stub retornam 501)
- Notificações (e-mail, Discord webhook, push in-game)
- SLA automático, macros de resposta
- Atribuição automática / round-robin entre admins
- Antivírus / moderação de anexos
- Painel de métricas e exportação
- Sincronização bidirecional com canal Discord de suporte

## Fluxo típico

1. Jogador faz login Steam → abre **Tickets** → opcionalmente salva Discord.
2. Cria ticket com categoria, prioridade, assunto, mensagem, pedido (se disputa) e anexos.
3. Admin filtra fila por categoria/prioridade/status.
4. Admin abre ticket → vê histórico e pedido vinculado → responde → **Em análise** → **Aguardando jogador** se necessário → **Encerrar**.
5. Jogador vê resposta e histórico na aba **Abertos**; após encerrar, ticket vai para **Encerrados**.

## Desenvolvimento local

### Testes automatizados

```bash
cd plugin/arkshop_web
pytest tests/test_tickets.py -q
```

Variáveis de teste: `ARKSHOP_SYNC_DB_MIGRATE=1`, `ARKSHOP_SKIP_DB_BOOT=1` (ver `tests/conftest.py`).

### Servidor standalone (SQLite)

Sem MariaDB configurado, o app usa SQLite em `{data}/orders.db` (padrão do arkshop_web):

```bash
cd plugin/arkshop_web
set ARKSHOP_WEB_SECRET=dev-secret-change-me
set PORT=5177
python app.py
```

Ou `start.bat` — abre `http://127.0.0.1:5177`.

1. Adicione seu SteamID64 em `data/admin_steamids.json` (ou copie de `admin_steamids.example.json`).
2. Faça login Steam (ou simule sessão em testes).
3. Navegue para **Tickets** (jogador) ou **Tickets — Suporte** (admin).
4. Crie um ticket de teste; use **+ Novo ticket** com categoria e prioridade.
5. Como admin, altere status/prioridade e verifique a timeline de histórico.

Para testar vínculo com pedido: crie um pedido via loja ou insira um registro em `orders` no SQLite, depois informe o `order_id` ao abrir o ticket.

### API rápida (curl)

```bash
# Metadados (público)
curl -s http://127.0.0.1:5177/api/tickets/meta

# Criar ticket (requer sessão Steam)
curl -s -X POST http://127.0.0.1:5177/api/tickets \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"subject":"Teste","body":"Olá","category":"suporte","priority":"normal"}'
```
