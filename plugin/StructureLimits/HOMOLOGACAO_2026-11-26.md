# Rodada humana — StructureLimits 0.9-dev

O administrador informou início e final em 227/100, incrementos/decrementos unitários e estabilidade tanto perto quanto longe. As imagens mostram a sequência 227 → 228/230 → 229/228/227 e uma localização 36,06/59,12.

O estado anterior foi preservado às 23:09:13 UTC no backup privado `E:\ARKLAND_Backups\StructureLimits\test-batch-20261126-200913`. A consulta posterior via SSH comparou os IDs iniciais/finais, eventos duráveis novos e log do PID 6924.

## Confirmado no servidor

- Cinco colocações e cinco remoções de TekLight, entre 23:18:10 e 23:20:18 UTC. IDs: 227759632, 950903498, 719602867, 1940750618 e 1988796081. Cada ID teve exatamente um evento de colocação e um de remoção; nenhum permaneceu ativo.
- Atribuição final da tribo: 227. Nenhum ID das 231 estruturas do inventário geral inicial desapareceu.
- Um evento de remoção adicional de `AmargaSpike_Armor` não pertence ao conjunto colocado pelo jogador e foi mantido separado da comprovação.
- Inventário geral: 231 → 244. Os 13 IDs novos restantes eram DeathItemCache, sem atribuição de tribo/Steam; portanto o total geral não foi declarado correto apenas porque o total da tribo fechou. Isso motivou a correção por marcadores nativos da 0.9.1-dev.
- Runtime/journal saudáveis, fila vazia e conflitos de ID zero. Não houve ativação de fiscalização nem reinício para conferir esta rodada.

## GPS e limites da evidência

O helper `FVectorToCoords` do SDK aplica `floor(coordenada*10)/10`. Assim, os logs 36,0/59,1 são compatíveis com a imagem 36,06/59,12 dentro dessa precisão. A 0.9.1-dev passa a calcular sem esse corte, usando a mesma calibração do mundo; isso exige nova conferência visual quando instalada.

As cinco construções registradas usaram o mesmo blueprint. Esta rodada não comprova diversidade de blueprints, decay, fusão, recuperação após reinício, licença, limite específico ou veto antes de consumir materiais. `Destroyed` continua registrando causa não especificada, sem inventar pickup/demolição/decay individualmente.
