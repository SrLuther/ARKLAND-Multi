# Debug ARKLAND — plugins (CustomShop / CustomDinoDeliver)

Sistema de debug **independente do log ArkApi**, com ficheiro JSONL, ring buffer in-memory e persistência MySQL (ou HTTP ingest) para a web Admin.

## Onde ficam os logs

Caminho completo (por mapa), exemplo CustomShop:

```
...\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\logs\arkland_debug.log
```

| Plugin | Ficheiro |
|--------|----------|
| CustomShop | `ArkApi/Plugins/CustomShop/logs/arkland_debug.log` |
| CustomDinoDeliver | `ArkApi/Plugins/CustomDinoDeliver/logs/arkland_debug.log` |

**A pasta `logs/` é criada sempre no boot do plugin** (mesmo com `Debug.Enabled=false`). No arranque:

- `arkland_debug.log` — linha JSONL `category: Boot` (explica se TRACE está off)
- `README.txt` — como ligar TRACE / TribeSync
- `.arkland_debug_ready` — marcador para a pasta ser óbvia no Explorer

Se **não há pasta `logs/`**, a DLL em execução é anterior a CustomShop **1.10.15** / DinoDeliver **1.10.14**, ou o plugin não carregou.

Exemplo CI: `...\MAPAS\CI\ShooterGame\Binaries\Win64\ArkApi\Plugins\CustomShop\logs\`

`Debug.Enabled` controla **apenas o volume TRACE** (ring + eventos detalhados no ficheiro) — **não** controla se o sistema/pasta existe.

Rotação: quando o ficheiro ultrapassa `MaxFileBytes` (default 10 MB), roda para `arkland_debug.1.log` … até `MaxFiles`.

Formato: **JSONL** (uma linha JSON por evento) com `ts`, `plugin`, `version`, `level`, `category`, `steam_id`, `server_id`, `order_id`, `correlation_id`, `message`, `fields`.

## Como activar TRACE (temporário)

Default de produção: `Enabled: false` (sem spam TRACE). Para diagnosticar (ex. TribeSync):

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

Override runtime (sem editar JSON):

- CustomShop: `Shop.DebugLevel trace` / `Shop.DebugLevel off`
- CustomDinoDeliver: `DinoDeliver.DebugLevel trace`
- Chat: `/shopdebug` ou `/dinodebug` — status + últimas linhas do ring buffer

**Produção:** `Enabled: false`. Mesmo assim:

- a pasta `logs/` e o marcador de boot existem;
- eventos **WARN/ERROR** das categorias críticas do CustomShop continuam a ir para MySQL (`arkland_plugin_debug`) para a web Admin — sem spammar ficheiro TRACE.

## Níveis e categorias

Níveis: `ERROR` / `WARN` / `INFO` / `DEBUG` / `TRACE`.

Categorias comuns: `Boot`, `TribeSync`, `Http`, `MySQL`, `Shop`, `License`, `Permissions`, `Deliver`, `DinoLab`, `SpawnExact`.

## Como ver na web Admin

1. Abrir a loja web como admin → **Sistema → Debug Plugins**.
2. Filtros: plugin, categoria (`Http`), nível (`WARN+`), SteamID, texto `q` (path/host/status).
3. Clique **Detalhe** numa linha para ver `fields_json` completo (method, path, duration_ms, winhttp_error, snippet, etc.).
4. API: `GET /api/admin/plugin-debug/events?plugin=CustomShop&category=Http&min_level=WARN&q=503&limit=100`.
5. CustomDinoDeliver (sem MySQL no plugin) envia críticos via `POST /api/plugin-debug/ingest` (api_key).

Tabela: `arkland_plugin_debug` (criada pelo CustomShop no `ShopPoints::Open` e pela web no primeiro acesso). Colunas + `fields_json`; a UI extrai steam/order do payload se as colunas estiverem vazias.

## O que está instrumentado

**CustomShop**

- Boot: marcador de canal no arranque
- TribeSync: skip / tentativa / OK / falha MySQL+HTTP (com `correlation_id`)
- HttpClient: HTTP ≥400 e falhas WinHTTP/timeout — com `method`, `path` (sem query), `host`, `http_status`, `duration_ms`, `winhttp_error`, timeouts, `response_snippet` truncado (sem API key)
- ShopPoints: falha de ligação MySQL
- ShopEntitlements::Grant: OK / falha
- Entrega pending: falha de kit/item

**CustomDinoDeliver**

- Boot: marcador de canal no arranque
- HttpClient: HTTP ≥400 / timeout (mesmos campos ricos que o CustomShop)
- SpawnExact: falha do motor, find-after-spawn, identity capture

## Dump da classe do dino (`/dinoclass`) — PropagatorDinoBlacklist

Quando falta o `*_Character_BP_C` de um mod (ex. Alfa Tek Strider Perfect / ItensAlfa — no repo só existe o **spawner** `AlfaItem_Spawner_Strider_Perfect*`, não a Character class):

1. Como **admin**, spawne o item ItensAlfa, use-o, fique ao lado do dino.
2. No chat: `/dinoclass` (alias `/dumpdino`).

Saída no chat (e no log do servidor `[DinoClass]`):

```
class=Something_Character_BP_C
path=/Game/Mods/ItensAlfa/.../Something_Character_BP.Something_Character_BP_C
```

Copie `class=` para `PropagatorDinoBlacklist` no `Game.ini` (S+). Raio ~12 000 uu. Plugin: **CustomDinoDeliver** ≥ 1.10.15.

> Nota: o scan em massa `/bp` (`docs/dinolab-blueprint-scan.md`) ainda é só especificação — não está implementado. Para um dino já spawnado, use `/dinoclass`.

## Extensão a outros plugins

Copiar o padrão `ShopDebug` / `DinoDebug` (ficheiro + ring + Emit com categorias) e gravar na mesma tabela `arkland_plugin_debug` (MySQL directo ou ingest HTTP). Criar `logs/` no `Configure`/boot **sempre**, não só no primeiro write TRACE.
