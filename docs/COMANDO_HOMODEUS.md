# Comando `/homodeus`

O CustomShop registra `/homodeus` no chat do jogo. O comando cobra o personagem que o executou e chama uma vez o método nativo `DefeatAllBosses` do ARK, concedendo os desbloqueios Alpha de todos os chefes disponíveis. Ele não inicia arenas ou cutscenes.

## Preço

O valor é configurável no arquivo `ArkApi/Plugins/CustomShop/config.json`, na seção `Settings`:

```json
"HomodeusCommandPrice": 20000
```

O padrão é 20.000 Âmbares. A cobrança usa o saldo do jogador e é registrada no histórico de transações como `homodeus_alpha_all`.

## Efeitos no personagem

Os engramas Tek correspondentes são liberados imediatamente. Os níveis extras podem só aparecer depois que o jogador renascer ou reconectar; o implante é atualizado após a morte. A concessão é aplicada ao perfil do personagem, mas deve ser validada no servidor de destino após transferência de mapa antes de divulgar o comando como permanente.

## Teste manual no servidor

Para testar o método nativo diretamente como administrador, use o **Player ID** do ARK (não o SteamID):

```text
cheat DefeatAllBosses <PlayerID>
```

O comando do CustomShop destinado ao jogador é `/homodeus`; não exige que o jogador informe ID ou use comandos administrativos.
