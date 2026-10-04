# EngramLevel — Engramas por nível

Plugin ArkApi (sem mod da Workshop). No level up, e ao reaplicar pontos depois do mindwipe, libera **só os engramas daquele nível**. Não tem comando para desbloquear o catálogo inteiro.

O crash do ASE 361.7 acontece dentro de `UPrimalCharacterStatusComponent::ServerApplyLevelUp` quando `bAutoUnlockAllEngrams` está ligado: a engine tenta aprender todos os engramas naquele único apply (típico depois do mindwipe). O ArkApi não apaga esse código da engine. Com o plugin ligado (`Enabled` e `SuppressAutoUnlockDuringLevelUp`, os dois default true), a flag fica **false** o tempo todo. Não volta a true no fim do `ServerApplyLevelUp` — repor aí rearmava o crash no level up seguinte em que o hook não corresse. No unload, ou quando `Enabled` passa a false, o plugin repõe o valor que leu no load. O mesmo se a supressão passar a false.

Um `OverridePlayerLevelEngramPoints` de **999** (ou maior) compra o catálogo num único nível. Essas linhas ficam em 0 enquanto o plugin estiver ligado e também não voltam no fim do apply. No unload ou com `Enabled: false`, voltam ao que foi lido no load. Os pontos modestos do `nivel200.txt` (200, 12, 400, 16, 800…) continuam.

Se `GetShooterGameMode()` vier nulo e não der para mascarar a flag, o plugin regista o erro e **não** chama o `ServerApplyLevelUp` original. Também não reativa a flag.

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

`/autoengram` liga o automático daquele SteamID. Usado de novo, desliga. O chat responde «Desbloqueio automático ligado» ou «Desbloqueio automático desligado». Quem nunca usou o comando continua desligado, também depois de relog e de restart.

A lista de quem ligou fica em `ArkApi/Plugins/EngramLevel/autoengram.json` (ao lado do config). A gravação vai para um ficheiro temporário e só depois troca o nome. Se a pasta não existir, o plugin cria. Não usa MySQL. Um JSON inválido no arranque não apaga a lista: fica o último estado bom em memória e o erro vai para o log.

O comando não libera tek por si e não repõe níveis já gastos antes de `/autoengram`. Com o automático ligado:

- `UnlockTotal: false` — só engramas não tek do nível deste clique.
- `UnlockTotal: true` — neste clique, os não tek desse nível. Os tek desse nível só entram num `ServerApplyLevelUp` seguinte, quando esses não tek já foram. Nunca os dois no mesmo lote.

`Enabled: false` desliga o plugin inteiro. O comando não religa e responde «Desbloqueio automático desligado no servidor.»

Exemplo para somar um engrama pelo nome interno (ou pelo nome mostrado, inteiro):

```json
"ExtraEngrams": [
  "EngramEntry_MachinedRifle_C"
]
```

`rifle` sozinho não entra: teria de ser o nome completo, por exemplo `Machined Rifle` se for isso que o jogo mostra.

## Limite

Cada ponto aplicado libera o nível correspondente, não os níveis já gastos antes de `/autoengram`. Se o mindwipe mantém o nível 200 e devolve os pontos, um `ServerApplyLevelUp` que gaste um ponto libera os engramas do nível 2 (o primeiro ponto); o seguinte, os do 3. Se um único apply gastar vários pontos, esses níveis saem em sequência, um de cada vez: só engramas cujo nível exigido é exatamente aquele número. Tek e não tek não vão no mesmo lote. Com `UnlockTotal: true`, o tek daquele nível é o lote seguinte, depois dos não tek. Não há backfill do que já tinha sido gasto antes do comando.

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
