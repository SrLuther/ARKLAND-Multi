# Changelog — CustomShop

Versão do plugin (independente do APP_VERSION do Server Manager).
Fonte de verdade: `plugin_version.txt` → sincronizar com
`python scripts/sync_plugin_versions.py --plugin CustomShop`.

A UI «Versões esperadas» lê `PluginInfo.json` embutido no app (`VersionLabel`).

<!-- markdownlint-disable MD024 -->

## [1.10.16] - 2026-07-12

### Fix

- **ShopDebug / TribeSync**: alinhamento pós-1.10.15 — boot de `logs/` + avisos TribeSync quando ServerId/MySQL offline (diagnóstico).

## [1.10.15] - 2026-07-12

### Fix

- **ShopDebug**: cria `logs/` + linha boot em `arkland_debug.log` no arranque **sempre** (mesmo com `Debug.Enabled=false`). Enabled só controla volume TRACE — o canal deixa de ficar invisível após deploy.

## [1.10.14] - 2026-07-12

### Feature

- **ShopDebug** ARKLAND-first: JSONL em `ArkApi/Plugins/CustomShop/logs/arkland_debug.log` (rotação), ring buffer, níveis ERROR→TRACE, categorias (`TribeSync`, `Http`, `MySQL`, `License`, …), `correlation_id`. Config `Debug.*` (default `Enabled=false`).
- MySQL `arkland_plugin_debug` para WARN/ERROR críticos (visível na web Admin sem abrir log do mapa).
- Comandos `/shopdebug` e `Shop.DebugLevel [off|trace|…]`; `Shop.Reload` reaplica config.
- Instrumentação: TribeSync skip/OK/fail, HttpClient ≥400/timeout, ShopPoints connect fail, License Grant, deliver pending fail.

## [1.10.13] - 2026-07-12

### Feature

- TribeSync: proteção de dono web — se `(server_id, tribe_id)` já tem proprietário em `tribe_map_links`, sync de outro jogador (mesmo como owner in-game) **não sobrescreve** o link; trata como membro.

## [1.10.12] - 2026-07-12

### Feature

- TribeSync **pull sem RCON**: «Verificar de novo» cria `tribe_sync_requests` na MySQL; plugin poll ~15s reclama o pedido, lê a tribo in-game e grava `tribe_presences` / `tribe_members` / auto-link **directo na mesma DB** (`arkland_shop`). HTTP `/api/tribe/presence` fica como redundância.
- RCON `Shop.TribeSync` passa a atalho opcional — falha de RCON não bloqueia o vínculo de mapa.

### Fix

- ShopPoints: cria tabelas de tribo (`tribe_presences`, `tribe_members`, `tribe_owners`, `tribe_map_links`, `tribe_sync_requests`) no Open() para o plugin escrever o que a web já lê.

## [1.10.11] - 2026-07-12

### Fix

- TribeSync: **causa raiz** — em ASE `MyTribeDataField()` pode ser NULL mesmo com o jogador numa tribo (TribeID válido via `GetTribeId` / `TargetingTeam`). Antes: early-return «sem tribo» → zero POST `/api/tribe/presence` → «Nenhuma presença in-game».
- TribeSync: resolve tribo por MyTribeData → GetTribeId/TargetingTeam; nome via character; ownership via IsTribeOwner mesmo sem FTribeData completo.
- Shop.Reload: reconfigura HttpClient (WebApiUrl/Key) antes do TribeSync.
- HttpClient: loga status HTTP ≥400 nos POSTs (diagnóstico 401 api_key).
- Retries pós-login: 2/8/20/45/90s (2s alinha com «Verificar de novo» via RCON).

## [1.10.10] - 2026-07-11

### Fix

- TribeSync: silêncio total no login — logs em **cada** tentativa/skip (offline, sem tribo, sem ServerId, HTTP fail); resolve jogador por SteamID (não só ponteiro); agenda log imediato no HandleNewPlayer.
- TribeSync: `ServerId` independente de `CrossChat.Enabled` — lê `Settings.ServerId` → `CrossChat.ServerId` → nome do mapa ASE; fallback explícito com aviso.
- Confirmado: CrossChat off **não** desactiva TribeSync (nunca esteve acoplado no C++; o problema era config sem ServerId + skips sem log).

## [1.10.9] - 2026-07-11

### Fix

- HttpClient: `WinHttpSetTimeouts` (5s/5s/8s/8s) — evita hang longo no game thread se a API não responder (HangWatcher ASE).
- TribeSync: poll separado do DeliverPending; `SyncAllOnlinePlayers` agenda 1 POST/s; retries pós-login param no primeiro sucesso.

## [1.10.8] - 2026-07-11

### Fix

- TribeSync: retries pós-login (8/20/45/90s), poll ~3 min, Shop.Reload/Shop.TribeSync e validação da resposta HTTP — corrige «Nenhuma presença in-game» quando a tribo demora a carregar ou o jogador já estava online.
- TribeSync: aviso claro se CrossChat.ServerId estiver em falta (server_id=unknown).

## [1.10.7] - 2026-07-11

### Feature

- ShopTribeSync: presença do proprietário no login (OwnerPlayerDataID/Proprietário) → API de mapa.
- Melhorias ShopCryoReader / ShopMarket (cryopod e comércio P2P).

### Fix

- SyncPlayerOnJoin: grupos temporários realinhados ao `expires` do DB mesmo se já estiverem no Permissions (evita residual stale após renovação).
- ShopEntitlements: sync de licenças temporárias alinhado ao expires residual+novos.

## [1.10.6] - 2026-07-06

### Other

- Baseline da versão publicada com o app v1.10.6 (antes do versionamento com CHANGELOG por plugin).
