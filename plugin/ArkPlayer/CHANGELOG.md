# Changelog — ArkPlayer

Versões sincronizadas via `plugin_version.txt` +
`python scripts/sync_plugin_versions.py --plugin ArkPlayer`.

## [1.0.2] - 2026-10-04

### Feature

- `/kill`, `/mindwipe` e `/nome` executam e cobram quando há saldo.
- `/nome` grava o nome no perfil do jogador. A permanência depois de morte ou troca de mapa ainda não foi retestada.
- Passa a cobrar pelo export de pontos do CustomShop (`CustomShop_PointsReady`, `CustomShop_GetPoints`, `CustomShop_SpendPoints`).

### Falha conhecida

- `/loot`: no teste de 04/10/2026 (personagem «teste», nível 17, bag de morte ao lado, feixe verde) o chat disse «Bag(s) de morte recuperada(s)» depois de «Comando comprado por 5 pontos», mas nada do loot entrou no inventário. O inventário ficou só com um item que já estava (peso 0.0). O comando mente sucesso. Sem correção nesta versão.
- Número de dano curto (`9k` / `27k` / `95.9k`): não aparece na tela. Com a opção nativa desligada, não apareceu nada. A tentativa de substituir o texto do widget flutuante também não mostrou número no teste seguinte. Sem correção nesta versão.

### Rebuild

Recompilar ArkPlayer e substituir `ArkPlayer.dll` + `PluginInfo.json` (VersionLabel 1.0.2) em cada mapa, com o mapa parado.

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
