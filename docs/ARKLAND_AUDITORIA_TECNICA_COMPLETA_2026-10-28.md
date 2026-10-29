# Auditoria técnica do Ark Land — 28/10/2026

## Escopo e conclusão executiva

Este relatório atende à solicitação de auditoria anexada. A execução foi somente de investigação, comparação e planejamento: nenhum código, configuração de servidor, banco, release ou arquivo de produção foi alterado. Nenhum teste que escreva em arquivos ou servidores reais foi executado.

O aplicativo ativo é o gerenciador desktop ASE baseado no fluxo TEK (`main.py` → `src.app_tek.ARKServerManagerApp`). O projeto declara suporte ao **ARK: Survival Evolved (ASE)**; não se deve misturar opções de ASA no inventário de requisitos.

Há problemas arquiteturais comprováveis na leitura/escrita de INI, na edição de rampas, na sincronização entre servidores, no diagnóstico de saves e na integridade textual da interface. A cobertura atual pode ser quantificada parcialmente: a tabela de mapeamento do gerenciador TEK contém **218 entradas** (136 em `ServerSettings`, 76 em `GameMode`, 3 em `SessionSettings`, 2 em `MessageOfTheDay`, 1 em `GameSession`). Isso mede o mapa interno, não o universo de opções ASE nem tudo que a interface permite. O novo anexo fornece um snapshot completo da antiga página Fandom e permite comparar candidatos, mas não é um inventário canônico validado para a versão ASE-alvo: tem opções históricas, comunitárias, placeholders e entradas cuja aplicabilidade precisa ser verificada. Portanto, não há percentual de cobertura confiável até concluir essa classificação. Inventar um denominador ou dizer “100% coberto” seria incorreto.

> Referência visual recebida nesta etapa: a captura e o vídeo mostram o editor ASM lado a lado para progressões de jogador e Dino, com XP máximo, habilitação independente, tabelas separadas e rolagem. O painel de jogador exibe nível, XP requerido, pontos de engrama do nível e total acumulado; Dino exibe nível e XP requerido. Há controles de adicionar/remover linha e uma barra de ações. O vídeo confirma o uso de rolagem nas tabelas e mostra os campos de XP máximo. O aviso sobre níveis reservados para ascensão aparece com dígitos pouco legíveis/variáveis; não fixar a regra dos 10 níveis apenas com base nessa referência visual.

## Evidência e limites

- **Confirmado no código**: comportamento diretamente observável em arquivos e funções indicados abaixo.
- **Inferência**: risco provável a partir do desenho atual; requer validação contra uma instalação ASE controlada.
- **Não confirmado**: depende de documentação externa bloqueada ou de teste com servidor real. Não será tratado como fato do jogo.

