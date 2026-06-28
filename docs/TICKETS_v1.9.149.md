# Sistema de Tickets — ARKLAND Web Store v1.9.149

Esboço inicial (MVP) do ecossistema de tickets que substitui **Mensagens do Sistema** no admin web. A edição de mensagens do plugin permanece apenas no app TEK (`customshop_panel`).

## Objetivo

Centralizar suporte jogador ↔ staff na loja web: abertura de ticket, thread de mensagens, anexos e vínculo opcional com Discord.

## Arquitetura

```
Jogador (Steam login)
    │
    ├─ POST /api/tickets              → cria ticket + 1ª mensagem
    ├─ GET  /api/tickets              → lista (abertos / encerrados)
    ├─ GET  /api/tickets/:id          → detalhe + thread
    ├─ POST /api/tickets/:id/reply    → resposta do jogador
    ├─ POST /api/tickets/:id/attachments
    └─ POST /api/tickets/discord-link → vínculo manual (MVP)

Admin (Steam admin)
    │
    ├─ GET  /api/admin/tickets              → fila
    ├─ GET  /api/admin/tickets/:id          → detalhe
    ├─ POST /api/admin/tickets/:id/reply    → resposta staff
    ├─ POST /api/admin/tickets/:id/status   → OPEN | IN_PROGRESS | CLOSED
    └─ POST /api/admin/tickets/:id/attachments
```

### Persistência (MySQL / SQLite)

| Tabela | Função |
|--------|--------|
| `support_tickets` | Cabeçalho: steam_id, nick, Discord, assunto, status, admin atribuído |
| `support_ticket_messages` | Mensagens (player / admin / system), corpo, links JSON |
| `support_ticket_attachments` | Metadados de arquivo; binário em `{data}/ticket_uploads/{ticket_id}/` |
| `support_ticket_discord_links` | Vínculo Steam ↔ Discord por jogador |

Modelos SQLAlchemy: `SupportTicket`, `SupportTicketMessage`, `SupportTicketAttachment`, `SupportTicketDiscordLink` em `app.py`.

Lógica de negócio: `ticket_service.py`  
Rotas HTTP: `ticket_routes.py`

### Nick Steam

No create, `player_name` é resolvido via `_resolve_player_display_name` (store_users, mercado, players.json).

### Anexos (MVP)

- Tipos: imagens (`image/*`) e PDF
- Tamanho máximo: 5 MB
- Links: até 10 URLs por mensagem (textarea, uma por linha)

## Frontend (`static/index.html`)

| Área | Página | Nav |
|------|--------|-----|
| Jogador | `#page-tickets` | Tickets (público, exige login) |
| Admin | `#page-tickets-admin` | Tickets (admin-only) |

Removido do web admin: `#page-messages`, nav **Mensagens do Sistema**, `renderMessages()` / `saveMessages()`.

Abas jogador: **Abertos**, **Encerrados**, **+ Novo ticket**.

## O que entra na 1.9.149 (este esboço)

- [x] Schema + modelos + migrate idempotente
- [x] CRUD básico (criar, listar, detalhe, responder, encerrar)
- [x] Upload de anexos (disco local)
- [x] Links em mensagens
- [x] Vínculo Discord manual
- [x] UI jogador + admin (fila + atendimento)
- [x] Testes unitários/HTTP mínimos (`tests/test_tickets.py`)
- [x] Remoção limpa da UI web de Mensagens do Sistema

## Fora de escopo (versões futuras)

- OAuth Discord (rotas stub retornam 501)
- Notificações (e-mail, Discord webhook, push in-game)
- SLA, prioridade, tags, macros de resposta
- Atribuição automática / round-robin entre admins
- Antivírus / moderação de anexos
- Painel de métricas e exportação
- Integração com disputas de pedidos existentes
- Sincronização bidirecional com canal Discord de suporte

## Fluxo típico

1. Jogador faz login Steam → abre **Tickets** → opcionalmente salva Discord.
2. Cria ticket com assunto, mensagem, links e anexos.
3. Admin vê fila em **Tickets** (antiga área de Mensagens).
4. Admin abre ticket → responde → marca **Em atendimento** → **Encerrar** quando resolvido.
5. Jogador vê resposta na aba **Abertos**; após encerrar, ticket vai para **Encerrados**.

## Desenvolvimento local

```bash
cd plugin/arkshop_web
pytest tests/test_tickets.py -q
```

Variáveis de teste: `ARKSHOP_SYNC_DB_MIGRATE=1`, `ARKSHOP_SKIP_DB_BOOT=1` (ver `tests/conftest.py`).
