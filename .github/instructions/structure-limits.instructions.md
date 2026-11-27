---
description: Identidade e prontidão do piloto StructureLimits após reinicializações do ARK.
applyTo: 'plugin/StructureLimits/**'
---

## Learnings

### StructureID é identidade de execução, não presumir persistência entre partidas

Na reinicialização do 05 de 27/11/2026, as 231 construções corresponderam integralmente por blueprint, nome de ator, TargetingTeam, OwningPlayerID, tribo e XYZ, mas todos os StructureIDs foram renumerados (462 diferenças entre os dois conjuntos de IDs). Uma recarga de DLL no mesmo processo pode preservar esses IDs; uma reinicialização completa exige nova reconciliação e não deve ser reportada como perda/ganho de construções só pela diferença numérica. Para persistência e ingestão futuras, delimite IDs pela época de execução e mantenha snapshots anteriores como candidatos não validados; não restaure autoridade por ID isolado.

### Totais estáveis e snapshots coalescidos não certificam uma revisão

Na comparação seguinte, as 234 construções corresponderam ao save, mas a varredura capturada tinha uma mutação de coleção; o antigo contador de estabilidade ainda aumentava porque comparava apenas ID/classe/time/jogador. Compare identidade física e atribuição completas, invalide estabilidade quando a coleção mudar e mantenha a ausência de um ator em scan parcial sem interpretá-la como remoção. Como o worker coalesce metadados e deltas separadamente, publique a revisão aplicada aos registros e recuse auditoria se ela divergir da revisão do estado; vincule o manifesto da cópia ao `run_id` e à revisão conferidos antes/depois, sem transformar uma coincidência de contagens em autoridade para bloquear.

### Prontidão precisa de fonte ativa

O arquivo atual ShooterGame.log permaneceu vazio nessa partida, mesmo com A2S público respondendo TheIsland e RCON informando runtime/journal saudáveis, 231 estruturas e varreduras estáveis. Não dependa exclusivamente de um marcador nesse arquivo para declarar prontidão: confira a instância/processo correto, resposta ativa de A2S e RCON, versão do plugin e varredura concluída.
