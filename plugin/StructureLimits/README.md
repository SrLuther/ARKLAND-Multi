# ARKLAND Structure Limits

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
