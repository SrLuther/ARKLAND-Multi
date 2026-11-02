# Integração da Fazenda com a WebStore

## Estado

A WebStore mantém o catálogo administrativo em `data/fazenda_recursos_config.json` e a tela **Minha Área → Fazenda** consulta o estoque por SteamID. O estoque só aparece como disponível quando o plugin o sincronizou nos últimos cinco minutos. A interface reserva a quantidade pedida e informa que a entrega depende de `/fazresgatar` no jogo.

O plugin FazendaRecursos atual ainda não chama estes endpoints: a rota `/fazresgatar` responde que não há pedidos sincronizados. Portanto, até a integração do plugin ser implementada, não haverá estoque recente, a seleção permanecerá desabilitada e nenhuma entrega será prometida.

## Autenticação

As rotas internas exigem `X-API-Key: <ARKSHOP_API_KEY>`. A chave deve ficar somente no processo servidor/plugin; nunca deve ser enviada ao navegador.

## Atualizar estoque

`POST /api/plugin/farm/sync`

```json
{
  "steam_id": "76561198000000000",
  "server_id": "01_alps",
  "plugin_version": "0.1.x",
  "stock": {
    "soul_shard": 19,
    "paragon_shard": 4
  }
}
```

O plugin deve enviar o saldo autoritativo por recurso e jogador. Identificadores precisam corresponder ao `Id` configurado no catálogo da Fazenda. Atualizações devem ocorrer após produção, upload, mudança por comando de resgate e ao iniciar/recarregar o plugin.

## Pedidos selecionados no site

O jogador autenticado chama `POST /api/player/farm/redemptions` com `resource_id` e `amount`. A WebStore exige snapshot com até cinco minutos, verifica disponibilidade descontando pedidos `PENDENTE` e `PROCESSANDO`, e reserva a quantidade ao gravar o pedido. O jogador pode cancelar um pedido ainda `PENDENTE` por `POST /api/player/farm/redemptions/<id>/cancel`. A licença `keyfarm` não bloqueia o download: a licença controla produção/upload, enquanto o resgate permanece permitido após expiração.

O plugin chama `POST /api/plugin/farm/redemptions/claim` quando o jogador usa `/fazresgatar`, enviando `steam_id` e `server_id`. A WebStore reserva os pedidos em processamento para uma instância por até dois minutos, evitando que comandos simultâneos em mapas diferentes entreguem a mesma solicitação. O comando precisa validar novamente o item e a quantidade, entregar ao jogador e chamar `POST /api/plugin/farm/redemptions/<id>/result` com `{"status":"ENTREGUE","server_id":"01_alps"}` ou `{"status":"ERRO","server_id":"01_alps"}`. Em caso de erro a reserva de estoque é liberada; em sucesso o plugin deve sincronizar o estoque atualizado.

## Cuidados para a implementação do plugin

- Não consultar nem entregar pedidos em background: a busca ocorre somente ao executar `/fazresgatar`.
- Validar SteamID do jogador contra o pedido e aceitar somente IDs de recursos habilitados no config carregado.
- Não confiar em quantidade, classe ou nome vindos do navegador; a definição no config do plugin é a autoridade para criar o item.
- Entrega e mudança de status precisam ser idempotentes para que timeout/repetição de HTTP não duplique itens.
- Se a API estiver indisponível, não entregar e não marcar pedido como concluído.
- O snapshot precisa representar o estoque real no servidor. Se a Fazenda for compartilhada entre mapas, a próxima etapa deve definir uma fonte de estoque central única; sobrescrever snapshots independentes por mapa não é seguro.


## FazendaRecursos 0.1.5-test

The plugin sends persisted stock snapshots to this endpoint asynchronously at startup, periodically, after Paragon Soul upload, and after `/fazstatus`. It reads `Settings.WebApiUrl` and `Settings.WebApiKey` from `ArkApi/Plugins/CustomShop/config.json`; the key is never sent to players or logged. Default Omega resource IDs are `omega_paragon_shard`, `omega_soul_shard`, and `omega_chest_shard`.

This build synchronizes stored balances only. Generic item upload, production activation, cloning, and `/fazresgatar` delivery are not implemented. The current API keeps the most recent snapshot per SteamID and does not aggregate independent per-map farm files.
