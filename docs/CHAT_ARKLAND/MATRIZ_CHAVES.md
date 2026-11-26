# Correspondência das configurações originais

Classificações: **mantida** preserva a função; **reorganizada** muda o caminho; **unificada** elimina duplicação; **reaproveitada** usa serviço existente; **substituída** usa outro mecanismo; **descartada** não faz parte da entrega. Os nomes seguintes se referem às chaves do documento de requisitos, não a uma promessa de compatibilidade binária com arquivos de terceiros.

## Identidade e gerais

- AccountKey — **descartada**: nenhum licenciamento comercial do terceiro. A autenticação interna é **reaproveitada** via Local.ApiKey e proteção existente da Web Store.
- Debug — **mantida**: Shared.config.Debug, diagnóstico com contadores sem conteúdo privado.
- DisableChat — **mantida**: suspende atuação do Chat Arkland, preserva chat nativo.
- DisableCrossServerChat — **mantida**: filtra distribuição cruzada, preservando o mapa de origem.
- RconIp / RconPortOverride — **reaproveitadas** no cadastro/gerenciador para suas funções operacionais; o novo relay usa SDK/API, não duplica IP/porta RCON.
- ServerKey — **reorganizada** em Local.ServerKey, associada a arkland_ref. Slug/nome de exibição não substitui essa chave.
- ClusterName — **unificada** em Shared.config.ClusterName. Não há segunda cópia em Messages.
- UseCrossChat, ShowMapName, HideServerTagOnLocal, ShowSteamName — **mantidas** com os padrões aprovados.
- GlobalChatSpamDelaySec, AdminImmuneToMuteAndSpamDelay — **mantidas**; AdminGroups explicita a origem da imunidade, sem conceder cargos.
- PollRate — **substituída a unidade**: segundos decimais, padrão 1.0; 250 do arquivo antigo não é importado como segundos nem automaticamente convertido.

## Notificações e comandos

- CrossMapNotifications.Enabled, ToggleCommand — **mantidas**, padrão habilitado e /joinleave.
- Display_Scale / Display_Time — **reorganizadas** em DisplayScale / DisplayTime.
- JoinDifferent_ColorRGB / LeaveDifferent_ColorRGB / JoinSame_ColorRGB / LeaveSame_ColorRGB — **reorganizadas** em JoinDifferentColor / LeaveDifferentColor / JoinSameColor / LeaveSameColor. RGB passa por seletor visual e RGBA validado.
- OnlinePlayersCommand.Enabled, ShowTribes, ShowOnlineTime, Command, DisplayTime, DisplayScale, AmountPerPage, OnlyShowMapToGroups, RestrictCommandToPermissions — **mantidas**. Presença **reaproveitada** do monitoramento compartilhado.
- PrivateMessages.Enabled — **mantida**.
- Private_Message_Command / Reply_Command — **reorganizadas** em PrivateMessages.Command / ReplyCommand. /pm usa o ID permanente do próprio chat.
- BadWords.Enabled, Words, IgnoredLetters — **mantidas**, filtro inicialmente desligado/lista vazia; censura em vez de bloqueio/punição.
- RandomTips — **descartada**. Dicas/respostas automáticas continuam responsabilidade do Lumo.

## Tags, cores e mapas

- Tags: texto, grupos, IDs de Steam/tribo e cores — **reorganizados** nas regras centrais Tags com Approved/Enabled, Kind e Priority. STAFF e Mod são referências pendentes, não privilégios automáticos.
- PermissionGroups — **reaproveitada** a identidade real do Permissions. Para licença paga, grupo sozinho não substitui entitlement vigente.
- Amount da hierarquia de referência — **descartada como prioridade automática**. A ordem inicial serve somente como sugestão editável; a administração aprova o catálogo real.
- Icons e caminhos de assets/ícones — **descartados** integralmente. Nenhum ícone de licença, tribo ou administrador é criado.
- ChatColors.ForAdmin / ForEveryone — **reorganizadas** em Kind admin / everyone; condições específicas usam PermissionGroups/SteamIds/TribeIds/LicenseGroups.
- MessageColor / NameColor / TribeNameColor — **reorganizadas** em Colors.Message / Name / Tribe ou overrides parciais em ChatColors[].Colors.
- HideTribeName / OverrideGraySelfNameColor — **reorganizadas** no mesmo objeto Colors/overrides, aplicadas na entrega.
- Cor da tag, mapa, origem Discord e ID — **unificadas** no mecanismo Colors/Tags/Maps, sem segundo conjunto de regras para Discord.
- Maps (chaves fixas 01/02/etc., nomes e cores) — **substituídas** pelo cadastro dinâmico por ServerKey permanente e Maps[key].Label/Color/Enabled.
- MasterServerRunDiscordBot_OnlySetOnOneServer — **substituída** pelo único Gateway central existente. Nenhum mapa elege um segundo cliente Discord.

