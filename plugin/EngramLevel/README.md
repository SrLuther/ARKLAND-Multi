# EngramLevel — Engramas por nível

Plugin ArkApi (sem mod da Workshop). No level up, e ao reaplicar pontos depois do mindwipe, libera **só os engramas daquele nível**. Não tem comando para desbloquear o catálogo inteiro.

O crash do ASE 361.7 acontece dentro de `UPrimalCharacterStatusComponent::ServerApplyLevelUp` quando `bAutoUnlockAllEngrams` está ligado: a engine tenta aprender todos os engramas naquele único apply (típico depois do mindwipe). O ArkApi não apaga esse código da engine. Com o plugin ligado (`Enabled` e `SuppressAutoUnlockDuringLevelUp`, os dois default true), a flag fica **false** o tempo todo. Não volta a true no fim do `ServerApplyLevelUp` — repor aí rearmava o crash no level up seguinte em que o hook não corresse. No unload, ou quando `Enabled` passa a false, o plugin repõe o valor que leu no load. O mesmo se a supressão passar a false.

Um `OverridePlayerLevelEngramPoints` de **999** (ou maior) compra o catálogo num único nível. Essas linhas ficam em 0 enquanto o plugin estiver ligado e também não voltam no fim do apply. No unload ou com `Enabled: false`, voltam ao que foi lido no load. Os pontos modestos do `nivel200.txt` (200, 12, 400, 16, 800…) continuam.

No arranque o ArkApi ainda não tem o GameMode: os plugins carregam no `UEngine::Init`, e o ponteiro global só é gravado no `AShooterGameMode::InitGame`. Isso não é um level-up e o plugin não escreve log. Num `ServerApplyLevelUp` real, se esse getter vier nulo, o modo é lido do mundo do componente (campo, `GetWorld`, dono, outer ou o controller). Se mesmo assim não houver GameMode, o original não corre — chamar com a flag ainda ligada é o crash — e o erro sai uma vez por apply. A flag não é reativada.

## Config (`plugin/EngramLevel/configs/config.json`)

Ficheiro no mapa: `ShooterGame/Binaries/Win64/ArkApi/Plugins/EngramLevel/config.json`. Depois de editar: `EngramLevel.Reload` (ou reiniciar o mapa na janela do admin).

| Chave | Default | Efeito |
|-------|---------|--------|
| `Enabled` | `true` | Liga ou desliga o plugin por completo. `false` restaura `bAutoUnlockAllEngrams` e as linhas >= 999 para o que foi lido no load. A engine volta a poder aprender o catálogo inteiro se a flag estiver ligada. |
| `UnlockNonTek` | `true` | Neste clique, só engramas **não tek** do nível que está a ser aplicado. |
| `UnlockTotal` | `false` | Desbloqueio total, desligado de fábrica. Com `true`, num apply de um ponto os tek daquele nível só entram num `ServerApplyLevelUp` **seguinte**, depois que os não tek desse nível já foram. Se o mesmo apply gastar vários pontos, o tek desse nível é o lote a seguir ao não tek, nunca o mesmo lote. `/autoengram` não liga isto. |
| `Engrams` | `[]` | Nome interno ou nome mostrado, comparação exata sem diferenciar maiúsculas. `rifle` não acerta `Tek Rifle` nem vários itens. Vazio mantém a base: todo engrama que o servidor carregou (vanilla e mods). Preencher substitui essa base pela lista escrita — apagar uma linha tira esse item. |
| `ExtraEngrams` | `[]` | Acrescenta um nome interno ou nome mostrado, exato, sem recompilar. Soma à base (ou à lista de `Engrams`). Não apaga o resto. |
| `RemovedEngrams` | `[]` | Tira um item da base, pelo nome interno ou pelo nome mostrado exato, sem colar o catálogo inteiro. |

`UnlockTotal` desligado é o default seguro: o mindwipe não despeja tek e não tek juntos.

## Comando `/autoengram`

O jogador começa com o automático **desligado**. O plugin não chama `ServerUnlockEngram` para ele até ele pedir.

