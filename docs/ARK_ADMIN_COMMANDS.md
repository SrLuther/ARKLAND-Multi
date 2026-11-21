# ARK: Survival Evolved — comandos administrativos

**Referência local do ARKLAND Multi.** Base principal: ARK: Survival Evolved (ASE), compatível conceitualmente com a tela Cheat Manager do servidor. Os nomes e parâmetros variam conforme a versão do jogo, ArkApi, mods e funções expostas pelo build. Use o Cheat Manager do próprio servidor como autoridade para o que está disponível naquele momento.

## Como consultar a lista efetiva no servidor

Entre como administrador e abra `ShowMyAdminManager`; no painel, a coluna **Cheat Manager** mostra as funções expostas pelo servidor, com parâmetros. Essa lista é dinâmica do build e pode conter funções técnicas que não são seguras ou apropriadas para uso rotineiro.

## Exemplo da imagem: `MaxAscend PlayerId[int32]`

`MaxAscend <PlayerId>` concede ao jogador as ascensões Alpha do Overseer e do Rockwell, com os níveis extras e engramas associados. Não equivale a derrotar todos os chefes. O ID é o ID numérico do personagem no jogo; `0` aplica ao perfil local/single-player. Em servidor, confira o ID antes de executar. O implante pode não refletir a alteração até o personagem sair e voltar ao mapa.

