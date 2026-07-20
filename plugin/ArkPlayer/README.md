# ArkPlayer — Plugin ARKLAND (MVP)

Substitui o **PlayerUtilities** de terceiros só com os 5 comandos activos no config de produção.

## Comandos

| Comando | Efeito | Preço Default (config) |
|---------|--------|------------------------|
| `/mindwipe` | Reseta pontos de atributo (DoRespec) | 5 |
| `/missao` | Completa missão activa (Genesis 1/2) | 30 |
| `/loot` | Recupera death bags no raio | 5 |
| `/nome <nome>` | Renomeia o personagem | 50 |
| `/kill` | Suicídio | 5 |

Grupo **Staff** (Permissions) tem preços reduzidos/zero — ver `configs/config.json`.

## Dependências

- **Permissions** (obrigatório no `PluginInfo.json`)
- **ArkShop** Points API (opcional): se o preço for >0 e a API não estiver disponível, o comando é recusado. Com `EverythingIsFREE: true` ou preço 0, funciona sem shop.
- **CustomShop** não exporta Points ainda — em servidores só CustomShop, use preço 0 ou `EverythingIsFREE`.

## Build

```bat
cd plugin\ArkPlayer
build_cl.bat
```

Reutiliza o SDK em `plugin/CustomShop/ArkServerAPI`. Saída: `bin/ArkPlayer.dll`.

Requisitos: Visual Studio C++ (x64), Windows SDK, `ArkApi.lib`.

## Instalação (manual)

1. **Remover** `ArkApi\Plugins\PlayerUtilities\` (DLL + config antigos) em cada mapa.
2. Criar `ShooterGame\Binaries\Win64\ArkApi\Plugins\ArkPlayer\`
3. Copiar de `plugin/ArkPlayer/bin/` (ou `configs/` + DLL compilada):
   - `ArkPlayer.dll`
   - `PluginInfo.json`
   - `config.json`
4. Reiniciar o servidor (ou hot-reload ArkApi se suportado).
5. Console/RCON: `ArkPlayer.Reload` após editar config.

## TEK / plugins tab

Não há botão TEK dedicado ainda (CustomShop/Dino Lab têm fluxo próprio). Instalação manual conforme acima.

## Init seguro

`Plugin_Init` **não** chama `GetMapName`. Permissions/Points e lógica de mapa (Genesis) só após `AShooterGameMode.BeginPlay` / `ServerStatus::Ready`.

## Config

Portado do `PlayerUtilities/config.json` activo (mensagens PT, grupos Default/Staff, cooldowns, preços). Guns/harvest/repair/engrams **não** foram reimplementados.
