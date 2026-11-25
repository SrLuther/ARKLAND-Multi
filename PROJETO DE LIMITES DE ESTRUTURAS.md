# Projeto de Limites de Estruturas — ARKLAND

**Produto:** ARKLAND Brasil PvE — ARK: Survival Evolved (ASE) / ArkServerAPI  
**Estado:** desenvolvimento local iniciado; núcleo de regras e testes implementados; integração com o jogo ainda não comprovada  
**Requisitos consolidados:** 21/11/2026  
**Implementação local:** 21/11/2026  
**Decisões de produto:** Ciano, com discussão técnica de Lumo e Codex  
**Release:** nenhuma; alterações permanecem `UNDEFINED`.

> Esta versão substitui decisões anteriores incompatíveis. Não reabrir regras marcadas como definitivas. O trabalho atual não está instalado em servidores ARK e não acessa nem altera produção.

## 1. Objetivo e princípio de segurança

Desenvolver um plugin próprio para contar estruturas efetivamente posicionadas por jogadores e aplicar limites por mapa, tribo e blueprint. A prioridade é não prejudicar os jogadores:

- O plugin nunca remove, destrói, recolhe ou modifica estruturas existentes.
- Reduzir limites, expirar licença, falhar o banco ou reconciliar contagens nunca remove estruturas.
- Não se bloqueia construção com base em inventário parcial, identidade duvidosa ou estado interno inconsistente.
- Se o sistema não consegue verificar uma decisão com segurança, suspende a fiscalização afetada, permite as construções e alerta a administração.
- A fiscalização só começa após inventário inicial completo e validado.
- Operações de banco/rede não podem bloquear o thread principal do jogo.

Esta política de fail-open em falhas internas é deliberada: pode permitir construções além do teto durante uma indisponibilidade que suspenda a fiscalização; o sistema deve registrar e reconciliar essa janela posteriormente.

## 2. Nomenclatura definitiva

- **LPG — Limite Primário Global:** capacidade básica compartilhada de estruturas da tribo em um mapa.
- **LPE — Limite Primário Extra:** capacidade global adicional compartilhada pela tribo, acessível somente a jogador com licença ativa.
- **LEG — Limite Específico Global:** capacidade básica compartilhada para um blueprint configurado.
- **LEE — Limite Específico Extra:** capacidade adicional compartilhada daquele blueprint, acessível somente a jogador com licença ativa.

Essas siglas não devem ser usadas com outros significados.

## 3. Fórmula dos limites extras

Existe um percentual único e editável pelo administrador:

```text
ExtraPercentage = 25
LPE = ceil(LPG × ExtraPercentage / 100)
LEE = ceil(LEG × ExtraPercentage / 100)
```

O valor inicial é 25%. O mesmo percentual vale para LPG e LEG. Reduzir o percentual ou o limite primário não remove estruturas; somente afeta colocações futuras. Valores que causarem overflow, forem negativos ou inválidos devem ser rejeitados, sem substituir a última configuração funcional.

## 4. Contabilização e consumo simultâneo

Toda estrutura realmente construída ou posicionada pelo jogador consome **uma unidade global**, seja vanilla ou de mod. Isso inclui fundações, paredes, tetos, portas, geradores, cabos, tubos, armadilhas, estruturas temporárias enquanto existirem e explosivos posicionáveis que sejam tecnicamente estruturas.

Atores internos que não representem estruturas construídas não devem ser contabilizados. A classificação deve usar evidência técnica do ator e do ciclo de construção; tipos desconhecidos devem gerar diagnóstico, não ser descartados silenciosamente. O plugin não terá uma allowlist/denylist manual como critério geral para incluir ou ignorar estruturas globais.

Blueprints cadastrados também consomem uma unidade de seu limite específico. Cada colocação verifica as dimensões de forma independente:

1. Se a capacidade global primária acabou, a colocação requer uma vaga de LPE e licença ativa.
2. Se o LEG do blueprint acabou, a colocação requer vaga de LEE e licença ativa.
3. A capacidade extra é compartilhada e não aumenta pelo número de jogadores licenciados.
4. Se qualquer dimensão estiver acima da capacidade total aplicável, a colocação é recusada somente se a contagem e o hook estiverem validados; caso contrário, a fiscalização afetada fica suspensa.

