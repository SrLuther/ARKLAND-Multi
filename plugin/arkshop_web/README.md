# ArkShop Web Manager

Interface web para gerenciar o plugin **ArkShop** (Pelayori/Ark-Server-Plugins) diretamente pelo browser, integrado ao ARKLAND-Multi.

## Funcionalidades

| Seção | O que faz |
|---|---|
| 🏪 Itens da Loja | Adicionar/editar/remover itens (item, dino, beacon, xp, engram, comando) |
| 🎁 Kits | Gerenciar kits com itens, dinos e comandos |
| 💰 Itens à Venda | Configurar o que jogadores podem vender |
| ⚙️ Configurações Gerais | TimedPoints, ItemsPerPage, cryopods, restrições |
| 💬 Mensagens | Customizar todas as mensagens do plugin |
| 🖥️ Console RCON | Consultar/dar pontos e enviar comandos RCON |
| 🔧 Paths | Configurar caminho do config.json e RCON |

## Como usar

### 1. Iniciar
```bat
plugin\arkshop_web\start.bat
```
O browser abre automaticamente em `http://127.0.0.1:5177`.

### 2. Configurar Paths (primeira vez)
- Ir em **Configurar Paths** na barra lateral
- Definir o caminho completo do `config.json` do ArkShop
  - Padrão: `C:\ARK\ShooterGame\Saved\Config\WindowsServer\ArkShop\config.json`
- Definir host/porta/senha RCON do servidor
- Clicar **Salvar Configurações**

### 3. Editar e salvar
- Edite itens, kits, configurações
- Clique **💾 Salvar & Reload** para gravar no arquivo **e** recarregar via RCON (`arkshop reload`)

## Estrutura do config.json (ArkShop 3.x)

```json
{
  "General": { ... },
  "Kits": { "nome_kit": { "Price": 0, "Items": [], "Dinos": [] } },
  "ShopItems": {
    "item_id": {
      "Type": "item|dino|command|beacon|experience|unlockengram",
      "Description": "...",
      "Price": 100,
      "Blueprint": "Blueprint'/Game/...'"
    }
  },
  "SellItems": { ... },
  "Messages": { ... }
}
```

## Porta customizada
```bat
set PORT=8080
python app.py
```

## Dependências
- Python 3.8+
- `flask` e `flask-cors` (instalados automaticamente pelo `start.bat`)
