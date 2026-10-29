# CustomShop — ArkApi Plugin

Plugin C++ para **ARK Survival Evolved (ASE)** que gerencia economia de pontos, kits e **entrega de compras da loja web** — sem dependência do ArkShop original nem do mod MX-E Ark Shop UI.

---

## Dependências

| Componente | Versão | Função |
|---|---|---|
| [ArkServerAPI](https://gameservershub.com/forums/resources/ark-server-api.12/) | v3.56+ | Runtime do plugin |
| [arkshop_web](../arkshop_web/) | — | Interface web + fila de pedidos pendentes |
| Visual Studio 2022 | C++20 | Compilador |
| [vcpkg](https://github.com/microsoft/vcpkg) | — | `nlohmann-json`, `sqlite3` |
| [ASE Permissions](https://ark-server-api.com/resources/ase-permissions.35/) | 2.1+ | **Obrigatório** quando o config usa grupos (kits VIP, pontos por grupo). Banco dedicado `ark_permission`. |

> **Não** instale ArkShop, ArkShopUI nem o mod Workshop **2693727499** (MX-E). A loja é acessada pela web.

---

## Compilar

### Pré-requisito: ArkServerAPI SDK

Coloque o SDK em `plugin/CustomShop/ArkServerAPI/` (ou passe o caminho no CMake):

```
ArkServerAPI/
├── version/Core/Public/API/ARK/Ark.h   (layout ASE v3)
├── out_lib/ArkApi.lib                  (ou lib/ArkApi.lib)
└── json.hpp
```

Para MySQL/MariaDB no build manual, copie `libmariadb.lib` para `mariadb/lib/`.

### Opção A — Visual Studio (mais simples)

1. Abra `CustomShop.vcxproj` no VS 2022
2. Configuração: **Release | x64**
3. Build → saída em `bin/CustomShop.dll`

### Opção B — Script batch

```powershell
cd plugin\CustomShop
.\build_cl.bat
```

Detecta o Visual Studio automaticamente via `vswhere`.

### Opção C — CMake + vcpkg

```powershell
cmake -B build -S . `
  -DCMAKE_TOOLCHAIN_FILE="<caminho>\vcpkg\scripts\buildsystems\vcpkg.cmake" `
  -DARKAPI_DIR="<caminho>\ArkServerAPI" `
  -DVCPKG_TARGET_TRIPLET=x64-windows `
  -A x64

cmake --build build --config Release
```

---

## Instalar no servidor

```
<ServerRoot>/
└── ArkApi/
    └── Plugins/
        └── CustomShop/
            ├── CustomShop.dll
            └── config.json
```

---

## config.json (campos principais)

| Campo | Descrição |
|---|---|
| `Settings.WebApiUrl` | URL do arkshop_web (ex: `http://127.0.0.1:5177`) |
| `Settings.WebApiKey` | Chave `X-API-Key` (mesmo valor de `ARKSHOP_API_KEY`) |
| `Settings.CloudShareKey` | Grupo de compartilhamento dos 4 slots `/nuvem`; mapas com a mesma chave compartilham. Em branco usa `default`. |
| `Settings.WebsiteUrl` | URL pública exibida ao jogador (`/shop`, licença Nuvem) — sincronizada pelo TEK a partir de **Domínio público da loja** |
| `Items.<id>` | Itens entregáveis (web + admin) |
| `Kits.<id>` | Kits com itens, dinos e comandos |

`CloudShareKey` é um identificador, não uma senha. Use exatamente o mesmo valor nos mapas que devem compartilhar as nuvens e valores diferentes para separar grupos. O valor é aparado, convertido para minúsculas e limitado a 64 caracteres; letras, números, ponto, hífen e sublinhado são aceitos. Registros anteriores à partição permanecem no grupo `default`.

Configure em cada `config.json` do CustomShop, dentro de `Settings`:

```json
{
  "Settings": {
    "CloudShareKey": "cluster_ragnarok_fjordur"
  }
}
```

Repita a mesma chave nos mapas que devem compartilhar os slots 0, 1, 2 e 3. Para separar os mapas, escolha outra chave; após a migração, cada partição nova começa vazia e os registros anteriores ficam em `default`.

Na migração, se houver blobs sem cabeçalho correspondente, o plugin cria os cabeçalhos contando os blobs existentes antes de ativar a FK composta. Isso preserva os dados restauráveis e evita que a validação da FK impeça o plugin de iniciar.

---

## Fluxo de entrega (web → plugin)

```
Jogador compra na web
    → pedido PENDENTE no banco (arkshop_web)

Jogador entra no servidor (ou poll a cada 60s)
    → CustomShop: GET /api/pending/{steam_id}
    → GiveItem / GiveKit (sem cobrar pontos)
    → POST /api/pending/delivered  { steam_id, order_ids }

RCON (Shop.Deliver) — apenas admin / modo legado (delivery_mode=rcon)
```

---

## Comandos

| Comando | Quem usa | Função |
|---|---|---|
| `/shop` | Jogador (chat) | Mostra URL da loja web + verifica entregas pendentes |
| `Shop.Deliver` | Admin RCON | Entrega manual (legado) |
| `Shop.AddPoints` / `SetPoints` / `GetPoints` | Admin | Gerenciar pontos |
| `Shop.Reload` | Admin | Recarrega config.json |
| `Shop.Debug` | Admin | Diagnóstico (pontos, web API, pending) |

---

## Arquitetura

```
Interface web (arkshop_web)          Plugin (servidor)
─────────────────────────────────────────────────────
Login Steam, catálogo, pagamento
Cria pedido PENDENTE          ──►  HttpClient::DeliverPending()
                                   ShopStore::GiveItem / GiveKit
                                   Confirma entrega na web
```