Assim, uma colocação pode consumir LPG junto com LEE ou LPE junto com LEG. Não é necessário esgotar o LPG para usar LEE, nem o LEG para usar LPE.

## 5. Licenças

- A licença é individual e identificada pelo SteamID.
- Cada período tem validade de 30 dias.
- Renovações acumulam-se: 2 dias restantes mais uma renovação de 30 dias resultam em 32 dias.
- A licença autoriza seu titular a consumir capacidade extra compartilhada pela tribo; não cria cota individual e não multiplica capacidade.
- Somente a pessoa que realiza a construção precisa ter licença válida para usar a vaga extra.
- Vencer ou revogar a licença nunca afeta estruturas já colocadas.
- Preço e integração de pagamento em Âmbares não estão definidos. O núcleo de licenças deve permanecer independente da economia.

O período de cache/offline e como revogações remotas chegam aos servidores continuam pendências técnicas/de produto; não introduzir TTL arbitrário como se estivesse aprovado.

## 6. Jogadores sem tribo

Um jogador sem tribo recebe os mesmos limites. Sua chave de contagem é individual e baseada no SteamID; dois jogadores solo não compartilham contadores. Ao entrar em tribo, sair, mudar de associação ou transferir propriedade, o sistema reconcilia a propriedade real dos atores. Não se presume que ingresso em tribo transfira automaticamente todas as estruturas.

## 7. Fusões de tribo — regra definitiva

Durante fusão, verificar exclusivamente a contagem global combinada:

```text
Estruturas da Tribo A + Estruturas da Tribo B <= LPG + LPE
```

- LEG e LEE não participam da decisão da fusão.
- Não se exige licença para a fusão.
- Se a soma exceder LPG+LPE, bloquear preventivamente somente se houver interceptação comprovadamente segura.
- Se a fusão não puder ser interceptada, preservar o mundo, reconciliar as contagens e registrar o evento.
- Nunca desfazer fusão destruindo estruturas.

## 8. Identidade por mapa e instância

O identificador legível aprovado combina o número de caracteres do nome do mapa, as três primeiras letras e o número da pasta da instância. Espaços não entram na contagem:

```text
Ragnarok  + instância 04 → 08RAG04
The Island + instância 05 → 09THE05
Alps + instância 03 → 04ALP03
```

Usar o caminho completo e normalizado da pasta como chave técnica para distinguir instâncias, inclusive se o identificador abreviado colidir. Não alterar unilateralmente o formato aprovado, não fixar cinco mapas e não migrar automaticamente dados ao mudar pasta ou mapa. Colisão ou identidade inválida impede carregar contadores de outra instância e suspende a fiscalização afetada.

## 9. Inventário inicial e reconciliação

Inventariar as estruturas existentes antes de ativar a fiscalização, inclusive as de jogadores solo. A contagem precisa cobrir estruturas carregadas, descarregadas/stasis e mods, sem bloquear o servidor. Se não houver comprovação de completude e validação:

1. manter enforcement desativado para a dimensão afetada;
2. permitir construção normal;
3. registrar causa e notificar administração;
4. tentar recuperação/reconciliação sem impacto indevido de desempenho;
5. ativar enforcement apenas após nova validação completa.

Auditorias comparam estruturas observadas no mundo, contador local, dados persistidos e eventos. Correção automática é permitida somente para dados derivados/contadores quando a evidência for suficiente; guardar valores antes/depois, causa e resultado e sempre alertar, inclusive após autocorreção. Nunca “corrigir” o mundo destruindo, transferindo ou alterando estruturas.

## 10. Falhas e persistência

O servidor deverá poder usar snapshot local validado, contadores em memória, licenças previamente validadas e fila local durável enquanto o MariaDB estiver indisponível. A sincronização é assíncrona. Nenhuma consulta de rede ou SQL é permitida no caminho de autorização de construção.

Se o sistema perder a capacidade de contar, identificar a instância, reservar vaga sem corrida ou registrar estado local conforme a política aprovada, suspender a fiscalização afetada e informar a administração. Eventos ainda não enviados não podem ser apagados por idade. Reenvio usa ID idempotente; o evento só é confirmado/removido após confirmação da transação remota.

