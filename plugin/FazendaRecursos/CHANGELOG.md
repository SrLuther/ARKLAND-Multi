# FazendaRecursos - changelog

## [0.1.17]
- Adiciona Element na categoria padrao usando a Blueprint base do ARK; quantidade, intervalo, capacidade e stack ficam configuraveis por recurso.

## [0.1.16]
- Sincroniza configuração mestre por ServerId, mantendo FarmShareKey apenas para compartilhar estoque entre servidores.

## [0.1.15]
- Adiciona fallback com backup ao migrar config.json quando o Windows impede a substituicao atomica; os logs agora registram os codigos Win32.

## [0.1.14]
- Desativa a exigencia de TLS no cliente MySQL para compatibilidade com MariaDB local, igual ao fluxo ja usado pelo CustomShop.

## [0.1.13]
- Persiste saldo e ciclos completos no MySQL; cada ciclo acrescenta exatamente a quantidade configurada por recurso.
- Resgate instancia a Blueprint configurada e entrega a quantidade agendada em stacks limitados por StackSize.
- Configuracao mestre, catalogo, uploads, estoque e pedidos ficam isolados nas tabelas farm_* e por FarmShareKey.
- Fluxo compilado; criacao e variantes de itens Omega ainda dependem de validacao no servidor ARK.


## [0.1.4-test]
- Implementa prévia de upload de Paragon Souls Omega em `/fazenda` e confirmação explícita por `/fazconfirmar`.
- Identifica a espécie pelo `CustomItemData` `SpeciesSoul` e aceita apenas o Blueprint `PrimalItem_SpeciesSoul` do caminho Ark Omega confirmado no diagnóstico.
- Exige licença `keyfarm`, item individual (sem stack) e uma Paragon por espécie; a prévia expira conforme `PreviewLifetimeSeconds`.
- Preserva o blob opaco retornado por `GetItemBytes` por jogador e só então consome a unidade original. Registros passam por estado pendente antes do consumo para reduzir risco em falha.
- Esta build testa o recebimento e persistência do upload; não fabrica, multiplica nem entrega itens.

## [0.1.3]
- Adiciona exportacao em texto do catalogo de engramas, incluindo a classe blueprint de cada entrada.
- Adiciona snapshot legivel e JSON dos assets que o AssetRegistry ja indexou, sem forcar busca sincrona.
- O relatorio informa quando o modulo esta ausente, carregando ou falha ao consultar; isso evita tratar ausencia como catalogo vazio.
- Continua sendo uma build de diagnostico: nao ativa producao, nao consome paragons e nao entrega itens.

# v0.1.5-test
- Adiciona sincronização assíncrona de estoque com a API da WebStore usando as credenciais do CustomShop.
- Sincroniza ao consultar status, após upload e periodicamente, incluindo jogadores com dados persistidos.
- Habilita Omega por padrão e inclui Paragon Shard, Soul Shard e Chest Shard (capacidade inicial 200; taxa inicial de teste 1 item/hora, ajustável na configuração).