`/autoengram` liga o automático daquele SteamID. Usado de novo, desliga. O chat responde quantos engramas não tek entraram na fila e até qual nível, ou o motivo se não entrou nenhum. Desligar responde «Desbloqueio automático desligado.» e apaga a fila daquele jogador. Quem nunca usou o comando continua desligado, também depois de relog e de restart.

`/ae` é o reforço manual. Com o automático desligado não solta nada e responde «Desbloqueio automático desligado.» Com ele ligado, faz a mesma releitura e completa a mesma fila.

A lista de quem ligou fica em `ArkApi/Plugins/EngramLevel/autoengram.json` (ao lado do config). A gravação vai para um ficheiro temporário e só depois troca o nome. Se a pasta não existir, o plugin cria. Não usa MySQL. Um JSON inválido no arranque não apaga a lista: fica o último estado bom em memória e o erro vai para o log.

Ao passar de desligado para ligado, o comando relê os engramas não tek cujo nível exigido é menor ou igual ao nível atual e que ainda não estão na lista que a tela mostra (`EngramItemBlueprints`). Não usa `HasEngram`. Não liga `bAutoUnlockAllEngrams` e não aprende o catálogo inteiro. Tek não entra nesse comando.

A lista não sai de uma vez. Entra numa fila do jogador: no máximo 10 engramas por bloco, 1 segundo entre blocos, no timer do ArkApi (o mesmo tipo de agendamento do TimedPoints do CustomShop). O primeiro bloco sai 1 segundo depois. Cada um sai por `ServerUnlockEngram` no `PlayerState`. Se o call não puser a classe na lista da tela, o plugin adiciona e avisa o cliente. Quando a fila acaba, o chat diz quantos foram desbloqueados e até qual nível.

`UnlockTotal: false` deixa o tek de fora desta fila. `UnlockTotal: true` não mete tek no mesmo bloco: a releitura do comando, do `/ae` e do level-up continua só com não tek.

Com o automático ligado, aplicar um nível não solta só o número daquele clique e não corre dentro de `ServerApplyLevelUp`. Espera 1 segundo e faz a mesma releitura (não tek até o nível atual). Antes do primeiro bloco, cada clique empurra esse bloco para daqui a 1 segundo — a espera não passa de 1 segundo. Depois que um bloco já saiu, um nível novo não reinicia a espera: o que faltar entra no fim da fila.

`Enabled: false` desliga o plugin inteiro. O comando não religa e responde «Desbloqueio automático desligado no servidor.»

Exemplo para somar um engrama pelo nome interno (ou pelo nome mostrado, inteiro):

```json
"ExtraEngrams": [
  "EngramEntry_MachinedRifle_C"
]
```

`rifle` sozinho não entra: teria de ser o nome completo, por exemplo `Machined Rifle` se for isso que o jogo mostra.

## Limite

Quem não ligou `/autoengram` não ganha engrama. Os níveis já gastos antes de `/autoengram` ficam para o momento em que o comando liga: a fila pega os não tek até o nível atual. Com o automático ligado, aplicar nível (também o primeiro ponto depois do mindwipe, que corresponde ao nível 2) espera 1 segundo e relê essa mesma faixa, sem precisar desligar e ligar o comando. Tek continua de fora enquanto `UnlockTotal` está false.

## Build

```bat
cd plugin\EngramLevel
build_cl.bat
```

Saída: `bin/EngramLevel.dll`. O SDK é o de `plugin/CustomShop/ArkServerAPI`.

## Instalação (janela do admin, mapa parado)

Não copie a DLL com o mapa no ar.

1. Pare o mapa.
2. Crie `ShooterGame\Binaries\Win64\ArkApi\Plugins\EngramLevel\`
3. Copie `EngramLevel.dll`, `PluginInfo.json` e `config.json` de `plugin/EngramLevel/bin/`.
4. Suba o mapa.

Console/RCON: `EngramLevel.Reload` depois de editar o config.

`bAutoUnlockAllEngrams` pode continuar no Game.ini. Com este plugin carregado, essa flag não dispara o pacote que derruba o servidor.
