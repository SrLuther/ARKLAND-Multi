# Fazenda de Recursos — visão, funcionamento esperado e critérios de conclusão

**Objetivo deste documento:** registrar a interpretação funcional da Fazenda de Recursos do ARKLAND, separar o que já existe do que ainda falta e servir de referência única para plugin, Web Store e banco de dados.

**Estado:** atualizado contra a revisao 0.1.13-test em 3 de novembro de 2026. O codigo agora contabiliza producao por ciclos completos no MySQL (`farm_player_resources.stock`) e instancia a Blueprint configurada no resgate. Build/implantacao e validacao ponta a ponta no ARK continuam pendentes.

## 1. Finalidade do projeto

A Fazenda deve receber itens reais do inventário do jogador, guardá-los com segurança, usar cada envio para ativar a produção daquele recurso e permitir que os itens produzidos sejam consultados e resgatados depois. A experiência precisa funcionar de ponta a ponta entre o servidor ARK, o backend da Web Store, o MySQL e a Minha Área do jogador.

O sucesso não é apenas o plugin aceitar `/fazconfirmar`, nem a Web Store receber um número por HTTP. O envio só está concluído quando o estado e os bytes necessários estão persistidos no MySQL e o jogador consegue ver o registro no site. A produção só está concluída quando existe estoque de itens reais, recuperáveis e entregáveis, e não apenas quando um contador aumenta.

## 2. Interpretação funcional da produção

Na configuração Omega atual, cada recurso tem `ItemClass`, `InputClass`, `InputQuantity`, `OutputQuantity`, `IntervalSeconds` e `Capacity`. Para Paragon Shard, Soul Shard e Chest Shard, a classe de entrada e saída é a mesma; hoje cada um está configurado para produzir uma unidade por 3.600 segundos, até 200 unidades. A taxa é individual por recurso: quantidade produzida e intervalo podem variar entre os recursos.

A interpretação adotada neste documento é:

1. O jogador envia exatamente uma unidade de um recurso configurado; upload de stack maior que um não é aceito.
2. O item enviado é removido do inventário e guardado como base/template daquele produtor. O envio ativa a produção, mas não conta como unidade produzida disponível para resgate.
3. Cada recurso tem sua própria quantidade por ciclo (`OutputQuantity`) e duração do ciclo (`IntervalSeconds`) no `config.json` do plugin. Exemplo: `OutputQuantity=5` e `IntervalSeconds=7200` significa cinco unidades a cada duas horas.
4. Ao completar um ciclo, a Fazenda cria itens reais na quantidade configurada e os mantém no estoque central até que sejam agendados para retirada.
5. Minha Área mostra, por recurso, se a produção está ativa, o intervalo, a quantidade por ciclo, o estoque produzido disponível e o que está reservado em pedidos.
6. O jogador insere a quantidade que deseja retirar em Minha Área e agenda a entrega. O pedido fica visível em uma lista persistente com data/hora e status.
7. No jogo, `/fazresgatar` entrega o pedido daquele jogador em stacks que respeitam o limite configurado por recurso. Exemplo: para retirar 50 com stack 25, entrega dois stacks de 25 em sequência.
8. Após entrega integral, as 50 unidades saem do estoque disponível no MySQL. O pedido não é apagado: a mesma linha passa de pendente para entregue e registra data/hora de conclusão, permanecendo no histórico visual.

Logo, “produzir X unidades a cada Y tempo” significa criar X itens válidos de ARK ao fim de cada ciclo Y, prontos para serem reservados e entregues. Um contador sem os itens correspondentes não representa produção concluída.

### Validação técnica da criação do item

O método de criar o item que será entregue ainda não foi validado pelo usuário no jogo. O teste deve ocorrer depois que o fluxo completo estiver pronto: upload e base persistidos, produção, agendamento no site, criação dos itens e resgate. É necessário conferir se a cópia do blob de `UPrimalItem::GetItemBytes` resulta em um item funcional, sem IDs internos repetidos ou metadados inválidos. Se a cópia integral não for segura, o plugin deve criar a saída pela classe Blueprint e preencher os dados permitidos. O stack gerado também precisa ser aceito pelo inventário do ARK.

