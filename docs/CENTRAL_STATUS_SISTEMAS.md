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

## Inventário identificado no código

O cadastro inicial cobre os sistemas de jogador, os plugins próprios e as integrações observáveis no repositório. Além dos 23 registros iniciais, o levantamento dos módulos de rotas e serviços identificou e separou ARKBANK, notificações, sugestões, avisos da página inicial, mídia da comunidade, presença de jogadores e aceite do regulamento. A lista inicial, portanto, contém 30 entradas.

| Área cadastrada | Evidência principal no projeto |
| --- | --- |
| Web Store, economia, pagamentos e licenças | `app.py`, `amber_ledger.py`, `arkbank_service.py`, `lottery_service.py` e rotas de pedidos |
| Catálogo, entregas, comércio e Dino Lab | `catalog_feed_service.py`, `dino_order_service.py`, `market_service.py`, `custom_dino_service.py` |
| Fazenda de Recursos | `resource_vitrine_service.py` e plugin `FazendaRecursos` |
| Equipes e tribos | `team_service.py`, `tribe_service.py`, `tribe_invite_service.py` |
| SeasonLand, BetLand, votações e eventos | `season_pass_service.py`, `lottery_service.py`, `poll_service.py`, `event_hunt_service.py`, plugin `ArkEventHunt` |
| Suporte, regulamento, notificações, sugestões e avisos | `ticket_service.py`, `regulamento_service.py`, `notification_service.py`, `suggestion_service.py`, `home_notice_service.py` |
| Lumo, mídia e presença de jogadores | `lumo_routes.py`, `media_service.py`, `player_monitoring_routes.py` |
| Cluster ARK e plugins próprios | integração de status em `app.py`, diretórios de plugins `CustomShop`, `CustomDinoDeliver`, `ArkPlayer`, `ArkEventHunt`, `EngramLevel`, `FazendaRecursos`, `StructureLimits` e `Permissions` |
| Discord e pagamentos externos | rotas de integração, bot do Discord e adaptadores de checkout presentes no projeto |

O inventário prova que o componente está no código; não prova que ele esteja instalado, liberado, saudável ou operacional em produção. Por isso os registros continuam como **Não avaliado / Não monitorado** até uma pessoa responsável validar cada estado. A validação administrativa do status real e a cobertura dos heartbeats continuam sendo etapas de homologação, e não são mascaradas como concluídas.

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
