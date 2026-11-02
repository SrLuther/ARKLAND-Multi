# Fazenda de Recursos (FazendaRecursos)

Plugin standalone C++ para ArkServerAPI. Usa o SDK compartilhado pelo CustomShop e persiste os dados em `ArkApi/Plugins/FazendaRecursos/data/farms.json`, separados por SteamID.

## Base disponível nesta etapa

- Categorias extensíveis em `config.json`: `default` é obrigatória; `omega` pode ser ativada/desativada. Cada categoria possui sua própria lista de recursos.
- Configuração individual de recurso: classe do item, custo de entrada, saída, intervalo, capacidade e habilitação.
- Grupo de licença independente `keyfarm`, consultado pela Permissions do ArkServerAPI. O prazo de 30 dias é responsabilidade da entitlement/grupo concedido pela Web Store; não se usa `keyvault`.
- Estado JSON gravado atomicamente no unload e estrutura de produção por tempo transcorrido, com estoque limitado por recurso.
- `/fazcoletar` (admin/Permissions group configurado) exporta `engram_catalog` de `UPrimalGameData.EngramBlueprintEntries`, `items` do inventario do administrador e, quando o modulo AssetRegistry ja esta carregado e sem scan em andamento, todos os registros retornados por `FAssetRegistry::GetAllAssets`. O índice de assets é somente leitura; o comando não força busca síncrona. Os assets são salvos em `assets.json` e `assets.txt` (nome, classe e caminho), e a lista de engramas também em `engram_catalog.txt` com a classe Blueprint do item. Se o módulo estiver indisponível/carregando ou a consulta falhar, `report.json` registra o estado; uma exportação ausente não deve ser interpretada como catálogo vazio. Para Souls/Paragons presentes no inventário, salva ainda o blob opaco integral de `UPrimalItem::GetItemBytes` como `.bin`; não interpreta offsets nem cria cópias. Tudo fica numa subpasta timestamp em `ArkApi/Plugins/FazendaRecursos/diagnostics`.
- `Fazenda.Reload`, no console do servidor, recarrega e valida `config.json` sem limpar estado de jogador. Se o arquivo estiver inválido, as configurações ativas anteriores permanecem. Para recarregar a DLL compilada, use os comandos ArkServerAPI `plugins.unload FazendaRecursos` e `plugins.load FazendaRecursos` em sequência.
- Comandos públicos definidos: `/fazenda`, `/fazconfirmar`, `/fazstatus`, `/fazresgatar`.

## Upload de teste na 0.1.4-test

O jogador precisa estar no grupo `keyfarm`. `/fazenda` lista Paragon Souls Omega individuais encontradas no inventario e cria uma previa temporaria. `/fazconfirmar` consome uma unidade de cada especie incluida nessa previa e grava o blob original opaco sob `data/souls/<SteamID>/`, com o indice em `data/farms.json`. Cada especie pode ser enviada uma vez por jogador. Itens empilhados, outras Souls, blueprints e classes parecidas sao rejeitados.

O blob preservado ainda nao e recriado como item. A producao de copias, a geracao de Shards e o resgate continuam desativados ate ser validada uma forma segura de instanciar itens Omega no servidor. Em falha de persistencia apos o consumo, o registro permanece pendente e e anotado no log; nao se considera o upload concluido.

## Limites explicitos da versao 0.1.4-test

Ainda nao se deve ativar recursos de producao: a lista comeca vazia ate identificar as variantes Omega reais. O catalogo de engramas revela blueprint classes registrados no jogo/mod e seus requisitos, mas nao contem os dados customizados de uma Paragon especifica; mantenha a Soul real no inventario para exportar seu blob. Geracao de itens e entrega de pedidos ainda nao estao conectadas.

Nesta versão, `assets.json`/`assets.txt` contêm apenas os registros que `GetAllAssets` retornar do AssetRegistry já carregado. O comando não força a indexação de conteúdo e não garante cobertura integral dos mods; confirme `asset_registry.status` em `report.json` e compare com a lista legível do catálogo em `engram_catalog.txt`.

O vencimento é conferido pela membership `keyfarm`. A produção offline com licença vencida requer reconciliação de entitlement com a Web Store (para delimitar o instante exato da expiração); não deve ser declarada garantida por esta etapa local.

## Build

Execute `build_cl.bat` em Windows com MSVC C++ e SDK ArkServerAPI acessível em `plugin/CustomShop/ArkServerAPI`. Copie a pasta gerada `bin` para `ArkApi/Plugins/FazendaRecursos` no servidor de teste, não em produção.

## WebStore stock synchronization (0.1.5-test)

The plugin posts persisted stock snapshots to `/api/plugin/farm/sync` at startup, on a periodic interval, after Paragon Soul upload, and after `/fazstatus`. It reads `Settings.WebApiUrl` and `Settings.WebApiKey` from `ArkApi/Plugins/CustomShop/config.json`, never sends the API key to players, and uses `ServerId` from the Fazenda config. This synchronizes persisted stock; it does not turn a Paragon Soul upload into production for Shards.

The Omega defaults include Paragon Shard, Soul Shard, and Chest Shard with capacity 200 and a provisional rate of one unit per hour. Those entries are configuration only: generic item upload/activation, cloning, and `/fazresgatar` delivery still require implementation before positive stock can be produced or delivered.
