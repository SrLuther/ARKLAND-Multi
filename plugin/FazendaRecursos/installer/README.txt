FAZENDA DE RECURSOS - PACOTE DE INSTALACAO DE TESTE v0.1.2-test

1. Extraia o ZIP.
2. Pare o servidor ARK de teste.
3. Execute Install-FazendaRecursos.ps1 no PowerShell e informe a pasta que contem ArkApi.
   O script pede a palavra INSTALAR, cria backup se ja existir uma instalacao e preserva
   o config.json existente.
4. Inicie o servidor e confira o log do ArkServerAPI.
5. Coloque as Paragons que quer analisar no inventario do administrador e execute /fazcoletar.
   O relatorio inclui o catalogo de engramas do jogo/mod (blueprint class, nome, requisitos,
   se esta desbloqueado e se os requisitos estao atendidos), alem dos objetos efetivamente
   no inventario. Coloque tambem as Paragons que quer analisar no inventario para exportar
   seus blobs originais opacos em .bin. A coleta nao altera itens nem cria duplicatas.
   Envie a pasta timestamp de diagnostics compactada para analise.

ROLLBACK
O caminho do backup e exibido pelo instalador. Com o servidor parado, execute:
  .\Rollback-FazendaRecursos.ps1 -ServerRoot "CAMINHO_DA_PASTA_QUE_CONTEM_ArkApi" -BackupPath "CAMINHO_DO_BACKUP"

SEM BACKUP ANTERIOR
Na primeira instalacao, o script nao cria backup. Remova somente a pasta
ArkApi/Plugins/FazendaRecursos apos parar o servidor para desinstalar.

LIMITES DA VERSAO
Este pacote valida instalacao/carregamento, config, permissao e coleta de metadados/blobs.
Nao habilita fazenda passiva, clonagem, consumo de Soul, producao, sincronizacao com Minha
Area ou resgate. Instalar apenas em servidor de teste; a coleta nao altera itens.