## DiscordConfig.json

- Arquivo DiscordConfig.json separado — **unificado**: somente config.json nos mapas, mais o armazenamento protegido central existente.
- GlobalChat.Enabled — **reorganizada** em Discord.Enabled; desativada suspende ambos os sentidos, preservando o chat do jogo.
- GlobalChat.GlobalChatChannelId — **reaproveitada** a configuração lumo_game_chat_channel_id.
- GlobalChat.ShowMap — **reorganizada** em Discord.ShowMap, aplicada ao sentido Jogo → Discord.
- GlobalChat.AllowDiscordToIngame — **reorganizada** em Discord.AllowDiscordToIngame; não desliga por si só Jogo → Discord.
- HostServerDiscordId — **reaproveitada** a configuração lumo_guild_id. Os IDs históricos são referências conferidas, não substituições automáticas.
- Token — **reaproveitado** o armazenamento protegido e Gateway do Lumo. Ausente nos arquivos dos mapas e nas respostas de consulta administrativa.
- ShowCodeBlocks — **descartada**: mensagens textuais legíveis, sem blocos de código; escape de Markdown e menções desativadas na publicação central.
- Use24HourTimeFormat — **substituída por regra fixa** de 24 horas, sem chave administrativa.
- DefaultChatFromDiscord / IngameChatFromDiscordConfig — **unificados** em Messages.Discord, Colors/Tags, vínculos reais e mesmo mecanismo de licenças/permissões. Não há hierarquia concorrente por origem.
- ShowServerStatusChannels — **descartada** deste plugin; o painel de status existente continua independente.
- RconCommands — **descartada**, sem executor de comandos administrativos pelo Discord.
- JoinLeaveMessages — **descartada no Discord**. Não afeta CrossMapNotifications dentro do jogo.
- PlayerList — **descartada no Discord**. Não afeta /online no jogo.
- PermanentMessages — **descartada**, sem painel permanente próprio de chat.
- SteamLink — **reaproveitada** a vinculação já existente. Nenhum novo processo de vinculação foi criado.
- RolePermissionSync — **descartada**: o chat não concede/sincroniza cargos ou permissões.
- TribeWebhookNames — **descartada**, sem webhooks por tribo.
- StatusPollRateSec / PlayerListUpdateRateSecs / JoinLeaveUpdateRateSecs / ResponsePollRate — **descartadas** por pertencerem às funções Discord excluídas. Não são aliases de PollRate.
- Mysql.MysqlHost/MysqlUser/MysqlPass/MysqlPort/MysqlDB e Database.host/user/port/password/database — **unificados/reaproveitados** na conexão central já existente. Os mapas usam API interna autenticada e não recebem uma segunda senha MySQL.

## Mensagens e acréscimos necessários

- Messages — **substituídas** por textos PT-BR, com variáveis permitidas e formatos de Global/Discord/PM/entrada/saída/online/erros. Editáveis no painel, preservando os campos obrigatórios do global.
- ID individual — **implementado** após verificar que SteamID, PlayerDataID, sessão e IDs de sorteio não atendiam à função. Registro permanente próprio por SteamID, sem duplicar cadastro de contas.
- ObserveOnly, participação aprovada por mapa, revisão, TTL, ACK e filas limitadas — controles próprios necessários para migração, sincronização e privacidade. Não habilitam funcionalidades descartadas.
