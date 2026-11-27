# Atribuição offline — StructureLimits 0.9.2-dev

## Evidências no piloto 05

- Antes: runtime 0.9.1-dev saudável, inventário observado de 231 estruturas, sem tribos residentes e sem atribuição de tribo nos registros enquanto não havia jogadores.
- Foram copiadas duas tribos e dois perfis de `Saved/savegame`, conferindo SHA-256 de origem antes/depois e da cópia. Zero erros de parser na revisão fixada `1d9a3e2b1a8052fdfc187174edfc920ca53216f3`. As cópias/manifesto ficam no backup privado `owners-checkpoint-20261127-044359`.
- As duas tribos correspondem ao `TargetingTeam` das 231 estruturas. O índice exportado contém somente as duas fontes necessárias às atribuições de tribo; os perfis não foram transformados artificialmente em tribos solo.
- DLL 0.9.2-dev aplicada somente no 05 após confirmação RCON de ausência de jogadores. SHA-256: `A57879A0A3CE3FC03149F2996F651736C95FD7C2066D95798A6C1B6308E7F27E`.
- Após concluir a varredura com o índice disponível: **231/231 atribuições offline verificadas**, grupos de **227 e 4**, conflitos zero. Todos os IDs anteriores preservados, sem IDs novos. Não houve jogador conectado nessa validação nem reinício dos cinco processos de jogo.
- Runtime/journal saudáveis; `offline_owners.state=verified`. SHA-256 do índice privado: `fb51047e0d8cfc546a6b91a06ff4565547cc54958d24b90d897535a1a39b3965`.
- A primeira leitura após a carga ainda estava numa varredura parcial. A confirmação dos 231 vínculos foi feita posteriormente, na quinta varredura, com snapshot separado `after-complete-owner-scan.json`; reconhecer duas tribos não foi tratado como prova de atualização de todos os registros.

## Validação de implementação

30 funções de teste C++ e 26 testes Python aprovados (mais três subtestes do auditor). Incluem instância/pasta errada, fontes duplicadas, identidade incompatível, revisão do parser, invalidação da evidência, origem nativa retida, verificação SHA-256 em arquivos temporários reais e encerramento do worker. Os arquivos reais do jogo foram apenas lidos/copiados; o teste de alteração de fonte usou arquivos temporários.

## Geração e atualização do índice

[owner_directory.py](tools/owner_directory.py) aceita um checkpoint privado com `manifest.json` e arquivos copiados. Recusa parser diferente/sujo, origem fora da instância, hash/tamanho divergente, ambiguidades e saída que substituiria entradas. Não analisa o diretório vivo. Usa `raw_tribe_id`; o fallback de auto-tribo do parser não é prova de tribo real.

```powershell
python tools/owner_directory.py --checkpoint <copia-privada> --parser-root <parser-fixado> --expected-instance 09THE05 --output <indice-privado.json>
```

`OfflineOwnersFile` é opcional e vazio por padrão. O arquivo produzido é privado e não entra no ZIP experimental. No piloto aponta para o índice dentro da pasta do plugin. O worker confere os hashes das fontes da instância a cada cinco segundos; se mudarem, o índice deve ser reexportado a partir de novas cópias verificadas. A substituição do índice pode ser lida sem reiniciar o mapa. Isso ainda não é um serviço completo de atualização automática das fontes.

## Publicação e conferência após aplicação

