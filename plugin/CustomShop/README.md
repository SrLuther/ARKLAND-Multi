# CustomShop — ArkApi Plugin

Plugin C++ para **ARK Survival Evolved (ASE)** que substitui o ArkShop como backend do mod [MX-E Ark Shop UI](https://steamcommunity.com/sharedfiles/filedetails/?id=2693727499) (Workshop ID 2693727499), sem nenhuma dependência do ArkShop original.

---

## Dependências

| Componente | Versão | Função |
|---|---|---|
| [ArkServerAPI](https://gameservershub.com/forums/resources/ark-server-api.12/) | v3.56+ | Runtime do plugin |
| [MX-E Ark Shop UI](https://steamcommunity.com/sharedfiles/filedetails/?id=2693727499) | qualquer | Mod cliente (Steam Workshop) |
| Visual Studio 2022 | C++20 | Compilador |
| [vcpkg](https://github.com/microsoft/vcpkg) | — | `nlohmann-json`, `sqlite3` |
| [ASE Permissions](https://ark-server-api.com/resources/ase-permissions.35/) | 2.1+ | *(Opcional)* Controle de acesso por grupo nos kits e pontos diferenciados por grupo |

> **Não** é necessário instalar o ArkShop ou ArkShopUI plugin.
> O plugin [ASE Permissions](https://ark-server-api.com/resources/ase-permissions.35/) é **opcional** — sem ele, a restrição de kits por grupo e os pontos diferenciados por grupo ficam desativados (todos os jogadores têm acesso irrestrito).

---

## Compilar

```powershell
# 1. Clone o repositório e instale o vcpkg caso ainda não tenha
git clone https://github.com/microsoft/vcpkg
.\vcpkg\bootstrap-vcpkg.bat

# 2. Configure o CMake apontando para o SDK do ArkApi
cmake -B build -S . `
  -DCMAKE_TOOLCHAIN_FILE="<caminho>\vcpkg\scripts\buildsystems\vcpkg.cmake" `
  -DARKAPI_DIR="<caminho>\ArkServerAPI" `
  -DVCPKG_TARGET_TRIPLET=x64-windows `
  -A x64

# 3. Build (Release)
cmake --build build --config Release
```

O arquivo `CustomShop.dll` será gerado em `build/Release/`.

---

## Instalar no servidor

```
<ServerRoot>/
└── ArkApi/
    └── Plugins/
        └── CustomShop/
            ├── CustomShop.dll       ← build output
            └── config.json          ← copiado de configs/config.json
```

Adicione o mod **2693727499** à lista de mods do servidor (GameUserSettings.ini ou painel do servidor).

---

## config.json

| Campo | Tipo | Descrição |
|---|---|---|
| `Settings.ShopName` | string | Nome exibido no topo da UI |
| `Settings.UiKey` | string | Tecla para abrir o shop (F1–F12) |
| `Settings.StartingPoints` | int | Pontos dados a jogadores novos |
| `Settings.DisableSellButton` | bool | Oculta o botão Sell na UI |
| `Settings.DisableTradeButton` | bool | Oculta o botão Trade na UI |
| `Items.<id>` | object | Item vendável |
| `Items.<id>.Type` | string | Categoria (aparece como filtro na UI) |
| `Items.<id>.Price` | int | Custo em pontos |
| `Items.<id>.Blueprint` | string | Caminho do blueprint ARK |
| `Items.<id>.Quantity` | int | Quantidade entregue por compra |
| `Items.<id>.Quality` | float | Qualidade (0 = base, 100 = ascendant) |
| `Items.<id>.ForceBlueprint` | bool | `true` = entrega o blueprint em vez do item |
| `Kits.<id>` | object | Kit com múltiplos items + comandos |
| `Kits.<id>.DefaultAmount` | int | Quantas vezes pode ser resgatado (use 999 para ilimitado) |
| `Kits.<id>.Items` | array | Lista de itens entregues |
| `Kits.<id>.Commands` | array | Comandos executados no console do servidor. Use `{SteamID}` como placeholder |

---

## Comandos admin (RCON ou console)

```
Shop.AddPoints  <steamid> <delta>    — adiciona/remove pontos
Shop.SetPoints  <steamid> <pontos>   — define pontos absolutos
Shop.GetPoints  <steamid>            — consulta saldo
Shop.Reload                          — recarrega config.json sem reiniciar o servidor
```

---

## Arquitetura

```
Mod (cliente)                          Plugin (servidor)
────────────────────────────────────────────────────────
Pressiona hotkey (F3)
  → BuyItem / GetShopItems /     ──►  Commands.cpp
    GetPoints / GetKits /
    PlayerKits (console commands)
                                       ShopConfig  ←  config.json
                                       ShopPoints  ←  points.db (SQLite)
                                       ShopStore   — dá itens via GiveItem
                                                     executa Commands[]
                                       ShopData    — monta JSON
                                       ShopBridge  — aplica BP_Shop_Buff
                                                     chama ClientReceiveCallback
  ◄── JSON payload (via ProcessEvent) ──────────────────
Mod renderiza UI com os dados
```
