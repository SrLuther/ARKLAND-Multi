# FazendaRecursos - changelog

## [0.1.32]
- Adiciona grupo de estoque Primal Fear com 8 Souls e 10 Hides solicitados; configurações existentes recebem apenas IDs ausentes, preservando ajustes locais.

## [0.1.31]
- Aceita os caminhos `/Game/Mods/2447186973/` e `/Game/Mods/ArkOmega/` como aliases ao identificar itens Omega no inventário, sem reescrever os caminhos salvos na configuração.

## [0.1.30]
- Acrescenta recursos Omega ausentes em configs existentes, inclusive configs gerenciadas pelo site, preservando IDs e ajustes personalizados j? cadastrados.

## [0.1.29]
- Amplia o catálogo Omega com os 11 recursos Soul/Token adicionais encontrados em `docs/SpawnCodes.txt` que ainda não estavam incluídos.

## [0.1.28]
- Corrige os caminhos padrão Omega para o diretório real do mod (`/Game/Mods/2447186973`) conforme `docs/SpawnCodes.txt`.
- Migra os caminhos antigos gerados com `/Game/Mods/ArkOmega/`, sem alterar outras configurações de item.

## [0.1.27]
- Inclui todos os 40 Blueprints Omega solicitados nos padrões da Fazenda, preservando recursos e ajustes já existentes ao migrar configurações.

## [0.1.26]
- Blueprint de resgate agora usa a mesma normalizacao de caminho do CustomShop e preserva o sufixo de classe gerada `_C` exigido pelo carregador.

## [0.1.25]
- Itens configurados e habilitados são avaliados pela classe de entrada antes de qualquer tratamento especial; Paragon Soul sem metadados de espécie segue o fluxo configurado normal.

## [0.1.24]
- `/fazenda` aceita stacks de recursos: envia uma unidade e mantém o restante no inventário, sem perder o stack em falhas de sincronização.

## [0.1.23]
- Corrige a ancora dos ciclos apos resgate quando o estoque estava cheio e persiste o horario exato em que a producao alcancou a capacidade.

## [0.1.22]
- Resgate mant?m o fluxo do CustomShop (BPLoadClass + AddNewItem) e normaliza caminhos de classe gerada para o caminho do asset, corrigindo o carregamento de Soul Shard.

## [0.1.21]
- Resgate agora divide a quantidade em stacks compativeis com o limite real do item no ARK e registra a causa especifica quando a Blueprint nao pode ser entregue.

## [0.1.20]
- Adiciona Paragon Breaker e Paragon Soul aos recursos padrão da categoria ARK Omega, sem alterar configurações existentes por servidor.

## [0.1.19]
- Permite recuperar Paragon Souls pelo /fazrecuperar e reenviar Souls/recursos apos recuperacao; uploads ativos ou pendentes continuam protegidos contra duplicacao.

## [0.1.18]
- Corrige a versao gravada no MySQL: usa a versao compilada do plugin em vez do valor fixo 0.1.13-test.

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