### Particularidades Omega: Paragons e Paragon Breaker

Paragons exigem tratamento diferente de um recurso comum. Várias instâncias podem usar a mesma Blueprint e ainda assim representar Paragons diferentes, com características próprias fornecidas pelo sistema/mod que controla essas entidades. A Blueprint identifica a classe base do item; não é prova suficiente da identidade ou das características daquela instância.

- As Blueprints/classes de Paragon devem fazer parte do catálogo/configuração da Fazenda para que esses itens possam ser reconhecidos e enviados.
- **Paragon Breaker deve ser explicitamente suportado** como recurso Omega usando a classe `/Game/Mods/ArkOmega/Items/Souls/GodSouls/PrimalItem_ParagonBreaker.PrimalItem_ParagonBreaker_C`; confirmar a criação do item no servidor.
- **Paragon Soul** usa a classe `/Game/Mods/ArkOmega/Items/Souls/GodSouls/PrimalItem_SpeciesSoul.PrimalItem_SpeciesSoul_C`, mas pode exigir dados de espécie na instância. A classe foi incluída no catálogo da Fazenda; a produção de um Soul genérico requer validação no servidor.
- O plugin deve preservar cada blob original completo e atribuir um `upload_id` único. Não combinar, sobrescrever ou rejeitar instâncias distintas somente porque têm a mesma Blueprint.
- O histórico/site deve identificar a classe/Blueprint conhecida e apresentar o nome/tipo disponível, deixando claro quando os atributos individuais não puderem ser inspecionados.
- Os testes iniciais não comprovaram que a Fazenda consiga distinguir ou reproduzir fielmente todos os atributos customizados de cada Paragon. A aceitação/upload da Blueprint pode ser suportada sem garantir que uma cópia produzida mantenha os atributos únicos.
- Para Paragons, a criação de itens de saída precisa preservar o blob inteiro quando isso for seguro. Se o sistema/mod de terceiros for responsável pelas características, o plugin não deve fabricar valores nem anunciar fidelidade que não verificou.
- O teste de que um Paragon criado a partir da base enviada funciona no jogo será feito pelo usuário quando upload, produção e resgate estiverem prontos. Até esse teste, a compatibilidade de atributos específicos permanece não comprovada.

As regras de quantidade por ciclo, intervalo, capacidade e stack continuam aplicáveis, mas a forma de instanciar Paragons pode ter restrições adicionais em comparação aos Omega Shards comuns.

## 3. Fluxo esperado de ponta a ponta

### 3.1 Envio e ativação

1. O jogador precisa estar conectado, vivo, com o inventário acessível e com licença `keyfarm` ativa.
2. `/fazenda` lista somente itens que correspondem a recursos habilitados, com classe e quantidade verificadas pelo plugin.
3. `/fazconfirmar` confirma a prévia; a prévia deve expirar e ser revalidada contra o inventário antes de qualquer alteração.
4. O plugin obtém os bytes opacos do item, identifica SteamID, servidor, recurso, quantidade e data do envio.
5. O plugin valida SteamID, recurso habilitado, quantidade e formato do item antes de alterar o inventário.
6. Seguindo o padrão funcional da Nuvem, o plugin grava os bytes e metadados em tabelas próprias da Fazenda no MySQL compartilhado com o site, dentro de uma transação.
7. O item só é removido/confirmado como enviado quando há persistência central. Se a gravação falhar, o item permanece ou é restaurado ao inventário e o envio é informado como falha.
8. Com o upload confirmado, a Fazenda marca a produção como ativa e registra o início do ciclo no mesmo banco que o site consulta.
9. A Minha Área mostra o recurso enviado, estado da produção, taxa de produção e stack máximo configurados.

