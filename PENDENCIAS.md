# Pendencias - ARKLAND Multi

## Em andamento (2 tarefas abertas)

- [ ] **FazendaRecursos - concluir e integrar:** o pacote de diagnóstico v0.1.2-test foi publicado isoladamente; validar no servidor as fontes separadas de engramas, receitas visíveis na fabricação e itens do inventário. O teste com GCM deve confirmar que receitas exibidas são catálogo de fabricação, não itens presentes; recursos sem receita fabricável e ausentes do inventário exigem outra fonte. O ArkServerAPI expõe `FAssetRegistry` (`SearchAllAssets`, `GetAllAssets`, `GetAssetsByClass`); falta prototipar uma varredura somente de leitura de blueprints de itens, dinos e recursos, incluindo conteúdo de mods, e medir cobertura/performance no servidor. Depois, concluir a fazenda (licença `keyfarm`, produção, estoque, depósito e resgate seguros) e integrar configuração administrativa e área do jogador, sem apresentar estoque ou resgates como sincronizados antes da API real.
- [ ] **Validação de produção - Tradutor e ArkEventHunt:** no Tradutor, confirmar build efetivo, credenciais e tradução real nos logs. A v1.11.23 removeu o download Argos do updater; a v1.11.24 publicada remove a pasta local obsoleta de modelos durante a instalação. No ArkEventHunt, confirmar nos logs que o 404 Mode B desapareceu e que as instâncias vivas foram reconciliadas. São verificações independentes, agrupadas aqui porque ambas dependem de evidências do host publicado.

## Regra de manutenção

1. Registrar aqui cada tarefa recebida antes de iniciar sua execução.
2. Usar `- [ ]` somente para trabalho ainda aberto; mover itens concluídos para a seção de concluídos localmente.
3. Ao publicar uma atualização, remover somente as tarefas concluídas que entraram nela; manter as demais.
