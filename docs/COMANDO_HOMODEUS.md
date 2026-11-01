# Comando `/homodeus`

O CustomShop registra `/homodeus` no chat do jogo. O comando solicita confirmação antes de cobrar e chama uma vez o método nativo `DefeatAllBosses` do ARK, concedendo as ascensões Alpha disponíveis para o personagem. Ele não inicia arenas ou cutscenes.

## Preço

O valor é configurável no arquivo `ArkApi/Plugins/CustomShop/config.json`, na seção `Settings`:

```json
"HomodeusCommandPrice": 20000
```

O padrão é 20.000 Âmbares. A cobrança usa o saldo do jogador e é registrada no histórico de transações como `homodeus_alpha_all`.

Ao usar `/homodeus`, o jogador recebe o custo e o saldo atual. Para aceitar a cobrança e conceder as ascensões, deve digitar `/concordo` em até dois minutos.

## Efeitos no personagem

O comando concede apenas as ascensões Alpha; engramas Tek não são entregues. Os níveis extras podem só aparecer depois que o jogador renascer ou reconectar; o implante é atualizado após a morte. A concessão é aplicada ao perfil do personagem, mas deve ser validada no servidor de destino após transferência de mapa antes de divulgar o comando como permanente.

## Teste manual no servidor

Para testar o método nativo diretamente como administrador, use o **Player ID** do ARK (não o SteamID):

```text
cheat DefeatAllBosses <PlayerID>
```

O comando do CustomShop destinado ao jogador é `/homodeus`; não exige que o jogador informe ID ou use comandos administrativos.