O fluxo deve ser idempotente: se o plugin repetir uma chamada por timeout, o mesmo `upload_id` não pode inserir duas sementes nem consumir o mesmo item duas vezes.

### 3.2 Produção por tempo

1. O plugin calcula ciclos completos por recurso usando `IntervalSeconds`, `OutputQuantity`, o último instante processado e o limite de capacidade. Ele aplica a quantidade como lote no fim do intervalo; não converte a taxa em entregas fracionadas menores.
2. O cálculo deve considerar períodos offline se essa for a regra aprovada, sem gerar duas vezes o mesmo intervalo após reinício ou sincronização.
3. A geração do blob do item produzido e a atualização da quantidade/estado precisam ser gravadas atomicamente no MySQL.
4. A produção deve parar ao alcançar `Capacity`; a contagem exibida é o número real de unidades disponíveis, descontando reservas de pedidos.
5. Produção em vários mapas/servidores precisa ter uma única fonte de verdade por jogador e recurso. Dois servidores não podem processar o mesmo intervalo em paralelo e duplicar a produção.
6. O site deve mostrar quando a produção está ativa, a hora da última sincronização e a quantidade real disponível.
7. Minha Área também deve mostrar a configuração efetiva (por exemplo, “1 unidade a cada 1 hora”) e, quando houver dados suficientes, o horário previsto do próximo ciclo.

Exemplo obrigatório de semântica do ciclo: `OutputQuantity=5` e `IntervalSeconds=300` produz cinco unidades juntas ao completar cinco minutos. Não produz uma unidade a cada minuto. A produção deve preservar a fase/tempo restante do ciclo segundo a regra de alteração de configuração definida abaixo.

### Tabela de recursos e taxas em Minha Área

Dentro de Minha Área → Fazenda deve existir uma tabela de referência com todos os recursos configurados para a Fazenda. No mínimo, as colunas são:

| Recurso | Produção por ciclo | Intervalo do ciclo | Disponibilidade |
| --- | ---: | --- | --- |
| Paragon Shard | 1 unidade | 1 hora | Ativo ou não enviado |

Cada linha usa os valores específicos daquele recurso no `config.json`: nome, `OutputQuantity` e `IntervalSeconds`. A interface pode apresentar também o resultado em texto claro (“5 unidades a cada 5 minutos”), mas não deve substituir os valores de ciclo por uma taxa unitária normalizada. Apenas recursos habilitados podem ser enviados/produzidos. Recursos configurados e desabilitados podem aparecer identificados como indisponíveis para informar a configuração, mas não podem aceitar upload nem pedido.

O editor administrativo da Web Store e a fonte mestre. Ele grava no MySQL uma configuracao por `FarmShareKey`, incluindo Blueprint/classe, quantidade e intervalo por ciclo, stack, capacidade e habilitacao. O plugin consulta a revisao pela chave, valida/aplica os valores, preserva seu `ServerId` local, espelha em `config.json` e publica em `farm_resource_catalog` o catalogo carregado. Minha Area seleciona a chave e mostra os recursos, taxas, intervalos e estoque desse grupo.

Os recursos disponíveis no catálogo devem mostrar a taxa mesmo quando o jogador ainda não enviou a semente. O estado pessoal (enviado/ativo, saldo, próximo ciclo, pedidos) é exibido junto ou em uma coluna separada da configuração geral.

### Alteração de taxa com ciclo em andamento

Quando `OutputQuantity` ou `IntervalSeconds` mudar, a tabela do site deve atualizar assim que a nova configuração sincronizar. A produção futura deve respeitar os novos valores exatamente como definidos. Para evitar produção retroativa duplicada, o plugin/backend precisa registrar revisão da configuração e o último ciclo processado. A política de fase para o ciclo que já estava em andamento — reiniciar o intervalo na hora da alteração ou preservar a fração de tempo já transcorrida — precisa ser definida antes da implementação do hot reload; até lá, uma mudança de taxa deve valer a partir do próximo ciclo completo iniciado com a configuração nova.