A [release 1.12.41](https://github.com/SrLuther/ARKLAND-Multi/releases/tag/v1.12.41) contém o instalador, o changelog desta evolução e o pacote `StructureLimits-0.9.2-experimental.zip`. O ZIP possui configuração desabilitada por padrão e não inclui o índice privado nem arquivos reais de personagens/tribos.

A WebStore foi aplicada e conferida pela API pública e por uma nova página do site, ambas na versão 1.12.41. SHA-256 do executável instalado: `9FFA1783D676ADF295B5414D8187D9E399D4869F1F74D4D3A46ADBDD9B8BF965`. Backup privado do banco antes da aplicação: 72.817.251 bytes; esquema preservado, sem nova migração nesta versão. Gateway online e configuração do chat na revisão 12.

Os cinco processos de jogo presentes imediatamente antes da aplicação continuaram com os mesmos PIDs e caminhos. Na conferência posterior do plugin, após 50 varreduras: runtime/journal saudáveis, 231 atribuições offline, grupos 227/4, conflitos zero e nenhuma diferença no conjunto de StructureIDs em relação à varredura completa homologada. Inventário completo e fiscalização permaneciam desligados.

O empacotamento utilizou a opção explícita de cache incremental do PyInstaller. Os gates do executável congelado aprovaram dependências, histórico até 1.12.41, apresentação online e adiamento dos anúncios diante de público vazio, inclusive com positivo antigo no cache. Nenhum plugin oficial sem alterações foi recompilado.

## Trabalho ainda pendente

`complete_inventory=false` e `enforcement=false` continuam obrigatórios. Atribuição de proprietários não prova cobertura de todas as estruturas: a auditoria anterior ainda apontava 32 atores dinâmicos pendentes, mutações de coleções e cobertura de stasis por validar. Licenças remotas, integração final com a loja, fusão/transferência, decay e veto antes do consumo de materiais continuam pendentes. O caminho solo foi testado no núcleo, não com personagem solo real neste piloto. Recuperação após recarga do plugin foi comprovada; não foi realizado novo reinício completo do servidor.

## Reinicialização autorizada — 0.9.3-dev

- Após a etapa 0.9.2 descrita acima, o administrador autorizou desligar o 05 para instalar a 0.9.3. O mundo foi salvo e o encerramento confirmado por RCON com resposta `Exiting...`. Foi preservado o comando de inicialização em arquivo privado e criada cópia offline do mundo (69.383.352 bytes).
- DLL instalada: `92CB43E0D3BC4F3087B0413184CE6CEEAAF24D01F081E149A4D8AC598C601E29`. Processo do 05 substituído; os outros quatro processos de jogo foram preservados. O plugin carregou e a consulta pública A2S retornou o mapa TheIsland. RCON confirmou runtime/journal saudáveis, quatro varreduras concluídas, 231 estruturas, duas tribos, grupos 227/4, evidências offline verificadas, fila em memória vazia e piloto inativo (`idle`). Nenhuma tentativa foi recusada automaticamente na inicialização.
- A cópia recém-salva, analisada pelo parser fixado, contém 105.119 objetos e 49.309 registros de ator. Houve 231 correspondências com o censo anterior, sem erros de parser, faltantes ou divergências de propriedade/posição. O checkpoint ainda contém 110 atores auxiliares pendentes (108 paredes de horda e dois beaver dams); essa auditoria não declarou completude.
- Na nova partida, todos os StructureIDs dessas 231 construções foram renumerados: a diferença entre conjuntos tem 462 entradas, mas a reconciliação por blueprint/nome de ator/TargetingTeam/OwningPlayerID/tribo/XYZ encontrou 231 correspondências, sem chaves repetidas ou divergências (tolerância 0,05). IDs de execução não podem ser tratados como identidade persistente entre partidas. O snapshot anterior permaneceu candidato não validado e não foi restaurado como contador autoritativo.
- O arquivo atual `ShooterGame.log` permaneceu sem marcador de início durante essa verificação. A prontidão foi comprovada por A2S ativo, RCON, versão da DLL e varreduras concluídas; os logs do ArkApi confirmaram o carregamento da 0.9.3.
- As provas de veto vanilla e de uma fundação S+ foram concluídas nas seções seguintes. Bloqueio geral e inventário completo continuam falsos.

## Veto com retenção — fundação Tek vanilla

- A primeira janela de 120 segundos expirou antes da tentativa. As três colocações relatadas foram permitidas e contabilizadas: grupo do administrador de 227 para 230, ledger geral de 231 para 234, `bypassed=3`, `denied=0` e nenhuma evidência de veto. Esse ensaio expirado não foi tratado como aprovação nem como recusa do piloto.
- Após rearmar, o administrador confirmou a recusa e que o item não foi consumido. A captura RCON privada `after-tek-veto-status.json` confirmou `pilot_state=item_preserved`, `denied=1`, `item_before=19`, `item_after=19`, `placement_callbacks_after_veto=0` e nenhuma reserva pendente. O total observado permaneceu 234; runtime/journal saudáveis.
- Blueprint de ator efetivamente exercitado: `/game/primalearth/structures/tektier/floor_tek.floor_tek`. O comando de item fornecido pelo administrador usa `PrimalItemStructure_TekFloor`; não foi confundido com o caminho do ator.
- Resultado: veto controlado comprovado para essa classe nesta execução, sem reposição artificial do item. Isso não prova cobertura de mods, fiscalização contínua por cota nem completude do inventário. `complete_inventory=false`, `enforcement=false` e `placement.cap_enforcement=false` permanecem explícitos.

## Veto com retenção — fundação metálica S+

- Item selecionado pelo administrador: `PrimalItemStructure_Foundation_Metal`, de Structures Plus. Depois de armar uma nova tentativa, o administrador confirmou visualmente que bloqueou e não consumiu; a captura de tela mantém o stack visível em 10.
- A captura RCON privada `after-splus-metal-veto-status.json` confirmou `pilot_state=item_preserved`, quantidade agregada da classe `item_before=11` e `item_after=11`, `placement_callbacks_after_veto=0`, nenhuma reserva pendente e `denied=2` acumulado (Tek + S+). O método soma os registros da classe em `InventoryItemsField()`, não somente o stack destacado; não se presume a origem da diferença entre o total nativo e o stack visível.
- Blueprint de ator exercitado: `/game/mods/structuresplusmod/structures/foundations/square/metal/bp_foundation_metal.bp_foundation_metal`. A lista de evidências desta execução contém essa classe e a fundação Tek. Total observado 234, runtime/journal saudáveis.
- Resultado: segundo veto controlado comprovado, agora para essa classe do S+, sem reposição artificial. Não habilita fiscalização geral por cota nem certifica outras estruturas S+. Inventário completo e enforcement continuam falsos.