O armazenamento local deve tolerar duplicidade e encerramento abrupto. A garantia de atomicidade entre save do ARK e histórico é limitada: o inventário pode reconstruir contagem, mas não necessariamente autoria histórica. Essa lacuna deve ser registrada.

## 11. Banco de dados e integração

O banco utilizado pelo ambiente é MariaDB/MySQL. O plugin terá esquema próprio, conta de menor privilégio e conexão isolada do caminho do jogo. Usar worker/filas, timeout, parâmetros, idempotência, backpressure e reconexão. Não reutilizar chamadas SQL síncronas existentes em callbacks do jogo.

Foi criado um primeiro schema versionado em [001_structure_limits.sql](./plugin/StructureLimits/migrations/001_structure_limits.sql). É apenas fonte para revisão; **não foi executado**. Migrações devem ocorrer somente em ambiente autorizado e nunca implicitamente ao carregar plugin de produção.

O site deverá expor mapas, tribos, solo, configurações, limites, contadores, licenças, histórico e auditorias. A página de uma tribo exige validar pertencimento atual; cache antigo não autoriza acesso.

**Avanço local da interface web (UNDEFINED):** foi adicionada a aba **Minha Área → Limites** e a rota autenticada e somente de leitura `/api/player/structure-limits`. A página apresenta LPG/LPE, LEG/LEE, validade da licença, estado/horário de validação do inventário e eventos dos últimos 30 dias. Contagens são mostradas somente para o owner `solo:<SteamID>` autenticado e apenas quando `inventory_state=validated`; os eventos também ficam restritos ao owner solo. Valores de tribo permanecem ocultos porque ainda não há uma ligação aprovada entre a identidade de instância do plugin e `server_id`, nem uma fonte de pertencimento atual confiável para autorização web. Tabelas ausentes retornam estado explícito de integração pendente; a rota não cria schema, não altera configurações, não compra licença e não lê banco de produção durante desenvolvimento. A página é, portanto, uma primeira fatia pronta para receber dados, não uma integração funcional com os servidores: o sink da outbox, ingestão de configurações/contadores e migração autorizada ainda não existem.

## 12. Histórico de movimentações e retenção

Eventos incluem construção, destruição, recolhimento, mudança de propriedade, mudança associada a fusão e correção de contador. Quando tecnicamente observável, registrar mapa/instância, tribo ou jogador solo, SteamID do responsável, estrutura/blueprint, tipo de evento, horário e contagens anterior/posterior. Não inferir autor quando o jogo não o fornece; usar “desconhecido”.

O histórico exibido no site tem retenção de **30 dias**, decisão que substitui 90 dias em registros anteriores. Eventos ainda na outbox e sem sincronização confirmada permanecem armazenados até confirmação/recuperação, mesmo além de 30 dias. Os canais e frequência de alertas, além da inclusão de logs administrativos no período de 30 dias, ainda serão definidos.

## 13. Comando `/limites`

O comando de jogador deve apresentar no mapa atual:

- uso e capacidade primária LPG da tribo (ou do jogador solo);
- uso, LEG e restante de cada blueprint configurado;
- aviso de que LPE/LEE, licença e detalhes adicionais ficam na Minha Área do site ARKLAND.

O comando de chat não deve exibir LPE/LEE. A implementação atual contém somente um formatador de resumo; não há comando registrado no jogo.

## 14. SDK e evidências técnicas

A inspeção estática encontrou declarações em [PrimalStructure.h](./plugin/CustomShop/ArkServerAPI/version/Core/Public/API/ARK/PrimalStructure.h) para `GetFromID`, `BPGetFromID`, `BPGetStructureID`, `IsAllowedToBuild`, `FinalStructurePlacement`, `PlacedStructure`, `Destroyed` e `BPIsAllowedToBuildEx`. Elas são candidatos para investigação, não comprovam o momento em relação ao consumo dos materiais, cobertura de mods ou retorno de veto.

[Actor.h](./plugin/CustomShop/ArkServerAPI/version/Core/Public/API/ARK/Actor.h) declara proprietário/equipe, `GetTribeId` e `AddToTribe`; este último é candidato para investigar fusão, mas não prova cobertura de todos os caminhos nem veto seguro. [GameMode.h](./plugin/CustomShop/ArkServerAPI/version/Core/Public/API/ARK/GameMode.h) expõe níveis e listas de atores, estrutura pendente de destruição, dados de tribo, `GetMapName` e `MaxNumberOfPlayersInTribeField`. Enumerar listas de atores em memória não prova cobertura de atores descarregados/stasis ou save em disco.