Exemplo local: `cheat MaxAscend 0`. Para servidor dedicado, autentique com `enablecheats <senha>` e use `admincheat MaxAscend <PlayerId>` no console/RCON, conforme o canal de administração. Consulte [MaxAscend — ARK Wiki](https://ark.wiki.gg/wiki/Cheat#MaxAscend).

## Catálogo administrativo do ARK (ASE)

Esta referência local foi atualizada em 20/11/2026 a partir do catálogo Arked.gg. Cada entrada traz uma explicação em português, a sintaxe publicada, exemplo (quando disponível), tipo de alvo, compatibilidade e nível de risco estimado. A descrição em português é uma tradução inicial da fonte inglesa; confira o efeito e a sintaxe na fonte quando for executar comandos importantes. A compatibilidade indicada não substitui a verificação no Cheat Manager do build instalado.

**Cobertura da fonte nesta revisão:** 238 registros publicados, correspondentes a 237 nomes distintos (a fonte lista `GetEgg` em duas variantes); 232 registros marcados como compatíveis com ASE e 6 exclusivos de ASA. Os comandos ASA estão marcados e não devem ser usados no ASE. O catálogo estruturado consumido pela Central de Comandos está em `plugin/arkshop_web/static/ark_admin_commands.json`, incluindo a descrição original em inglês para auditoria.

**Identificadores de jogadores:** `SteamID64` identifica a conta Steam; `PlayerID` é outro identificador. A consulta `ListPlayers` no site fornece SteamID64, não PlayerID numérico. Nunca substitua um pelo outro; quando um comando exigir PlayerID, informe o valor correto obtido por uma fonte confiável.

| Comando | Categoria | O que faz | Sintaxe publicada | Exemplo | Alvo / compatibilidade / risco |
|---|---|---|---|---|---|
| `AddChibiExp` | Jogador | O comando AddChibiExp adicionará XP ao seu animal de estimação chibi. Se nenhum chibi estiver equipado, o XP será adicionado ao jogador. | `AddChibiExp <Amount>` | `AddChibiExp 5000` | Sem jogador específico · ASE · baixo |
| `AddChibiExpToPlayer` | Jogador | O comando AddChibiExpToPlayer adicionará XP ao animal de estimação chibi do jogador (use o ID UE4 do jogador). Se nenhum chibi estiver equipado, o XP será adicionado ao jogador. | `AddChibiExpToPlayer <PlayerID> <Amount>` | `AddChibiExpToPlayer 12345678901 5000` | PlayerID · ASE · baixo |
| `AddEquipmentDurability` | Jogador | O comando AddEquipmentDurability adiciona água/energia/durabilidade aos itens/armaduras equipados (incluindo hotbar). | `AddEquipmentDurability <Amount>` | `AddEquipmentDurability 10` | Sem jogador específico · ASE · baixo |
| `AddExperience` | Jogador | O comando AddExperience adiciona a quantidade especificada de XP ao jogador. Se o jogador estiver montado quando o comando for usado, a criatura receberá o XP. <FromTribeShare> - Use 1 para compartilhamento de tribo, use 0 para todo. <PreventSharingWithTribe> - Use 1 apenas para o jogador, use 0 para compartilhar com a tribo. | `AddExperience <Amount> <FromTribeShare> <PreventSharingWithTribe>` | `AddExperience 5000 0 1` | Sem jogador específico · ASE · baixo |
| `ResetSkillCooldowns` | Jogador, Árvore de habilidades | O comando ResetSkillCooldowns irá limpar quaisquer cooldowns em habilidades na Árvore de Habilidades (ASA Lost Colony DLC). | `ResetSkillCooldowns` | `ResetSkillCooldowns` | Sem jogador específico · ASA · alto |
| `AddHexagons` | Jogador | O comando AddHexagons adicionará a quantidade especificada de Hexágonos (para gastar em HLNA) ao jogador. | `AddHexagons <Amount>` | `AddHexagons 1000` | Sem jogador específico · ASE · baixo |
| `AddItemToAllClustersInventory` | Não documentado | O comando AddItemToAllClustersInventory existe, mas não se sabe qual é o seu propósito. | `AddItemToAllClustersInventory` | — | Sem jogador específico · ASE · baixo |
| `AllowPlayerToJoinNoCheck` | Administração do servidor | O comando AllowPlayerToJoinNoCheck adiciona o jogador especificado à lista de permissões do servidor. | `AllowPlayerToJoinNoCheck <SteamID>` | `AllowPlayerToJoinNoCheck 12345678901` | SteamID · ASE · baixo |
| `AutoCycle` | Jogador | O comando AutoCycle fornece saúde ilimitada pelo número especificado de segundos. | `AutoCycle <DurationSeconds>` | `AutoCycle 60` | Sem jogador específico · ASE · baixo |
| `BanPlayer` | Administração do servidor | O comando BanPlayer expulsa um jogador do servidor e o proíbe permanentemente de voltar a entrar. Funciona para nomes SteamID / Xbox / Playstation. | `BanPlayer <SteamID>` | `BanPlayer 12345678901` | SteamID · ASE · alto |
| `Broadcast` | Administração do servidor, Chat | O comando Broadcast transmite uma mensagem para todos os jogadores no servidor. | `Broadcast <MessageText>` | `Broadcast Empty the beaverdams!` | Sem jogador específico · ASE · baixo |
| `CCC` | Jogador, Mundo e mapa, Teletransporte, Sem autenticação de cheat | O comando CCC é um atalho do comando CopyCoordsToClipboard que copia suas coordenadas atuais para a área de transferência. (X, Y, Z, inclinação e guinada). | `CCC` | `CCC` | Sem jogador específico · ASE · baixo |
| `CE` | Mundo e mapa | O comando CE inicia e para o clima. Observe que alguns comandos exigem aspas. A Ilha - starttime, stoptime, onda de calor, coldfront, makeitrain, stoprain, fogitup, stopfog Scorched Earth - start_superheat, stop_superheat, start_sandstorm, stop_sandstorm, start_electricalstorm, stop_electricalstorm, start_rain, stop_rain Ragnarok - "iniciar chuva", "parar chuva", "iniciar tempestade elétrica", "parar tempestade elétrica", "iniciar tempestade de areia", "parar tempestade de areia", "iniciar superaquecimento", "parar superheat", Start_Volcano Aberration - startquake, stopquake Extinction - "start meteors" Valguero - SpawnRainbow, TestNorthernLights1 | `CE <Type>` | `CE stopfog` | Sem jogador específico · ASE · baixo |
| `ChangeSize` | Jogador | O comando ChangeSize altera o tamanho do seu personagem. Usar um multiplicador de 0,5 reduzirá metade do tamanho do caractere, usar 3 triplicará o tamanho do caractere (muito grande ou pequeno, não recomendado). Usar 1 retornará o personagem ao normal. | `ChangeSize <Multiplier>` | `ChangeSize 2` | Sem jogador específico · ASE · baixo |
| `ClearCryoSickness` | Criatura | O comando ClearCryoSickness acordará qualquer criatura que você esteja olhando (sob sua mira) que esteja afetada pela criose. | `ClearCryoSickness` | `ClearCryoSickness` | Sem jogador específico · ASE · baixo |
| `ClearMyBuffs` | Jogador | O comando ClearMyBuffs removerá quaisquer buffs atuais (de sopas, etc). Não funciona em todos os buffs. | `ClearMyBuffs` | `ClearMyBuffs` | Sem jogador específico · ASE · baixo |
| `ClearPlayerInventory` | Jogador, Administração do servidor | O comando ClearPlayerInventory limpará o inventário, os itens equipados ou os itens de slot do jogador especificado. (0=Falso, 1=Verdadeiro) | `ClearPlayerInventory <PlayerID> <ClearInventory> <ClearSlotItems> <ClearEquippedItems>` | `ClearPlayerInventory 12345678901 0 0 1 (0=False, 1=True)` | PlayerID · ASE · alto |
| `ClearTutorials` | Jogador | O comando ClearTutorials redefine todos os tutoriais. Permite ao jogador ver os tutoriais novamente se já concluídos. | `ClearTutorials` | `ClearTutorials` | Sem jogador específico · ASE · baixo |
| `CopyCoordsToClipboard` | Jogador, Mundo e mapa, Teletransporte, Sem autenticação de cheat | O comando CopyCoordsToClipboard (atalho CCC) copia suas coordenadas atuais para sua área de transferência. (X, Y, Z, Pitch e Yaw). | `CopyCoordsToClipboard` | `CopyCoordsToClipboard` | Sem jogador específico · ASE · baixo |
| `CryoMyTarget` | Criatura | O comando CryoMyTarget coloca a criatura que você está olhando (sob sua mira) em um criópode. | `CryoMyTarget` | `CryoMyTarget` | Alvo sob a mira · ASE · baixo |
| `DCMSet` | Mundo e mapa | O comando DCMSet redefine o ciclo do dia atual. Na Gen2, quando a <propriedade> for alterada para skybox, os asteróides atuais serão alterados para - 0: Ambergris / 1: Crystal / 2: Enxofre / 3: Element Shards / 4: Obsidian / 5: Oil / 6: Element Dust / 7: Black Pearls | `DCMSet <Property> <Value>` | `dcmset skybox 0` | Sem jogador específico · ASE · moderado |
| `DebugAllowvrMissionTeleport` | Jogador, Teletransporte, Chefes | O comando DebugAllowvrMissionTeleport o levará ao chefe final na Gen1 sem ter que completar todos os missões. | `DebugAllowvrMissionTeleport` | `DebugAllowvrMissionTeleport` | Sem jogador específico · ASE · moderado |
| `DebugStructures` | Estruturas | O comando DebugStructures exibe informações sobre as estruturas que você observa, incluindo o nome da classe e o ID da entidade. | `DebugStructures` | `DebugStructures` | Sem jogador específico · ASE · baixo |
| `DefeatAllBosses` | Chefes, Jogador | O comando DefeatAllBosses irá desbloquear, como se fosse derrotado, todos os chefes alfa. Use 0 para <PlayerId> para jogador local/único. | `DefeatAllBosses <PlayerId>` | `DefeatAllBosses 0` | PlayerID · ASE · alto |
| `DefeatBoss` | Chefes, Jogador | O comando DefeatBoss derrotará um chefe específico na dificuldade especificada. Usar 0 para <PlayerId> direcionará o jogador usando o comando. Nomes dos chefes (Supervisor = Guardião) • (Mãe de ninhada Lysrix = Uberaranha) • (Megapithecus = Megapithecus) • (Dragão = Dragão) • (Manticore = Manticore) • (Rockwell = Rockwell) • (Rei Titã = Rei Titã) • (Ice Titan = IceKaiju) • (Forest Titan = ForestKaiju) • (Desert Titan = DesertKaiju) • (Controlador Mestre Corrompido = VrMainBoss) • (Rockwell Prime = Gen2Rockwell). Dificuldade (0 para Gama, 1 para Beta ou 2 para Alfa). | `DefeatBoss <PlayerId> <BossName> <Difficulty>` | `DefeatBoss 0 "Broodmother" 2` | PlayerID · ASE · alto |
| `DestroyActors` | Destruição, Criatura, Administração do servidor | O comando DestroyActors destruirá todas as criaturas de um determinado tipo. | `DestroyActors <Type> <Exact Match>` | `DestroyActors Ankylo_Character_BP_C 1` | Sem jogador específico · ASE · alto |
| `DestroyAll` | Criatura, Destruição | O comando DestroyAll destruirá todas as criaturas/estruturas/ovos, etc. de um determinado tipo. (<Correspondência exata> - 0=Falso, 1=Verdadeiro) | `DestroyAll <Type> <Exact Match>` | `destroyall DroppedItemGeneric_FertilizedEgg_NoPhysicsWyvern_C 0` | Sem jogador específico · ASE · alto |
| `DestroyAllEnemies` | Criatura, Destruição | O comando DestroyAllEnemies destruirá todas as criaturas domesticadas ou selvagens no mapa. | `DestroyAllEnemies` | `DestroyAllEnemies` | Sem jogador específico · ASE · alto |
| `DestroyFoliage` | Destruição, Mundo e mapa | O comando DestroyFoliage destruirá todas as folhagens e nós dentro do raio especificado. Os materiais dos nós serão adicionados ao seu inventário (<PutFoliageResourcesInInventory> 0=False, 1=True). | `DestroyFoliage <Radius> <PutFoliageResourcesInInventory>` | `DestroyFoliage 250 1` | Sem jogador específico · ASE · alto |
| `DestroyMyTarget` | Criatura, Destruição, Estruturas | O comando DestroyMyTarget destruirá qualquer entidade na mira do jogador. | `DestroyMyTarget` | `DestroyMyTarget` | Alvo sob a mira · ASE · alto |
| `DestroyStructures` | Estruturas, Destruição, Mundo e mapa | O comando DestroyStructures destrói todas as estruturas em um mapa. | `DestroyStructures` | `DestroyStructures` | Sem jogador específico · ASE · alto |
| `DestroyTribeDinos` | Criatura, Tribos, Destruição | O comando DestroyTribeDinos destrói todos os dinossauros da entidade (dino, jogador ou estrutura) que você está olhando no momento. Todos os outros dinossauros permanecerão intocados. | `DestroyTribeDinos` | `DestroyTribeDinos` | Sem jogador específico · ASE · alto |
| `DestroyTribeId` | Tribos, Jogador, Criatura, Destruição | O comando DestroyTribeId destrói todos os dinossauros da tribo especificada. (Se <TribeID> for 0, então a entidade sob mira será usada). | `DestroyTribeId <Tribe ID>` | `DestroyTribeId 12345678901` | Sem jogador específico · ASE · alto |
| `DestroyTribeIdDinos` | Tribos, Criatura, Destruição | O comando DestroyTribeIdDinos destrói todos os dinossauros de uma tribo específica. (Se <TribeID> for 0, então a entidade sob mira será usada). | `DestroyTribeIdDinos <TribeId>` | `DestroyTribeIdDinos 12345678901` | Sem jogador específico · ASE · alto |
| `DestroyTribeIdPlayers` | Tribos, Destruição, Jogador | O comando DestroyTribeIdPlayers destrói todos os jogadores de uma tribo específica. (Se <TribeID> for 0, então a entidade sob mira será usada). | `DestroyTribeIdPlayers <TribeId>` | `DestroyTribeIdPlayers 12345678901` | Sem jogador específico · ASE · alto |
| `DestroyTribeIdStructures` | Tribos, Destruição, Estruturas | O comando DestroyTribeIdStructures destrói todas as estruturas dentro da tribo especificada. (Se <TribeID> for 0, então a entidade sob mira será usada). | `DestroyTribeIdStructures <TribeId>` | `DestroyTribeIdStructures 12345678901` | Sem jogador específico · ASE · alto |
| `DestroyTribePlayers` | Tribos, Destruição, Jogador | O comando DestroyTribePlayers destrói todos os jogadores dentro da tribo do jogador/coisa que você está olhando atualmente. | `DestroyTribePlayers` | `DestroyTribePlayers` | Sem jogador específico · ASE · alto |
| `DestroyTribeStructures` | Tribos, Destruição, Estruturas | O comando DestroyTribeStructures destrói todas as estruturas pertencentes à tribo do jogador/coisa que você está olhando atualmente. | `DestroyTribeStructures` | `DestroyTribeStructures` | Sem jogador específico · ASE · alto |
| `DestroyTribeStructuresLessThan` | Tribos, Destruição, Estruturas, Administração do servidor, Mundo e mapa | O comando DestroyTribeStructuresLessThan destruirá qualquer estrutura com menos do que o número especificado de conexões. Útil para remover estruturas solitárias ou pilares com uma escada anexada. | `DestroyTribeStructuresLessThan <TribeTeamID> <Connections>` | `cheat DestroyTribeStructuresLessThan 1234567890 3` | Sem jogador específico · ASE · alto |
| `DestroyWildDinoClasses` | Criatura, Destruição, Mundo e mapa | O comando DestroyWildDinoClasses destruirá todos os dinossauros selvagens da classe especificada. | `DestroyWildDinoClasses <Creature ID>` | `DestroyWildDinoClasses "Ankylo_Character_BP_C" 1` | Sem jogador específico · ASE · alto |
| `DestroyWildDinos` | Criatura, Destruição, Mundo e mapa | O comando DestroyWildDinos destrói todos os dinossauros selvagens no mapa. Muito útil para forçar o reaparecimento de criaturas após implementar um evento ou alterar o nível de dificuldade. | `DestroyWildDinos` | `DestroyWildDinos` | Sem jogador específico · ASE · alto |
| `Dino DestroyCenterNode` | Chefes, Destruição | O comando Dino DestroyCenterNode destrói o nó central do Titã da Floresta | `Dino DestroyCenterNode` | `Dino DestroyCenterNode` | Sem jogador específico · ASE · alto |
| `Dino DestroyLeftNode` | Chefes, Destruição | O comando Dino DestroyLeftNode desmembra o braço esquerdo e destrói o nó esquerdo do Titã da Floresta | `Dino DestroyLeftNode` | `Dino DestroyLeftNode` | Sem jogador específico · ASE · alto |
| `Dino DestroyRightNode` | Chefes, Destruição | O comando Dino DestroyRightNode desmembra o braço direito e destrói o nó direito da Floresta Titan | `Dino DestroyRightNode` | `Dino DestroyRightNode` | Sem jogador específico · ASE · alto |
| `Dino DontHideRiderDuringBlink` | Criatura, Jogador | O comando Dino DontHideRiderDuringBlink alterna a invisibilidade do cavaleiro durante um piscar do Enforcer. (Garante que os pilotos ocultos não apareçam quando o Enforcer estiver piscando). | `Dino DontHideRiderDuringBlink` | `Dino DontHideRiderDuringBlink` | Sem jogador específico · ASE · baixo |
| `Dino InfiniteBlink` | Criatura | O comando Dino InfiniteBlink dá ao Enforcer piscadas infinitas. Afeta o Enforcer que você está montando ou olhando (sob a mira). | `Dino InfiniteBlink` | `Dino InfiniteBlink` | Sem jogador específico · ASE · baixo |
| `Dino InfiniteFuel` | Criatura | O comando Dino InfiniteFuel dará combustível infinito ao Mek. Pode ser desativado usando o comando novamente. | `Dino InfiniteFuel` | `Dino InfiniteFuel` | Sem jogador específico · ASE · baixo |
| `Dino InfiniteGas` | Criatura | O comando Dino InfiniteGas manterá a inflação dos Gasbags em 100%. Pode ser desativado usando o comando novamente. | `Dino InfiniteGas` | `Dino InfiniteGas` | Sem jogador específico · ASE · baixo |
| `Dino Inflate` | Criatura | O comando Dino Inflate dará aos Gasbags 100% de inflação. | `Dino Inflate` | `Dino Inflate` | Sem jogador específico · ASE · baixo |
| `Dino NoHeat` | Criatura | O comando Dino NoHeat impedirá que um Mek ganhe calor. Isso significa que o calor permanecerá em 0% e o Mek pode pairar indefinidamente. | `Dino NoHeat` | `Dino NoHeat` | Sem jogador específico · ASE · baixo |
| `Dino ReplayIntro` | Criatura | O comando Dino ReplayIntro tornará o MegaMek invisível e reproduzirá o VFX de introdução. | `Dino ReplayIntro` | `Dino ReplayIntro` | Sem jogador específico · ASE · baixo |
| `Dino Reset` | Criatura | O comando Dino Reset redefine os resfriamentos de piscar em um Enforcer, ou o combustível / calor para um Mek. | `Dino Reset` | `Dino Reset` | Sem jogador específico · ASE · moderado |
| `Dino TitanMode` | Criatura | O comando Dino TitanMode infla os sacos de gás em 10x. | `Dino TitanMode` | `Dino TitanMode` | Sem jogador específico · ASE · baixo |
| `Dino ToggleUpkeep` | Criatura | O comando Dino ToggleUpkeep pode ser alternado para pausar/ativar a subtração de combustível/saúde a cada minuto. | `Dino ToggleUpkeep` | `Dino ToggleUpkeep` | Sem jogador específico · ASE · baixo |
| `DinoSet Blink` | Criatura | O comando DinoSet Blink define a porcentagem de piscada do Enforcer para o número especificado. O número <Porcentagem de piscadas> deve estar entre 0 e 1. (Por exemplo, 0,5 para 50%) | `DinoSet Blink <Blink Percentage>` | `DinoSet Blink 0.5` | Sem jogador específico · ASE · moderado |
| `DinoSet BlinkBack` | Criatura | O comando DinoSet BlinkBack define a porcentagem de intermitência retroativa do Enforcer para o número especificado. O número <Porcentagem de piscadas> deve estar entre 0 e 1. (Por exemplo, 0,5 para 50%) | `DinoSet BlinkBack <Blink Percentage>` | `DinoSet BlinkBack 0.5` | Sem jogador específico · ASE · moderado |
| `DinoSet Cooldowns` | Criatura | O comando DinoSet Cooldowns definirá o número de piscadas que um Enforcer terá antes do resfriamento. | `DinoSet Cooldowns <Number>` | `DinoSet Cooldowns 3` | Sem jogador específico · ASE · moderado |
| `DinoSet EatTime` | Criatura | O comando DinoSet EatTime definirá o número de segundos entre cada vez que um Gacha se senta para comer. | `DinoSet EatTime <Number of Seconds>` | `DinoSet EatTime 2` | Sem jogador específico · ASE · moderado |
| `DinoSet Fuel` | Criatura | O comando DinoSet Fuel irá adicionar ou subtrair a quantidade de combustível que um Mek possui. | `DinoSet Fuel <Number>` | `DinoSet Fuel -50` | Sem jogador específico · ASE · moderado |
| `DinoSet Inflate` | Criatura | O comando DinoSet Inflate infla ou esvazia os Gasbags na quantidade especificada. | `DinoSet Inflate <Number>` | `DinoSet Inflate -50` | Sem jogador específico · ASE · moderado |
| `DinoSet UpkeepInterval` | Criatura | O comando DinoSet UpkeepInterval alterará o intervalo entre atualizações de combustível/aquecimento em um Mek. (O padrão é 60) | `DinoSet UpkeepInterval` | `DinoSet UpkeepInterval 60` | Sem jogador específico · ASE · moderado |
| `DisableSpectator` | Administração do servidor, Espectador | O comando DisableSpectator tira você do modo espectador (seu personagem é morto, então você precisará reaparecer). | `DisableSpectator` | `DisableSpectator` | Sem jogador específico · ASE · baixo |
| `DisallowPlayerToJoinNoCheck` | Administração do servidor | O comando DisallowPlayerToJoinNoCheck remove o jogador da lista de permissões do servidor. | `DisallowPlayerToJoinNoCheck <SteamID>` | `DisallowPlayerToJoinNoCheck 12345678901` | SteamID · ASE · baixo |
| `DoExit` | Administração do servidor | O comando DoExit força o servidor a desligar o mais rápido possível. | `DoExit` | `DoExit` | Sem jogador específico · ASE · alto |
| `DoRestartLevel` | Administração do servidor | O comando DoRestartLevel reinicia o mapa atual. | `DoRestartLevel` | `DoRestartLevel` | Sem jogador específico · ASE · alto |
| `DoTame` | Criatura | O comando DoTame irá domar a criatura que você está olhando (sob sua mira) como se você a tivesse domesticado normalmente. | `DoTame` | `DoTame` | Sem jogador específico · ASE · baixo |
| `DumpDinoStats` | Criatura | O comando DumpDinoStats listará todas as estatísticas do dinossauro no console. Isso se aplica ao dinossauro que você está montando ou olhando (sob a mira). | `DumpDinoStats` | `DumpDinoStats` | Sem jogador específico · ASE · baixo |
| `DupeLastItem` | Não documentado | O comando DupeLastItem existe, mas não se sabe qual é sua finalidade, pois parece não fazer nada. | `DupeLastItem` | `DupeLastItem` | Sem jogador específico · ASE · baixo |
| `EnableCheats` | Administração do servidor, Jogador | O comando EnableCheats permite ao jogador usar comandos admincheat no servidor. (Use ServerAdminPassword para <Senha>) | `EnableCheats <Password>` | `EnableCheats thepassword` | Sem jogador específico · ASE · baixo |
| `EnableSpectator` | Administração do servidor, Espectador | O comando EnableSpectator colocará seu personagem no modo espectador. Destrói seu inventário. | `EnableSpectator` | `EnableSpectator` | Sem jogador específico · ASE · baixo |
| `EnemyInvisible` | Criatura, Jogador | O comando EnemyInvisible torna o jogador invisível para todas as criaturas. Seu personagem será ignorado mesmo se você atacar criaturas. | `EnemyInvisible <True / False>` | `EnemyInvisible True` | Sem jogador específico · ASE · baixo |
| `EnvQA` | Jogador | O comando EnvQA lhe dará vários buffs destinados aos testadores de controle de qualidade. Inclui GMBuff, stat fps, unidade de estatísticas e armadura tek completa. | `EnvQA` | `EnvQA` | Sem jogador específico · ASE · baixo |
| `ExecSetSleeping` | Jogador | O comando ExecSetSleeping colocará seu personagem para dormir (True) ou acordar (False) | `ExecSetSleeping <True / False>` | `ExecSetSleeping True` | Sem jogador específico · ASE · moderado |
| `FindMutagenDrops` | Jogador, Mundo e mapa | O comando FindMutagenDrops lista todas as lâmpadas mutagênicas no mapa (somente Gen2) para o console. | `FindMutagenDrops` | `FindMutagenDrops` | Sem jogador específico · ASE · baixo |
| `Fly` | Jogador, Teletransporte | O comando Fly permite ao jogador se mover em todas as direções sem gravidade ou física. Use o comando Walk para retornar ao normal. | `Fly` | `Fly` | Sem jogador específico · ASE · baixo |
| `ForceCompleteActiveMission` | Jogador | O comando ForceCompleteActiveMission completará a missão atual (Gen1 ou Gen2) | `ForceCompleteActiveMission` | `ForceCompleteActiveMission` | Sem jogador específico · ASE · baixo |
| `ForceGiveBuff` | Jogador | O comando ForceGiveBuff dará ao jogador ou dinossauro montado o buff especificado (use ListMyBuffs para encontrar os IDs de Buff atualmente habilitados). Use ativar (1) ou desativar (0). | `ForceGiveBuff <Buff ID> <Enable>` | `Forcegivebuff buff_namelesspreggers 1` | Sem jogador específico · ASE · moderado |
| `ForceJoinTribe` | Tribos, Jogador | O comando ForceJoinTribe fará com que seu personagem se junte à tribo da entidade (jogador, dinossauro ou estrutura) que você está olhando (sob sua mira). | `ForceJoinTribe` | `ForceJoinTribe` | Sem jogador específico · ASE · baixo |
| `ForceMutagenSpawn` | Mundo e mapa, Jogador | O comando ForceMutagenSpawn forçará a geração do bulbo mutagênico mais próximo. | `ForceMutagenSpawn` | `ForceMutagenSpawn` | Sem jogador específico · ASE · moderado |
| `ForcePlayerToJoinTargetTribe` | Tribos, Jogador | O comando ForcePlayerToJoinTargetTribe forçará o jogador especificado por seu ID de jogador a se juntar à tribo da entidade (jogador, dinossauro ou estrutura) que você está olhando (sob sua mira). | `ForcePlayerToJoinTargetTribe <PlayerID>` | `ForcePlayerToJoinTargetTribe 12345678901` | PlayerID · ASE · alto |
| `ForcePlayerToJoinTribe` | Tribos, Jogador | O comando ForcePlayerToJoinTribe força o jogador com o ID especificado a ingressar na tribo especificada. (Somente UE4 ID, não funciona no console). | `ForcePlayerToJoinTribe <PlayerID> <TribeName>` | `ForcePlayerToJoinTribe 12345678901 12345678901` | PlayerID · ASE · alto |
| `ForcePoop` | Criatura | O comando ForcePoop força o dinossauro que você está montando ou que está olhando (sob a mira) a fazer cocô. | `ForcePoop` | `ForcePoop` | Sem jogador específico · ASE · baixo |
| `ForceTame` | Criatura | O comando ForceTame doma a criatura que você está olhando (sob sua mira). A criatura poderá ser montada sem sela (buff sem sela removido após colocar um criópode). | `ForceTame` | `ForceTame` | Sem jogador específico · ASE · moderado |
| `ForceTameAOE` | Criatura | O comando ForceTameAOE domesticará todas as criaturas dentro do raio especificado. As criaturas poderão ser montadas sem sela (buff sem sela removido após colocar um criópode). | `ForceTameAOE <Radius>` | `ForceTameAOE 500` | Sem jogador específico · ASE · moderado |
| `ForceTribes` | Tribos, Jogador | O comando ForceTribes forçará os jogadores nomeados a usarem o novo nome de tribo especificado. | `ForceTribes <PlayerName1> <PlayerName2> <NewTribeName>` | `ForceTribes Bob Jane ArkLoversTribe` | Sem jogador específico · ASE · baixo |
| `ForceUpdateDynamicConfig` | Administração do servidor | O comando ForceUpdateDynamicConfig aplica quaisquer alterações feitas no arquivo de configuração. | `ForceUpdateDynamicConfig` | `ForceUpdateDynamicConfig` | Sem jogador específico · ASE · baixo |
| `GameCommand` | Administração do servidor | O comando GameCommand executa um comando específico do jogo para mods gamemode que o servidor está executando, como SOTF. | `GameCommand <TheCommand>` | `gamecommand startgame` | Sem jogador específico · ASE · baixo |
| `GCM` | Jogador, Modo criativo | O comando GCM ativa o Modo Criativo (esta é uma versão abreviada de GiveCreativeMode). | `GCM` | `GCM` | Sem jogador específico · ASE · baixo |
| `GetAllState` | Administração do servidor, Criatura, Mundo e mapa | O comando GetAllState imprime no console uma lista de todas as entidades do tipo especificado atualmente presentes no servidor. Útil para verificar se um dinossauro raro está presente. | `GetAllState <Type>` | `GetAllState Carcha_Character_BP_C` | Sem jogador específico · ASE · baixo |
| `GetChat` | Administração do servidor | O comando GetChat lista o bate-papo mais recente (apenas tanto quanto o buffer de bate-papo que um jogador normal vê) | `GetChat` | `GetChat` | Sem jogador específico · ASE · baixo |
| `GetEgg` | Criatura | O comando GetEgg (ASA) fará com que a criatura à sua frente (sob sua mira) solte um ovo fertilizado com estatísticas idênticas às do pai se a contagem de mutações estiver definida como 0. Aumentar a contagem de mutações adicionará esse número de mutações ao ovo (parece ser aleatório distribuição). | `GetEgg` | `GetEgg` | Sem jogador específico · ASE · baixo |
| `GetGameLog` | Administração do servidor | O comando GetGameLog imprime as últimas 100 entradas do log do jogo no console. Use -servergamelog para ativar os logs do servidor. | `GetGameLog` | `GetGameLog` | Sem jogador específico · ASE · baixo |
| `GetPlayerIDForSteamID` | Administração do servidor, Não documentado | O comando GetPlayerIDForSteamID não funciona atualmente. | `GetPlayerIDForSteamID <SteamId>` | `GetPlayerIDForSteamID 12345678901` | PlayerID · ASE · baixo |
| `GetTribeIdPlayerList` | Administração do servidor, Jogador, Tribos | O comando GetTribeIdPlayerList lista todos os jogadores da tribo especificada no console. | `GetTribeIdPlayerList <TribeID>` | `GetTribeIdPlayerList 12345678901` | Sem jogador específico · ASE · baixo |
| `GFI` | Jogador | O comando GFI fornece ao jogador o item especificado na qualidade especificada como um projeto ou item. Veja nossa lista completa de códigos GFI . | `GFI <BlueprintPathPart> <Quantity> <Quality> <ForceBlueprint>` | `GFI GPS 1 0 0` | Sem jogador específico · ASE · baixo |
| `Ghost` | Jogador | O comando Ghost ativa um modo 'no clip' onde o jogador pode se mover livremente pelo mapa, passando por objetos ou terreno. | `Ghost` | `Ghost` | Sem jogador específico · ASE · baixo |
| `GiveAllExplorerNotes` | Jogador | O comando GiveAllExplorerNotes desbloqueia todas as Notas do Explorador e Runas Fjordur para o jogador. Isso pode congelar o jogo enquanto o comando é executado. Nota: Atualmente há um bug onde você precisa estar perto de qualquer nota do explorador para que as notas do explorador sejam desbloqueadas. | `GiveAllExplorerNotes` | `GiveAllExplorerNotes` | Sem jogador específico · ASE · moderado |
| `GiveAllStructure` | Jogador, Tribos, Estruturas | O comando GiveAllStructure fornece ao jogador todas as estruturas conectadas à estrutura que o jogador está olhando no momento (sob a mira). | `GiveAllStructure` | `GiveAllStructure` | Sem jogador específico · ASE · moderado |
| `GiveArmorSet` | Jogador | O comando GiveArmorSet equipa o jogador com um conjunto completo de armadura do nível especificado. Opções de <Tier>: tecido, quitina, metal, motim, perigo, tek. Se aplicável, o comando givearmor set está listado em nossa página de itens de armadura individuais. Veja uma lista completa de truques de armadura. | `GiveArmorSet <Tier> <Quality>` | `GiveArmorSet metal 100` | Sem jogador específico · ASE · moderado |
| `GiveColors` | Jogador | O comando GiveColors dá ao jogador a quantidade especificada de cada corante de cor no jogo. Veja a lista completa de códigos Dye GFI. | `cheat GiveColors <Amount>` | `GiveColors 10` | Sem jogador específico · ASE · moderado |
| `GiveCreativeMode` | Jogador, Modo criativo | O comando GiveCreativeMode habilita o Modo Criativo (pode ser abreviado para GCM). | `GiveCreativeMode` | `GiveCreativeMode` | Sem jogador específico · ASE · moderado |
| `GiveCreativeModeToPlayer` | Jogador, Modo criativo | O comando GiveCreativeModeToPlayer ativa o Modo Criativo no jogador especificado. | `GiveCreativeModeToPlayer <PlayerID>` | `GiveCreativeModeToPlayer 12345678901` | PlayerID · ASE · moderado |
| `GiveCreativeModeToTarget` | Jogador, Modo criativo | O comando GiveCreativeModeToTarget ativa o Modo Criativo para o jogador que você está olhando (sob a mira). | `GiveCreativeModeToTarget` | `GiveCreativeModeToTarget` | Alvo sob a mira · ASE · moderado |
| `GiveDinoSet` | Criatura | O comando GiveDinoSet fornece o número especificado de criaturas no Tier Group associado (opções de Tier: 0, 1, 2, 3, Flyers, Mek, SiegeMek, MissileMek, ShieldMek, Argent, Extinção). Veja a lista completa de códigos de trapaça de criaturas. | `GiveDinoSet <Tier> <Quantity>` | `GiveDinoSet Flyers 5` | Sem jogador específico · ASE · moderado |
| `GiveEngrams` | Jogador | O comando GiveEngrams desbloqueia todos os engramas para o seu personagem - apenas para aquela sessão. | `GiveEngrams` | `GiveEngrams` | Sem jogador específico · ASE · moderado |
| `GiveEngramsTekOnly` | Jogador | O comando GiveEngramsTekOnly desbloqueia todos os engramas Tek para o seu personagem - apenas para aquela sessão. | `GiveEngramsTekOnly` | `GiveEngramsTekOnly` | Sem jogador específico · ASE · moderado |
| `GiveExplorerNote` | Jogador | O comando GiveExplorerNote desbloqueia uma nota de explorador especificada. Atualmente, há um bug em que você precisa estar perto de qualquer nota do explorador para que a nota do explorador seja desbloqueada. | `GiveExplorerNote <NoteIndexNumber>` | `GiveExplorerNote` | Sem jogador específico · ASE · moderado |
| `GiveExpToPlayer` | Jogador, Criatura | O comando GiveExpToPlayer adiciona a quantidade especificada de XP ao jogador. <FromTribeShare> - Use 1 para compartilhamento de tribo, use 0 para todo. <PreventSharingWithTribe> - Use 1 apenas para o jogador, use 0 para compartilhar com a tribo. | `GiveExpToPlayer <PlayerID> <Amount> <FromTribeShare> <PreventSharingWithTribe>` | `GiveExpToPlayer 12345678901 5000 0 1` | PlayerID · ASE · moderado |
| `GiveInfiniteStatsToTarget` | Jogador, Criatura | O comando GiveInfiniteStatsToTarget fornece estatísticas infinitas ao jogador ou criatura que você está olhando (sob a mira). Atualmente existe um bug onde este comando só funciona em criaturas. | `GiveInfiniteStatsToTarget` | `GiveInfiniteStatsToTarget` | Alvo sob a mira · ASE · moderado |
| `GiveItem` | Jogador, Modo criativo | O comando GiveItem fornece o item especificado na quantidade ou qualidade necessária, você pode especificar se precisa de um projeto ou do item real. Consulte a página de cada item individual neste site para obter um construtor de comando giveitem. Veja nossa lista completa de códigos GFI para encontrar a página de um item. | `GiveItem <BlueprintPath> <Quantity> <Quality> <ForceBlueprint>` | `Giveitem "Blueprint'/Game/PrimalEarth/Test/PrimalItem_WeaponGPS.PrimalItem_WeaponGPS'" 1 0 0` | Sem jogador específico · ASE · moderado |
| `GiveItemNum` | Jogador, Modo criativo | O comando GiveItemNum fornece o item especificado na quantidade ou qualidade necessária, você também pode especificar se precisa de um modelo ou do item real. Este comando só funciona para aqueles itens que possuem um número associado, é recomendado usar GiveItem pois abrange todos os itens. Consulte a página de cada item individual neste site para obter o número do item (se existir). Veja nossa lista completa de códigos GFI para encontrar a página de um item. | `GiveItemNum <ItemNum> <Quantity> <Quality> <ForceBlueprint>` | `Giveitemnum 45 1 0 0` | Sem jogador específico · ASE · moderado |
| `ResetSkills` | Jogador, Árvore de habilidades | O comando ResetSkills removerá todas as habilidades aprendidas na Árvore de Habilidades (DLC ASA Lost Colony), mas não removerá pontos de habilidade. | `ResetSkills` | `ResetSkills` | Sem jogador específico · ASA · alto |
| `GiveItemNumToPlayer` | Jogador, Modo criativo | O comando GiveItemNumToPlayer fornece o item especificado na quantidade ou qualidade necessária. Você pode especificar se precisa de um modelo ou do item real. Este comando só funciona para os itens que possuem um número associado; é recomendado usar GiveItemToPlayer, pois abrange todos os itens. Consulte a página de cada item individual neste site para obter o número do item (se existir). Veja nossa lista completa de códigos GFI para encontrar a página de um item. | `GiveItemToPlayer <PlayerID> <BlueprintPath> <Quantity> <Quality> <ForceBlueprint>` | `GiveItemNumToPlayer 12345678901 45 1 0 0` | PlayerID · ASE · moderado |
| `GiveItemSet` | Jogador, Modo criativo | O comando GiveItemSet fornece um conjunto de itens. Números do conjunto de itens <Tier>: (0 = 200 stimberries, 90 carne cozida e 2 odres de água) - (1 = 200 stimberries, 100 cervejas medicinais, 90 carne cozida e 2 potes de água) - (2 = 100 cervejas energéticas, 100 cervejas medicinais, 100 caldo de cacto, 60 carne seca cozida e 2 cantis) - (3 = 100 caldo de cacto, 100 cervejas medicinais, 100 cervejas energéticas, 90 carne seca cozida, 5 bifes refogados, 5 ensopados de enduro, 5 chilis focais e 5 sopas de lazaurs. | `GiveItemSet <Tier>` | `GiveItemSet 3` | Sem jogador específico · ASE · moderado |
| `GiveItemToPlayer` | Jogador, Modo criativo | O comando GiveItemToPlayer fornece o item especificado na quantidade ou qualidade necessária, você também pode especificar se precisa de um projeto ou do item real para um jogador específico. código. Veja nossa lista completa de códigos GFI para encontrar a página de um item. | `GiveItemToPlayer <PlayerID> <BlueprintPath> <Quantity> <Quality> <ForceBlueprint>` | `GiveItemToPlayer 12345678901 "Blueprint'/Game/PrimalEarth/Test/PrimalItem_WeaponGPS.PrimalItem_WeaponGPS'" 1 0 0` | PlayerID · ASE · moderado |
| `GiveResources` | Jogador, Modo criativo | O comando GiveResources adiciona 50 de cada recurso ao jogador. | `GiveResources` | `GiveResources` | Sem jogador específico · ASE · moderado |
| `GiveSlotItem` | Jogador, Modo criativo | O comando GiveSlotItem fornece o item especificado, colocado no slot especificado. | `GiveSlotItem <BlueprintPath> <SlotNum> <Quantity>` | `GiveSlotItem "Blueprint'/Game/PrimalEarth/Test/PrimalItem_WeaponGPS.PrimalItem_WeaponGPS'" 1 1` | Sem jogador específico · ASE · moderado |
| `GiveAllSkills` | Jogador, Árvore de habilidades | O. O comando GiveAllSkills dará ao jogador todas as habilidades na Skill Tree (ASA Lost Colony DLC). | `GiveAllSkills` | `GiveAllSkills` | Sem jogador específico · ASA · alto |
| `GiveSlotItemNum` | Jogador, Modo criativo | O comando GiveSlotItemNum fornece o item especificado, colocado no slot especificado, como nem todos os itens têm um número associado, é recomendado usar GiveSlotItem em vez disso. | `GiveSlotItemNum <ItemNum> <SlotNum> <Quantity>` | `GiveSlotItemNum 45 1 1` | Sem jogador específico · ASE · moderado |
| `GiveTekEngramsTo` | Jogador, Modo criativo | O comando GiveTekEngramsTo fornece o item especificado ao jogador especificado. Veja nossa lista completa de códigos GFI. | `GiveTekengramsTo <Playerid> <GFI code>` | `GiveTekEngramsTo 12345678901 ded` | PlayerID · ASE · moderado |
| `GiveToMe` | Criatura, Jogador, Estruturas | O comando GiveToMe fornece a criatura ou estrutura alvo que você está olhando (sob a mira). Não funciona totalmente em criaturas indomadas, então você precisará forçar. | `GiveToMe` | `GiveToMe` | Sem jogador específico · ASE · moderado |
| `GiveWeaponSet` | Jogador | O comando GiveWeaponSet fornece um conjunto de armas dependendo do número do nível e do valor da qualidade fornecidos. Os números de nível são (0 = arco, lança, lança e bola) - (1 = rifle de assalto, espingarda, rifle longneck, espada e granada) - (2 = arco composto, rifle de precisão fabricado, lançador de foguetes, carga C4) - (3 = granada tek, canhão elétrico tek, rifle tek e espada tek). | `cheat GiveWeaponSet <Weapon Set Number> <Quality>` | `GiveWeaponSet 3 70` | Sem jogador específico · ASE · moderado |
| `GMBuff` | Jogador | O comando GMBuff que dá ao jogador God, InfiniteStats, EnemyInvisible true e muito XP. LeaveMeAlone oferece os mesmos buffs, mas sem XP. | `GMBuff` | `GMBuff` | Sem jogador específico · ASE · baixo |
| `GMSummon` | Criatura | O comando GMSummon gera uma criatura domesticada como se tivesse sido domesticada naturalmente (com eficiência máxima de domesticação). Veja nossa lista completa de criaturas para encontrar sua página individual listando todos os comandos de domesticação com construtor de comandos para cada criatura. | `GMSummon <"Creature ID"> <Level>` | `GMSummon "Dodo_Character_BP_C" 150` | Sem jogador específico · ASE · moderado |
| `God` | Jogador, Criatura | O comando de Deus torna o jogador imune a danos (exceto saque). Use o comando de Deus novamente para sair do modo Deus. | `God` | `God` | Sem jogador específico · ASE · baixo |
| `HatchEgg` | Criatura | O comando HatchEgg completa o progresso da incubação do ovo que você está olhando (sob a mira). Observe que o ovo ainda não eclodirá a menos que os requisitos de temperatura sejam atendidos. | `HatchEgg` | `HatchEgg` | Sem jogador específico · ASE · baixo |
| `HideRiders` | Aparência, Criatura, Jogador | O comando HideRiders torna invisível o jogador que está montando uma criatura. O jogador permanece invisível após desmontar. | `HideRiders <Visible True / False>` | `HideRiders` | Sem jogador específico · ASE · baixo |
| `HideTutorial` | Jogador | O comando HideTutorial oculta o tutorial especificado. | `HideTutorial <TutorialIndex>` | `HideTutorial 1` | Sem jogador específico · ASE · baixo |
| `HurtMe` | Jogador | O comando HurtMe causa danos ao jogador na quantia especificada. | `HurtMe <Amount>` | `HurtMe 50` | Sem jogador específico · ASE · baixo |
| `InfiniteStats` | Jogador | O comando InfiniteStats dá ao jogador saúde, oxigênio, resistência, comida e água infinitas. | `InfiniteStats` | `InfiniteStats` | Sem jogador específico · ASE · baixo |
| `InfiniteWeight` | Jogador | O comando InfiniteWeight dá ao jogador peso infinito, embora ainda limitado a 299 slots e 2x o peso máximo normal. | `InfiniteWeight` | `InfiniteWeight` | Sem jogador específico · ASE · baixo |
| `KickPlayer` | Administração do servidor | O comando KickPlayer expulsa o jogador especificado do servidor. | `KickPlayer <Steam ID>` | `KickPlayer 12345678901` | SteamID · ASE · alto |
| `Kill` | Criatura, Jogador, Estruturas | O comando Kill mata instantaneamente qualquer estrutura ou criatura que você esteja olhando (sob a mira). Observe que se usado em uma criatura deixará um cadáver. Como trata de aprox. 10 milhões de danos, pode não matar certos chefes do OP. | `Kill` | `Kill` | Sem jogador específico · ASE · alto |
| `KillAOE` | Administração do servidor, Criatura, Jogador, Estruturas, Mundo e mapa | O comando KillAOE mata instantaneamente estruturas ou dinossauros no raio especificado (padrão 1200). As categorias são: - peões - todos os peões / dinossauros próximos - todos os dinossauros próximos / selvagens - todos os dinossauros selvagens próximos / domesticados - todos os dinossauros / jogadores domesticados próximos - todos os jogadores / estruturas próximas - todas as estruturas próximas. | `KillAOE <category> <Radius>` | `KillAOE wild 1000` | Sem jogador específico · ASE · alto |
| `KillPlayer` | Administração do servidor, Jogador | O comando KillPlayer mata o jogador especificado. Se nenhum ID de jogador for usado, o jogador que você está olhando será morto (sob a mira). | `KillPlayer <PlayerID>` | `KillPlayer 12345678901` | PlayerID · ASE · alto |
| `LeaveMeAlone` | Jogador | O comando LeaveMeAlone é uma combinação dos comandos God, InfiniteStats e EnemyInvisible. | `LeaveMeAlone` | `LeaveMeAlone` | Sem jogador específico · ASE · baixo |
| `LevelUp` | Jogador | O comando LevelUp aumenta o XP do jogador e depois aumenta a estatística especificada na quantidade especificada de níveis. As estatísticas que podem ser usadas são: - Saúde, Vigor, Torpidez, Oxigênio, Comida, Água, Temperatura, Peso, MeleeDamageMultiplier, SpeedMultiplier, TemperatureFortitude, CraftingSpeedMultiplier. | `LevelUp <StatName> <NumLevels>` | `LevelUp Food 6` | Sem jogador específico · ASE · baixo |
| `LevelUpAOE` | Jogador, Mundo e mapa, Criatura | O comando LevelUpAOE aumenta o XP de todas as criaturas e jogadores no raio especificado e, em seguida, aumenta a estatística especificada na quantidade especificada de níveis. As estatísticas que podem ser usadas são: - Saúde, Vigor, Torpidez, Oxigênio, Comida, Água, Temperatura, Peso, MeleeDamageMultiplier, SpeedMultiplier, TemperatureFortitude, CraftingSpeedMultiplier. | `LevelUpAOE <StatName> <Radius> <NumLevels>` | `LevelUpAOE Health 500 10` | Sem jogador específico · ASE · baixo |
| `LevelUpTarget` | Jogador, Criatura | O comando LevelUpTarget aumenta o XP da criatura alvo e do jogador e, em seguida, aumenta a estatística especificada na quantidade especificada de níveis. As estatísticas que podem ser usadas são: - Saúde, Vigor, Torpidez, Oxigênio, Comida, Água, Temperatura, Peso, MeleeDamageMultiplier, SpeedMultiplier, TemperatureFortitude, CraftingSpeedMultiplier. | `LevelUpTarget <StatName> <NumLevels>` | `LevelUpTarget Stamina 2000 5` | Alvo sob a mira · ASE · baixo |
| `ListActiveHordeEvents` | Mundo e mapa | O comando ListActiveHordeEvents lista todas as entregas de suprimentos orbitais e nós de elementos atuais no mapa de extinção. | `ListActiveHordeEvents` | `ListActiveHordeEvents` | Sem jogador específico · ASE · baixo |
| `ListPlayers` | Administração do servidor, Mundo e mapa, Jogador | O comando ListPlayers lista todos os jogadores no mapa atual com seus SteamIDs | `ListPlayers` | `ListPlayers` | Sem jogador específico · ASE · baixo |
| `MakeTribeAdmin` | Administração do servidor, Tribos, Jogador | O comando MakeTribeAdmin torna o jogador Administrador da tribo em que ele está atualmente. | `MakeTribeAdmin` | `MakeTribeAdmin` | Sem jogador específico · ASE · baixo |
| `MakeTribeFounder` | Administração do servidor, Tribos, Jogador | O comando MakeTribeFounder torna o jogador o Fundador/Proprietário da tribo em que está atualmente. | `MakeTribeFounder` | `MakeTribeFounder` | Sem jogador específico · ASE · baixo |
| `MaxAscend` | Jogador | O comando MaxAscend desbloqueia Alpha Rockwell e Alpha Overseer Ascensions para o jogador especificado. Embora os Tekgrams sejam concedidos instantaneamente, o jogador precisará sair e retornar ao mapa para ver as alterações relevantes em seu implante. Se 0 for usado em vez de <PlayerId> o efeito será aplicado ao jogador que executa o comando. | `MaxAscend <PlayerId>` | `MaxAscend 0` | PlayerID · ASE · moderado |
| `MoveTargetTo` | Jogador, Teletransporte | O comando MoveTargetTo teletransportará a criatura ou o jogador para as coordenadas especificadas. | `MoveTargetTo <x> <y> <z>` | `MoveTargetTo -12345 -12346 12345` | Alvo sob a mira · ASE · baixo |
| `OnToggleInGameMenu` | Jogador | O comando OnToggleInGameMenu alterna (abre/fecha) o menu do jogo. | `OnToggleInGameMenu` | `OnToggleInGameMenu` | Sem jogador específico · ASE · baixo |
| `Open` | Administração do servidor | O comando Abrir entra em um servidor específico. | `Open <IP:Port>` | `Open <IP:Port>` | Sem jogador específico · ASE · baixo |
| `OpenMap` | Administração do servidor, Jogador | O comando OpenMap abre o mapa especificado. | `OpenMap <MapName>` | `OpenMap Ragnarok` | Sem jogador específico · ASE · baixo |
| `Playercommand` | Jogador | O comando OpenMap abre o mapa especificado. O comando Playercommand dá ao jogador o efeito de Ascensão da Ascensão especificada. Opções: Ascend1 para Ascensão Gama, Ascend2 para Ascensão Beta ou Ascend3 para Ascensão Alfa. | `Playercommand <CommandName>` | `Playercommand Ascend3` | Sem jogador específico · ASE · baixo |
| `PlayersOnly` | Administração do servidor, Mundo e mapa, Criatura | O comando PlayersOnly interrompe todas as criaturas e criações no jogo. Somente os jogadores poderão se movimentar. Repita o comando para desligar. | `PlayersOnly` | `PlayersOnly` | Sem jogador específico · ASE · baixo |
| `Previewmode` | Cliente | O comando Previewmode altera os gráficos do jogo para o modo de visualização. | `Previewmode` | `Previewmode` | Sem jogador específico · ASE · baixo |
| `PrintActorLocation` | Criatura, Mundo e mapa, Possível erro | O comando PrintActorLocation imprime para consolar a localização do jogador especificado. Não foi possível replicar, pode haver bug. | `PrintActorLocation <PlayerID>` | `PrintActorLocation 12345678901` | PlayerID · ASE · baixo |
| `PrintColors` | Chat, Possível erro | O comando PrintColors imprime uma lista de todos os IDs de cores. Não foi possível replicar, pode estar bugado. Consulte IDs de cores para Dinos para obter uma lista completa de cores. | `PrintColors` | `PrintColors` | Sem jogador específico · ASE · baixo |
| `RainCritters` | Criatura, Jogador | O comando RainCritters gera uma mistura de dodôs e ovelhas no jogo. | `RainCritters <Amount> <Spread Radius> <Height>` | `RainCritters 30 300 200` | Sem jogador específico · ASE · baixo |
| `RainDanger` | Criatura, Jogador | O comando RainDanger gera uma mistura de Rexes e Allos no jogo. | `RainDanger <Amount> <Spread Radius> <Height>` | `RainDanger 30 300 200` | Sem jogador específico · ASE · baixo |
| `RainDinos` | Criatura, Jogador | O comando RainDinos gera uma mistura de Trikes e Parasaurs no jogo. | `RainDinos <Amount> <Spread Radius> <Height>` | `RainDinos 30 300 200` | Sem jogador específico · ASE · baixo |
| `RefillStats` | Jogador | O comando RefillStats irá recarregar todas as estatísticas. As estatísticas serão drenadas normalmente. | `RefillStats` | `RefillStats` | Sem jogador específico · ASE · baixo |
| `RemoveAllWorldBuffs` | Administração do servidor, Mundo e mapa | O comando RemoveAllWorldBuffs remove todos os buffs mundiais na Gen2. | `RemoveAllWorldBuffs` | `RemoveAllWorldBuffs` | Sem jogador específico · ASE · baixo |
| `RemoveTribeAdmin` | Tribos, Jogador | O comando RemoveTribeAdmin remove todos os administradores de tribo da tribo, exceto o jogador em execução. | `RemoveTribeAdmin` | `RemoveTribeAdmin` | Sem jogador específico · ASE · baixo |
| `RenamePlayer` | Jogador | O comando RenamePlayer dá ao jogador especificado o novo nome. Observe que o nome antigo precisa estar entre aspas. | `RenamePlayer <"Player Name"> <New Name>` | `RenamePlayer "OldName" NewName` | Sem jogador específico · ASE · moderado |
| `RenameTribe` | Tribos, Jogador | O comando RenameTribe dá à tribo especificada o novo nome da tribo. Observe que o nome antigo precisa estar entre aspas. | `RenameTribe <"Tribe Name"> <New Name>` | `RenameTribe "OldTribe" NewTribe` | Sem jogador específico · ASE · moderado |
| `RepairArea` | Jogador | O comando RepairArea repara todas as estruturas no raio especificado do jogador. Relatado com bug, não foi possível replicar, mas parece ser útil no reparo de nós de recursos que não aparecem no modo single player. | `RepairArea <Radius>` | `RepairArea 5000` | Sem jogador específico · ASE · baixo |
| `RequestSpectator` | Administração do servidor, Espectador | O comando RequestSpectator ativa o modo espectador se a senha correta for fornecida. A "SpectatorPassword" é definida em GameUserSettings.ini | `RequestSpectator <Password>` | `RequestSpectator GoodPassword` | Sem jogador específico · ASE · baixo |
| `SaveWorld` | Administração do servidor, Mundo e mapa | O comando SaveWorld força um server save. | `SaveWorld` | `SaveWorld` | Sem jogador específico · ASE · baixo |
| `ScriptCommand` | Administração do servidor | O comando ScriptCommand executa um comando/script fornecido por um mod. | `ScriptCommand <CommandString>` | `ScriptCommand startevent` | Sem jogador específico · ASE · baixo |
| `SDF` | Criatura | O comando SDF gera a criatura especificada, selvagem ou domesticada, no nível especificado. Veja nossa lista completa de criaturas para encontrar sua página individual listando todos os comandos de domesticação (incluindo SDF) com construtor de comandos para cada criatura. | `SDF <Creature ID> <Tamed> <Level>` | `SDF` | Sem jogador específico · ASE · baixo |
| `SDFRide` | Criatura | O comando SDFRide permite que você jogue como o dinossauro. Temos uma lista completa de todos os dinossauros onde o SDFRide é possível. Você precisará fazer logoff para retornar ao seu personagem. | `SDFRide <Creature ID> <Level>` | `SDFRide Gigant_Character_BP 150` | Sem jogador específico · ASE · baixo |
| `GiveSkillPoints` | Jogador, Árvore de habilidades | O comando GiveSkillPoints dará ao jogador o número de pontos de habilidade especificados na Skill Tree (ASA Lost Colony DLC). | `GiveSkillPoints <Number of Points To Add>` | `GiveSkillPoints 100` | Sem jogador específico · ASA · alto |
| `ServerChat` | Administração do servidor, Chat | O comando ServerChat envia a mensagem especificada para todos os jogadores atualmente no servidor. | `ServerChat <MessageText>` | `ServerChat "Hello Server"` | Sem jogador específico · ASE · baixo |
| `ServerChatTo` | Administração do servidor, Chat | O comando ServerChatTo enviará uma mensagem de bate-papo para um jogador específico usando seu SteamID. | `ServerChatTo <SteamID> <MessageText>` | `ServerChatTo 12345678901 "Hello Player"` | SteamID · ASE · baixo |
| `ServerChatToPlayer` | Administração do servidor, Chat | O comando ServerChatToPlayer envia uma mensagem de bate-papo para um jogador específico usando seu nome Steam. | `ServerChatToPlayer <PlayerSteamName> <MessageText>` | `ServerChatToPlayer 123 "Hello 123"` | Sem jogador específico · ASE · baixo |
| `SetAdminIcon` | Administração do servidor | O comando SetAdminIcon ativa/desativa o ícone do administrador. | `cheat SetAdminIcon <True / False>` | `SetAdminIcon True` | Sem jogador específico · ASE · moderado |
| `SetBabyAge` | Criatura | O comando SetBabyAge define a idade do bebê (valor entre 0,01 e 1) que você está olhando (sob a mira). | `SetBabyAge <Age>` | `SetBabyAge 0.4` | Sem jogador específico · ASE · moderado |
| `SetCheatPlayer` | Administração do servidor | O comando SetCheatPlayer ativa/desativa a capacidade de usar cheats. | `SetCheatPlayer <True / False>` | `SetCheatPlayer True` | Sem jogador específico · ASE · moderado |
| `SetDay` | Mundo e mapa | O comando SetDay define a contagem de dias do servidor para o número especificado. | `SetDay <Day>` | `SetDay 1` | Sem jogador específico · ASE · moderado |
| `SetDifficultyValue` | Administração do servidor, Mundo e mapa, Criatura | O O comando SetDifficultyValue define o nível máximo que as criaturas irão aparecer no mapa. Use DestroyWildDinos depois de definir a dificuldade para permitir/forçar o surgimento de novas criaturas. | `SetDifficultyValue <Level>` | `SetDifficultyValue 5` | Sem jogador específico · ASE · moderado |
| `SetFacialHairPercent` | Aparência, Jogador | O comando SetFacialHairPercent define o comprimento percentual dos pelos faciais dos jogadores (use 0-1, que se traduz em 0%-100%) | `SetFacialHairPercent <PercentageLength>` | `SetFacialHairPercent 0.5` | Sem jogador específico · ASE · moderado |
| `SetFacialHairStyle` | Aparência, Jogador | O comando SetFacialHairStyle altera o estilo dos pelos faciais do jogador. (Use 0-Padrão. 1-Bigode. 2-Cavanhaque. 3-Romântico. 4-Dread Beard. 5-Costeletas de carneiro. 6-Barba encaracolada. 7-Barba Viking) | `SetFacialHairStyle <HairIDNumber>` | `SetFacialHairStyle 2` | Sem jogador específico · ASE · moderado |
| `SetGlobalPause` | Server Admin. Map | O comando SetGlobalPause irá pausar / retomar o servidor. | `SetGlobalPause <True/False>` | `SetGlobalPause True` | Sem jogador específico · ASE · alto |
| `SetGodMode` | Jogador | O comando SetGodMode ativa/desativa o modo Deus. | `SetGodMode <True/False>` | `SetGodMode True` | Sem jogador específico · ASE · moderado |
| `SetGraphicsQuality` | Cliente | O SetGraphicsQuality O comando define a qualidade dos gráficos, embora seja muito mais fácil usar o menu do jogo (0 Baixo. 1 Médio. 2 Alto. 3 Épico) | `SetGraphicsQuality <Quality>` | `SetGraphicsQuality 3` | Sem jogador específico · ASE · moderado |
| `SetHeadHairPercent` | Aparência, Jogador | O comando SetHeadHairPercent define o comprimento percentual do cabelo da cabeça do jogador (use 0-1 que se traduz em 0% -100%) | `SetHeadHairPercent <PercentageLength>` | `SetHeadHairPercent 0.5` | Sem jogador específico · ASE · moderado |
| `SetHeadHairStyle` | Aparência, Jogador | O comando SetHeadHairStyle altera o estilo de cabelo da cabeça do jogador. (Use 0-Padrão. 1-Moicano. 2-Afro. 3-Romântico. 4-Dreadlocks. 5-Rabo de cavalo. 6-Tranças. 7-Viking) | `SetHeadHairStyle <HairIDNumber>` | `SetHeadHairStyle 1` | Sem jogador específico · ASE · moderado |
| `SetImprintedPlayer` | Criatura, Jogador | O comando SetImprintedPlayer altera a impressora da criatura que você está olhando (sob a mira). | `SetImprintedPlayer <NewImprinterName> <PlayerID>` | `SetImprintedPlayer Bob 12345678901` | PlayerID · ASE · moderado |
| `SetImprintQuality` | Criatura | O comando SetImprintQuality define o valor de impressão da criatura que você está olhando (sob a mira). mira). Use 0-1, onde 1 = 100%. | `SetImprintQuality <ImprintValuePercentage>` | `SetImprintQuality 1` | Sem jogador específico · ASE · moderado |
| `SetMessageOfTheDay` | Administração do servidor | O comando SetMessageOfTheDay define a Mensagem do Dia que será vista por todos os jogadores que ingressarem naquele servidor. | `SetMessageOfTheDay <Message>` | `SetMessageOfTheDay Hello` | Sem jogador específico · ASE · moderado |
| `SetMyTargetSleeping` | Criatura, Jogador | O comando SetMyTargetSleeping coloca a criatura ou jogador na sua frente (sob a mira) para dormir. Usar True ou 1 os coloca para dormir, usar False ou 0 os acorda. | `SetMyTargetSleeping <True / False>` | `SetMyTargetSleeping True` | Alvo sob a mira · ASE · moderado |
| `SetPlayerPos` | Jogador, Teletransporte | O comando SetPlayerPos teletransporta o jogador para o local especificado. | `SetPlayerPos <x> <y> <z>` | `SetPlayerPos -12345 -12346 12345` | Sem jogador específico · ASE · moderado |
| `SetShowAllPlayers` | Administração do servidor, Espectador | O comando SetShowAllPlayers exibe todos os nomes do jogador quando no modo espectador. (atalho SAP) | `SetShowAllPlayers <True / False>` | `SetShowAllPlayers True` | Sem jogador específico · ASE · moderado |
| `SetStatOnTarget` | Criatura, Jogador, Estruturas | O comando SetStatOnTarget altera o Stat especificado para o valor especificado para tudo o que você está olhando (jogador, criatura ou estrutura). Os valores estatísticos possíveis são Saúde, Vigor, Torpidez, Oxigênio, Comida, Peso, Velocidade. | `SetStatOnTarget <Stat> <Value>` | `SetStatOnTarget Health 100` | Alvo sob a mira · ASE · moderado |
| `SetTamingEffectivenessModifier` | Criatura | O comando SetTamingEffectivenessModifier altera a eficácia de domesticação da criatura que você está olhando (sob a mira). Use 0-1, onde 1 = 100%. | `SetTamingEffectivenessModifier <TameEffectiveness>` | `SetTamingEffectivenessModifier 1` | Sem jogador específico · ASE · moderado |
| `SetTargetDinoColor` | Aparência, Criatura | O comando SetTargetDinoColor altera a cor da região especificada do dinossauro que você está olhando (sob a mira). Veja a lista completa de IDs de cores para dinossauros. | `SetTargetDinoColor <ColorRegion> <ColorID>` | `SetTargetDinoColor 2 95` | Alvo sob a mira · ASE · moderado |
| `SetTargetPlayerBodyVal` | Aparência, Jogador | O comando SetTargetPlayerBodyVal redimensiona a parte do corpo especificada para o tamanho especificado. Use um valor entre -1,0 e 1,0, onde 0 é o padrão. Renasça para ver o efeito. Não testado. | `SetTargetPlayerBodyVal <BodyRegion> <BodyVal>` | `SetTargetPlayerBodyVal 1 0.5` | Alvo sob a mira · ASE · moderado |
| `SetTargetPlayerColorVal` | Aparência, Jogador | O comando SetTargetPlayerColorVal altera a cor da parte específica do corpo. (0: corpo, 1: cabelo, 2: olhos). Este comando não usa IDs de cores, mas é semelhante à tela de criação de personagem (0 é amarelo, 0,4 é verde-azulado, 0,5 é verde, 0,7 é laranja, 0,8 é vermelho). Renasça para ver o efeito. Não testado. | `SetTargetPlayerColorVal <BodyPart> <ColorVal>` | `SetTargetPlayerColorVal` | Alvo sob a mira · ASE · moderado |
| `SetTimeOfDay` | Mundo e mapa, Administração do servidor | O comando SetTimeOfDay configura a hora do servidor em horas, minutos e segundos. | `SetTimeOfDay <Hour:Minute[:Second]>` | `SetTimeOfDay 11:30:00` | Sem jogador específico · ASE · moderado |
| `ShowDebug` | Cliente | O comando ShowDebug habilita uma tela especial de depuração. Use Redefinir - Redefine tudo de volta ao normal. Física - localização, velocidade e gravidade. Câmera - câmera (posição, FOV, ângulo, etc.). Ossos - Use a visão de 3ª pessoa para ver a malha esquelética. Animação - animação. Entrada - Todas as teclas de entrada são mostradas com sua ação ao pressioná-las, mouse, entrada do joystick. Colisão - Dados de colisão. Net - Remoterole e NetNode. Arma - Nenhuma informação especial é fornecida atualmente. AI - Nenhuma informação especial é fornecida atualmente | `ShowDebug <Debug Type>` | `ShowDebug Physics` | Sem jogador específico · ASE · baixo |
| `ShowInGameMenu` | Cliente, Jogador | O comando ShowInGameMenu mostra o menu do jogo. | `ShowInGameMenu` | `ShowInGameMenu` | Sem jogador específico · ASE · baixo |
| `ShowMessageOfTheDay` | Chat, Administração do servidor | O comando ShowMessageOfTheDay exibe a Mensagem do Dia. (Definido por SetMessageOfTheDay). | `ShowMessageOfTheDay` | `ShowMessageOfTheDay` | Sem jogador específico · ASE · baixo |
| `ShowMyAdminManager` | Administração do servidor | O comando ShowMyAdminManager exibe o Admin Manager do jogo. | `ShowMyAdminManager` | `ShowMyAdminManager` | Sem jogador específico · ASE · baixo |
| `ShowTutorial` | Jogador | O comando ShowTutorial mostra um tutorial mesmo que o jogador já o tenha visto. | `ShowTutorial <Tutorial ID> <Force Display>` | `ShowTutorial 1 True` | Sem jogador específico · ASE · baixo |
| `Slomo` | Administração do servidor | O comando Slomo acelera ou desacelera o jogo. O padrão é 1. | `Slomo <SpeedMultiplier>` | `Slomo 50` | Sem jogador específico · ASE · baixo |
| `SpawnActor` | Criatura | O comando SpawnActor gera um dinossauro selvagem conforme especificado a uma distância específica do jogador. Veja a página de truques de cada criatura para usar o construtor de comandos. Veja nossa lista completa de criaturas para encontrar sua página individual. | `SpawnActor <Blueprint> <SpawnDistance> <Y Offset> <Z Offset>` | `SpawnActor "Blueprint'/Game/PrimalEarth/Dinos/Allosaurus/Allo_Character_BP.Allo_Character_BP'" 500 0 0` | Sem jogador específico · ASE · moderado |
| `SpawnActorSpread` | Criatura | O comando SpawnActorSpread gera o número especificado de dinossauros, na distância e distribuição especificadas. | `SpawnActorSpread <BlueprintPath> <SpawnDistance> <YOffset> <ZOffset> <NumberActors> <SpreadAmount>` | `SpawnActorSpread "Blueprint'/Game/PrimalEarth/Dinos/Allosaurus/Allo_Character_BP.Allo_Character_BP'" 500 0 0 10 10` | Sem jogador específico · ASE · moderado |
| `SpawnDino` | Criatura | O comando SpawnDino irá gerar uma criatura selvagem na distância e no nível especificados. Veja a página de truques de cada criatura para usar o construtor de comandos. Veja nossa lista completa de criaturas para encontrar sua página individual. | `SpawnDino <Blueprint> <Spawn Distance> <Y Offset> <Z Offset> <Level>` | `SpawnDino "Blueprint'/Game/PrimalEarth/Dinos/Allosaurus/Allo_Character_BP.Allo_Character_BP'" 500 0 0 150` | Sem jogador específico · ASE · moderado |
| `SpawnExactDino` | Criatura | O comando SpawnExactDino gera uma criatura com valores especificados exaustivos. Construtor de comandos para este comando em breve. | `SpawnExactDino <Blueprint> <Saddle Blueprint> <Saddle Quality> <Base Level> <Extra Levels> <Base Stats> <Added Stats> <Name> <Cloned> <Neutered> <Tamed Date> <Uploaded From> <Imprinter Name> <Imprinter ID> <Imprint Quality> <0> <Region Colors> <Creature ID> <Experience> <Spawn Distance> <Spawn Y> <Spawn Z>` | `SpawnExactDino <Blueprint> <Saddle Blueprint> <Saddle Quality> <Base Level> <Extra Levels> <Base Stats> <Added Stats> <Name> <Cloned> <Neutered> <Tamed Date> <Uploaded From> <Imprinter Name> <Imprinter ID> <Imprint Quality> <0> <Region Colors> <Creature ID> <Experience> <Spawn Distance> <Spawn Y> <Spawn Z>` | Sem jogador específico · ASE · moderado |
| `SpawnSetupDino` | Criatura | O comando SpawnSetupDino gera um dinossauro com os valores especificados. Construtor de comandos para este comando em breve. | `SpawnSetupDino <Blueprint Path> <Blueprint Path (Saddle)> <Saddle Quality> <Level> <Stats> <Spawn Distance> <Y Offset> <Z Offset>` | `SpawnSetupDino <Blueprint Path> <Blueprint Path (Saddle)> <Saddle Quality> <Level> <Stats> <Spawn Distance> <Y Offset> <Z Offset>` | Sem jogador específico · ASE · moderado |
| `SPI` | Jogador, Teletransporte | O comando SPI teletransporta o jogador para o local especificado. | `SPI <x> <y> <z> <yaw> <pitch>` | `SPI -12345 -12346 12345 5 5` | Sem jogador específico · ASE · baixo |
| `StartNearestHorde` | Jogador, Mundo e mapa | O comando StartNearestHorde inicia o drop orbital ou nó de elemento mais próximo na dificuldade especificada (valor de dificuldade entre 0-4). Apenas extinção. Use a caixa para queda orbital. Elemento para nó de elemento. Pode haver um atraso na desova. | `StartNearestHorde <Crate / Element> <Difficulty>` | `StartNearestHorde Crate 4` | Sem jogador específico · ASE · baixo |
| `Stat` | Cliente | O comando Stat exibe a estatística especificada. (FPS, Níveis, Unidade e Gráfico de Unidade). | `Stat <Command>` | `Stat FPS` | Sem jogador específico · ASE · baixo |
| `StopSpectating` | Administração do servidor, Espectador | O comando StopSpectating desativa o modo Espectador para esse jogador. | `StopSpectating` | `StopSpectating` | Sem jogador específico · ASE · baixo |
| `Suicide` | Jogador | O comando Suicide mata o jogador. Não console. | `Suicide` | `Suicide` | Sem jogador específico · ASE · baixo |
| `Summon` | Criatura | O comando Summon gera um dinossauro selvagem em nível aleatório. lista completa de IDs de criaturas | `Summon <Creature ID>` | `Summon Rex_Character_BP_C` | Sem jogador específico · ASE · moderado |
| `SummonTamed` | Criatura | O comando SummonTamed gera um dinossauro domesticado em nível aleatório. lista completa de IDs de criaturas | `SummonTamed <Creature ID>` | `SummonTamed Rex_Character_BP_C` | Sem jogador específico · ASE · moderado |
| `TakeAllDino` | Administração do servidor, Criatura, Jogador, Tribos | O comando TakeAllDino assume a propriedade de cada dinossauro na tribo do jogador, dinossauro ou estrutura da tribo que você está olhando (sob a mira). | `TakeAllDino` | `TakeAllDino` | Sem jogador específico · ASE · baixo |
| `TakeAllStructure` | Administração do servidor, Estruturas, Jogador, Tribos | O comando TakeAllStructure assume a propriedade de cada estrutura na tribo do jogador, dinossauro ou estrutura da tribo que você está olhando (sob a mira). | `TakeAllStructure` | `TakeAllStructure` | Sem jogador específico · ASE · baixo |
| `TakeTribe` | Administração do servidor, Estruturas, Jogador, Criatura, Tribos | O comando TakeTribe assume a propriedade de toda a tribo especificada. Se nenhum ID e 0 for usado, então a tribo que você está olhando será levada (sob a mira). | `TakeTribe <TribeID>` | `TakeTribe 0` | Sem jogador específico · ASE · moderado |
| `Teleport` | Jogador, Teletransporte | O comando Teleporte move o jogador para frente até a colisão. Se não houver colisão ou no console ele teletransporta o jogador para 0,0 | `Teleport` | `Teleport` | Sem jogador específico · ASE · moderado |
| `TeleportPlayerIDToMe` | Administração do servidor, Jogador, Teletransporte | O comando TeleportPlayerIDToMe teletransporta o jogador especificado para o jogador em execução. Jogador identificado por PlayerID. | `TeleportPlayerIDToMe <PlayerID>` | `TeleportPlayerIDToMe 12345678901` | PlayerID · ASE · moderado |
| `TeleportPlayerNameToMe` | Administração do servidor, Jogador, Teletransporte | O comando TeleportPlayerNameToMe teletransporta o jogador especificado para o jogador em execução. Jogador identificado pelo nome no jogo. | `TeleportPlayerNameToMe <PlayerName>` | `TeleportPlayerNameToMe Bob` | Sem jogador específico · ASE · moderado |
| `TeleportToActiveHorde` | Jogador, Teletransporte | O comando TeleportToActiveHorde teletransporta o jogador para o evento de horda especificado. Não testado. | `TeleportToActiveHorde` | `TeleportToActiveHorde 3` | Sem jogador específico · ASE · moderado |
| `TeleportToActorLocation` | Criatura, Jogador, Teletransporte | O comando TeleportToActorLocation teletransporta o jogador para o Ator especificado. Não testado. | `TeleportToActorLocation <Type>` | `TeleportToActorLocation Rex_Character_BP_C_12` | Sem jogador específico · ASE · moderado |
| `TeleportToPlayer` | Administração do servidor, Jogador, Teletransporte | O comando TeleportToPlayer teletransporta o jogador para o jogador especificado (use ID do jogador). | `TeleportToPlayer <PlayerID>` | `TeleportToPlayer 12345678901` | PlayerID · ASE · moderado |
| `TeleportToPlayerName` | Administração do servidor, Jogador, Teletransporte | O comando TeleportToPlayerName teletransporta o jogador para o jogador especificado (use o nome do jogo). | `TeleportToPlayerName <PlayerName>` | `TeleportToPlayerName Bob` | Sem jogador específico · ASE · moderado |
| `TestSteamRefreshItems` | Administração do servidor | O comando TestSteamRefreshItems testa se o Steam pode atualizar itens. Não testado. | `TestSteamRefreshItems` | `TestSteamRefreshItems` | Sem jogador específico · ASE · baixo |
| `ToggleDamageNumbers` | Administração do servidor, Mundo e mapa | O comando ToggleDamageNumbers ativa/desativa os números de dano flutuantes no servidor. | `ToggleDamageNumbers` | `ToggleDamageNumbers` | Sem jogador específico · ASE · baixo |
| `ToggleGun` | Aparência | O comando ToggleGun ativa/desativa a visibilidade do item segurado pelo jogador (ou das mãos se nada estiver equipado). | `ToggleGun` | `ToggleGun` | Sem jogador específico · ASE · baixo |
| `ToggleInfiniteAmmo` | Jogador | O comando ToggleInfiniteAmmo ativa/desativa a munição ilimitada. | `ToggleInfiniteAmmo` | `ToggleInfiniteAmmo` | Sem jogador específico · ASE · baixo |
| `TP` | Jogador, Teletransporte | O comando TP teletransporta o jogador para o local especificado. Tipos de códigos de locais conhecidos: - Vermelho, Azul, Verde, Cave1, Cave2, Cave3, Cave4, Cave5, Cave6, Cave7, Cave8, Cave9. | `TP <Location Code>` | `TP Red` | Sem jogador específico · ASE · baixo |
| `TPCoords` | Jogador, Teletransporte | O comando TPCoords teletransporta o jogador para as coordenadas GPS do jogo. | `TPCoords <GPS Latitude> <GPS Longitude> <Altitude>` | `TPCoords 50 50 50` | Sem jogador específico · ASE · baixo |
| `TransferImprints` | Criatura, Jogador | O comando TransferImprints transfere impressões de um jogador especificado para outro jogador especificado. | `TransferImprints <OldPlayerID> <NewPlayerID> <NewImprinterName>` | `TransferImprints 12345678901 98745678901 Bob` | PlayerID · ASE · baixo |
| `TribeDinoAudit` | Administração do servidor, Tribos, Criatura | O comando TribeDinoAudit lista para consolar todos os dinossauros da tribo especificada. (use setcheatplayer 1 e observe a estrutura da tribo para ver o TeamID que é o TribeID) | `TribeDinoAudit <TribeID>` | `TribeDinoAudit 12345678901` | Sem jogador específico · ASE · baixo |
| `TribeMessage` | Administração do servidor, Tribos | O comando TribeMessage adiciona uma mensagem ao Tribelog da tribo especificada. (use setcheatplayer 1 e observe uma estrutura de tribo para ver o TeamID que é o TribeID). | `TribeMessage <TribeId> <Message>` | `TribeMessage 12345678901 Hello` | Sem jogador específico · ASE · baixo |
| `TribeStructureAudit` | Administração do servidor, Tribos, Estruturas | O comando TribeStructureAudit lista para consolar todas as estruturas pertencentes à tribo especificada (use setcheatplayer 1 e observe uma estrutura de tribo para ver o TeamID que é o TribeID) | `TribeStructureAudit <TribeID>` | `TribeStructureAudit 12345678901` | Sem jogador específico · ASE · baixo |
| `UnbanPlayer` | Administração do servidor, Jogador | O comando UnbanPlayer remove o jogador especificado da lista de banidos do servidor. | `UnbanPlayer <SteamID>` | `UnbanPlayer 12345678901` | SteamID · ASE · alto |
| `UnlockEngram` | Jogador | O comando UnlockEngram desbloqueia o engrama especificado. Veja nossa lista completa de itens para encontrar a página individual de cada item, que inclui o caminho do projeto e o comando de desbloqueio completo do engrama (se aplicável) para qualquer item que você precisar. | `UnlockEngram <BlueprintPath>` | `Unlockengram "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponBola.PrimalItem_WeaponBola'"` | Sem jogador específico · ASE · moderado |
| `Walk` | Jogador, Teletransporte, Modo criativo | O comando Walk desativa o comando 'Fly'. Certifique-se de estar perto do chão antes de usar. | `Walk` | `Walk` | Sem jogador específico · ASE · baixo |
| `GiveSkill` | Jogador, Árvore de habilidades | O comando GiveSkill dará ao jogador habilidades específicas específicas. | `GiveSkill <Skill Name> <Number of increments to add>` | `GiveSkill SpectralMount 1 List of all skills available pre Lost Colony DLC:- Tier 3 GiveSkill CurseReflection 1 Copy GiveSkill SpectralMount 1 Copy GiveSkill SpiritRush 1 Copy GiveSkill Telekinesis 1 Copy GiveSkill TwinImprint 1 Copy GiveSkill Tracker 1 Copy Tier 2 GiveSkill BarbedBlades 1 Copy GiveSkill BarbedBlades 2 Copy GiveSkill EssenceEater 1 Copy GiveSkill EssenceEater 2 Copy GiveSkill Imprinter 1 Copy GiveSkill Imprinter 2 Copy GiveSkill MassProduction 1 Copy GiveSkill MassProduction 2 Copy GiveSkill MidasTouch 1 Copy GiveSkill MidasTouch 2 Copy GiveSkill SmokeMagician 1 Copy GiveSkill SmokeMagician 2 Copy Tier 1 GiveSkill ExperiencedKiller 1 Copy GiveSkill ExperiencedKiller 2 Copy GiveSkill ExperiencedKiller 3 Copy GiveSkill Bloodlust 1 Copy GiveSkill Bloodlust 2 Copy GiveSkill Bloodlust 3 Copy GiveSkill BondedTaming 1 Copy GiveSkill BondedTaming 2 Copy GiveSkill BondedTaming 3 Copy GiveSkill HeavyFooted 1 Copy GiveSkill HeavyFooted 2 Copy GiveSkill HeavyFooted 3 Copy GiveSkill HotBlooded 1 Copy GiveSkill HotBlooded 2 Copy GiveSkill HotBlooded 3 Copy GiveSkill MountedOpportunist 1 Copy GiveSkill MountedOpportunist 2 Copy GiveSkill MountedOpportunist 3 Copy GiveSkill Strongback 1 Copy GiveSkill Strongback 2 Copy GiveSkill Strongback 3 Copy GiveSkill WellOiledMachine 1 Copy GiveSkill WellOiledMachine 2 Copy GiveSkill WellOiledMachine 3 Copy` | Sem jogador específico · ASA · alto |
| `GetEgg` | Criatura | O comando GetEgg (ASA) fará com que a criatura à sua frente (sob sua mira) solte um ovo fertilizado com estatísticas idênticas às do pai se a contagem de mutações estiver definida como 0. Aumentar a contagem de mutações adicionará esse número de mutações ao ovo (parece ser aleatório distribuição). | `GetEgg <Number of Mutations>` | `GetEgg 10` | Sem jogador específico · ASA · baixo |

## Inventário do wrapper ArkServerAPI ASE incluído no projeto

A tabela lista funções declaradas no wrapper local `plugin/CustomShop/ArkServerAPI/version/Core/Public/API/ARK/Actor.h` dentro de `UShooterCheatManager`. Ela serve como referência de nomes e assinaturas de API; **não significa que todas sejam comandos `admincheat` registrados no jogo**. O Cheat Manager do servidor continua sendo a fonte para confirmar disponibilidade.

| Função | Assinatura declarada no wrapper |
|---|---|
| `AddEquipmentDurability` | `void AddEquipmentDurability(const float durability)` |
| `AddExperience` | `void AddExperience(float HowMuch, bool fromTribeShare, bool bPreventSharingWithTribe)` |
| `AddExperienceToTarget` | `void AddExperienceToTarget(float HowMuch, bool fromTribeShare, bool bPreventSharingWithTribe)` |
| `AddHexagons` | `void AddHexagons(float HowMuch)` |
| `AddItemToAllClustersInventory` | `void AddItemToAllClustersInventory(FString UserId, int MasterIndexNum)` |
| `AllowPlayerToJoinNoCheck` | `void AllowPlayerToJoinNoCheck(FString* SteamId)` |
| `BanPlayer` | `void BanPlayer(FString PlayerSteamName)` |
| `Broadcast` | `void Broadcast(FString* MessageText)` |
| `CamZoomIn` | `void CamZoomIn()` |
| `CamZoomOut` | `void CamZoomOut()` |
| `ClearCryoSickness` | `void ClearCryoSickness()` |
| `ClearMyBuffs` | `void ClearMyBuffs()` |
| `ClearPlayerInventory` | `void ClearPlayerInventory(int playerID, bool bClearInventory, bool bClearSlotItems, bool bClearEquippedItems)` |
| `ClearTutorials` | `void ClearTutorials()` |
| `CompleteMission` | `void CompleteMission()` |
| `DeactivateMission` | `void DeactivateMission()` |
| `DebugAllowVRMissionTeleport` | `void DebugAllowVRMissionTeleport()` |
| `DebugCompanionAsyncLoadedFiles` | `void DebugCompanionAsyncLoadedFiles()` |
| `DebugCompanionReactions` | `void DebugCompanionReactions()` |
| `DebugMyTarget` | `void DebugMyTarget()` |
| `DebugMyTargetFromLocation` | `void DebugMyTargetFromLocation(FVector* spectatorLocation, FRotator* rotator)` |
| `DebugMyTargetPrint` | `void DebugMyTargetPrint(AActor* actor)` |
| `DeepPockets` | `void DeepPockets()` |
| `DefeatAllBosses` | `void DefeatAllBosses(int playerID)` |
| `DefeatBoss` | `void DefeatBoss(int playerID, FName bossName, char difficulty)` |
| `DestroyActors` | `void DestroyActors(FString* ClassName)` |
| `DestroyAllEnemies` | `void DestroyAllEnemies()` |
| `DestroyAllTames` | `void DestroyAllTames()` |
| `DestroyFoliage` | `void DestroyFoliage(float Radius)` |
| `DestroyMyTarget` | `void DestroyMyTarget()` |
| `DestroyStructures` | `void DestroyStructures()` |
| `DestroyTribeDinos` | `void DestroyTribeDinos()` |
| `DestroyTribeId` | `void DestroyTribeId(int TribeTeamID)` |
| `DestroyTribeIdDinos` | `void DestroyTribeIdDinos(int TribeTeamID)` |
| `DestroyTribeIdPlayers` | `void DestroyTribeIdPlayers(int TribeTeamID)` |
| `DestroyTribeIdStructures` | `void DestroyTribeIdStructures(int TribeTeamID)` |
| `DestroyTribePlayers` | `void DestroyTribePlayers()` |
| `DestroyTribeStructures` | `void DestroyTribeStructures()` |
| `DestroyTribeStructuresLessThan` | `void DestroyTribeStructuresLessThan(int TribeTeamID, int Connections, bool includeContainers)` |
| `DestroyWildDinoClasses` | `void DestroyWildDinoClasses(FString* ClassName)` |
| `DestroyWildDinos` | `void DestroyWildDinos()` |
| `DetachChar` | `void DetachChar()` |
| `Dino` | `void Dino(FName CheatName)` |
| `DinoSet` | `void DinoSet(FName CheatName, float Value)` |
| `DisableSpectator` | `void DisableSpectator()` |
| `DisallowPlayerToJoinNoCheck` | `void DisallowPlayerToJoinNoCheck(FString* SteamId)` |
| `DoExit` | `void DoExit()` |
| `DoHang` | `void DoHang()` |
| `DoRestartLevel` | `void DoRestartLevel()` |
| `DoSummon` | `AActor* DoSummon(FString* ClassName)` |
| `DoTame` | `void DoTame()` |
| `DoTestingThing` | `void DoTestingThing()` |
| `DumpAssetProperties` | `void DumpAssetProperties(FString* Asset)` |
| `DumpDinoStats` | `void DumpDinoStats()` |
| `DupeLastItem` | `void DupeLastItem()` |
| `EnableCheats` | `void EnableCheats(FString pass)` |
| `EnableSpectator` | `void EnableSpectator()` |
| `EnemyInVisible` | `void EnemyInVisible(bool Invisible)` |
| `FindPlayerControllerFromPlayerID` | `AShooterPlayerController* FindPlayerControllerFromPlayerID(__int64 PlayerID)` |
| `ForceCheckInMesh` | `void ForceCheckInMesh()` |
| `ForceCompleteActiveMission` | `void ForceCompleteActiveMission(FString* MissionStateSimValues)` |
| `ForceEnableMeshCheckingOnMe` | `void ForceEnableMeshCheckingOnMe(bool bEnableChecking)` |
| `ForceGiveBuff` | `void ForceGiveBuff(FName* BuffBlueprintPath, bool bEnable)` |
| `ForceJoinTribe` | `void ForceJoinTribe()` |
| `ForcePlayerToJoinTargetTribe` | `void ForcePlayerToJoinTargetTribe(__int64 PlayerID)` |
| `ForcePlayerToJoinTribe` | `void ForcePlayerToJoinTribe(__int64 PlayerID, FString TribeName)` |
| `ForcePlayerToJoinTribeId` | `void ForcePlayerToJoinTribeId(__int64 PlayerID, int TribeTeamID)` |
| `ForcePoop` | `void ForcePoop()` |
| `ForceStartMission` | `void ForceStartMission(FName MissionTag)` |
| `ForceTame` | `void ForceTame()` |
| `ForceTameAOE` | `void ForceTameAOE(float Radius)` |
| `ForceTribes` | `void ForceTribes(FString* PlayerName1, FString* PlayerName2, FString* NewTribeName)` |
| `ForceUpdateDynamicConfig` | `void ForceUpdateDynamicConfig()` |
| `FuzzyMissionSearch` | `TArray<TSubclassOf<AMissionType>>* FuzzyMissionSearch(TArray<TSubclassOf<AMissionType>>* result, FString* MissionTag)` |
| `GameCommand` | `void GameCommand(FString* TheCommand)` |
| `GCM` | `void GCM()` |
| `GCMP` | `void GCMP(__int64 PlayerID)` |
| `GCMT` | `void GCMT()` |
| `GetChat` | `void GetChat()` |
| `GetGameLog` | `void GetGameLog()` |
| `GetPlayerIDForSteamID` | `void GetPlayerIDForSteamID(int SteamID)` |
| `GetPrivateStaticClass` | `static UClass* GetPrivateStaticClass(const wchar_t* Package)` |
| `GetSteamIDForPlayerID` | `void GetSteamIDForPlayerID(int PlayerID)` |
| `GetTribeIdPlayerList` | `void GetTribeIdPlayerList(int TribeID)` |
| `GFI` | `void GFI(FName* blueprintPath, int quantityOverride, float qualityOverride, bool bForceBlueprint)` |
| `GiveAllExplorerNotes` | `void GiveAllExplorerNotes()` |
| `GiveAllItemsInSet` | `static void GiveAllItemsInSet(AShooterPlayerController* Controller, TArray<FItemCount>* Items)` |
| `GiveAllStructure` | `void GiveAllStructure()` |
| `GiveArmorSet` | `void GiveArmorSet(FName Tier, FName QualityName)` |
| `GiveCreativeMode` | `void GiveCreativeMode()` |
| `GiveCreativeModeToPlayer` | `void GiveCreativeModeToPlayer(__int64 PlayerID)` |
| `GiveCreativeModeToTarget` | `void GiveCreativeModeToTarget()` |
| `GiveDinoSet` | `void GiveDinoSet(FName Tier, int NumDinos)` |
| `GiveDinoSet` | `void GiveDinoSet()` |
| `GiveEngrams` | `void GiveEngrams()` |
| `GiveEngramsTekOnly` | `void GiveEngramsTekOnly()` |
| `GiveExplorerNote` | `void GiveExplorerNote(int NoteIndex)` |
| `GiveExpToPlayer` | `void GiveExpToPlayer(__int64 PlayerID, float HowMuch, bool fromTribeShare, bool bPreventSharingWithTribe)` |
| `GiveExpToTarget` | `void GiveExpToTarget(float HowMuch, bool fromTribeShare, bool bPreventSharingWithTribe)` |
| `GiveInfiniteStatsToTarget` | `void GiveInfiniteStatsToTarget()` |
| `GiveItem` | `void GiveItem(FString* blueprintPath, int quantityOverride, float qualityOverride, bool bForceBlueprint)` |
| `GiveItemNum` | `void GiveItemNum(int masterIndexNum, int quantityOverride, float qualityOverride, bool bForceBlueprint)` |
| `GiveItemNumToPlayer` | `void GiveItemNumToPlayer(int playerID, int masterIndexNum, int quantityOverride, float qualityOverride, bool bForceBlueprint)` |
| `GiveItemSet` | `void GiveItemSet(FName Tier)` |
| `GiveItemToPlayer` | `void GiveItemToPlayer(int playerID, FString* blueprintPath, int quantityOverride, float qualityOverride, bool bForceBlueprint)` |
| `GiveResources` | `void GiveResources()` |
| `GiveTekEngramsTo` | `void GiveTekEngramsTo(__int64 PlayerID, FName* blueprintPath)` |
| `GiveToMe` | `void GiveToMe()` |
| `GiveToMeAOE` | `void GiveToMeAOE(float Radius)` |
| `GiveWeaponSet` | `void GiveWeaponSet(FName Tier, FName QualityName)` |
| `GlobalObjectCount` | `void GlobalObjectCount()` |
| `GMBuff` | `void GMBuff()` |
| `GMComp` | `void GMComp(int level)` |
| `GMSummon` | `void GMSummon(FString* ClassName, int Level)` |
| `God` | `void God()` |
| `HatchEgg` | `void HatchEgg()` |
| `HibernationReport` | `void HibernationReport(FString* ClassName)` |
| `HideTutorial` | `void HideTutorial(int TutorialInde)` |
| `HiWarp` | `void HiWarp(FString* ClassName, int Index)` |
| `InfiniteStats` | `void InfiniteStats()` |
| `InfiniteWeight` | `void InfiniteWeight()` |
| `IsUndermesh` | `void IsUndermesh(const float debugDrawSeconds)` |
| `JoinTribe` | `void JoinTribe(__int64 PlayerID, int TribeTeamID)` |
| `KickPlayer` | `void KickPlayer(FString PlayerSteamName)` |
| `Kill` | `void Kill()` |
| `KillAOE` | `void KillAOE(FName Category, float Radius)` |
| `KillAOETribe` | `void KillAOETribe(FName Category, float Radius, int TribeID)` |
| `KillPlayer` | `void KillPlayer(__int64 PlayerID)` |
| `LeaveMeAlone` | `void LeaveMeAlone()` |
| `LeaveMission` | `void LeaveMission()` |
| `LessThan` | `void LessThan(int TribeTeamID, int Connections, bool includeContainers)` |
| `LevelUp` | `void LevelUp(FName statName, int numLevels)` |
| `LevelUpAOE` | `void LevelUpAOE(FName statName, float Radius, int numLevels)` |
| `LevelUpInternal` | `void LevelUpInternal(APrimalCharacter* character, FName statName, int numLevels)` |
| `LevelUpTarget` | `void LevelUpTarget(FName StatName, int NumLevels)` |
| `ListActiveHordeEvents` | `void ListActiveHordeEvents()` |
| `ListBuffs` | `FString* ListBuffs(FString* result, APrimalCharacter* target)` |
| `ListMyBuffs` | `void ListMyBuffs()` |
| `ListMyTargetBuffs` | `void ListMyTargetBuffs()` |
| `ListPlayers` | `void ListPlayers()` |
| `LvlUp` | `void LvlUp(__int64 PlayerID, __int16 Level)` |
| `MakeTribeAdmin` | `void MakeTribeAdmin()` |
| `MakeTribeFounder` | `void MakeTribeFounder()` |
| `MaxAscend` | `void MaxAscend(int playerID)` |
| `Mission` | `void Mission(FName CheatName, float Value)` |
| `MoveTargetTo` | `void MoveTargetTo(float x, float y, float z)` |
| `OnToggleInGameMenu` | `void OnToggleInGameMenu()` |
| `OpenMap` | `void OpenMap(FString* MapName)` |
| `PlayerCommand` | `void PlayerCommand(FString* TheCommand)` |
| `PrintActorLocation` | `void PrintActorLocation(FString* ActorName)` |
| `PrintMessageOut` | `void PrintMessageOut(FString* Msg)` |
| `psc` | `void psc(FString* command)` |
| `QualityNameToFloat` | `static float QualityNameToFloat(FName QualityName)` |
| `RainCritters` | `void RainCritters(int NumberActors, float SpreadAmount, float ZOffset)` |
| `RainDanger` | `void RainDanger(int NumberActors, float SpreadAmount, float ZOffset)` |
| `RainDinos` | `void RainDinos(int NumberActors, float SpreadAmount, float ZOffset)` |
| `RainDinosHelper` | `void RainDinosHelper(TArray<FString>* dinoRefs, int NumberActors, float SpreadAmount, float ZOffset)` |
| `ReassertColorization` | `void ReassertColorization()` |
| `RefillStats` | `void RefillStats()` |
| `RegrowFoliage` | `void RegrowFoliage(float Radius)` |
| `RemoveTribeAdmin` | `void RemoveTribeAdmin()` |
| `RenamePlayer` | `void RenamePlayer(FString* PlayerName, FString* NewName)` |
| `RenamePlayerId` | `void RenamePlayerId(int PlayerID, FString* NewName)` |
| `RenameTribe` | `void RenameTribe(FString* TribeName, FString* NewName)` |
| `RenameTribeID` | `void RenameTribeID(int TribeID, FString* NewName)` |
| `ReportLeastSpawnManagers` | `void ReportLeastSpawnManagers()` |
| `ReportSpawnManagers` | `void ReportSpawnManagers()` |
| `ResetLiveTuningOverloads` | `void ResetLiveTuningOverloads()` |
| `SAP` | `void SAP()` |
| `SaveWorld` | `void SaveWorld()` |
| `SaveWorldDisableTransfer` | `void SaveWorldDisableTransfer()` |
| `ScriptCommand` | `void ScriptCommand(FString* commandString)` |
| `SDF` | `void SDF(FName* DinoBlueprintPath, bool bIsTamed)` |
| `SendDataDogMetric` | `void SendDataDogMetric(FString msg)` |
| `ServerChat` | `void ServerChat(FString* MessageText)` |
| `ServerChatTo` | `void ServerChatTo(FString* SteamID, FString* MessageText)` |
| `ServerChatToPlayer` | `void ServerChatToPlayer(FString* PlayerName, FString* MessageText)` |
| `SetActiveMissionDebugFlags` | `void SetActiveMissionDebugFlags(int DebugFlags)` |
| `SetBabyAge` | `void SetBabyAge(float AgeValue)` |
| `SetChatLogMaxAgeInDays` | `void SetChatLogMaxAgeInDays(int NumDays)` |
| `SetCreativeModeOnPawn` | `bool SetCreativeModeOnPawn(AShooterCharacter* Pawn, bool bCreativeMode)` |
| `SetDebugMeleeAttacks` | `void SetDebugMeleeAttacks(bool bDebugMelee, const float drawDuration)` |
| `SetDifficultyValue` | `void SetDifficultyValue(float Value)` |
| `SetFacialHairPercent` | `void SetFacialHairPercent(float thePercent)` |
| `SetFacialHairstyle` | `void SetFacialHairstyle(int hairStyleIndex)` |
| `SetGlobalPause` | `void SetGlobalPause(bool bIsPaused)` |
| `SetGodMode` | `void SetGodMode(bool bEnable)` |
| `SetGraphicsQuality` | `void SetGraphicsQuality(int val)` |
| `SetHeadHairPercent` | `void SetHeadHairPercent(float thePercent)` |
| `SetHeadHairstyle` | `void SetHeadHairstyle(int hairStyleIndex)` |
| `SetImprintedPlayer` | `void SetImprintedPlayer(FString NewImprinterName, int NewImprinterPlayerDataID)` |
| `SetImprintQuality` | `void SetImprintQuality(float ImprintQuality)` |
| `SetInfiniteStats` | `void SetInfiniteStats(bool bInfinite)` |
| `SetInstantHarvest` | `void SetInstantHarvest(bool bEnable)` |
| `SetMessageOfTheDay` | `void SetMessageOfTheDay(FString* Message)` |
| `SetMyTargetSleeping` | `void SetMyTargetSleeping(bool bIsSleeping)` |
| `SetNetworkTime` | `void SetNetworkTime(float NewTime)` |
| `SetPlayerLevel` | `void SetPlayerLevel(__int64 PlayerID, __int16 Level)` |
| `SetPlayerPos` | `void SetPlayerPos(float X, float Y, float Z)` |
| `SetShowAllPlayers` | `void SetShowAllPlayers(bool bEnable)` |
| `SetStatOnTarget` | `void SetStatOnTarget(FName StatName, float value)` |
| `SetTamingEffectivenessModifier` | `void SetTamingEffectivenessModifier(float TamingEffectiveness)` |
| `SetTargetDinoColor` | `void SetTargetDinoColor(int ColorRegion, int ColorID)` |
| `SetTargetPlayerBodyVal` | `void SetTargetPlayerBodyVal(int BodyValIndex, float BodyVal)` |
| `SetTargetPlayerColorVal` | `void SetTargetPlayerColorVal(int ColorValIndex, float ColorVal)` |
| `SetTimeOfDay` | `void SetTimeOfDay(FString* timeString)` |
| `ShowActiveMissions` | `void ShowActiveMissions()` |
| `ShowInGameMenu` | `void ShowInGameMenu()` |
| `ShowMessageOfTheDay` | `void ShowMessageOfTheDay()` |
| `ShowTutorial` | `void ShowTutorial(int TutorialIndex, bool bForceDisplay)` |
| `SpawnActor` | `void SpawnActor(FString* blueprintPath, float spawnDistance, float spawnYOffset, float ZOffset)` |
| `SpawnActorSpread` | `void SpawnActorSpread(FString* blueprintPath, float spawnDistance, float spawnYOffset, float ZOffset, int NumberActors, float SpreadAmount)` |
| `SpawnActorSpreadTamed` | `void SpawnActorSpreadTamed(FString* blueprintPath, float spawnDistance, float spawnYOffset, float ZOffset, int NumberActors, float SpreadAmount)` |
| `SpawnActorTamed` | `void SpawnActorTamed(FString* blueprintPath, float spawnDistance, float spawnYOffset, float ZOffset)` |
| `SpawnDino` | `void SpawnDino(FString* blueprintPath, float spawnDistance, float spawnYOffset, float ZOffset, int DinoLevel)` |
| `SpawnExactDino` | `void SpawnExactDino(FString* DinoBlueprintPath, FString* SaddleBlueprintPath, float SaddleQuality, int BaseLevel, int ExtraLevels, FString* BaseStats, FString* AddedStats, FString* DinoName, char Cloned, char Neutered, FString* TamedOn, FString* UploadedFrom, FString* ImprinterName, int ImprinterPlayerID, float ImprintQuality, FString* Colors, __int64 DinoID, __int64 Exp, float SpawnDistance, float YOffset, float ZOffset)` |
| `SpawnSetupDino` | `void SpawnSetupDino(FString* DinoBlueprintPath, FString* SaddleBlueprintPath, float SaddleQuality, int DinoLevel, FString* DinoStats, float SpawnDistance, float YOffset, float ZOffset)` |
| `SpawnSetupDinoInternal` | `APrimalDinoCharacter* SpawnSetupDinoInternal(FDinoSetup* DinoSetup, FRotator* SpawnRot)` |
| `SPI` | `void SPI(float X, float Y, float Z, float Yaw, float Pitch)` |
| `StartMission` | `void StartMission(FName MissionTag)` |
| `StartNearestHorde` | `void StartNearestHorde(FName HordeType, int DifficultyLevel)` |
| `StartSaveBackup` | `void StartSaveBackup()` |
| `StaticClass` | `static UClass* StaticClass()` |
| `StaticRegisterNativesUShooterCheatManager` | `static void StaticRegisterNativesUShooterCheatManager()` |
| `Suicide` | `void Suicide()` |
| `Summon` | `void Summon(FString* ClassName)` |
| `SummonTamed` | `void SummonTamed(FString* ClassName)` |
| `TakeAllDino` | `void TakeAllDino()` |
| `TakeAllStructure` | `void TakeAllStructure()` |
| `TakeTribe` | `void TakeTribe(int TribeTeamID)` |
| `TeleportPlayerIDToMe` | `void TeleportPlayerIDToMe(__int64 PlayerID)` |
| `TeleportPlayerNameToMe` | `void TeleportPlayerNameToMe(FString* PlayerName)` |
| `TeleportToActiveHorde` | `void TeleportToActiveHorde(int EventIndex)` |
| `TeleportToActorLocation` | `void TeleportToActorLocation(FString* ActorName)` |
| `TeleportToPlayer` | `void TeleportToPlayer(__int64 PlayerID)` |
| `TeleportToPlayerName` | `void TeleportToPlayerName(FString* PlayerName)` |
| `TestSteamRefreshItems` | `void TestSteamRefreshItems()` |
| `ToggleClawStepping` | `void ToggleClawStepping()` |
| `ToggleDamageLogging` | `void ToggleDamageLogging()` |
| `ToggleDamageNumbers` | `void ToggleDamageNumbers()` |
| `ToggleGun` | `void ToggleGun()` |
| `ToggleHud` | `void ToggleHud()` |
| `ToggleLocation` | `void ToggleLocation()` |
| `ToggleLowGravSpin` | `void ToggleLowGravSpin()` |
| `TP` | `void TP(FString LocationName)` |
| `TPCoords` | `void TPCoords(float lat, float lon, float z)` |
| `TPName` | `void TPName(FString* PlayerName)` |
| `TransferImprints` | `void TransferImprints(int oldPlayerId, int newPlayerId, FString NewImprinterName)` |
| `TribeDinoAudit` | `void TribeDinoAudit(int TribeTeamID)` |
| `TribeMessage` | `void TribeMessage(int TribeTeamID, FString Message)` |
| `TribeStructureAudit` | `void TribeStructureAudit(int TribeTeamID)` |
| `UnbanPlayer` | `void UnbanPlayer(FString PlayerSteamName)` |
| `UnlockEngram` | `void UnlockEngram(FString* ItemClassName)` |
| `VerifyTransferInventory` | `void VerifyTransferInventory()` |
| `VisualizeClass` | `void VisualizeClass(FString* ClassIn, int MaxTotal)` |
| `WhatIsMyTarget` | `void WhatIsMyTarget()` |

Funções no wrapper local: **256** (inclui sobrecargas quando existem).

## Fontes e limites

- [ARK Wiki — comandos de console](https://ark.wiki.gg/wiki/Cheat): comportamento e parâmetros, incluindo MaxAscend.
- [Arked.gg — catálogo de comandos](https://arked.gg/cheat-codes/commands/): índice de nomes, categorias, parâmetros e descrições.
- [Ark Server API ASE — UShooterCheatManager](https://arkserverapi.wiki/ase/struct_u_shooter_cheat_manager.html): referência de API do gerenciador de cheats.
- O catálogo precisa ser revisto após atualização do servidor ou ArkApi. Comandos que possam apagar estruturas, jogadores, dinos, saves ou encerrar o servidor devem ser tratados como destrutivos e não executados sem revisão.
