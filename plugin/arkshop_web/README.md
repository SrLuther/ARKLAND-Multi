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

## Controles de servidores pelo site

A página **Controle de servidores** usa o agente integrado ao Server Manager. Administradores configuram URL e token na própria tela; a equipe de suporte vê apenas os controles operacionais. O token fica protegido no `settings.json` da Web Store e não é devolvido pela API. Como alternativa, as variáveis `ARKSHOP_SERVER_AGENT_URL` e `ARKSHOP_SERVER_AGENT_TOKEN` continuam aceitas. No Server Manager instalado no Windows, o `.env` persistente pode ser criado em `%APPDATA%\ARKLAND-ServerManager\arkshop_web\.env`; o diretório é criado pela instalação/execução da Web Store. Após editar esse arquivo, reinicie a Web Store. Mantenha a porta do agente acessível somente pela rede administrativa. Administradores e suporte podem listar jogadores, kickar SteamID conectado e iniciar/parar/reiniciar servidores registrados no agente.

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

## Imagens de espécies (Catálogo + Comércio P2P)

**Não** use wiki Fandom, Dododex, Ark IDs ou assets do jogo sem licença escrita — ver `static/species/ATTRIBUTION.md`.

O projeto inclui **ícones SVG originais ARKLAND** por espécie (`static/species/icons/{species_key}.svg`), gerados proceduralmente. Fallback: silhuetas por tier (`tier-*.svg`).

Regenerar ícones após novas espécies no registro:

```bash
python tools/generate_species_icons.py
```

Para substituir por arte licenciada: coloque o arquivo em `static/species/` e defina `icon_path` ou `image_url` em `data/market_species_defaults.json` ou `data/ark_species_registry.json` (sobrescreve o ícone procedural).
