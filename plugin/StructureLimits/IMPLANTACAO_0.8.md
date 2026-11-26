# Implantação piloto 0.8-dev — 26/11/2026

## Escopo e versão

Somente instância 05 (`TheIsland`, `09THE05`). DLL e arquivos do plugin em sua própria pasta. Configuração existente preservada, acrescentando apenas `LiveInventoryEnabled=true` e desativando o probe residente antigo. LPG=100, extra=25%, lista específica vazia e fiscalização suspensa permaneceram iguais.

Backup protegido da DLL 0.6-dev, metadados e configuração foi preservado antes da troca. Nenhum save foi restaurado, removido ou editado. Nenhuma migração de banco foi executada; o inventário observado ainda não alimenta contadores autoritativos do site.

DLL final: 749.056 bytes; SHA-256 `1C5F6CD5BD480E5FDF8333A69AECC3DC5407040802166777FAD45CBE4CDD7A60`.

## Operação e evidências

- Solicitado SaveWorld e parada apenas do UUID do mapa 05. O agente HTTP excedeu o timeout e permaneceu sem responder.
- Confirmado salvamento por RCON direto e atualização real de `TheIsland.ark`. `DoExit` não encerrou o processo no prazo; encerrado somente o PID 1628, depois de validar caminho exato e save recente.
- Preservados argumentos originais de inicialização em arquivo privado com ACL restrita. Servidor iniciado como PID 6924 por tarefa persistente, sem depender da duração da sessão SSH.
- Log confirmou StructureLimits 0.8-dev, instalação dos callbacks, estado de fiscalização suspenso e `Loaded all plugins`.
- Primeira implantação revelou custo de cópia dos arrays do SDK. Corrigido acesso aos campos nativos, compilado apenas o arquivo alterado e recarregado somente StructureLimits com `plugins.unload` / `plugins.load`, recursos confirmados no fonte local do ArkApi. PID 6924 preservado.
- RCON `StructureLimits.Status` respondeu com `plugin_version=0.8-dev`, instância correta, 231 estruturas, scan concluído, conflitos/duplicidade zero, runtime e journal saudáveis e fila vazia.
- Estado derivado contém 231 registros e 231 posições com latitude/longitude. Nenhum blueprint contendo SupplyCrate presente no ledger. A varredura visitou 92.405 entradas, contando referências das coleções percorridas; esse número não representa atores únicos nem prova completude do save.
- Chat Arkland continuou carregado, conectado ao hub e com revisão 4 aplicada após o reinício.
- 23 testes standalone passaram. As ações de colocação, recolhimento, demolição e validação visual por GPS pela nova DLL aguardam homologação humana conforme `TESTE_0.8.md`.

## Pendência operacional do TEK

O agente HTTP do gerenciador continua sem responder após a requisição de parada. Não foi reiniciado o gerenciador: o código de startup inclui autostart, limpeza de blacklist de mods e migração de URLs em todos os mapas, o que excederia a autorização restrita ao 05. A operação e a validação do piloto usaram RCON diretamente e caminho/PID exatos. A indisponibilidade afeta a atualização de status no site; não significa que os demais processos de jogo tenham sido desligados.

## Limites desta entrega

O inventário permanece explicitamente parcial e não habilita enforcement. Não há afirmação de cobertura completa de saves/stasis, veto antes do consumo, causa de decay identificada ou sincronização MySQL. Arquivos anteriores são candidatos históricos, sem restauração automática de contagens. Eventos ainda somente em memória podem ser perdidos em encerramento abrupto; estado/outbox já publicados são preservados.