Exemplo de configuração por recurso:

```json
{
  "Id": "omega_paragon_shard",
  "Name": "Paragon Shard",
  "ItemClass": "/Game/Mods/ArkOmega/Items/Souls/PrimalItem_ParagonShard.PrimalItem_ParagonShard_C",
  "OutputQuantity": 1,
  "IntervalSeconds": 3600,
  "StackSize": 25,
  "Capacity": 200,
  "Enabled": true
}
```

`StackSize` é o máximo colocado em cada stack no inventário durante o resgate. Não altera `OutputQuantity`: taxa de produção e tamanho de stack são configurações independentes.

### 3.3 Resgate

1. Minha Área permite selecionar quantidade somente quando há itens reais disponíveis depois de descontadas outras reservas.
2. O pedido reserva as unidades no MySQL, descontando reservas concorrentes.
3. `/fazresgatar` consulta pedidos pendentes daquele jogador e inicia a entrega de um pedido por vez.
4. O plugin divide a quantidade pedida por `StackSize` do recurso. Um pedido de 50 com stack 25 resulta em dois stacks de 25; se houver resto, o último stack contém somente o restante.
5. O plugin adiciona os stacks em sequência no inventário e confirma o resultado ao backend. Deve haver controle por stack para que uma falha parcial possa continuar sem repetir o que já foi entregue.
6. Depois de confirmar entrega no jogo, o backend remove as unidades entregues do estoque na mesma transação que atualiza o pedido. A solicitação permanece no histórico, com horário e status atualizado.
7. A lista de Minha Área deve mostrar pedidos pendentes e entregues, com data/hora da solicitação, quantidade e status; quando entregue, acrescenta data/hora de conclusão. Não apagar a linha do histórico ao remover os itens do estoque.
8. Falha, timeout ou repetição deve liberar/retomar a reserva sem perda nem duplicação de item ou stack. Cada pedido e cada stack precisam de IDs idempotentes.
9. A licença `keyfarm` controla envio/produção; resgatar estoque já produzido depois do vencimento continua permitido.

### 3.4 Mensagens no chat do jogo

Toda resposta ao jogador enviada pelos comandos da Fazenda deve usar o tamanho padrão do chat do ARK. Evitar texto ampliado, que polui o chat. A cor pode ser amarela; se a API não permitir a cor amarela mantendo o tamanho convencional, usar branco normal. Isso vale para prévia, confirmação, falha, estado da produção, resgate e confirmação de entrega.

## 4. Papel do MySQL e comparação com a Nuvem

A Nuvem é o modelo de persistência a seguir: o plugin conecta ao MySQL usado pelo site e grava/lê suas próprias tabelas diretamente, em transação. A Fazenda deve seguir esse mesmo caminho e oferecer garantias equivalentes.

Plugin e Web Store devem operar sobre o mesmo banco MySQL e as mesmas tabelas `farm_*`, cada um pelo seu próprio código/conexão. O plugin grava e consulta catálogo, uploads, ciclos, estoque, pedidos e entregas; o backend do site consulta esses mesmos registros para Minha Área e grava os pedidos de retirada nas mesmas tabelas. Uma alteração confirmada por um lado deve ficar visível ao outro sem depender de um segundo armazenamento ou de sincronizações de snapshots para uma API intermediária.

As tabelas `player_cloud_inventory` e `player_cloud_items` pertencem somente à Nuvem e não devem ser reutilizadas, alteradas ou misturadas com os dados da Fazenda. As tabelas `farm_*` são exclusivas da Fazenda, no mesmo banco de dados, com esquema, chaves e transações próprios.

A conexao do plugin reutiliza as configuracoes MySQL do `CustomShop/config.json`; a senha nao vai ao navegador nem aos logs. `farm_share_configs` guarda uma definicao mestre por `FarmShareKey`; `farm_resource_catalog` registra a revisao carregada para o site. Se a transacao falhar, o upload nao e confirmado e o item fica ou retorna ao inventario.