O projeto demonstra configuração de hooks em [Main.cpp](./plugin/ArkPlayer/src/Main.cpp). O código de conexão e consulta direta do CustomShop em [ShopPoints.cpp](./plugin/CustomShop/src/ShopPoints.cpp) é síncrono e não deve ser copiado para o hook de construção. A resolução de `server_id` em [ShopTribeSync.cpp](./plugin/CustomShop/src/ShopTribeSync.cpp) não é uma identidade mapa+pasta dedicada.

Licenças existentes do site em [app.py](./plugin/arkshop_web/app.py), ledger em [amber_ledger.py](./plugin/arkshop_web/amber_ledger.py) e banco de Âmbares em [arkbank_service.py](./plugin/arkshop_web/arkbank_service.py) podem orientar integração futura, mas não implementam a semântica deste plugin.

### 14.1 Inspeção da referência local StructuresLimit

Foi lida em modo somente de leitura a cópia local [StructuresLimit.cpp](./referencias-plugins/Ark-Server-Plugins/StructuresLimit/StructuresLimit/StructuresLimit.cpp) e sua configuração [config.json](./referencias-plugins/Ark-Server-Plugins/StructuresLimit/Configs/config.json). O código confirma uma implementação de referência que registra `APrimalStructure.IsAllowedToBuild`, recebe `bFinalPlacement`, extrai um caminho de blueprint da classe e retorna `0` quando julga o limite excedido. Isso torna o hook um candidato concreto para uma PoC, mas não prova que o retorno ocorra antes de consumir itens em todas as situações.

Limitações observáveis no código consultado:

- A varredura limpa os contadores e percorre somente `PersistentLevelField()->GetActorsField()`. Não cobre evidencialmente outros níveis, stasis, atores descarregados ou saves ainda não materializados.
- O hook incrementa as contagens antes de chamar a função original. Se a função original ou outra validação rejeitar a colocação, pode haver contagem temporária incorreta até a próxima varredura.
- A atualização periódica recria as contagens a cada 30 segundos. O callback de morte/destruição está comentado, então remoções dependem dessa varredura.
- Os contadores usam `TargetingTeamField()` como chave; não há separação explícita de jogadores solo por SteamID, transferência de proprietário, ID estável da estrutura ou mapa/pasta.
- Não há licença, LPE/LEE, fila durável, persistência ou tratamento de fusão.

**Conclusão:** a referência ajuda a identificar assinaturas e um formato de blueprint que merece validação. Ela não atende aos requisitos do ARKLAND sem redesenho de contagem, reservas, identidade, licenças, persistência e fail-open. O código não foi copiado para o plugin novo; não foi executado nem testado em servidor.

## 15. Estado da implementação local

### 15.1 Implementado nesta etapa

O núcleo isolado em [StructureLimitsCore.h](./plugin/StructureLimits/src/StructureLimitsCore.h) e [StructureLimitsCore.cpp](./plugin/StructureLimits/src/StructureLimitsCore.cpp) implementa:

- parser JSON estrito para configuração local, validando `Enabled`, LPG, percentual, blueprints duplicados, mapa/pasta e pasta de outbox;
- cálculo de LPE/LEE com `ceil`, validação e proteção contra overflow;
- identidade abreviada aprovada com nome de mapa, prefixo e número de pasta, mais caminho de instância normalizado;
- contadores por tribo ou jogador solo;
- ativação somente por snapshot completo, validado, da instância exata e com evidência explícita de segurança do hook de colocação;
- bypass seguro enquanto não há inventário validado;
- reservas de vaga sob mutex para impedir sobrecarga por tentativas simultâneas no núcleo;
- decisão independente global/específica; extra exige licença ativa do SteamID construtor;
- commit/cancel da reserva e liberação idempotente por ID de estrutura;
- reatribuição de propriedade move a contagem global e específica sem duplicar;
- renovação de licença cumulativa por 30 dias;
- fusão validada somente pelo teto global, sem licença e sem LEG/LEE;
- formatação de mensagem de dados para LPG/LEG primários.
- probe ArkServerAPI compilável, desativado por padrão e condicionado a `Enabled=true` e a opt-ins diagnósticos separados: `ObservationProbeEnabled` para posicionamento e `LifecycleObservationEnabled` para callbacks `BeginPlay`/`Destroyed`, ambos falsos por padrão; observa `APrimalStructure.IsAllowedToBuild` em chamadas finais e callbacks de ciclo de vida, preservando as chamadas originais e registrando retorno/IDs disponíveis/classe. `BeginPlay` pode representar carregamento do save e `Destroyed` não identifica sozinho a causa; não são eventos autoritativos de construção ou remoção. Nada altera o retorno nem declara que colocação ocorreu.

