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

## Limites desta etapa

`complete_inventory=false` e `enforcement=false` continuam obrigatórios. Atribuição de proprietários não prova cobertura de todas as estruturas: a auditoria anterior ainda apontava 32 atores dinâmicos pendentes, mutações de coleções e cobertura de stasis por validar. Licenças remotas, integração final com a loja, fusão/transferência, decay e veto antes do consumo de materiais continuam pendentes. O caminho solo foi testado no núcleo, não com personagem solo real neste piloto. Recuperação após recarga do plugin foi comprovada; não foi realizado novo reinício completo do servidor.
