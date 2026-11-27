---
description: Identidade e prontidão do piloto StructureLimits após reinicializações do ARK.
applyTo: 'plugin/StructureLimits/**'
---

## Learnings

### StructureID é identidade de execução, não presumir persistência entre partidas

Na reinicialização do 05 de 27/11/2026, as 231 construções corresponderam integralmente por blueprint, nome de ator, TargetingTeam, OwningPlayerID, tribo e XYZ, mas todos os StructureIDs foram renumerados (462 diferenças entre os dois conjuntos de IDs). Uma recarga de DLL no mesmo processo pode preservar esses IDs; uma reinicialização completa exige nova reconciliação e não deve ser reportada como perda/ganho de construções só pela diferença numérica. Para persistência e ingestão futuras, delimite IDs pela época de execução e mantenha snapshots anteriores como candidatos não validados; não restaure autoridade por ID isolado.

### Prontidão precisa de fonte ativa

O arquivo atual ShooterGame.log permaneceu vazio nessa partida, mesmo com A2S público respondendo TheIsland e RCON informando runtime/journal saudáveis, 231 estruturas e varreduras estáveis. Não dependa exclusivamente de um marcador nesse arquivo para declarar prontidão: confira a instância/processo correto, resposta ativa de A2S e RCON, versão do plugin e varredura concluída.
