# StructureLimits 0.9-dev — censo e auditoria do save

## Escopo e implantação

Instalada somente na instância 05, `09THE05`, em 26/11/2026. RCON confirmou ausência de jogadores antes de cada recarga. O ArkApi descarregou/carregou somente StructureLimits; o jogo permaneceu no PID 6924. Os cinco processos de jogo foram conferidos antes/depois e preservados. Nenhum plugin dos 01–04 ou do 06 foi alterado.

DLL final: 779.264 bytes; SHA-256 `43E40E44D4E0DB7BB7CD87CE2DFC4D7A1AE1BBAD4133C20ABD76868080730213`. A compilação final reaproveitou os objetos válidos e recompilou somente `LiveInventoryRuntime.cpp` após o refinamento. A configuração do piloto foi preservada. Backups privados da 0.8 e da primeira build 0.9 em `E:\ARKLAND_Backups\StructureLimits\0.9-dev-20261126`.

Na conferência posterior, 14 varreduras concluídas mantiveram 231 estruturas, sem conflitos de ID, com runtime/journal saudáveis e fila de journal vazia. Os cinco processos permaneceram os mesmos; não foram encontradas linhas de erro/critical do StructureLimits nas últimas 1.000 linhas do log consultado. As coleções gerais de atores continuaram sofrendo mudanças, registradas no diagnóstico.

## Implementação

- Cada estrutura observada inclui nome do ator, nome completo, blueprint, StructureID, propriedade quando comprovada, XYZ/GPS e máscara das fontes: 1=PersistentLevel, 2=outros níveis, 4=stasis, 8=colocação concluída. A máscara acumula fontes observadas no boot; não afirma residência simultânea em todas elas.
- Classes são classificadas pelo SDK durante a varredura. O catálogo exporta herança de estrutura/supply crate, sem usar lista manual de blueprints para contabilização global. Limites de 2.048 classes e 4.096 evidências de exclusão têm indicadores explícitos de saturação; o ledger continua observacional.
- Último scan concluído tem sequência, horário, entradas e IDs únicos por fonte, conflitos e mudanças no tamanho das coleções. Mudanças de tamanho são diagnóstico conservador; não comprovam perda de estrutura, nem garantem detectar toda alteração interna de uma coleção.
- Atores derivados de estrutura que não entram no ledger têm evidência separada: nome, classe, StructureID, time, PlayerDataID, posição, NetStartup, LoadedFromSave e motivo. Esses indicadores não são interpretados isoladamente como prova de construção por jogador.
- O cadastro de tribos residente do GameMode é consultado sem I/O. Ele retornou zero tribos no piloto sem jogadores; identificação de todos os proprietários offline continua pendente. Não há consulta SQL/rede ou carregamento de perfil no callback.

## Auditoria independente

Foi solicitado um `SaveWorld` normal, confirmado por RCON. O save foi copiado para backup privado; hash de origem antes/depois e da cópia iguais. Não houve edição/restauração de save. O snapshot observado foi copiado separadamente e conserva seu horário, pois não existe transação atômica entre o save do ARK e o journal.

Checkpoint de save: 26/11/2026 22:25:47 UTC; formato **11**; **55.648.627 bytes**; SHA-256 `FD4C94F219B5976234DFCA8E6C4D484E3ED0BEC913E0AAFE13C73DA3CA234940`. O snapshot final do runtime é posterior e a comparação explicita os dois horários.

Resultado reproduzido com [save_audit.py](tools/save_audit.py):

- 84.286 objetos lidos; 39.557 registros de atores; zero erros reportados pelo parser.
- 710 registros técnicos de classes derivadas de estrutura; 226 duplicatas com a mesma identidade/escopo e metadados relevantes idênticos foram colapsadas. Metadados discordantes não seriam escolhidos arbitrariamente.
- **231 estruturas observadas: 231 correspondências**, por nome, classe, time/PlayerDataID e XYZ. Diferença máxima de posição: **0**. Sem ator observado ausente do save, sem correspondência observada em falta e sem conflito de identidade.
- 221 atores de origem em arquivo do mapa, com propriedade zero no save e no censo nativo, separados das construções observadas. A origem usa `from_data_file` do cabeçalho do save e correspondência do ator. StructureID não zero e NetStartup falso também ocorreram em atores do mapa; esses campos não servem isoladamente como critério.
- **32 atores dinâmicos permanecem sem classificação suficiente**: 15 `ElementWall_Horde` e 17 `ElementWall_Horde_3`. Não foi criada exceção pelo nome dessas classes.
- Sem classe desconhecida ou colisão de classificação no checkpoint. Duas classes curtas existiam em caminhos diferentes, mas todas as alternativas eram não estruturais segundo o SDK; não se inferiu blueprint de estrutura a partir dessa colisão.
- O scan sofreu mutações de coleção. `tracked_structures_match=true`, mas `checkpoint_matches=false`, `complete_inventory=false`, `enforcement=false`. O exit code **2** do comparador indica essas pendências de validação, não falha de execução da DLL.

O parser externo é opcional, MIT, fixado em [1d9a3e2b](https://github.com/vertyco/arkparser/tree/1d9a3e2b1a8052fdfc187174edfc920ca53216f3). Não foi instalado no servidor nem incluído na DLL/WebStore. A ferramenta confere revisão, hash, tamanho e instância, recusa analisar o caminho do save vivo e só grava o relatório solicitado. Saves/relatórios privados ficam fora do Git.

## Reprodução

Preparar clone limpo do parser na revisão fixada e cópias estáveis do save, do `observed-inventory.json` e do manifesto de captura. O manifesto inclui `instance`, `source` (caminho original), `save_bytes`, `save_modified_utc` e `sha256`. Usar ambiente Python 3.12 ou superior; o comparador usa `hashlib.file_digest`.

```powershell
python plugin/StructureLimits/tools/save_audit.py `
  --save <copia/TheIsland.ark> --live <copia/observed-inventory.json> `
  --manifest <copia/manifest.json> --expected-instance 09THE05 `
  --parser-root <clone-do-parser> --output <relatorio-privado.json>
```

A leitura de propriedades é sob demanda, com liberação após extrair os metadados necessários. A comparação não depende das heurísticas de `get_structures()` do parser; a classificação de classes vem do censo nativo e ambiguidades ficam registradas.

## Testes e próximos critérios

24 casos C++ aprovados, incluindo acúmulo de fontes e conflito do nome completo para um mesmo ID. 14 testes do comparador aprovados: duplicatas, conflitos, classes desconhecidas/ambíguas, escopo, propriedade, posição, metadados não finitos, origem de mapa, classificação dinâmica pendente e resultado que nunca autoriza enforcement.

No jogo, aguardar 30 segundos após conectar e consultar `/limites`. Afastar-se para outra região sem construir/remover nada e consultar novamente. A contagem da mesma tribo deve permanecer estável; voltar e conferir outra vez. GPS visual e cenários de decay/mods continuam pendentes.

Para ativar fiscalização ainda faltam classificação suficiente dos atores ambíguos, cobertura contínua/reconciliação, propriedade offline e prova do veto antes de consumir materiais. A correspondência deste checkpoint não habilita limites nem substitui esses critérios.
