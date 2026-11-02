# Pendencias - ARKLAND Multi

## Em andamento (2 tarefas abertas)

- [ ] **FazendaRecursos - concluir e integrar:** relatório real recebido do servidor confirma `plugin_version` 0.1.2-test; contém 1.297 entradas de `EngramBlueprintEntries`, 1.335 objetos do inventário e 36 blobs binários de candidatos a Soul/Paragon. Os metadados de Paragon incluem o caminho da espécie em `CustomDataStrings`. A build isolada 0.1.3-test compila e exporta listas legíveis (`engram_catalog.txt`, `assets.txt`) junto de JSON; tenta ler somente o índice já carregado por `FAssetRegistry::GetAllAssets`, sem scan síncrono. **Pendente:** instalar no servidor de teste e analisar o próximo relatório, medir cobertura/desempenho e decidir se é preciso um scan controlado separado. Ainda falta corrigir/validar os indicadores de engrama (no relatório todos aparecem `unlocked=true`, `requirements_met=false` e `available_to_player=false`), separar Souls comuns de Paragons e confirmar cobertura dos blueprints. Depois, concluir a fazenda (licença `keyfarm`, produção, estoque, depósito e resgate seguros) e integrar configuração administrativa e área do jogador, sem apresentar estoque ou resgates como sincronizados antes da API real.
- [ ] **Validação de produção - Tradutor e ArkEventHunt:** no Tradutor, confirmar build efetivo, credenciais e tradução real nos logs. A v1.11.23 removeu o download Argos do updater; a v1.11.24 publicada remove a pasta local obsoleta de modelos durante a instalação. No ArkEventHunt, confirmar nos logs que o 404 Mode B desapareceu e que as instâncias vivas foram reconciliadas. São verificações independentes, agrupadas aqui porque ambas dependem de evidências do host publicado.

## Regra de manutenção

1. Registrar aqui cada tarefa recebida antes de iniciar sua execução.
2. Usar `- [ ]` somente para trabalho ainda aberto; mover itens concluídos para a seção de concluídos localmente.
3. Ao publicar uma atualização, remover somente as tarefas concluídas que entraram nela; manter as demais.
