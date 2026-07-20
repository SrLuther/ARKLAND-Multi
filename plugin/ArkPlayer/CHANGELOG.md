# Changelog — ArkPlayer

Versões sincronizadas via `plugin_version.txt` +
`python scripts/sync_plugin_versions.py --plugin ArkPlayer`.

## [1.0.1] - 2026-07-20

### Fix

- **config.json ausente**: warning + defaults embutidos em vez de critical fail no init (`PlayerConfig::Load`).

### Rebuild

Recompilar ArkPlayer e substituir `ArkPlayer.dll` + `PluginInfo.json` (VersionLabel 1.0.1) em cada mapa. O instalador TEK passa a copiar `config.json` padrão quando o destino ainda não tem.

## [1.0.0] - 2026-07-19

- MVP inicial: `/mindwipe`, `/missao`, `/loot`, `/nome`, `/kill`.
- Substitui PlayerUtilities (só os 5 comandos activos em produção).
- Dependência Permissions; Points API opcional (ArkShop).
- Instalação via TEK/Manager (aba Plugins + botão Loja) ou manual.
