# Fazenda de Recursos (FazendaRecursos)

Plugin standalone C++ para ArkServerAPI. Usa o SDK compartilhado pelo CustomShop e persiste os dados em `ArkApi/Plugins/FazendaRecursos/data/farms.json`, separados por SteamID.

## Base disponível nesta etapa

- Categorias extensíveis em `config.json`: `default` é obrigatória; `omega` pode ser ativada/desativada. Cada categoria possui sua própria lista de recursos.
- Configuração individual de recurso: classe do item, custo de entrada, saída, intervalo, capacidade e habilitação.
- Grupo de licença independente `keyfarm`, consultado pela Permissions do ArkServerAPI. O prazo de 30 dias é responsabilidade da entitlement/grupo concedido pela Web Store; não se usa `keyvault`.
- Estado JSON gravado atomicamente no unload e estrutura de produção por tempo transcorrido, com estoque limitado por recurso.
- `/fazcoletar` (admin/Permissions group configurado) exporta duas fontes: `engram_catalog`, lido de `UPrimalGameData.EngramBlueprintEntries` (classe do item, nome, requisitos de nivel/pontos, oculto, requisitos atendidos, desbloqueado e disponivel ao jogador), e `items`, objetos presentes no inventario do administrador com campos `FCustomItemData` e `ItemNetID`. A lista de engramas nao inclui criaturas selvagens. Para Souls/Paragons presentes no inventario, salva tambem o blob opaco integral de `UPrimalItem::GetItemBytes` como `.bin`; nao interpreta offsets nem cria copias. As fontes ficam numa subpasta timestamp em `ArkApi/Plugins/FazendaRecursos/diagnostics`.
- `Fazenda.Reload`, no console do servidor, recarrega e valida `config.json` sem limpar estado de jogador. Se o arquivo estiver inválido, as configurações ativas anteriores permanecem. Para recarregar a DLL compilada, use os comandos ArkServerAPI `plugins.unload FazendaRecursos` e `plugins.load FazendaRecursos` em sequência.
- Comandos públicos definidos: `/fazenda`, `/fazconfirmar`, `/fazstatus`, `/fazresgatar`.

## Limites explicitos da versao 0.1.2-test

Ainda nao se deve ativar recursos de producao: a lista comeca vazia ate identificar as variantes Omega reais. O catalogo de engramas revela blueprint classes registrados no jogo/mod e seus requisitos, mas nao contem os dados customizados de uma Paragon especifica; mantenha a Soul real no inventario para exportar seu blob. Deposito/consumo, geracao de itens e entrega de pedidos ainda nao estao conectados.

O vencimento é conferido pela membership `keyfarm`. A produção offline com licença vencida requer reconciliação de entitlement com a Web Store (para delimitar o instante exato da expiração); não deve ser declarada garantida por esta etapa local.

## Build

Execute `build_cl.bat` em Windows com MSVC C++ e SDK ArkServerAPI acessível em `plugin/CustomShop/ArkServerAPI`. Copie a pasta gerada `bin` para `ArkApi/Plugins/FazendaRecursos` no servidor de teste, não em produção.
