# ArkShop Web Manager

Interface web da loja ARKLAND — catálogo, compras, admin e fila de entregas para o plugin **CustomShop**. Integrado ao ARKLAND Desktop.

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
- Clique **💾 Salvar & Reload** para gravar no arquivo **e** recarregar via RCON (`Shop.Reload`)

## Entrega de pedidos

Por padrão (`delivery_mode: plugin`), compras ficam **PENDENTE** no banco e o **CustomShop** entrega quando o jogador está online — sem depender de RCON.

RCON (`Shop.Deliver`) permanece disponível como modo legado (`delivery_mode: rcon`) ou forçado pelo admin (`/api/admin/orders/{id}/reprocess?force_rcon=1`).

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

## Deploy em produção (MariaDB)

Ao iniciar, a Web Store executa **migração automática** do schema (`_migrate_schema` + `market_migrate`). Não é necessário rodar SQL manualmente em upgrades — as tabelas do **Mercado de Dinos** (`market_*`) são criadas no primeiro boot com MariaDB configurado.

Instalação **limpa** via ARKLAND Server Manager continua usando `setup_db.sql` (já inclui as tabelas `market_*`).

### Variáveis de ambiente opcionais (Mercado)

| Variável | Padrão | Efeito |
|----------|--------|--------|
| `MARKET_AUTO_SYNC_CATALOG` | `0` | Se `1`, importa dinos `Type: dino` do catálogo quando `market_species` está vazio |
| `MARKET_AUTO_ACTIVATE_SPECIES` | `0` | Com sync automático, ativa todas as espécies (`ACTIVE`) |

Diagnóstico admin: `GET /api/market/admin/schema-status` ou aba **Comércio (admin)** na Web Store.

## Porta customizada
```bat
set PORT=8080
python app.py
```

## Dependências
- Python 3.8+
- `flask` e `flask-cors` (instalados automaticamente pelo `start.bat`)