[DurableOutbox.cpp](./plugin/StructureLimits/src/DurableOutbox.cpp) implementa spool local file-per-event no Windows: ID restrito, escrita temporária, `FlushFileBuffers`, publicação atômica, leitura pendente, deduplicação por ID/payload e remoção somente por confirmação explícita. Arquivos temporários de gravação interrompida são detectados e sinalizados, não apagados. [OutboxSynchronizer.cpp](./plugin/StructureLimits/src/OutboxSynchronizer.cpp) percorre a fila em worker separado, tenta entregar cada evento e só confirma o arquivo após retorno de sucesso do sink; falhas mantêm o evento pendente para retry. A entrega é at-least-once, portanto o sink precisa de timeout limitado e idempotência pelo event ID. O worker é infraestrutura genérica: ainda não existe sink MariaDB/MySQL conectado.

[LocalSnapshotStore.cpp](./plugin/StructureLimits/src/LocalSnapshotStore.cpp) grava inventário completo e validado em JSON versionado, calcula CRC32, impõe teto de 128 MiB, publica por arquivo temporário/flush/troca atômica e recusa identidade de mapa divergente, IDs repetidos ou campos essenciais vazios. Ao carregar, valida o conteúdo e retorna estruturas como candidato não validado, sempre com `complete=false`, `validated=false` e `placementHookValidated=false`; exige nova varredura ao vivo antes de ativar fiscalização. Detecta temporários interrompidos, inclusive quando o arquivo final não existe. A integridade detecta corrupção acidental, não adulteração maliciosa.

O parser em [StructureLimitsConfig.cpp](./plugin/StructureLimits/src/StructureLimitsConfig.cpp) aceita o exemplo deliberadamente desabilitado com `LPG=0`; para configuração habilitada exige mapa, pasta numérica da instância, LPG positivo e caminhos absolutos de snapshot e outbox. Também rejeita valores inválidos e blueprints repetidos. A segurança do hook é uma evidência interna de ativação, não uma opção editável no JSON. `configs/config.json.example` não é configuração operacional. O schema inicial em [001_structure_limits.sql](./plugin/StructureLimits/migrations/001_structure_limits.sql) é somente um artefato versionado para futura revisão/autorização. O projeto e testes standalone estão definidos em [CMakeLists.txt](./plugin/StructureLimits/CMakeLists.txt) e [core_tests.cpp](./plugin/StructureLimits/tests/core_tests.cpp).

### 15.2 Ainda não implementado — não é utilizável em servidor

- DLL de produção com fiscalização: há um probe observacional compilável que registra o retorno original de `IsAllowedToBuild` e callbacks de ciclo de vida, mas ainda não foi instalado ou executado em servidor; ele não faz veto nem declara colocação concluída.
- Hooks de colocação, remoção, pickup, demolição, destruição, mudança de propriedade ou fusão.
- Prova de bloqueio anterior ao consumo de recursos.
- Identificação/classificação runtime de estruturas vanilla, mods e atores auxiliares.
- Inventário completo do mundo, stasis e retomada de scan.
- `Plugin_Init` valida a configuração uma vez, cria o `LimitEngine` ainda suspenso, abre a outbox, carrega snapshot anterior somente como candidato não validado e registra identidade/capacidades/pendências; os hooks continuam somente observacionais. Não há inventário live nem ativação de enforcement.
- Snapshot e outbox estão ligados ao início/fim do plugin; ainda não há produção de eventos autoritativos nem worker conectado a sink. Faltam cliente/pool MySQL, sink transacional idempotente, timeouts/reconexão do cliente real e sincronização da outbox.
- API/site, permissões do histórico, alertas administrativos, interface e comando de chat.
- Migração/autorização de banco em ambiente de desenvolvimento.

