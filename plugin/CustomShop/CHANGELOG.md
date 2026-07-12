# Changelog — CustomShop

Versão do plugin (independente do APP_VERSION do Server Manager).
Fonte de verdade: `plugin_version.txt` → sincronizar com
`python scripts/sync_plugin_versions.py --plugin CustomShop`.

A UI «Versões esperadas» lê `PluginInfo.json` embutido no app (`VersionLabel`).

<!-- markdownlint-disable MD024 -->

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