O JSON local `farms.json` pode continuar como cache/recuperação durante a migração, mas não é fonte de verdade nem substitui a persistência compartilhada. O MySQL é a fonte central para estado, configuração, estoque e pedidos de resgate. O plugin e o site podem manter caches de leitura curtos, desde que invalidação/atualização não deixe versões divergentes visíveis.

## 5. Modelo de dados proposto

As tabelas são próprias da Fazenda e não reutilizam `player_cloud_inventory` / `player_cloud_items`, pois as regras de capacidade, produção, sementes, pedidos e entrega são diferentes.

### `farm_player_states` — resumo e sincronização

Tabela já representada no ORM atual. Guarda SteamID, servidor, versão do plugin, último snapshot e instante da última sincronização. Pode ser mantida por compatibilidade/visão resumida.

### `farm_resource_catalog` — configuração carregada pelo plugin

Tabela central da configuração efetivamente carregada por `(server_id, resource_id)`: nome, categoria, classe/Blueprint, habilitado, `OutputQuantity`, `IntervalSeconds`, `StackSize`, capacidade, versão/revisão e data da sincronização. O plugin a publica depois de aplicar a configuração mestre; Minha Área lê esta tabela para montar a tabela de produção.

### `farm_share_configs` — configuração mestre do site

Uma linha por `FarmShareKey`, com JSON validado, revisao/hash e data. O editor grava uma definicao por chave; limite maximo quatro, novas chaves limitadas pelo numero de servidores registrados. Instalacoes na mesma chave compartilham configuracao e estoque; `ServerId` segue local. O catalogo efetivo confirma o que o plugin carregou.

### `farm_player_resources` — saldo e produção por jogador/recurso

Tabela nova proposta, com chave composta `(steam_id, resource_id)`. Guarda quantidade central disponível, estado ativo, início/último ciclo processado, configuração efetiva (quantidade por ciclo, intervalo, stack máximo e capacidade), servidor que atualizou e instante. A quantidade representa itens reais associados ao estoque e deve mudar na mesma transação que os itens.

### `farm_uploaded_resources` — itens-base enviados

Tabela nova proposta, com chave composta `(steam_id, upload_id)`. Guarda `resource_id`, classe, nome, quantidade, estado (`active`, `recovered`, `rolled_back` ou estado transitório), servidor, data, tamanho e blob original. Um reenvio do mesmo ID e mesmos bytes atualiza status sem duplicar linha; mesmo ID com bytes diferentes deve ser rejeitado.

### Estoque produzido ? `farm_player_resources.stock`

O saldo numerico no MySQL representa unidades produzidas e disponiveis. O plugin acrescenta `OutputQuantity` somente apos cada `IntervalSeconds` completo, respeitando `Capacity`; nao materializa item/blob por ciclo. Ao agendar, a Minha Area reserva unidades e divide a entrega conforme `StackSize`.

### `farm_redemptions` — pedidos criados no site

Tabela já representada no ORM atual. Reserva pedidos por jogador e recurso e guarda quantidade solicitada, quantidade entregue, stack size usado, `created_at`, `completed_at` e status. A solicitação permanece no banco depois de entregue, atualizada com o novo status e horário de conclusão.

Uma tabela filha `farm_redemption_deliveries` deve registrar cada stack de um pedido: índice, quantidade, estado e data/hora de entrega. Isso permite que um pedido de 50 (dois stacks de 25) apareça como um pedido na Minha Área e seja entregue/retomado stack por stack no servidor.

`farm_redemption_delivery_items` nao e necessaria: `farm_redemption_deliveries` registra quantidades reservadas por stack. A Blueprint e instanciada pelo plugin somente no resgate.

### Relações e integridade

