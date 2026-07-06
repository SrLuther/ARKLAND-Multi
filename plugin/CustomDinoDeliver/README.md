# CustomDinoDeliver — Plugin ARKLAND (Dino Lab)

Plugin C++ **separado do CustomShop** para entregar dinos com cores customizadas via fila HTTP `item_type=custom_dino`.

## Documentação

| Documento | Público |
|-----------|---------|
| **[`docs/DINO_LAB_GUIA.md`](../../docs/DINO_LAB_GUIA.md)** | Guia completo — instalação, uso web, RCON, troubleshooting |
| [`docs/DINO_LAB_SPEC.md`](../../docs/DINO_LAB_SPEC.md) | Spec de produto e arquitetura |

## Status

| Fase | Estado |
|------|--------|
| Fase 0 — Web + schema | ✅ `custom_dino_service.py`, `payload_json`, rotas admin/plugin |
| Fase 1 — Plugin MVP | ✅ Spawn + 6 cores + cryopod + poll HTTP |
| Fase 2 — UI admin | ✅ Menu **Dino Lab** na Web Store |
| Integração TEK | ✅ Instalar todos + sync config + `DinoDeliver.Reload` via RCON |

## Endpoints do plugin

| Método | Rota |
|--------|------|
| POST | `/api/pending/custom-dino/claim` |
| POST | `/api/pending/custom-dino/delivered` |
| POST | `/api/pending/custom-dino/release` |

Headers: `X-API-Key` (mesma chave do CustomShop).

## Config (`configs/config.json`)

```json
{
  "WebApiUrl": "http://127.0.0.1:5177",
  "WebApiKey": "sua-chave",
  "PollIntervalSeconds": 60,
  "GroundFallbackOnFullInventory": true,
  "CryoItemPath": ""
}
```

Aliases aceitos: `WebStoreUrl`, `ApiKey`.

## Comandos

| Comando | Efeito |
|---------|--------|
| `DinoDeliver.Reload` | Recarrega `config.json` (console / RCON) |
| `/dinolab` | Força verificação de fila (chat) |

## Build

```bat
cd plugin\CustomDinoDeliver
build_cl.bat
```

Reutiliza ArkServerAPI de `plugin/CustomShop/ArkServerAPI`. Saída: `bin/CustomDinoDeliver.dll`.

Incluído no `build.bat` do ARKLAND Multi e empacotado em `ARKLAND-Multi.spec`.

## Instalação nos servidores

**TEK** → Loja → **🦕 Instalar Dino Lab** → **Aplicar em todos os plugins** → **Sync + Reload RCON**.

Destino: `ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomDinoDeliver/`

## Referência de código

- `src/DinoDeliver.cpp` — spawn, cores, cryopod (paridade `ShopCryoDino.cpp`)
- `src/DinoHttpClient.cpp` — WinHTTP claim/delivered/release
- `plugin/CustomShop/src/ShopCryoDino.cpp` — referência histórica (não estender)