A referência fornecida, `ark.fandom.com/wiki/Server_configuration`, foi migrada para a [ARK Official Community Wiki — Server configuration](https://ark.wiki.gg/wiki/Server_configuration). Também são pertinentes [Server Config](https://ark.wiki.gg/wiki/Server_Config) e [Ini](https://ark.wiki.gg/wiki/Ini). Nesta continuação, o usuário forneceu como anexo o texto completo da página Fandom (snapshot comunitário); foi possível comparar sua lista textual com o código. Esse snapshot pode conter entradas históricas, de versão específica, placeholders e afirmações comunitárias incertas. Ele permite uma reconciliação melhor, mas não equivale a uma validação completa da documentação canônica vigente nem de cada opção no binário ASE usado em produção. O repositório possui [ARK_SERVER_CONFIG_REFERENCE.md](../ARK_SERVER_CONFIG_REFERENCE.md), referência própria atualizada em 31/05/2026.

### Reconciliação adicional usando o snapshot fornecido

O snapshot tem 1.878 linhas e divide o conteúdo em Command Line, GameUserSettings.ini, Game.ini, whitelist de administradores e transferências Cross-ARK. Um parser lexical simples identificou 135 tokens candidatos a opções em `GameUserSettings.ini`/`Game.ini`; 70 aparecem com o mesmo nome em `INI_MAP`. **Esse não é um percentual de cobertura**: o conjunto contém campos internos de estruturas, placeholders, exemplos e configurações que o projeto representa como raw ou em outros módulos, portanto o resultado serve apenas para localizar itens que precisam de classificação manual.

Entre opções compostas/avançadas no snapshot que não aparecem como campo simples em `INI_MAP` estão `ConfigAddNPCSpawnEntriesContainer`, `ConfigSubtractNPCSpawnEntriesContainer`, `ConfigOverrideNPCSpawnEntriesContainer`, `ConfigOverrideItemCraftingCosts`, `ConfigOverrideItemMaxQuantity`, `ConfigOverrideSupplyCrateItems`, `LevelExperienceRampOverrides`, `OverrideNamedEngramEntries`, `OverrideEngramEntries` e `NPCReplacements`. Isso **não** significa que estejam totalmente ausentes: há suporte parcial/raw específico em `asm_game_list_ini.py`, `asm_server_config.py`, `asm_engram_entries.py`, `asm_spawner_editor.py` e `asm_server_panel.py`. O que falta é uma matriz por subcampo que confirme parse, validação, edição, preservação de linhas repetidas, escrita e round-trip para todas as estruturas.

O snapshot também documenta opções como `CryopodNerfDamageMult`, `CryopodNerfDuration`, `CryopodNerfIncomingDamageMultPercent`, `EnableCryopodNerf`, `StructurePickupHoldDuration`, `StructurePickupTimeAfterPlacement`, `MutagenLevelBoost*`, `UnicornSpawnInterval`, `VolcanoIntensity` e `WorldBuffScalingEfficacy`. A busca no mapa INI TEK e nos editores não encontrou campos/UI dedicados para várias delas. Como o snapshot pode ser antigo e parte das opções pode ser contextual ou obsoleta, classificá-las como ausentes exige primeiro confirmar aplicabilidade à versão ASE-alvo. O estado prudente é **candidato a não mapeado**, não “opção atual certamente suportada pelo servidor”.

Na linha de comando, o snapshot lista grande conjunto de flags `-...`, parâmetros `?...=...`, URLs dinâmicas/live-tuning e opções de mods/mapas. O projeto aceita `additional_args` genérico e constrói alguns argumentos geridos por campo; esse mecanismo permite ao administrador tentar opções sem UI dedicada, mas não oferece catálogo tipado, validação por plataforma/versão, detecção de duplicidade/conflito ou reconciliação de parâmetros `?` contra flags `-`. Por isso CLI deve ser uma trilha própria do inventário; “pode colar em argumentos adicionais” não equivale a suporte de primeira classe nem prova de funcionamento.

## 1. Arquitetura atual e cobertura de configuração

### Caminho ativo

`main.py` inicia `src.app_tek.ARKServerManagerApp`. A aplicação TEK usa configuração de servidor tipada em `src/asm_engine/asm_server_config.py`, campos de interface em `src/pages/` e `src/asm_ui/`, leitura/geração INI em `src/asm_engine/asm_ini_manager.py`, e gerenciamento de instâncias em `src/asm_engine/asm_server_manager.py`. Há também módulos clássicos ainda presentes (`src/app.py`, `src/server_config.py`, `src/ark_ini.py` e `src/ark_ini_fields.py`). Essa coexistência aumenta o risco de correção em uma tela/fluxo não usado pelo executável atual.

### Reconciliação quantitativa disponível

| Camada | Evidência mensurável | O que significa | Limite |
|---|---:|---|---|
| Mapa TEK de opções INI | 218 mapeamentos: 136 `ServerSettings`, 76 `GameMode`, 3 `SessionSettings`, 2 `MessageOfTheDay`, 1 `GameSession` | Entradas conhecidas pela tabela de mapeamento | Não conta todos os campos CLI, valores dinâmicos, opções raw ou o universo publicado pela wiki |
| Modelo de servidor | Aproximadamente 300 campos declarados/computados em `AsmServerConfig` | Configuração operacional do app, nem todos são opções nativas do ARK | Inclui estado interno, caminhos, plugins e preferências |
| Opções de inicialização | Parte representada por campos e `additional_args`/construtor de argumentos | Flexibilidade parcial para flags sem UI dedicada | Não existe reconciliação comprovada de todas as flags documentadas e seus valores/repetições |
| INI avançado | Campos raw e injeção de texto, além do mapa de campos tipados | Escape hatch para configurações não expostas | Raw também passa por estruturas que podem colapsar ocorrências |
| Cobertura documental total | **Indeterminada** | A comparação correta exige inventário canônico versionado | Fonte online inacessível nesta execução; não declarar percentual |

O projeto não possui um catálogo único que relacione cada opção documentada a versão ASE, arquivo/seção, tipo, padrão, faixa, dependências, repetição, tela, parser e serializer. Sem esse catálogo, a manutenção depende de mapas e telas dispersos e não é possível comprovar cobertura completa.

## 2. INI: estrutura, round-trip e edição isolada

### Achados confirmados

1. `src/ark_ini.py`, `src/ark_ini_fields.py` e `src/asm_engine/asm_ini_manager.py` utilizam `configparser.RawConfigParser` como modelo central. `optionxform = str` preserva caixa de chaves, mas o parser ainda é um mapa de seção→chave→valor, não uma sequência de ocorrências.
2. `strict=False` permite carregar algumas duplicidades sem erro, mas não as representa como entradas distintas: valores com a mesma chave são sobrescritos no mapeamento. Ao serializar, comentários, espaçamento, posição original e ocorrências duplicadas não têm identidade preservada.
3. A normalização de seção/canonicalização pode juntar seções repetidas. Escritas são reconstruções do arquivo; preservação de conteúdo desconhecido é semântica no nível de chave/seção, não preservação textual/lexical.
4. O importador e o replicador também trabalham com objetos indexados por campos/chaves. Portanto, não há garantia geral de round-trip estrutural nem de que uma alteração isolada seja a única diferença no arquivo exportado.
5. `asm_game_list_ini.py` trata algumas linhas repetidas por uma allowlist e pós-patch textual. Isso é uma exceção específica, não uma solução geral; linhas/seções repetidas fora da lista continuam vulneráveis a colapso ou edição da ocorrência errada.

Não foi encontrada evidência que justifique afirmar que **toda** opção repetida depende de ordem ou que todas as duplicatas têm significado independente. O requisito correto é preservar ocorrências por padrão e só normalizar uma estrutura quando uma especificação ASE ou ensaio controlado demonstrar que é seguro. A wiki precisa ser consultada para cada caso, e comportamento não documentado deve ser rotulado como inferência/teste empírico.

### Modelo recomendado

Substituir o parser de edição por uma representação ordenada de nós: comentário, seção, linha de chave/valor, linha raw e linha em branco. Cada linha deve reter arquivo, seção/instância da seção, chave, valor, índice/posição, codificação e texto original. Um adaptador semântico separado resolve campos conhecidos; as linhas não geridas permanecem intactas. A gravação deve aplicar patch ao nó identificado, fazer backup transacional e reler/verificar a saída. Assim, round-trip sem mudanças pode preservar bytes ou ao menos estrutura/semântica comprovável e alteração pontual limita o diff.

## 3. Rampas de XP e editor

### Estado atual

`src/player_level_ramp.py` contém construtores e parser de `ExperiencePointsForLevel[index]`, inferência de curva, cálculo de teto e geração de dados de rampa do **jogador**. O modelo `AsmServerConfig` guarda `player_level_stats_raw` e `dino_level_stats_raw` como texto bruto; isso não é um modelo semântico independente de listas de níveis jogador/dino. A configuração de Dino é essencialmente raw/cap, sem editor equivalente à experiência visual solicitada.

`src/ui/player_level_panel.py` é um painel de nível máximo e atalhos/campos de curva; não é uma grade de progressão completa com edição independente por linha de nível, XP, pontos de engrama e total acumulado. A interpretação de rampas existentes é focada em padrões conhecidos, não há garantia de importação arbitrária preservando entradas desconhecidas/ordem/ocorrências. As funções de jogador e referências no INI não constituem prova de que as entradas idênticas de jogador e dino tenham semântica definida somente pela ocorrência: isso precisa de confirmação documental e/ou experimento ASE controlado antes de fixar a regra.

O parser armazena índices conhecidos e o gerador cria linhas indexadas. O UX esperado (nível, XP, pontos e total para jogador; nível e XP para Dino) não está implementado de ponta a ponta. O total acumulado de engramas não aparece como uma tabela visual auditável por nível; há geração de `OverridePlayerLevelEngramPoints=` em outro módulo e lógica de pontos separada.

### Riscos e desenho futuro

- Modelos separados `PlayerProgression` e `DinoProgression`, cada um com linhas explícitas (nível, XP total, pontos incrementais quando aplicável), estado enabled, origem e metadados de serialização.
- Importar do INI sem descartar entradas; se houver ambiguidade, mostrar aviso e preservar o raw até confirmação.
- Grade virtualizada para centenas de níveis, edição em lote, adicionar/remover, validação de índices únicos, XP monotônico e não negativo, contagem e preview de diffs.
- Total acumulado de engramas calculado somente se a semântica incremental estiver confirmada; XP máximo derivado do último limiar segundo regra ASE confirmada, nunca exibido como valor contraditório.
- Validar a geração relendo o arquivo e comparando os modelos independentes. Replicar através do mesmo serviço de patch INI com preview, seleção múltipla de destinos e resultado individual.

### Critérios de interface observados na referência

- Jogador e Dino aparecem simultaneamente em painéis independentes; editar um lado não altera o outro.
- Teto de XP e habilitação de progressão são controles visíveis por tipo. Tabelas expõem seus dados essenciais sem depender de atalhos de curva.
- A tabela do jogador mostra pontos por nível e total acumulado; o total é derivado e deve ser recalculado ao editar pontos.
- Ações por linha incluem adicionar e remover; ações de barra incluem editar/resetar e transferência/importação/exportação. O produto deve nomear cada ação e confirmar operações destrutivas.
- A rolagem deve manter cabeçalhos e permitir centenas de níveis sem montar uma janela com centenas de widgets simultâneos.
- A imagem é referência de organização e fluxo, não prova da semântica de XP do ARK. A regra dos 10 níveis de ascensão e os limites devem ser validados antes de gerar INI.

## 4. Importação e replicação entre servidores

Os caminhos legados em `src/app.py` mostram funções de importação e sincronização de INI separadas do fluxo ativo TEK. Mesmo quando o mecanismo copia arquivos completos, isso não é merge semântico: pode transferir caminhos e valores exclusivos do destino, substituir chaves desconhecidas, ou copiar conteúdo inadequado a outro mapa/instalação. A presença de funções em `src/app.py` não prova que sejam a tela usada pelo `app_tek`.

O modelo por dicionário não preserva duplicatas. Uma operação que termina sem exceção tampouco prova que todos os arquivos foram gravados ou que o destino pode relê-los. Importações devem ser transacionais por arquivo e por servidor: validar origem/destino, gerar diff, criar backup, aplicar, reler, validar e retornar sucesso/falha explicitamente. Em múltiplos destinos, cada servidor precisa de estado próprio; resultados parciais não podem ser resumidos como sucesso global. Preservar configurações locais requer uma política explícita de copiar categoria, copiar campos geridos ou copiar arquivo inteiro, com preview.

## 5. Saves

### Comportamento observado

`src/asm_engine/asm_savegame_manager.py` escolhe `ShooterGame/Saved/{AltSaveDirectoryName}` (fallback `savegame`) como pasta ativa. A listagem também procura `SavedArks` e `SavedArksLocal`; o painel atual está em `src/asm_ui/asm_savegame_panel.py`.

O carregamento sempre grava em `AltSaveDirectoryName`, que também é emitido como `?AltSaveDirectoryName=...` na inicialização quando configurado; o valor padrão do perfil é `savegame`. Assim, listar saves encontrados em `SavedArks`/`SavedArksLocal` e copiá-los para a pasta ativa configurada pode ser intencional, não evidência de bug. O ponto a validar é se o argumento chega ao processo em todos os fluxos de start e se a interface mostra claramente pasta de origem e destino. O achado anterior de divergência como falha comprovada foi forte demais e fica reclassificado como hipótese.

No painel, exceções individuais são convertidas em `SaveInventory(error=...)`; quando o inventário selecionado está ausente ou vazio, a apresentação pode dizer que não foi possível ler ou mostrar zero arquivos sem distinguir claramente diretório inexistente, permissão negada, erro de leitura e pasta vazia. A solicitação exige especificamente não converter erro em lista vazia; o estado precisa ficar visível por servidor.

Outro fluxo legado, `src/asm_ui/asm_save_restore.py`, deve ser tratado como possível fonte de inconsistência: a inspeção encontrou caminho fixo `SavedArks`, exclusão/recriação de destino e controle de parada com timeout não confirmado. Antes de qualquer ajuste, validar se ele ainda é alcançável no executável ativo; não usar esse fluxo como fonte de verdade se estiver desativado.

### Segurança e correção futura

Separar inventário de pastas candidatas de localização ativa, mostrar caminho absoluto e origem de cada save, estado da pasta e erro real. Carregar só deve ser habilitado quando servidor parado e destino ativo resolvido; backend deve revalidar isso, não confiar apenas em botão desativado. Antes de sobrescrever, validar espaço, integridade/tamanho, caminho contido na pasta do servidor, backup e confirmação; gravação temporária + replace deve manter o backup disponível. Não excluir pasta/arquivo ativo até confirmar que backup e substituição terminaram. Exibir resultado da cópia e validar hash/tamanho. Cobrir `AltSaveDirectoryName`, `-savedir`, `SavedArks`, `SavedArksLocal`, mapas com nome distinto e saves `.ark`/`.bak` em testes de diretório temporário.

## 6. UX: Dashboard, sidebar e configuração

### Dashboard

`src/asm_ui/asm_dashboard.py` reserva linhas fixas para topo, cinco métricas (total, online, offline, CPU, RAM), discos e barra de ações antes da lista de servidores. Isso empurra os servidores para baixo e privilegia métricas agregadas sobre ações e saúde por servidor, contra o objetivo “servidores primeiro”. Sugestão: resumo compacto em uma faixa recolhível; área principal com cards/linhas de servidor, status, mapa, jogadores, CPU/RAM, última atualização e ações; alertas e falhas no topo; filtros e busca.

### Sidebar

`src/pages/build_sidebar_tek.py` constrói primeiro 14 destinos gerais e depois a seção SERVIDORES. Com muitos destinos, exige rolagem antes de chegar à lista de servidores. Não há sistema visível de favoritos/pins nesta construção. Priorizar servidores no topo, permitir recolher grupos gerais e servidores, busca, favoritos, ordenação manual e status resumido. Preferências de pin devem persistir por usuário; preservar acessibilidade de teclado/foco.

### Páginas e configuração

Não foi identificada nesta construção uma abstração geral de páginas fixáveis. Recomenda-se tabs destacáveis/pináveis por servidor, com contexto explícito e indicador de alterações não salvas. Para os formulários, agrupar opções por tarefa/domínio com busca, descrição, padrão, valor atual, unidade/faixa, dependências, origem (padrão/INI/CLI) e preview de diff. Expor modo avançado/raw sem retirar opção do administrador, mas marcar sintaxe e destino técnico.

## 7. Integridade textual e causa provável

Existem strings mojibake gravadas no código-fonte, por exemplo em `src/pages/tab_game.py` (“Consumo de Ãgua”, “Dano Ã s Estruturas”) e `src/asm_ui/asm_savegame_panel.py` (“Em execuÃ§Ã£o”, símbolos `ðŸ…`). Também há pelo menos um caractere de substituição literal `�` em `src/pages/tab_ini_mods.py`. Isso comprova corrupção de texto em arquivos, além de possíveis problemas de console/terminal. A busca no histórico `src/version.py` também detecta formas como `Â` em frases que deveriam conter “Âmbares”; parte disso pode ser texto legítimo de moeda, então é necessário classificar por string/contexto.

Não é possível atribuir causa raiz única só lendo os bytes atuais. Hipóteses plausíveis incluem arquivo UTF-8 decodificado e salvo como Windows-1252/Latin-1, console com code page incompatível e cópia/edição posterior. O programa usa múltiplos caminhos de leitura com fallback de encoding nos INIs, mas isso não corrige strings já corrompidas no fonte. Corrigir manualmente cada ocorrência sem política cria regressões.

Plano textual: inventariar suspeitas com ferramenta que lê UTF-8 estrito e sinaliza padrões, revisar contexto; padronizar fontes em UTF-8; definir encoding de arquivos externos explicitamente (INI conforme BOM e fallback limitado); impedir salvamento silencioso com `�`; checar CLI/Windows e build congelado; adicionar validação automatizada de texto em fase de implementação. Separar strings de UI de histórico/changelog e texto comunitário.

## 8. Vinculação Discord

No fluxo atual em `src/discord_bot/moderation.py`, o bot lê o autor da mensagem (`message.author.id`) e encaminha código à API; o usuário não deveria digitar seu próprio ID. O código precisa obedecer o formato/canal configurado. O bot precisa de token e canal de validação; um cargo opcional pode ser aplicado. `src/discord_bot/settings.py` exige `ARKSHOP_WEB_URL` e `ARKSHOP_API_KEY`; a ausência retorna a mensagem “Integração não configurada”. O canal é configuração de infraestrutura, não identidade manual do usuário.

Ainda há compatibilidade/configuração legada no projeto. `src/discord_bot/legacy_import.py` importa variáveis antigas de configuração; isso é diferente de pedir manualmente ID do usuário, mas pode manter campos de IDs de guild/canais/cargos no setup. Não foi possível afirmar, sem percorrer todos os componentes administrativos do webapp e todas as rotas backend, que nenhum caminho manual antigo continua exposto. A interface de operação deve ocultar/desativar caminho de vínculo manual e comunicar que a identidade vem do autor Discord; IDs de canal/cargo permanecem configuração administrativa legítima.

Arquitetura esperada: site gera token aleatório, curto prazo, de uso único, vinculado à conta Steam; bot lê usuário Discord autenticado e envia API key em canal definido; backend valida token e unicidade transacional, grava IDs e nomes observados, aplica bônus de primeira vinculação idempotente no ledger e registra auditoria; revinculação/desvinculação é ação administrativa auditada com regra explícita de bônus. Validar expiração, replay, concorrência, discord já ligado a outra Steam, falha de API e crédito duplicado. A auditoria de código não comprova que deploy atual esteja usando exatamente o código fonte deste checkout.

## 9. Achados priorizados

| Prioridade | Achado | Impacto |
|---|---|---|
| P0 | INI modelado como mapas por chave, sem identidade geral de ocorrências | Perda de duplicatas/estrutura e risco em edição/round-trip |
| P0 | Universo canônico de opções ASE sem catálogo reconciliado/versionado | Impossível comprovar meta de cobertura total ou evitar opções de versão errada |
| P1 | Rampas de Jogador/Dino não têm modelos e UX equivalentes e independentes até a geração validada | Configuração difícil, importação incompleta e risco de cruzamento semântico |
| P1 | Listagem de saves em pastas candidatas e caminho de carregamento ativo podem divergir | Carregar pode gravar em local que não é usado pelo servidor |
| P1 | Erro de leitura de save não é um estado de interface suficientemente distinto de lista vazia | Diagnóstico enganoso e operação insegura |
| P1 | Import/replicação sem diff/validação transacional comum | Sobrescrita e falso sucesso/parcial |
| P1 | Fontes possuem texto comprovadamente mojibake e `�` | Interface e ajuda podem exibir conteúdo quebrado |
| P2 | Sidebar lista navegação global antes dos servidores; dashboard reserva grande área para métricas | Atrasa administração diária, especialmente em clusters grandes |
| P2 | Preferências de páginas fixáveis e edição avançada uniforme não encontradas | Fluxos repetitivos e baixa ergonomia |
| P2 | Fluxos Discord legado coexistem com novo mecanismo e há setup externo obrigatório | Confusão de configuração; risco de caminhos de vinculação inconsistentes |

## 10. Referência de produto: ARK Dedicated Server Tool / Ark Server Manager

O usuário indicou os repositórios do [HellsGuard](https://github.com/HellsGuard/ARK-Dedicated-Server-Tool) e do [ChronosWS](https://github.com/ChronosWS/ARK-Dedicated-Server-Tool) como a base funcional que deseja adotar. A inspeção pública confirma que o repositório ChronosWS é um fork do HellsGuard e contém histórico maior visível no GitHub (1.092 commits contra 398 no repositório HellsGuard no momento da consulta). Ambos mostram branch `In-Development`, licença GPL-3.0 e nenhuma release publicada na página do GitHub consultada. Os READMEs informam Visual Studio/.NET Framework 4.5; portanto são aplicações .NET/WPF de outra geração tecnológica, enquanto Ark Land é Python/CustomTkinter. Esses metadados não invalidam a experiência real do usuário com o programa; apenas impedem que este relatório declare por conta própria que o checkout público atual foi testado e funciona perfeitamente.

Foi feita leitura somente de código do branch `In-Development` do ChronosWS em checkout temporário: o HEAD obtido era o commit `d00e76f395022a37052fdf92801e90caa2a6664b`, datado de 2018-06-05. Isso indica que o branch público consultado não é uma base atualizada recentemente, mesmo tendo histórico maior. A alegação de funcionamento perfeito refere-se à experiência/instalação do usuário e será tratada como baseline desejado; não foi reproduzida em ambiente de teste nesta etapa.

### Como usar essa base

Adotar o Ark Server Manager como **referência funcional e de fluxo operacional** é uma direção coerente para resolver as lacunas: comparar telas, organização dos campos, comportamento de importação/exportação INI, editores de progressão, saves, mapas, mods, instalação, atualização e validações; documentar os casos que o usuário já considera comprovados; e tornar o Ark Land equivalente onde aplicável. A descrição/guia de uso associado ao projeto serve como referência de comportamento, mas a cobertura de opções ainda deve ser cruzada com o snapshot ASE anexado e com a versão suportada.

“Usar como base” pode significar duas coisas distintas: (a) reproduzir conceitos e comportamento no código atual; ou (b) incorporar/portar diretamente código do projeto .NET. Para esta auditoria, a proposta é a opção (a) como caminho inicial de menor risco. A opção (b) exigiria prova de compatibilidade de dependências e plataforma, avaliação de arquitetura e plano de migração da aplicação; não é uma troca direta de biblioteca. O repositório Ark Land não apresentou arquivo LICENSE na raiz durante a inspeção, enquanto os dois projetos ASM declaram GPL-3.0. Antes de copiar ou adaptar código, é necessário decidir e revisar a compatibilidade/licenciamento da distribuição do Ark Land, manter avisos/autoria e cumprir a licença. Reutilizar padrões de interação não é a mesma coisa que copiar código.

### Atualização do plano e versão

Adicionar à Fase 0 uma matriz comparativa Ark Land × ASM × referência ASE: fluxo/tela; opção/configuração; leitura; escrita; importação; validação; save/backup; evidência; estado; gaps. Em cada comparação registrar qual comportamento do ASM é baseline aceito pelo usuário e quais exceções decorrem do escopo (integrações Ark Land, plugins, loja, Discord, web/API). Em seguida, priorizar paridade de funcionalidade no gerenciador TEK atual, mantendo explícita a decisão de arquitetura e licença antes de qualquer reaproveitamento literal de código.

**Aceite adicional:** nenhuma funcionalidade declarada “equivalente ao ASM” sem um caso de uso comparado; os casos validados pelo usuário têm critério reproduzível; opções exclusivas do Ark Land permanecem cobertas; a estratégia de licença está aprovada antes da incorporação de código externo.

O usuário definiu a entrega reestruturada como **versão 1.11.0**, em vez de 1.10.138. Esse é o alvo de versão da reestruturação; o identificador de versão deve ser atualizado quando a implementação e os critérios de aceite estiverem prontos para release, não durante a análise intermediária.

## 11. Plano de implementação em fases e critérios de aceite

### Fase 0 — Baseline e fonte de verdade

1. Fixar suporte ASE e matriz de versões/ambientes suportados.
2. Obter snapshot navegável/exportável da documentação oficial aplicável (incluindo argumentos CLI) e registrar data/URL/versão/evidência.
3. Criar catálogo versionado com cada opção, arquivo/seção/contexto/tipo/padrão/faixa/dependências/repetição/evidência e estado Ark Land: completo, parcial, ausente ou não aplicável justificado.

**Aceite:** toda entrada tem fonte e versão; ASA e conhecimento comunitário estão separados; total e cobertura são calculáveis; nenhum item ausente fica sem classificação.

### Fase 1 — Parser preservador e escrita segura

1. Implementar AST INI ordenada para interpretar arquivos existentes. Na saída para o ARK, serializar somente seções e linhas válidas `chave=valor`; remover comentários, linhas soltas/malformadas e qualquer conteúdo fora da configuração.
2. Ligar adaptadores de campos semânticos sem tornar o AST dependente deles.
3. Fazer preview/diff, backup, gravação atômica, reler e validar; erros impedem notificação de sucesso.

**Aceite:** saída nunca contém comentários, linhas vazias ou conteúdo que não seja cabeçalho de seção/atribuição válida; opções válidas desconhecidas permanecem; duplicatas de opções configuráveis preservam a semântica conhecida; seções repetidas são normalizadas; codificações suportadas e escrita atômica são verificadas; falha conserva o original.

### Fase 2 — Catálogo e interface de opções

Implementar os itens do catálogo por grupos, com testes de parse→modelo→serialize, defaults e dependências, incluindo CLI e configurações que não cabem em formulário simples.

**Aceite:** cada item aplicável tem UI ou editor avançado seguro e cobertura de leitura/escrita; nenhum campo é silenciosamente omitido; validação explica restrições e origem.

### Fase 3 — Editor semântico de progressões

Criar modelos separados para Jogador e Dino, importar rampas existentes, tabela virtualizada, derived values e geradores próprios; só fixar relação entre ocorrências repetidas após confirmar a documentação/experimento.

**Aceite:** centenas de níveis editáveis sem travamento; XP monotônico e limites validados; engramas acumulados consistentes; XP máximo coincide com o modelo; rampa importada sem alteração não muda; editar Jogador não afeta Dino e vice-versa; preview e reparse conferem; jogador/dino desativados não têm linhas indevidas.

### Fase 4 — Importação e replicação

Unificar import/export/replicação em serviço por servidor/categoria, com preview, política de preservação local e resultado detalhado.

**Aceite:** um destino e vários destinos reportam sucesso/falha individual; configurações não escolhidas continuam iguais; erro parcial não é sucesso; backups e rollback funcionam; reaplicar operação idempotente não cria duplicatas.

### Fase 5 — Saves

Unificar UI antiga/nova ou remover o caminho inativo após confirmar; resolver pasta ativa a partir de configuração e argumentos reais; diferenciar ausente/vazia/sem acesso/erro; proteger operações no backend.

**Aceite:** testes em temporários de todas as pastas/casos; app mostra caminho ativo e origem; servidor rodando nunca pode ser sobrescrito; backup validado antes da troca; erro é visível; carregar e reler comprova destino/hash; nenhuma exclusão fora da raiz permitida.

### Fase 6 — UX de operação

Reorganizar dashboard e sidebar, incluir busca/favoritos/colapso e persistência, compactar métricas, páginas fixáveis com contexto por servidor e indicar estado sujo.

**Aceite:** servidor e ações principais visíveis sem scroll em janela de referência; escala com clusters grandes; navegação por teclado; favoritos persistem; painel não mostra estado stale como atual.

### Fase 7 — Encoding e Discord

Normalizar fontes/textos e checks; eliminar campos de ID de usuário quando não necessários, preservando IDs técnicos de canal/cargo; validar vínculo, bônus e auditoria no backend.

**Aceite:** varredura textual sem mojibake ou replacement character não justificado; testes Windows/build; fluxo manual de identidade indisponível; código expira e é de uso único; ID de autor é capturado pelo bot; primeira recompensa exatamente uma vez; operações administrativas ficam auditadas.

## Testes necessários na implementação futura

- Fixtures INI ASE: BOM UTF-8/UTF-16 e codificação legada, comentários/linhas inválidas que devem sair, chaves duplicadas, seções repetidas, valores vazios, arrays e ordem.
- Round-trip intacto, edição isolada, importação de versão conhecida, geração e reparsing.
- Rampas de jogador/dino, centenas de níveis, entradas incompletas, índices fora de ordem, duplicados, XP inválido, engrames e limites.
- Replicação para destino único/múltiplo, permissões insuficientes, arquivo bloqueado e rollback.
- Saves em cada diretório candidato, arquivo ausente, diretório sem permissão, processo ativo, backup inválido, espaço insuficiente e interrupção de gravação.
- Encoding de fontes e mensagens em Windows, console e pacote congelado.
- Discord: válido, expirado, replay, usuário/Steam duplicado, concorrência, backend offline, bônus idempotente, revinculação e auditoria.
- Testes de UX com poucos e muitos servidores, resolução de tela de referência, scroll, teclado e janela redimensionada.

## Decisão final da auditoria

O projeto tem suporte substancial, mas disperso, a configurações ASE; não há evidência suficiente para afirmar cobertura integral. O maior bloqueio estrutural é o parser INI como mapa de chave/valor, que enfraquece round-trip, edição isolada, importação e replicação. Em paralelo, Saves precisa resolver uma única fonte para a pasta ativa e expor erros reais; rampas precisam de modelo semântico independente; a interface precisa priorizar servidores; e fontes precisam de saneamento sistemático.

O próximo passo seguro é concluir a Fase 0: classificar o snapshot recém-fornecido contra a documentação vigente e a versão ASE efetivamente suportada, confirmar candidatos a obsoletos/contextuais e completar o catálogo CLI/INI antes de alterar o parser. Isso evita implementar sintaxe errada ou misturar ASE com ASA e cria critérios mensuráveis para as fases seguintes.

## Implementação em andamento para 1.11.0

O trabalho autorizado começou pela base de leitura ordenada de INI. `src/asm_engine/ini_document.py` retém seções, comentários, chaves repetidas, encoding e BOM durante a interpretação; o serializador de saída do ARK agora remove comentários, linhas soltas e conteúdo que não seja configuração. O escritor principal migrou de `configparser` para aplicar patches sobre esse documento, conserva opções válidas desconhecidas e normaliza seções repetidas. Esta mudança precisa passar pela regressão mais ampla antes de ser considerada pronta para servidores.

A referência visual do editor de progressão agora está incorporada aos critérios acima. Foram iniciados modelos de domínio separados para jogador e Dino em `src/asm_engine/level_progression.py`; o modelo do jogador calcula o total de engramas a partir dos pontos por nível e ambos validam XP crescente e limites. Esses modelos ainda não estão ligados ao parser INI nem à interface.

Validação executada nesta etapa: `pytest -q tests/test_ini_document.py tests/test_level_progression_models.py tests/test_asm_game_ini_ramp.py tests/test_asm_custom_ini_sections.py tests/test_asm_platform_saddle_ini.py tests/test_asm_engram_editor_truncate.py` — **41 testes passaram**. Isso valida cenários focados de INI/rampa e não equivale à validação integral do aplicativo, build Windows ou teste em servidor ARK.

O release **1.11.0 não está pronto**: ainda faltam a migração do escritor INI, a paridade das rampas na UI, testes amplos de aplicação/build e o fluxo formal de changelog/empacotamento/publicação. Não alterar a versão publicada para 1.11.0 até esses critérios serem concluídos.