- Todas as tabelas usam InnoDB e chaves/índices que suportem transações e consultas por SteamID.
- IDs de upload e de ciclo/item precisam impedir duplicidade em retries.
- O blob do upload e preservado como registro do item depositado; o estoque produzido e numerico. No resgate, o plugin cria itens pela Blueprint configurada.
- Metadados apresentados no site não devem incluir os bytes dos itens.
- `farm_player_resources.stock` e a fonte unica do saldo produzido. Pedidos pendentes/em processamento reservam parte do saldo; cada stack confirmado reduz estoque e atualiza `delivered_amount` em transacao MySQL.
- A linha de pedido entregue permanece como histórico; somente as unidades físicas/bytes do estoque são removidas ou marcadas consumidas.

### Responsabilidade de leitura e gravação

| Dado | Plugin ARK | Backend/Web Store | Tabela Fazenda |
| --- | --- | --- | --- |
| Configuração mestre | Consulta revisão no MySQL, valida, aplica e espelha em `config.json` | Admin lê e grava; backend valida recursos/valores | `farm_share_configs` |
| Catálogo efetivo e taxa carregada | Grava após aplicar a revisão mestre; lê para validar operações | Lê para exibir tabela e validar pedidos | `farm_resource_catalog` |
| Item enviado e base de produção | Grava blob e metadados na mesma transação da confirmação | Lê metadados para mostrar o envio; nunca recebe bytes para o navegador | `farm_uploaded_resources` |
| Ciclos produzidos | Processa lote exato por ciclo e atualiza estoque numerico | Mostra estoque menos reservas | `farm_player_resources`, `farm_redemption_deliveries` |
| Agendamento de retirada | Lê pedidos pendentes e confirma cada stack entregue | Cria/cancela pedidos e mostra histórico | `farm_redemptions`, `farm_redemption_deliveries` |

As tabelas acima são compartilhadas no sentido de que plugin e site consultam os mesmos registros persistidos no MySQL. Não significa compartilhar as tabelas da Nuvem: o isolamento é por conjunto de tabelas `farm_*`.

## 6. O que a implementação local faz hoje

Com base nos arquivos locais e no histórico registrado em [PENDENCIAS.md](../PENDENCIAS.md), na revisão atual:

- `/fazenda` e `/fazconfirmar` já reconhecem e consomem uploads de recursos configurados, preservando o blob original localmente por SteamID.
- O upload pode ativar produção local; `FarmState::Accrue` calcula períodos e incrementa um saldo numérico até a capacidade.
- A build 0.1.10 grava diretamente no MySQL do CustomShop, publica definições carregadas em `farm_resource_catalog` e grava blobs/metadados em `farm_uploaded_resources`. `/api/plugin/farm/*` permanece para compatibilidade com builds antigas.
- Minha Área consulta o catálogo MySQL e apresenta quantidade por ciclo, intervalo, stack, capacidade e disponibilidade. Se o plugin ainda não publicou catálogo, valores fallback locais são identificados como referência, não como configuração efetiva.
- Minha Área lista uploads persistidos e seus metadados; bytes de itens não são enviados ao navegador.
- A página ainda não reserva e entrega itens por stack de ponta a ponta. Há histórico de pedidos, mas status e datas de entrega dependem do fluxo ainda pendente.
- Estoque e producao seguem o modelo numerico MySQL em `farm_player_resources.stock`; nao ha item fisico por ciclo.
- `/fazresgatar` reivindica pedidos no MySQL, cria cada item pela Blueprint configurada com a quantidade da linha de entrega, entrega no inventario e confirma a reducao do estoque. Falta validar dentro do ARK.
- Estoque e producao seguem o modelo numerico MySQL em `farm_player_resources.stock`; nao ha item fisico por ciclo.
- O usuário ainda não testou a criação/entrega de uma cópia real no ARK. Esse teste depende da conclusão do fluxo de produção e resgate; não se deve tratar a clonagem como validada antes disso.
- A build local está identificada como `0.1.13-test`; instalação no servidor e confirmação da versão após reinício continuam pendentes.

## 7. Trabalho de implementação necessário

### Etapa A — persistir e exibir o envio

