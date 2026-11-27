# ARKLAND Structure Limits

## Evolução atual — 0.9.3-dev (27/11/2026)

Integra a decisão de colocação ao núcleo (reservar, confirmar/cancelar e suspender em falha) e fornece o primeiro veto controlado. Com `PlacementPilotEnabled=true`, o administrador usa `StructureLimits.Pilot <SteamID64 conectado> next` pelo RCON. O piloto recusa **uma única tentativa final que o jogo permitiria**, apenas desse jogador, e expira em 120 segundos. É possível trocar `next` por um blueprint exato. `StructureLimits.Pilot cancel` cancela uma tentativa ainda armada.

Antes de armar, deixe o item no inventário. Depois, faça uma tentativa e aguarde dois segundos sem mover/craftar o item nem tentar novamente. `StructureLimits.Status` apresenta `placement.pilot_state`, `item_before`, `item_after` e `placement_callbacks_after_veto`. `item_preserved` só significa que aquele blueprint preservou a quantidade nessa tentativa e não gerou callback de colocação; não certifica todos os mods. `inventory_changed_before_hook` invalida a prova e preserva o retorno original do jogo. Não são alterados, repostos ou retirados itens pelo plugin.

O opt-in é falso no exemplo. Nenhum piloto é armado ao iniciar/recarregar o plugin. A contagem básica já validada não precisa ser repetida. A próxima validação humana é **uma recusa com retenção do item**, preferencialmente uma estrutura vanilla e uma do mod usado. O bloqueio geral continua dependendo de inventário completo e validação do caminho de colocação; os indicadores globais continuam falsos.

## Histórico — 0.9.2-dev (27/11/2026)

Atribuição offline por índice de fatos exportado de cópias estáveis de tribos/perfis com o parser fixado. Um worker lê o índice e verifica os hashes dos arquivos reais na instância; não existe I/O de perfil, SQL ou rede no callback do jogo. Fontes alteradas deixam de autorizar essa atribuição. Dados nativos têm prioridade, e cada estrutura informa `owner_source`.

No 05 vazio, as 231 estruturas foram atribuídas às duas tribos corretas (227 e 4), preservando todos os IDs. Não foi necessário repetir o teste de colocar/remover estruturas. Fiscalização e inventário completo permanecem desligados. O caminho solo tem testes locais, mas não foi homologado com jogador solo no piloto. Evidências e atualização do índice em [HOMOLOGACAO_2026-11-27.md](HOMOLOGACAO_2026-11-27.md).

## Histórico — evolução 0.9-dev (26/11/2026)

A build piloto do 05 agora exporta identidade dos atores, proveniência das observações, catálogo de classes do SDK e evidências dos atores excluídos por identidade/propriedade ausente. A última varredura concluída fica separada da varredura corrente e registra mutações de coleções e conflitos.

A ferramenta [save_audit.py](tools/save_audit.py) compara uma cópia estável do save com esse censo. No piloto, as 231 estruturas observadas corresponderam ao save em nome, classe, proprietário e XYZ, com diferença zero. A auditoria também identificou 221 atores de origem no mapa, sem dono jogador, e manteve 32 atores dinâmicos como classificação pendente. O resultado global não foi promovido a inventário completo: `complete_inventory=false`, `enforcement=false`.

Foram aprovados 24 casos C++ e 14 testes do comparador. A versão foi carregada somente no 05, preservando os processos de jogo. Evidências, limitações e procedimento em [IMPLANTACAO_0.9.md](IMPLANTACAO_0.9.md). O teste em jogo seguinte é conferir estabilidade da contagem ao mudar de região.

## Histórico — evolução 0.8-dev (26/11/2026)

O runtime agora mantém inventário observado por StructureID, com consulta `/limites`, confirmação de colocação pelo retorno bem-sucedido de `FinalStructurePlacement`, remoção idempotente pelo ciclo `Destroyed` durante servidor pronto e coordenadas XYZ/latitude/longitude usando a conversão do SDK para o mapa atual.

`LiveInventoryEnabled` é opt-in e desativado no modelo. A varredura incremental cobre PersistentLevel, demais níveis residentes e LocalStasisActors, deduplicando IDs. Ela respeita orçamento de 2 ms/512 entradas por tick. Ausência em uma varredura não remove um registro. Supply crates e previews são excluídos. Atribuição de tribo usa a associação comprovada de controladores conectados; jogador solo requer SteamID associado ao PlayerDataID. Atores ainda sem identidade atribuível permanecem no inventário técnico, sem serem atribuídos arbitrariamente a jogadores.

