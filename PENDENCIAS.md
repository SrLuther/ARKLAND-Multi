# Pendencias - ARKLAND Multi

## Em andamento (3 tarefas abertas)


- [ ] **FazendaRecursos - concluir e integrar:** o pacote de diagnóstico v0.1.2-test foi publicado isoladamente; validar no servidor as fontes separadas de engramas, receitas visíveis na fabricação e itens do inventário. O teste com GCM deve confirmar que receitas exibidas são catálogo de fabricação, não itens presentes; recursos sem receita fabricável e ausentes do inventário exigem outra fonte. O ArkServerAPI expõe `FAssetRegistry` (`SearchAllAssets`, `GetAllAssets`, `GetAssetsByClass`); falta prototipar uma varredura somente de leitura de blueprints de itens, dinos e recursos, incluindo conteúdo de mods, e medir cobertura/performance no servidor. Depois, concluir a fazenda (licença `keyfarm`, produção, estoque, depósito e resgate seguros) e integrar configuração administrativa e área do jogador, sem apresentar estoque ou resgates como sincronizados antes da API real.
- [ ] **Validacao de producao - Tradutor e ArkEventHunt:** no Tradutor, confirmar build efetivo, credenciais e traducao real nos logs. A v1.11.23 removeu o download Argos do updater; a v1.11.24 removera a pasta local obsoleta de modelos durante a instalacao. No ArkEventHunt, confirmar nos logs que o 404 Mode B desapareceu e que as instancias vivas foram reconciliadas. Sao verificacoes independentes, agrupadas aqui porque ambas dependem de evidencias do host publicado.
- [ ] **Publicar update geral 1.11.24:** incluir as mudancas locais da Web Store aprovadas (painel Azure do tradutor, aba Fazenda e apresentacao de decay), atualizar changelog/build e publicar a release geral depois da versao isolada FazendaRecursos v0.1.2-test.

## Concluidas localmente (aguardando publicacao)

- [x] **Minha Area - estrutura inicial da aba Fazenda:** adicionada a nova aba; painel do jogador consulta a entitlement `keyfarm` e mostra apenas recursos configurados, sem fabricar saldos. Configuracao administrativa restrita por `admin_required`, validada e persistida no diretorio de dados da Web Store. Estoque, pedidos e entrega ainda dependem da integracao plugin/Web Store e seguem em andamento.
- [x] **Web Store - configuracao compacta do tradutor:** controles Azure movidos para painel sobreposto, fechado por padrao; engrenagem liberada somente para administradores apos verificacao autenticada; painel pode ser fechado e tem rolagem propria sem ocupar o fluxo do chat. Implementado localmente; falta publicar a Web Store atualizada.
- [x] **Web Store - decay por material:** o modal dos ajustes exibe o prazo calculado por material usando os tempos base ARK (palha 4, madeira 8, pedra 12, metal 16, Tek 20 dias) multiplicados por `PvEStructureDecayPeriodMultiplier` do snapshot do servidor, com a fórmula visível em cada linha e notas sobre exceções especiais. O multiplicador e estado de desativação vêm da leitura dos INIs; falta publicar a Web Store atualizada.
- [x] **App - reorganizacao das subpaginas da Loja:** abas principais compactadas; campos alinhados para reduzir espaco vazio em telas largas; Web Store dividida em Conexao, Servico, Banco de pedidos e Servidores e acesso, preservando controles e callbacks existentes. Sintaxe Python e referencias das abas conferidas; validacao visual em execucao ainda nao realizada.

## Regra de manutencao

1. Registrar aqui cada tarefa recebida antes de iniciar sua execucao.
2. Usar `- [ ]` somente para trabalho ainda aberto; mover itens concluidos para a secao de concluidos localmente.
3. Ao publicar uma atualizacao, remover somente as tarefas concluidas que entraram nela; manter as demais.