- Aplicar `plugin/arkshop_web/migrations/fazenda_mysql.sql`, que cria/atualiza as tabelas próprias de catálogo, jogador, upload, produção, pedidos e entregas.
- Adicionar `StackSize` por recurso no `config.json` e validar o valor contra limites suportados pelo item no jogo.
- Conferir no servidor que a build 0.1.10 conecta ao MySQL do CustomShop e publica catálogo e uploads nas tabelas `farm_*`.
- Confirmar `/fazconfirmar` com persistência MySQL como condição do envio concluído e restauração do item em falha.
- Confirmar que a Web Store consulta as mesmas tabelas `farm_*`, sem snapshots HTTP como fonte concorrente.
- Fazer `/api/player/farm` retornar os metadados dos uploads do próprio SteamID, sem os bytes.
- Mostrar na Minha Área cada item enviado, recurso, estado e data, incluindo produção ativa.
- Atualizar log e mensagem do comando para distinguir “salvo localmente”, “gravado no MySQL” e “produção ativa”.

### Etapa B — produzir itens reais

- Validar no servidor o método seguro de gerar cópias válidas dos Omega Shards.
- Estoque e producao seguem o modelo numerico MySQL em `farm_player_resources.stock`; nao ha item fisico por ciclo.
- Processar ciclos com lock/transação para evitar duplicidade após reinício, múltiplos mapas e retries.
- Fazer o site calcular disponibilidade pelo estoque real e pelas reservas.

### Etapa C — resgatar e entregar

- Validar in-game `/fazresgatar` reivindicando pedidos e blobs específicos, conferindo SteamID e entregando os itens em stacks configurados.
- Confirmar no servidor que cada entrega altera estado do pedido e consome estoque apenas depois da entrega, inclusive em falhas e retries.
- Manter o item-base original separado das unidades produzidas; recuperar a semente não deve apagar silenciosamente estoque já produzido.

### Etapa D — licença, configuração e operação

- Definir o comportamento de produção offline e expiração/renovação da `keyfarm`.
- Definir a regra para múltiplos servidores/mapas e qual instância processa ciclos.
- Concluir o polling da configuração mestre do site, aplicar revisão no plugin, espelhar `config.json` e confirmar o catálogo efetivo no mesmo `server_id`.
- Exibir pedidos pendentes e entregues em histórico persistente, com horário de agendamento e horário de conclusão.
- Gerar e instalar uma versão identificável do plugin depois do build; manter migração de banco e instruções de rollback.

## 8. Critérios de aceitação

1. Enviar um Shard e confirmar: item removido do inventário uma única vez, blob original em `farm_uploaded_resources`, estado ativo e registro visível em Minha Área.
2. Desligar/reiniciar o plugin e o backend: o upload continua visível e os dados binários continuam íntegros no MySQL.
3. Indisponibilizar temporariamente o MySQL: `/fazconfirmar` não reporta sucesso central; o item permanece ou é restaurado; retry não duplica linhas.
4. Após um intervalo curto de teste, existem itens produzidos reais, e o site mostra saldo compatível com os itens armazenados.
5. No limite de capacidade, não são criados itens extras.
6. Dois ciclos/retries simultâneos não duplicam a produção.
7. Solicitar 50 no site com `StackSize=25`, usar `/fazresgatar` e receber dois stacks de 25, sem exceder o limite configurado.
8. Após a entrega, o estoque diminui em 50; o pedido permanece no histórico com data/hora de solicitação, data/hora de entrega e status entregue.
9. Se a entrega parcial ou uma falha ocorrer, o sistema retoma somente os stacks restantes; uma repetição não entrega duplicado.
10. Os comandos/site diferenciam upload persistido, produção ativa, estoque disponível, pedido pendente, entrega concluída e falha de sincronização.
11. Todas as respostas dos comandos da Fazenda aparecem no tamanho convencional do chat; usar amarelo quando possível e branco normal como alternativa.
12. As Blueprints de Paragon configuradas, incluindo Paragon Breaker, são reconhecidas no upload. Instâncias com a mesma Blueprint mantêm uploads/blobs separados e não são tratadas como idênticas só pela classe.
13. Configurar um recurso para cinco unidades a cada cinco minutos resulta em um lote de cinco ao fim de cada ciclo, nunca uma unidade por minuto.
14. Alterar quantidade, intervalo, stack ou Blueprint no editor mestre do site atualiza o registro MySQL, o `config.json` espelhado do servidor e o catálogo efetivo publicado, sem edição manual divergente.

