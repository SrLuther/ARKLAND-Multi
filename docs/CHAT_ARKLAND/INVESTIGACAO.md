# Investigação do Chat Arkland

## Evidências encontradas (26/11/2026)

- O chat anterior próprio está em `plugin/CustomShop/src/ShopCrossChat.cpp`. Seu funcionamento depende do ciclo e da conexão do CustomShop, usa cursor compartilhado por instância e possui rotinas MySQL/HTTP disparadas em callbacks do jogo. `SanitizeAscii` descarta acentos; construir `wstring` byte a byte também não decodifica UTF-8. O desligamento consulta a configuração atual antes de remover callbacks e não mantém identificadores para cancelar timers recorrentes. Estes são riscos demonstráveis no código, não uma prova retrospectiva de todas as falhas relatadas.
- O gerenciador força `cross_chat_enabled=false` em `src/config_manager.py`; `src/shop_integration.py` mantém nomes/IDs históricos. Os antigos módulos web `cross_chat_discord.py` aparecem no histórico Git e não existem no checkout atual. Não serão ressuscitados como dependência.
- No mapa 05 há `KalsCrossChat/config.json` e `DiscordConfig.json`. Foram consultadas somente as chaves e identificadores públicos: guild `1440802112601854159`, canal global `1550610698332012724`, PollRate original 250. Nenhum token, senha ou AccountKey foi copiado. A causa exata do filtro de bots não pode ser afirmada sem o código desse terceiro.
- SDK local: `plugin/CustomShop/ArkServerAPI/version/Core/Public`; biblioteca `out_lib/ArkApi.lib`. São os mesmos headers e biblioteca utilizados nos plugins próprios ASE x64. `ICommands` confirma callbacks de chat, tick e suas remoções. `EChatSendMode` separa GlobalChat, GlobalTribeChat, LocalChat e AllianceChat.
- O timer público aceita intervalos inteiros. O Chat Arkland utilizará tick para despachar ações do jogo e uma thread própria com espera fracionária para PollRate; não simulará segundos decimais passando milissegundos ao SDK.
- O ABI de Permissions foi conferido no header público e nos exports de sua DLL de referência: `GetPlayerGroups(uint64)` retorna `TArray<FString>`; `IsPlayerInGroup` recebe `const FString&`. Não será copiado o binding antigo que presume `const wchar_t*`.
- A implementação de referência em `Permissions/Private/Database/MysqlDB.h` consulta o cache de jogadores/tribos sob mutex em GetPlayerGroups/IsPlayerExists, sem consulta SQL por chamada. O callback do Chat Arkland usa somente essa API pública no jogo; consultas de licenças e de grupos para usuários Discord são executadas no backend. A latência e a equivalência da DLL efetivamente instalada ainda exigem medição no piloto.
- `Commands.cpp` do SDK registra comandos por nome em uma lista e remove por nome, sem associação de dono. A implementação nova trata seus comandos no callback de chat, sem registrar/remover comandos de outros plugins. Os comandos de terceiros são executados pelo SDK antes desse callback; conflitos precisam ser conferidos no piloto. Os callbacks de outros plugins também precisam ser isolados na migração.
- Discord.py local 2.7.1 aceita `nonce` em `channel.send` e expõe `Message.nonce`; não oferece `enforce_nonce` nessa assinatura. O publicador central usa lease, estado de envio e nonce próprio para reconhecer somente o relay original, e não reenvia automaticamente resultados ambíguos. Referência oficial: [Message resource](https://github.com/discord/discord-api-docs/blob/main/developers/resources/message.mdx).

## Integrações reutilizadas

1. Cadastro: `_load_servers`, `arkland_ref` e `server_id` da Web Store. `arkland_ref` (ex.: `tek:<uuid>`) é a chave permanente; nome e `server_id` de exibição podem mudar.
2. Identidade real: SteamID64 já utilizado por `store_users` e `game_players`. Esses campos são chaves textuais; PlayerDataID, sessão e número fixo de sorteio não atendem ao ID público persistente de chat. Será necessário um contador próprio, único por SteamID, sem reutilização nem exclusão rotineira.
3. Monitoramento: `player_monitoring_routes.py`, `game_players` e `game_player_sessions`. A ingestão será extraída para uma função compartilhada; o plugin publicará snapshots do SDK através dela. Não haverá uma segunda tabela independente de presença de jogadores.
4. Licenças: catálogo `_catalog_license_options` e leitura em lote `_get_player_entitlements_batch`; o transporte não será responsável por conceder licenças ou grupos.
5. Permissões: plugin Permissions no jogo; serviço central `src/permission_entitlements_sync.py` para leitura de grupos de usuários Discord vinculados. Sem validação, cargos administrativos não serão inferidos.
6. Vinculação: `support_ticket_discord_links`, sem novo processo de códigos ou cargos.
7. Discord/Lumo: Gateway existente em `lumo_gateway.py`, armazenamento protegido existente do token e canal global já configurado. Não haverá token nos arquivos dos mapas nem bot concorrente por mapa.
8. Autenticação: `admin_required` no painel e autenticação de API existente para instâncias; nenhuma execução administrativa via texto do Discord.
9. Central de Status: `system_status_center.py`, com estado de desenvolvimento e validação em jogo separada dos testes automatizados.

## Decisões de transporte

O banco central é acessado pela Web Store. As instâncias usam a API autenticada em uma thread própria, reutilizando a conexão central existente. Não precisam distribuir uma segunda senha MySQL para cada mapa. O arquivo único separa `Local`, `Shared` e `Runtime`; sincronizar Shared nunca substitui Local.ServerKey ou Local.ApiKey.

Mensagens globais usam UUID, sequência e prazo de validade. Mensagens privadas possuem entregas por destinatário, confirmação e lease, acompanhando o jogador em transferências; nunca entram na fila do Discord. Entrega exatamente uma vez não é prometida entre um processo ARK e a rede: IDs processados são persistidos e tentativas ambíguas são deduplicadas, com expiração e confirmação explícitas.

O primeiro pacote será seguro para observação: as funcionalidades compartilhadas têm os padrões aprovados; a participação de mapas e a saída do modo observacional exigem ativação administrativa. O KalsCrossChat não será removido ou desativado automaticamente. Validação em produção e migração dependem de um piloto isolado, sem dois mecanismos retransmitindo a mesma mensagem.
