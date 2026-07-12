# Changelog — CustomDinoDeliver (Dino Lab)

Versão do plugin (independente do APP_VERSION do Server Manager).
Fonte de verdade: `plugin_version.txt` → sincronizar com
`python scripts/sync_plugin_versions.py --plugin CustomDinoDeliver`.

A UI «Versões esperadas» (Dino Lab) lê `PluginInfo.json` embutido no app (`VersionLabel`).

<!-- markdownlint-disable MD024 -->

## [1.10.12] - 2026-07-11

### Fix

- DinoHttpClient: `WinHttpSetTimeouts` (5s/5s/8s/8s) — limita bloqueio síncrono no game thread se a API estiver lenta/indisponível (mitigação HangWatcher ASE).

## [1.10.11] - 2026-07-11

### Fix

- SpawnExact: encomendas com HP/melee geram `wild_stats`; find-after-spawn deixa de escolher tame antigo (cryopod com stats errados).
- NormalizeBlueprintPath endurecido; find-after-spawn com raio 15k, retry e só dinos novos.
- Erro `spawn_exact_not_found` em vez de `identity_capture_failed` falso (ex.: Titan Wyvern).
- DinoHttpClient / entrega: robustez no callback e identificação pós-spawn.

## [1.10.10] - 2026-07-07

### Other

- Baseline da versão publicada com o app v1.10.10 (antes do versionamento com CHANGELOG por plugin).