`observed-inventory.json` é um estado derivado e explicitamente parcial, gravado atomicamente por worker. Eventos confirmados ficam na outbox durável; não são apagados por idade. A fila é limitada e sinaliza falha ao saturar. Serialização do inventário completo e disco ficam no worker; callbacks nunca esperam rede/SQL. O estado observado anterior não é restaurado como verdade após reinício.

`StructureLimits.Status` no RCON informa saúde do worker, contagens, scans, conflitos e estado de fiscalização. `/limites` apresenta contagem observada, LPG/LEG e aviso de inventário em validação. Não exibe LPE/LEE no jogo.

**Ainda não aplica bloqueios.** A cobertura de estruturas descarregadas/save, o veto antes do consumo de materiais e as regras de propriedade/transferência precisam ser comprovados. Uma destruição não informa automaticamente a causa: pickup, demolição, dano e decaimento compartilham a liberação do ID observado, sem inventar a origem. Encerramento/carregamento são ignorados enquanto o servidor não está pronto. Falhas de disco não produzem garantias de recuperação de eventos que ainda estavam somente em memória.

Compilação: os scripts aceitam `STRUCTURELIMITS_SDK_ROOT` para reaproveitar um SDK existente. Somente este plugin é compilado. A instalação piloto continua restrita ao servidor 05; seções abaixo registram as etapas anteriores e suas limitações históricas.

Plugin em desenvolvimento para ARK: Survival Evolved / ArkServerAPI. Este diretório contém núcleo C++ independente do jogo, parser/validador JSON, persistência local, outbox durável, testes locais, schema versionado e build observacional. **Ainda não é um plugin funcional de limites**: a build 0.2-dev foi carregada no servidor de teste 05 (ARK 361.7 / ArkServerAPI 3.56) e registrou uma verificação final permitida para uma fundação de madeira do Structures Plus. A build local 0.4-dev inicializa o núcleo, abre a outbox, carrega snapshots somente como candidatos não validados e instala hooks observacionais por opt-in; também exclui callbacks lifecycle de atores derivados da classe-base de supply crate. A versão 0.4-dev não foi carregada em servidor. Continua sem bloquear construção, sem fazer inventário completo do mundo, sem integração MySQL e sem prova de consumo de materiais.

## Regras já representadas no núcleo

- LPG e LEG primários; LPE e LEE calculados com `ceil(limite primário × ExtraPercentage / 100)`.
- Licença individual de 30 dias, com renovação acumulada. A licença somente autoriza consumir extra compartilhado.
- Contabilização separada por tribo; jogador sem tribo usa uma chave individual SteamID.
- Reservas atômicas de vaga para que tentativas concorrentes não ultrapassem o limite em memória.
- Fusão validada exclusivamente contra o teto global combinado; licenças e limites específicos não participam.
- Fiscalização suspensa até receber inventário completo, validado e correspondente ao mapa e pasta da instância.
- A ativação também exige evidência interna explícita de que o hook de colocação foi validado; não existe opção JSON para forçar essa condição.
- Parser de configuração que exige parâmetros válidos e rejeita limites específicos duplicados.
- Outbox local por arquivo, com ID idempotente, escrita temporária seguida de flush e publicação atômica no Windows. A remoção do evento só ocorre por chamada explícita de confirmação.
- Snapshot local versionado, com CRC32, limite de tamanho, escrita e troca atômicas; o carregamento retorna apenas um candidato e nunca marca o inventário como completo/validado.
- Worker genérico de sincronização da outbox fora da thread do jogo, com retry, confirmação somente depois do sink e sem descarte de evento em erro; o sink deve impor timeout e idempotência.
- `/limites` tem um formatador de dados para exibir LPG e LEG primários e encaminhar LPE/LEE ao site; o comando do jogo ainda não está conectado.

## Integração local com a web

A Minha Área ganhou a aba **Limites** e o endpoint autenticado somente de leitura `/api/player/structure-limits`. Ele está preparado para apresentar configuração por mapa, LPG/LPE, LEG/LEE, estado do inventário, licença e eventos com retenção de 30 dias. Até existir um vínculo seguro com a identidade atual da tribo, a API retorna contagens e eventos somente do owner solo cujo SteamID corresponde à sessão autenticada; dados de tribo não são inferidos de cache antigo. Se as tabelas não estiverem instaladas, a página informa que a integração está pendente. O sink da outbox, a migração autorizada, o vínculo instância↔servidor e a sincronização de dados ainda não existem; por isso a interface não significa que os servidores já estejam publicando contagens.

## Segurança e limites atuais