O exemplo de configuração está `Enabled=false`, tem LPG zero e não deve ser instalado como configuração funcional. As opções `ObservationProbeEnabled` e `LifecycleObservationEnabled` são opt-ins independentes e desativados por padrão; o probe de ciclo de vida pode gerar logs volumosos e só deve ser usado em ambiente controlado. A chave duplicada `LifecycleBeginPlayObservationEnabled` foi removida do exemplo, e o parser agora rejeita chaves JSON duplicadas. Configuração habilitada exige caminhos absolutos para `LocalSnapshotFile` e `LocalOutboxDirectory`. Em 24/11/2026, [build_plugin_probe.bat](./plugin/StructureLimits/build_plugin_probe.bat) compilou a DLL de runtime diagnóstico 0.4-dev, incluindo núcleo, snapshot, outbox e worker. O filtro dos callbacks de ciclo de vida exclui supply crates que derivam da classe-base conhecida no SDK; outras classes auxiliares ainda não foram classificadas. O pacote está em [StructureLimits-observer-probe-0.4-dev.zip](./plugin/StructureLimits/packages/StructureLimits-observer-probe-0.4-dev.zip). A DLL compilou e linkou localmente, mas 0.4-dev ainda não foi carregada em servidor. Não existe DLL de enforcement implantável.

## 16. Testes locais executados

Compilação standalone C++20 com MSVC em diretório temporário fora do repositório. Executável também ficou fora do repositório. Resultado: `StructureLimits core tests passed` (exit code 0). O probe ArkServerAPI também compilou e linkou contra o SDK local; a compilação verifica assinatura/tipos de C++ apenas, não execução ou segurança em runtime.

Os testes em [core_tests.cpp](./plugin/StructureLimits/tests/core_tests.cpp) cobrem parser/validação de config, cálculo/arredondamento, identidade de instância e mismatch, fail-open sem snapshot e com hook não validado, capacidade primária/extra, compartilhamento de extra por múltiplos licenciados, reserva/cancel/commit, liberação idempotente, LEG/LEE e LPE, licença expirada/renovação cumulativa, jogadores solo, reatribuição de propriedade, preservação de estruturas após redução de limite, reserva em voo durante suspensão, fusão que ignora limites específicos, concorrência de 24 reservas contra uma vaga, recuperação do outbox após reabertura, evento idempotente, detecção de temporário incompleto, snapshot válido e não validado, CRC corrompido, mapa divergente, recusa de snapshot incompleto, temporário órfão sem arquivo final e retry assíncrono do sink.

Esses testes validam somente o núcleo standalone, persistência local, fila e retry genérico no host de desenvolvimento. **Não validam** registro/chamada dos hooks no runtime, timing ASE, consumo de materiais, world scan, mods, rede, MySQL, falha abrupta de energia ou estabilidade/performance de servidor. O DLL de probe compilado não foi executado. Em 22/11/2026, o probe foi ampliado para registrar callbacks `BeginPlay` e `Destroyed`; a compilação/link local passou contra o SDK presente, mas essa verificação não substitui execução controlada em servidor de teste.

Em 24/11/2026, a DLL 0.4-dev compilou e linkou com MSVC usando `build_plugin_probe.bat`; não foram executados testes unitários nesta rodada nem feito teste runtime em servidor. A compilação confirma ligação dos módulos, não funcionamento de persistência, hooks ou enforcement no jogo.

## 17. Pendências técnicas e riscos prioritários

