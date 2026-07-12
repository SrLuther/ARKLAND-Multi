# Debug ARKLAND — plugins (CustomShop / CustomDinoDeliver)

Sistema de debug **independente do log ArkApi**, com ficheiro JSONL, ring buffer in-memory e persistência MySQL (ou HTTP ingest) para a web Admin.

## Onde ficam os logs

| Plugin | Ficheiro |
|--------|----------|
| CustomShop | `ArkApi/Plugins/CustomShop/logs/arkland_debug.log` |
| CustomDinoDeliver | `ArkApi/Plugins/CustomDinoDeliver/logs/arkland_debug.log` |

Rotação: quando o ficheiro ultrapassa `MaxFileBytes` (default 10 MB), roda para `arkland_debug.1.log` … até `MaxFiles`.

Formato: **JSONL** (uma linha JSON por evento) com `ts`, `plugin`, `version`, `level`, `category`, `steam_id`, `server_id`, `order_id`, `correlation_id`, `message`, `fields`.

## Como activar (temporário / TRACE)

Em `config.json` do plugin (secção top-level `Debug`):

```json
"Debug": {
  "Enabled": true,
  "Level": "TRACE",
  "Categories": ["*"],
  "MySqlPersist": true,
  "MySqlMinLevel": "WARN"
}
```

Depois: `Shop.Reload` / `DinoDeliver.Reload` (ou reiniciar o mapa).

**Produção:** `Enabled: false` (default). Mesmo assim, eventos **WARN/ERROR** das categorias críticas do CustomShop continuam a ir para MySQL (`arkland_plugin_debug`) para a web Admin — sem spammar ficheiro TRACE.

Override runtime (sem editar JSON):

- CustomShop: `Shop.DebugLevel trace` / `Shop.DebugLevel off`
- CustomDinoDeliver: `DinoDeliver.DebugLevel trace`
- Chat: `/shopdebug` ou `/dinodebug` — status + últimas linhas do ring buffer

## Níveis e categorias

Níveis: `ERROR` / `WARN` / `INFO` / `DEBUG` / `TRACE`.

Categorias comuns: `TribeSync`, `Http`, `MySQL`, `Shop`, `License`, `Permissions`, `Deliver`, `DinoLab`, `SpawnExact`.

## Como ver na web Admin

1. Abrir a loja web como admin → **Sistema → Debug Plugins**.
2. API: `GET /api/admin/plugin-debug/events?plugin=CustomShop&category=TribeSync&limit=100`.
3. CustomDinoDeliver (sem MySQL no plugin) envia críticos via `POST /api/plugin-debug/ingest` (api_key).

Tabela: `arkland_plugin_debug` (criada pelo CustomShop no `ShopPoints::Open` e pela web no primeiro acesso).

## O que está instrumentado

**CustomShop**

- TribeSync: skip / tentativa / OK / falha MySQL+HTTP (com `correlation_id`)
- HttpClient: HTTP ≥400 e falhas WinHTTP/timeout
- ShopPoints: falha de ligação MySQL
- ShopEntitlements::Grant: OK / falha
- Entrega pending: falha de kit/item

**CustomDinoDeliver**

- HttpClient: HTTP ≥400 / timeout
- SpawnExact: falha do motor, find-after-spawn, identity capture

## Extensão a outros plugins

Copiar o padrão `ShopDebug` / `DinoDebug` (ficheiro + ring + Emit com categorias) e gravar na mesma tabela `arkland_plugin_debug` (MySQL directo ou ingest HTTP).