O núcleo não identifica por conta própria quais atores do mundo são estruturas válidas, não faz inventário Ark, não atribui autoria a estruturas antigas, não observa transferência de propriedade, não valida o timing do hook de construção e não consulta licenças remotas. A fiscalização permanece fail-open enquanto não há snapshot validado. O probe registra retorno do `IsAllowedToBuild` somente em verificações finais, depois de chamar a implementação original; esse retorno não prova que a estrutura foi colocada nem que materiais foram consumidos. O callback `Destroyed` é uma pista de ciclo de vida, não prova pickup ou demolição; a build 0.2-dev só registra candidatos com metadados de dono/tribo. `BeginPlay` é opt-in separado porque dispara também durante carregamento e pode gerar alto volume. Supply crates derivados da classe-base do SDK são excluídos dos logs lifecycle na 0.4-dev; outros falsos positivos continuam possíveis. A integração histórica 0.2-dev com o servidor de teste 05 não equivale à validação da nova build. O schema SQL não foi aplicado.

O arquivo `configs/config.json.example` é um exemplo deliberadamente desabilitado, com `LPG=0`; não é uma configuração operacional. O parser rejeita chaves JSON duplicadas para impedir que edições ambíguas sejam aceitas com o último valor silenciosamente prevalecendo. `ObservationProbeEnabled` e `LifecycleObservationEnabled` são opções diagnósticas distintas e desativadas por padrão. `LifecycleObservationEnabled` observa o callback `Destroyed` apenas quando encontra metadados de propriedade/tribo; `LifecycleBeginPlayObservationEnabled` controla separadamente o callback ruidoso de carregamento e também fica desativado. Configuração habilitada requer caminhos absolutos para `LocalSnapshotFile` e `LocalOutboxDirectory`. `migrations/001_structure_limits.sql` é somente um artefato versionado para futura revisão/autorização.

`build_plugin_probe.bat` compila a DLL 0.4-dev com todos os componentes de núcleo e persistência local. A DLL permanece diagnóstica: ao iniciar, registra identidade/capacidades e estado do snapshot/outbox, mas não considera snapshot anterior como inventário atual e não ativa fiscalização. Não instalar essa build como limitador de estruturas.

## Testes do núcleo

Com Visual Studio C++ instalado:

```powershell
plugin\StructureLimits\build_core_tests.bat
```

`build_core_tests.bat` descobre o Visual Studio, compila em `%TEMP%` e executa os testes standalone do núcleo. `CMakeLists.txt` oferece também targets de biblioteca e CTest quando CMake estiver disponível. `build_plugin_probe.bat` somente compila/linka em `%TEMP%` a DLL de observação; esse artefato não é copiado ao servidor nem é DLL de enforcement. A versão 0.4-dev ainda precisa ser validada em ambiente isolado compatível com a versão exata do ARK/ArkServerAPI antes de qualquer uso.

## Avanço para ARKLAND Multi v1.12.25

Em 25/11/2026, a build observacional 0.6-dev foi instalada somente no servidor de teste 05 e carregou após a reinicialização do processo. O log confirmou inicialização e manteve enforcement suspenso/fail-open; o servidor e os demais mapas não tiveram alterações nesta etapa. O probe agora inclui `blueprint_key` na verificação final para orientar a validação em jogo. A instalação ainda não comprova o resultado de novas construções, remoções, consumo de materiais, inventário completo, integração MySQL ou aplicação de limites.

A identidade de blueprint é normalizada de forma central antes da comparação de limites específicos: aceita caminhos `Blueprint'...'` e nomes completos de classe ArkApi, remove wrappers/prefixos UObject, `Default__` e o sufixo `_C`, e normaliza caixa e separadores. Colisões depois da normalização são rejeitadas. Isso reduz divergências de formatação entre a classe observada e o blueprint configurado; não converte uma enumeração parcial em inventário completo nem habilita enforcement.

## Próxima etapa local — 0.7-dev

`ResidentInventoryProbeEnabled` é uma opção diagnóstica desativada por padrão. Com opt-in, uma chamada no timer do ArkServerAPI espera o mundo e um jogador conectado, percorre uma vez os atores de todas as `UWorld.Levels` carregadas e registra métricas de estruturas e qualidade dos IDs/metadados. Supply crates derivados da classe-base conhecida são excluídos e o mesmo ponteiro de ator não é contado duas vezes. A varredura é explicitamente parcial: não lê stasis nem registros diretamente dos saves, não prova atribuição de tribo e não cria `WorldSnapshot` validado. Portanto, não autoriza limites nem altera contagens. O propósito é medir cobertura no ambiente de teste e descobrir o próximo bloqueio para o inventário autoritativo.
