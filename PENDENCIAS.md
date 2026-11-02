# Pendencias - ARKLAND Multi

## Concluido localmente, aguardando publicacao

- [x] **Progresso do jogador:** valor informado no gerador e na tabela representa o cap total alcancavel, incluindo ascensoes, notas, runas e chibi; a rampa tem exatamente essa quantidade de entradas.
- [x] **Home - Servidores do cluster:** remover a contagem de jogadores do status dos cards. A lista publica de jogadores permanece como fonte para nomes, mapas e total exibido na comunidade.
- [x] Criar este arquivo e adotar o fluxo de registrar tarefas novas antes de executa-las, atualizar seu estado ao concluir e limpar as concluidas somente depois que forem incluidas em uma atualizacao publicada.
- [x] **Auditoria de persistencia:** revisados os fluxos centrais de `config.json`, `servers.json`, `clusters.json`, `asm_servers.json`, salvamento de INIs classico/TEK, tela de perfil de servidor, configuracoes globais e vinculo de cluster. JSONs de perfil sao gravados atomicamente; corrupcao gera copia `.corrupt-*`; operacoes centrais bloqueiam/avisam em falhas para nao anunciar sucesso falso. O cache de telas e volatil e nao e fonte de restauracao apos reinicio.
- [x] **Detalhar cap total na tela de progressao:** mostrar a divisao entre nivel base, 10 notas, 10 runas, 5 chibi e 75 niveis de ascensoes dentro do maximo informado.
- [x] **Explicacao do nivel maximo do jogador:** o resumo detalha base + 10 notas + 10 runas + 5 chibi + 75 niveis de ascensoes de bosses.
- [x] **Decay de estruturas:** resumo mostra auto-demolicao PvE padrao escalada pelo multiplicador: palha 4, madeira 8, pedra 12, metal 16 e Tek 20 dias em 1x. Referencia: https://ark.wiki.gg/wiki/Building
- [x] **Relatorio do tradutor:** sintomas observados, alteracoes locais e evidencias ainda necessarias no host documentados em `RELATORIO_TRADUTOR.md`.
- [x] **Migracao do cap em perfis antigos:** causa confirmada no gerador antigo: salvava o cap digitado em `player_base_level`, que depois recebia +100. Perfis com assinatura desse gerador sao migrados uma unica vez para base = cap - 100; rampa/limiares/pontos excedentes sao limitados ao cap total e o schema versionado e salvo. Perfis unificados que declaram `base_level` explicitamente sao preservados.
- [x] **Tradutor - robustez local e diagnostico:** upload multipart confirmado e testado; codigos de erro/stage/reference/build adicionados; modelos persistentes instalados apenas quando ausentes; falha do indice nao bloqueia modelos ja instalados; pacote baixado e validado antes da instalacao. 29 testes direcionados passaram. A causa do incidente em producao e a validacao de traducao real ainda dependem do host.

## Em andamento (2 tarefas abertas)

- [ ] **Tradutor - validacao de producao:** iniciar somente depois que a versao com instrumentacao estiver publicada. A pagina oficial ainda reporta assets `1.11.20`; este checkout nao foi publicado. Depois, consultar o traceback para `ff5cfdeb3067`, testar upload autenticado por interface e multipart, confirmar os quatro modelos persistentes, reinicio sem download desnecessario e traducao real em cada direcao.
- [ ] **Publicacao:** incluir as alteracoes locais concluidas acima em uma atualizacao. Apos publicar, remover deste arquivo as tarefas concluidas que entraram nela; manter as demais pendencias.

## Regra de manutencao

1. Registrar aqui cada tarefa recebida antes de iniciar sua execucao.
2. Usar `- [ ]` somente para trabalho ainda aberto; mover itens concluidos para a secao de concluidos localmente.
3. Ao publicar uma atualizacao, remover somente as tarefas concluidas que entraram nela; manter as demais.
