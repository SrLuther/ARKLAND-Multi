# Central de Status dos Sistemas ARKLAND

## O que a página informa

A página **Status dos sistemas** (`#/system-status`) reúne os serviços web, integrações, servidores e plugins documentados no repositório. Cada registro tem dimensões distintas:

- **Estágio**: planejado, desenvolvimento, alpha, beta, homologação, finalizado, reformulação, descontinuado ou não avaliado.
- **Estado operacional**: operacional, parcialmente operacional, instável, manutenção, indisponível, não disponibilizado, não monitorado ou desconhecido.
- **Disponibilidade**: disponível, experimental, restrita, suspensa ou ainda não lançada.

Um campo não substitui o outro. Por exemplo, um componente em alpha pode estar operacional para testes; isso não significa que esteja liberado para todos. Valores iniciais ficam como **Não avaliado** e **Não monitorado**, até a equipe confirmar os dados. A interface explica que ausência de monitoramento não comprova falha.

## Dados automáticos e revisão humana

Os mapas usam o feed já recebido em `/api/servers/runtime-status` e o cadastro atual do gerenciador. A página agrega estados recentes por mapa (janela de 10 minutos), nomes públicos, mapa, horário, versão disponível e detalhe de estado. Ela não realiza uma nova consulta à Steam nem mede disponibilidade de plugins sem um produtor de telemetria próprio.

As informações de maturidade, recursos, limitações e incidentes são mantidas pela administração. Edições e transições de incidentes geram histórico em `system_status_audit`. Mudanças de disponibilidade operacional devem ser feitas após validação; o registro não as deduz do nome do serviço ou da existência de arquivos.

Há um endpoint de heartbeat de plugin autenticado em `/api/plugin/systems-status/heartbeat`, limitado a mapas registrados no gerenciador. Nenhum plugin é considerado monitorado por esse endpoint até que seu código passe a enviar heartbeats. Um estado ausente não é convertido em “indisponível”.

## Administração

Administradores autenticados podem revisar nome, categoria, descrição, versão, estágio, estado operacional, disponibilidade, recursos disponíveis, desenvolvimento, limitações, problemas conhecidos, observação pública e visibilidade. Também podem registrar incidente/manutenção, avançar sua etapa e marcá-lo como resolvido. As rotas de escrita exigem `admin_required`; heartbeats usam a autenticação de API existente.

## Persistência e rotas

As tabelas `system_status_catalog`, `system_status_instances`, `system_status_incidents` e `system_status_audit` são criadas de modo idempotente na migração existente para SQLite e MySQL. A página pública consulta `/api/public/systems-status`; administração usa `/api/admin/systems-status`. Incidentes resolvidos permanecem no histórico administrativo, mas deixam de aparecer no resumo público de itens ativos.

## Limitações conhecidas

- O catálogo inicial identifica componentes pelo código e pela documentação; os estados não foram presumidos como verdadeiros e exigem revisão de uma pessoa responsável.
- O feed do gerenciador representa o estado runtime/listagem reportado, não substitui uma confirmação dentro do jogo.
- Plugins sem heartbeat integrado continuam corretamente identificados como não monitorados.
- A página informa a hora de consulta e a hora de verificação de cada registro, mas não promete atualização em tempo real.
