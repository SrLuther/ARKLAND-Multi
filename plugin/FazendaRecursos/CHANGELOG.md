# FazendaRecursos - changelog

## [0.1.3]
- Adiciona exportacao em texto do catalogo de engramas, incluindo a classe blueprint de cada entrada.
- Adiciona snapshot legivel e JSON dos assets que o AssetRegistry ja indexou, sem forcar busca sincrona.
- O relatorio informa quando o modulo esta ausente, carregando ou falha ao consultar; isso evita tratar ausencia como catalogo vazio.
- Continua sendo uma build de diagnostico: nao ativa producao, nao consome paragons e nao entrega itens.
