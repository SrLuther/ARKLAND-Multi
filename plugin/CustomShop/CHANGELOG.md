# Changelog — CustomShop

Versão do plugin (independente do APP_VERSION do Server Manager).
Fonte de verdade: `plugin_version.txt` → sincronizar com
`python scripts/sync_plugin_versions.py --plugin CustomShop`.

A UI «Versões esperadas» lê `PluginInfo.json` embutido no app (`VersionLabel`).

<!-- markdownlint-disable MD024 -->

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
