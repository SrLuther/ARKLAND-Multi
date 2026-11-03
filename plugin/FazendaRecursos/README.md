# Fazenda de Recursos - build de teste 0.1.13

## Fluxo implementado

- `/fazenda` aceita o envio de uma unidade real de um recurso habilitado. O blob do upload representa o deposito inicial, nao os itens produzidos.
- A configuracao mestre por `FarmShareKey` reside em `farm_share_configs` (ate quatro chaves, limitadas pelo numero de servidores registrados). Chaves iguais compartilham configuracao e estoque.
- Plugin e Web Store usam tabelas `farm_*` proprias no MySQL. A Fazenda nao usa as tabelas `player_cloud_*`.
- `farm_player_resources.stock` e o saldo numerico. Cada ciclo completo acrescenta exatamente `OutputQuantity` apos `IntervalSeconds`, respeitando `Capacity`; nao cria blobs por ciclo.
- Minha Area mostra o saldo menos as unidades reservadas por pedidos pendentes/em processamento. O jogador agenda a quantidade e as linhas de entrega sao divididas por `StackSize`.
- `/fazresgatar` cria o item pela Blueprint configurada e passa a quantidade da linha como stack. Cinco unidades podem sair em um item de quantidade cinco; pedidos maiores sao divididos conforme `StackSize`. O saldo e reduzido ao confirmar cada entrega.
- Pedidos permanecem no historico da Minha Area com estado e datas.

## Validacao necessaria

- Aplicar a migracao, implantar site/plugin e validar ponta a ponta no servidor ARK.
- Confirmar que cada `ItemClass`/Blueprint cria o item esperado. Compilar nao confirma variantes Paragon nem preservacao de dados Omega; Paragon Breaker depende de Blueprint correta.
- Ajustar `StackSize` ao limite real de cada item e validar inventario no jogo.
- Entrega ao inventario e confirmacao MySQL nao sao atomicas. Se o servidor cair entre as duas, verificar inventario e historico antes de repetir.

## Instalacao de teste

1. Fazer backup do banco e parar o servidor ARK.
2. Aplicar `migrations/fazenda_mysql.sql` no database compartilhado com CustomShop/Web Store.
3. Instalar os arquivos da pasta `FazendaRecursos` em `ArkApi/Plugins/FazendaRecursos`; revisar configuracao sem sobrescrever `config.json` operacional.
4. Configurar `OutputQuantity`, `IntervalSeconds`, `Capacity`, `StackSize` e `ItemClass` por recurso.
5. Iniciar e conferir versao 0.1.13-test, conexao MySQL, chave, catalogo e estoque nos logs.

## Build

Execute `build_cl.bat` no Windows com MSVC e SDK ArkServerAPI em `plugin/CustomShop/ArkServerAPI`.