## 9. Regras funcionais alinhadas e pendências técnicas

### Regras funcionais alinhadas

- Upload exige uma unidade individual de um recurso configurado; consome o item e ativa a produção daquele recurso.
- Cada recurso configura sua própria quantidade por ciclo e duração do ciclo no `config.json`.
- A produção respeita o lote e o intervalo exatamente: cinco unidades a cada cinco minutos são entregues como lote de cinco ao fim do ciclo, sem normalizar para uma unidade por minuto.
- Minha Área mostra uma tabela de todos os recursos configurados com nome, quantidade por ciclo e intervalo; a tabela acompanha alterações do `config.json` após o plugin sincronizar/recarregar.
- Minha Área exibe taxa de produção, intervalo, estoque produzido e pedidos de resgate.
- O jogador agenda uma quantidade em Minha Área; o pedido fica numa lista persistente com data/hora e status.
- `/fazresgatar` entrega em stacks no tamanho máximo configurado para o recurso.
- Depois da entrega, o estoque é reduzido; o pedido fica no histórico com status entregue e data/hora de conclusão.
- Blueprints de Paragon configuradas, incluindo Paragon Breaker, devem ser aceitas; a Blueprint sozinha não identifica todos os atributos específicos da instância.
- O teste de validade da cópia do item será realizado pelo usuário quando a implementação de ponta a ponta estiver pronta. Ainda não há conclusão sobre esse teste.

### Pendências técnicas

- **Produção offline:** contar tempo decorrido e retomar ciclos após reinício sem gerar o mesmo ciclo duas vezes.
- Estoque e producao seguem o modelo numerico MySQL em `farm_player_resources.stock`; nao ha item fisico por ciclo.
- **Catálogo por servidor:** sincronizar o `server_id` correto para cada estado do jogador; catálogo removido da configuração deve ficar desativado no banco, sem apagar uploads, pedidos ou histórico já existentes.
- **Licença vencida:** interromper produção nova e preservar estoque já produzido; resgate do estoque existente continua permitido.
- **Recuperar o item enviado:** `/fazrecuperar` encerra a produção correspondente. Definir e implementar o que acontece com estoque ainda não coletado e pedidos já agendados; não apagar esses dados silenciosamente.
- **Stack real:** confirmar a API do jogo para criar/inserir stacks no tamanho configurado e tratar o restante.
- **Entrega parcial:** controlar cada stack e continuar do ponto correto se o inventário não comportar o pedido inteiro.
- **Múltiplos mapas/servidores:** garantir fonte central única e impedir dois processadores de ciclo para o mesmo jogador/recurso.
- **Testes de item:** gerar o item a partir da base enviada, entregar no jogo e verificar que funciona normalmente; esse teste ainda aguarda a conclusão do sistema.
- **Paragons:** preservar o blob individual e não prometer reprodução das características únicas até que o comportamento do mod/controlador de Paragons seja comprovado no jogo.

## 10. Regra de produto resumida

**O jogador envia uma unidade de um recurso habilitado, ativando a produção configurada especificamente para ele. Minha Área mostra taxa, saldo e pedidos. O jogador agenda a retirada; `/fazresgatar` entrega o pedido em stacks dentro do limite configurado. O MySQL remove as unidades entregues e mantém o pedido no histórico com os horários de solicitação e entrega. O usuário testará no jogo se o item criado a partir da base enviada funciona normalmente quando o sistema de ponta a ponta estiver concluído.**