1. **Placement pré-consumo:** provar em jogo que o hook intercepta antes do custo para vanilla e mods. É bloqueador para qualquer enforcement real.
2. **Cobertura de objetos:** encontrar inventário completo incluindo stasis/descarregados e critério para distinguir estrutura construída de ator interno.
3. **Identificadores:** validar persistência/uniqueness do `StructureID` e identidade estável de blueprint entre versões/mods.
4. **Eventos de saída:** provar coverage/deduplicação de destruir, demolir, recolher, pickup, transferência e operações de mods.
5. **Fusão:** investigar `AddToTribe` e outros caminhos; se não houver veto seguro, observar e reconciliar sem destruir.
6. **Snapshot local:** implementação inicial concluída com formato versionado, CRC32, teto de tamanho, escrita atômica e reabertura como candidato não validado; falta teste de falha abrupta no Windows e integração com scan/ciclo de vida.
7. **Outbox:** spool e worker genérico implementados; reportar/reter arquivos `.tmp` órfãos e validar fila cheia/disco indisponível, timeout, retry e idempotência ponta a ponta com um sink real.
8. **MySQL:** criar worker/conexão própria, grants mínimos, TLS se necessário, timeouts, migrations versionadas e retry/outbox; nenhuma ligação foi feita.
9. **Configuração:** parse e validação, configurações por mapa e blueprints, preservação da última versão funcional, fonte administrativa e publicação.
10. **Licença offline:** política de cache/TTL, revogação, relógio local e compra/renovação financeira.
11. **Identidade:** gerar/testar chave técnica estável do caminho completo, tratar colisão e mudança de diretório sem misturar dados.
12. **Performance/observabilidade:** scan em lotes, progresso, contadores de saúde, alertas, atraso de fila e métricas sem travar o thread do jogo.

Decisões de produto ainda não especificadas não devem virar constantes arbitrárias. Falha de banco por si só não pode bloquear construção legítima; falha de contagem ou identidade suspende enforcement até recuperar evidência.

## 18. Sequência de desenvolvimento

1. **Consolidação:** requisitos atualizados neste documento; siglas e regras fechadas não devem ser reabertas.
2. **Núcleo:** concluído em versão inicial e coberto por testes unitários standalone; ampliar testes adversariais e validar no compilador/runtime de produção.
3. **Persistência:** snapshot local inicial, outbox/recovery e worker genérico implementados e cobertos em teste local; próxima etapa é adapter MySQL transacional e integração controlada em staging autorizado, sem acessar produção.
4. **Investigação paralela de SDK:** inspecionar assinaturas e call sites; construir uma PoC isolada somente quando disponível/explicitamente aprovada, sem ativar bloqueios não comprovados.
5. **Integração Ark:** iniciar adapter somente depois de demonstrar ciclo seguro de autorização e cobertura observável; nenhuma integração parcial deve se anunciar como fiscalização ativa.
6. **Auditoria/command/site:** implementar somente após contrato de dados e autorização atual estarem definidos.
7. **Validação:** ambiente isolado, save descartável e casos de mod, concorrência, crash e recuperação; produção fica fora do escopo sem autorização própria.

## 19. Matriz mínima futura de aceitação

Testes unitários já cobrem subconjuntos da regra. A futura integração deve também demonstrar:

1. construção dentro de LPG; excedente sem licença; uso de LPE com licença; excedente de LPG+LPE;
2. LEG independente; LEE com licença; licença vencida; renovação cumulativa; dois licenciados compartilhando o mesmo teto;
3. solo isolado; ingresso/saída/transferência; fusão dentro e acima do teto global;
4. fusão acima de LEG+LEE mas dentro de LPG+LPE permitida;
5. snapshot incompleto/inválido fail-open; DB indisponível; reconexão; outbox pendente após reinício; evento duplicado;
6. redução de limites sem remoção; divergência de contadores e reconciliação sem tocar o mundo;
7. tentativa simultânea; falha/cancelamento após reserva; destruir/recolher exatamente uma vez;
8. estrutura vanilla, de mod, cabo/tubo, armadilha, temporária e classificações internas não contabilizáveis;
9. custo de materiais preservado em toda recusa comprovada.

## 20. Segurança e autorização

Este desenvolvimento local está autorizado. Permanecem proibidos nesta autorização: alterar servidor de produção, instalar plugin, reiniciar ARK, modificar saves, excluir/mover estruturas, editar configuração ativa, consultar/escrever no MySQL de produção ou executar migrações reais. Testes locais seguros são permitidos. Qualquer validação que dependa do runtime real, dados de jogadores ou impacto operacional exige procedimento isolado e autorização específica.

Alterações locais permanecem `UNDEFINED`; não incrementar versão publicada nem anunciar release. O próximo relatório deve separar o que foi implementado, testado, bloqueado por dependência técnica e ainda não integrado.
