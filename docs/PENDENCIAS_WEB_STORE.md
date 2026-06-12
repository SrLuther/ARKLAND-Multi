# Pendências — Integração Web Store / Banco de Dados / CustomShop

**Última atualização:** 12/06/2026 01:09  
**Sessão de trabalho:** Correções de integração Loja ↔ BD ↔ Web ↔ Plugin

---

## Status das Correções

| # | ID | Descrição | Status |
|---|----|-----------|--------|
| 1 | fix-schema | Normalizar `Items` ↔ `ShopItems` entre app e web (`app.py` + `index.html`) | ✅ Concluído |
| 2 | fix-catalog-api | Endpoint `GET /api/catalog` público; `index.html` usa este endpoint | ✅ Concluído |
| 3 | fix-db-name | Default `arkshop` → `arkland_shop`; auto-preencher credenciais do DB Manager | ✅ Concluído |
| 4 | fix-orders-schema | Dropar tabelas com schema errado e deixar SQLAlchemy recriar | ✅ Concluído |
| 5 | fix-debit-points | Débito de pontos em `player_purchase` após criar pedido | ✅ Concluído |
| 6 | fix-buy-button | Botão "🛒 Comprar" no catálogo com modal de confirmação e saldo | ✅ Concluído |
| 7 | fix-balance-display | Exibir saldo de pontos em "Minha Área" e atualizar após compra | ✅ Concluído |
| 8 | fix-plugin-endpoints | Revisar `/api/pending` e `/api/pending/delivered` para formato CustomShop.dll | ✅ Verificado — endpoints OK |
| 9 | fix-autostart-webstore | Web Store iniciar automaticamente ao abrir o app (sem precisar abrir aba Loja) | ✅ Corrigido — aplicado em `app_tek.py` + log file de módulo |

---

## Detalhes das Pendências

### 8 — Endpoints para o plugin CustomShop.dll (`fix-plugin-endpoints`)

O plugin CustomShop.dll busca pedidos pendentes e confirma entrega via HTTP.  
**Verificar:** `GET /api/pending?server_id=X` e `POST /api/pending/delivered` estão no formato correto?

**Arquivo:** `plugin/arkshop_web/app.py`  
**Endpoints a revisar:**
- `GET /api/pending` — retorna lista de pedidos pendentes para o plugin entregar
- `POST /api/pending/delivered` — plugin confirma que entregou um pedido

**Formato esperado pelo CustomShop.dll** (a confirmar com a DLL):
```json
// GET /api/pending
[
  { "order_id": "uuid", "steam_id": "...", "item_id": "...", "amount": 1 }
]

// POST /api/pending/delivered
{ "order_ids": ["uuid1", "uuid2"] }
```

---

### 9 — Auto-start da Web Store (`fix-autostart-webstore`)

**Objetivo:** A Web Store deve iniciar automaticamente ~3 segundos após o app abrir, sem precisar navegar para a aba da Loja.

**Implementação atual:**
- `src/app.py` → `self.after(3000, self._auto_start_webstore)`
- `src/app.py` → método `_auto_start_webstore` chama `from .pages.customshop_panel import auto_start_webstore`
- `src/pages/customshop_panel.py` → função `auto_start_webstore(app)` usa `get_shop_subprocess_env` e `subprocess.Popen`

**Problema:** Ainda falha silenciosamente. Logging adicionado para capturar o erro na próxima execução.

**Para debugar:** Verificar console/logs do app na próxima sessão para ver a exceção real.

**Possíveis causas:**
1. `shop.mode` não é `"host"` (valor padrão ou outro)
2. `get_shop_subprocess_env` retornando env inválido
3. Problema de timing (módulo não totalmente inicializado em 3s)

---

## Arquivos Modificados Nesta Sessão

| Arquivo | Mudanças |
|---------|----------|
| `plugin/arkshop_web/app.py` | Schema normalization, `_resolve_database_url` prioriza settings.json, startup com senha descriptografada, endpoint `/api/catalog` público, endpoint `/api/db/test`, débito de pontos em `player_purchase`, retorna `new_balance` |
| `plugin/arkshop_web/static/index.html` | `loadCatalog` usa `/api/catalog`, `nav()` recarrega Minha Área, `saveSettings` chama `loadMyArea`, botão "Comprar" nos cards, modal de confirmação, exibe saldo em Minha Área |
| `src/shop_integration.py` | `build_orders_database_url` lê credenciais do DB Manager como fallback; `_db_manager_prefs()` helper |
| `src/pages/customshop_panel.py` | Campos "Banco de Pedidos" pré-preenchem com prefs do DB Manager; `auto_start_webstore()` pública; auto-start removido da aba (movido para boot do app) |
| `src/app.py` | `self.after(3000, self._auto_start_webstore)`; método `_auto_start_webstore` |

---

## Notas Técnicas Importantes

### Senha criptografada no settings.json
A senha do banco em `plugin/arkshop_web/settings.json` é criptografada via `_encrypt_value`.  
Ao ler para conexão, usar `_load_settings()` (descriptografa) e NÃO `_load_state_settings_snapshot()` (retorna valor criptografado).  
**Corrigido em:** startup do `app.py` — descriptografa manualmente antes de passar para `_build_database_url_from_settings`.

### Schema das tabelas (orders)
As tabelas `orders`, `order_attempts`, `rebuys`, `disputes` foram criadas pelo `setup_db.sql` com schema diferente do modelo SQLAlchemy.  
**Solução:** Dropadas manualmente e SQLAlchemy recriou com schema correto.  
**Ação futura:** Remover criação dessas tabelas do `setup_db.sql` para evitar conflito.

### Prioridade de conexão do banco (web store)
Ordem correta:
1. `settings.json` (salvo pelo usuário via web UI) — tem senha descriptografada
2. `ARKSHOP_DATABASE_URL` env var (gerado automaticamente pelo app desktop — pode não ter senha)
3. SQLite fallback

### Auto-start da Web Store
Depende de `shop.mode == "host"` e `_is_web_running() == False`.  
O `_web_process` é variável de módulo em `customshop_panel.py` — resetada a cada reinício do app.

---

## Como Continuar

1. Abrir o app e verificar logs do console para ver erro do `auto_start_webstore`
2. Implementar `fix-plugin-endpoints` (verificar formato dos endpoints para CustomShop.dll)
3. Resolver auto-start definitivamente
4. Fazer testes de compra end-to-end (Web → BD → Plugin → ARK)
5. Commit e release quando tudo estiver funcional
