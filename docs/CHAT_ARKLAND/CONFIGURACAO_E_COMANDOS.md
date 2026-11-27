# Configuração e comandos

## Arquivo único e autoridade

O arquivo `config.json` possui três blocos:

- `Local`: `ServerKey` permanente do cadastro (`arkland_ref`, como `tek:<uuid>`), `ApiUrl` do backend, `ApiKey` interna e `ObserveOnly`. Nunca é substituído por uma publicação global. Mudanças locais exigem recarga controlada do plugin/reinício apenas do piloto.
- `Shared`: `revision` e `config`, cópia da última configuração central validada. O banco é a autoridade. Não editar essa cópia para tentar publicar no cluster.
- `Runtime`: cursor, IDs públicos conhecidos e histórico limitado de entregas processadas. Não contém mensagens privadas ou token Discord. O cache é substituído atomicamente através de arquivo temporário no mesmo diretório.

Bootstrap em Administração → Chat Arkland → Mapas entrega o arquivo por rota administrativa com `no-store`. Esse download contém uma credencial interna real: mantenha ACL restrita à conta do servidor e administradores, não publique nem envie como anexo em canais públicos. Use HTTPS; HTTP é destinado somente a rede privada ou loopback controlados. O plugin não segue redirects, para não encaminhar a chave a outro host.

## Publicação e cache

`GET /api/admin/chat-arkland` mostra revisão, mapas, candidatos e saúde. `PUT .../config` exige `expected_revision`. Publicação inválida preserva a anterior; publicação sobre revisão desatualizada exige nova consulta. Rollback publica uma nova revisão auditável, não apaga o histórico.

Cada instância consulta o hub com PollRate em segundos (padrão 1,0, mínimo 0,1, máximo 30). A API mantém cache de configuração de até dois segundos; PollRate não é promessa de latência total. `PresenceTtlSeconds` deve ser pelo menos três intervalos; `MessageTtlSeconds`, pelo menos dois intervalos mais dois segundos. A interface valida estes limites.

Falha de rede mantém o chat nativo disponível; comandos privados informam indisponibilidade em particular. Mensagem global já capturada cuja resposta de rede falhe pode receber uma única apresentação local com o último cache; não se promete entrega exatamente uma vez diante de encerramento abrupto no intervalo entre exibição e persistência do ACK. O histórico de deduplicação é limitado a 4096 entregas. Nenhum texto privado é persistido no cache local.

## Esquema compartilhado

- Gerais: `SchemaVersion=1`, `ClusterName=ARKLAND`, `DisableChat=false`, `UseCrossChat=true`, `DisableCrossServerChat=false`, `Debug=false`, `PollRate=1.0`.
- Identificação: `ShowMapName=true`, `HideServerTagOnLocal=false`, `ShowSteamName=false`. Desativar o Chat Arkland preserva o chat nativo; suspender comunicação entre mapas mantém a mensagem no mapa de origem. UseCrossChat desativado entrega o chat global ao jogo, sem personalização desse canal.
- Limites: `MaxMessageLength=500`, `GlobalChatSpamDelaySec=2`, `MessageTtlSeconds=30`, `PresenceTtlSeconds=45`. A imunidade administrativa ao intervalo depende de `AdminImmuneToMuteAndSpamDelay` e de `AdminGroups`; não concede cargos.
- `CrossMapNotifications`: Enabled, ToggleCommand, DisplayScale, DisplayTime e quatro cores de entrada/saída para mesmo/outro mapa. Padrões habilitados, `/joinleave`, escala 1, duração 5 segundos. A preferência é individual e persistente.
- `OnlinePlayersCommand`: Enabled, Command, ShowTribes, ShowOnlineTime, DisplayScale, DisplayTime, AmountPerPage, OnlyShowMapToGroups e RestrictCommandToPermissions. Padrões `/online`, 15 por página, escala 0,5, duração 10 segundos. A lista usa sessões recentes dos mapas participantes e os mesmos IDs do chat; não é uma lista histórica de personagens offline.
- `PrivateMessages`: Enabled, Command (`/pm`) e ReplyCommand (`/r`). Não há transporte de mensagens privadas pelo Discord.
- `BadWords`: Enabled=false, Words=[], IgnoredLetters=[ponto, hífen, sublinhado, espaço]. Censura antes do relay com asteriscos; considera acentos, caixa e evasões simples; preserva limites de palavras e não aplica punição.
- `Discord`: Enabled=true, AllowDiscordToIngame=true e ShowMap=true. Guild, canal, token e vinculações vêm dos serviços existentes do Lumo; não são duplicados neste arquivo.
- `Colors`: Message, Name, Tribe, Tag, Map, Discord, Id, OverrideGraySelfNameColor e HideTribeName. A interface oferece seletor de cor e opacidade; o contrato usa `#RRGGBBAA`, convertido para RGBA de 0 a 1 no jogo.
- `Maps`: objeto pela ServerKey permanente, com Enabled, Label e Color. O cadastro do gerenciador define as instâncias; o administrador aprova participação e texto/cor do chat. Novos mapas começam sem participação aprovada. Instâncias sem `arkland_ref` não recebem bootstrap até regularizar o cadastro.
- `Tags`: regras com Key, Label, Kind, Priority, Enabled, Approved, PermissionGroups, LicenseGroups, SteamIds, TribeIds e Color. Kind admin exige grupo validado; Kind license exige licença vigente, nunca apenas um grupo pago antigo. O menor Priority vence dentro da categoria; administrativa sempre precede licença. Empate é resolvido pela chave. Uma única tag é exibida.
- `ChatColors`: mesmas condições de autorização e prioridade, com objeto Colors parcial. Campos omitidos herdam as cores gerais. A seleção da regra visual não acumula todas as regras concorrentes.
- `Messages`: textos em português e templates com variáveis permitidas por mensagem. Campos desconhecidos, templates incompatíveis, cores inválidas, comandos repetidos e limites inválidos são recusados.

O painel não ativa automaticamente STAFF, Mod nem licenças descobertas. Cada regra exige aprovação e ativação. A descoberta consulta o catálogo atual, sem presumir a hierarquia final pelo preço. Aprovação administrativa é necessária para regras especiais.

## Apresentação no Discord (1.12.34)

Mensagens globais do jogo são agrupadas em blocos monoespaçados de texto, conforme a referência visual aprovada pelo Ciano. O publicador atualiza somente seu bloco corrente; ao atingir o limite de 2000 unidades UTF-16, 40 linhas ou aparecer outra conversa no canal, abre outro bloco sem apagar o anterior. Crases do conteúdo são representadas por um caractere visual equivalente para impedir fechamento indevido do bloco. Menções continuam desativadas. IDs, horários, tags e nomes são preservados; cores RGBA do jogo não são simuladas no Discord.

O Lumo recebe uma vez o evento original autenticado do hub, em fila separada, sem depender do texto do bloco ou dos eventos de edição. Ecos do próprio relay não são retransmitidos ao jogo nem reinterpretados como novas perguntas. Depois de reiniciar o Gateway, um bloco novo é iniciado; não se edita um bloco antigo sem estado confirmado. Resultado de envio/edição ambíguo fica incerto e não é republicado às cegas.

## Formato e identidade

Formato do jogo: `[HH:mm][MAPA] <TAG> Jogador (ID) [Tribo]: Mensagem`. Tag/tribo ausentes não deixam separadores vazios. Horário obrigatório em 24 horas, Brasília; Windows usa UTC−03 no formatador local. O backend usa America/Sao_Paulo quando disponível, com fallback UTC−03.

O ID compacto é uma sequência permanente associada ao SteamID64 na tabela `chat_arkland_players`. Não depende do nome, tribo, PlayerDataID, sessão ou mapa. O banco possui restrição única por SteamID. Não excluir, zerar contador ou restaurar parcialmente esse registro: o downgrade deliberadamente preserva a tabela. Backups devem preservar a associação completa. Um rollback de banco para antes da emissão de novos IDs exige bloquear o piloto e reconciliar essas emissões, nunca reutilizá-las silenciosamente.

## Comandos do jogador

- `/pm 125 Olá!`: resolve o ID e envia somente aos dois participantes. ID inexistente, próprio ID, destinatário offline e mensagem vazia recebem resposta privada.
- `/r Obrigado!`: responde à última conversa privada. Para o destinatário, o interlocutor é atualizado somente após ACK de exibição; uma mensagem global não modifica essa conversa. Sem conversa anterior, informa como iniciar.
- `/online` ou `/online 2`: consulta jogadores com presença recente, página limitada, ID igual ao chat e permissões específicas para mostrar mapa. Não transmite a listagem ao Discord.
- `/joinleave`: alterna notificações de entrada/saída para o próprio jogador; preferência persistente.

### Colunas da consulta online (sistema 1.12.37)

Com o modelo padrão de `Messages.OnlinePlayer`, a consulta apresenta NOME, ID, TRIBO, MAPA e TEMPO em colunas. `ShowTribes`, `ShowOnlineTime` e `OnlyShowMapToGroups` continuam controlando as colunas disponíveis. O ID não é abreviado; nomes, tribos e mapas longos recebem `...`, e ausência de tribo aparece como `--`. O tempo usa `0h50m`.

O espaçamento usa avanços de caracteres medidos na fonte Roboto Bold distribuída no servidor, limites absolutos de coluna e um delimitador final que preserva a largura de cada linha no aviso centralizado do ASE. Não usa contagem simples de caracteres nem tabulações. A correspondência exata depende da fonte efetivamente usada pelo cliente; fontes modificadas podem exigir ajuste visual. A homologação em jogo desta disposição ainda está pendente.

Um `Messages.OnlinePlayer` personalizado mantém sua disposição anterior; restaurar o modelo padrão `{jogador} ({id}){tribo}{mapa}{tempo}` ativa as colunas. A alteração ocorre no backend e não exige trocar DLLs nem migrar o banco. Os arquivos de fonte não são distribuídos no pacote.

Implementação publicada na [release 1.12.37](https://github.com/SrLuther/ARKLAND-Multi/releases/tag/v1.12.37) e aplicada na WebStore oficial em 26/11. SHA-256 do executável: `4DEC2BB2E87CA600F6B7802D286EB9D9DA6563F353432B669DE9E9F4F71C3EBF`. Foram aprovados 35 testes de serviço/transporte/formatação e executado o formatador extraído do executável congelado. Changelog do gerenciador e módulos/tabela de métricas no pacote foram conferidos. Backup consistente do banco e configurações foi preservado; nenhum mapa foi reiniciado. A conferência dentro do cliente permanece pendente.

### Correção da disposição — 1.12.38

A captura posterior do administrador **reprovou a disposição da 1.12.37**. A validação com a fonte TrueType de Slate não representava o HUD do jogo. Os assets antigos chamados Roboto contêm Sansation Bold com glifos já rasterizados; o Roboto51 usa kerning -9 e espaço com largura 19 em unidades do asset. O Canvas aplica o kerning antes do próximo caractere não branco, e a centralização depende da largura final de cada linha.

A 1.12.38 extrai as larguras do asset `OldAssets/UI/HUD/Roboto51.uasset`, calcula esse kerning e distribui os espaços considerando as larguras finais das linhas centralizadas. O extrator é [measure_notification_font.py](../../plugin/ChatArkland/tools/measure_notification_font.py); não distribui fontes nem texturas. O modelo explica as 16 barras da captura anterior com erro máximo inferior a meio pixel. A regressão também verifica os campos após a centralização, em vez de apenas somar caracteres ou reproduzir uma fonte de desktop.

Foram aprovados 38 testes de serviço, transporte e disposição. Espaços inteiros ainda impõem pequena discretização; não se promete alinhamento subpixel com esse RPC. A nova disposição ainda precisa de conferência visual no cliente. Permissões de mapa, modelos personalizados, IDs completos e tamanho do aviso são preservados.

Publicada na [release 1.12.38](https://github.com/SrLuther/ARKLAND-Multi/releases/tag/v1.12.38), com instalador e changelog atualizados. Aplicada na WebStore oficial, SHA-256 `860A0671E85E21236D35FC118B0A4F5EE6963B1F0E14D98D5B29ED2B7BE4BC05`; API pública 1.12.38, revisão 12 e escala 1 preservadas, Gateway online. O formatador extraído do executável também passou na regressão da captura. Backup consistente privado preservado (71.181.833 bytes), sem mudança de schema.

A primeira aplicação reverteu por divergência com o registro de processos feito no backup: o 03 havia encerrado normalmente às 23:06:30, antes da inicialização da WebStore às 23:07:34; uma tentativa posterior de inicialização desse mapa gerou dump. Os logs foram apenas consultados, sem alterar/iniciar o mapa. A nova aplicação capturou uma referência imediatamente anterior à troca central e preservou os quatro processos ativos. Tarefa persistente `ARKLAND-WebStore-Update-1.12.38` confirmada em execução após desconectar SSH. A homologação visual nova foi solicitada ao administrador e permanece pendente.

### Separador entre cabeçalhos e conteúdo — 1.12.39

O administrador enviou nova captura da 1.12.38 e pediu apenas uma linha entre cabeçalhos e jogadores, como no exemplo de referência. A 1.12.39 insere esse separador usando hífens ASCII (presentes na fonte nativa), dimensionados para a largura média das linhas da tabela. Mantém as colunas e o tamanho do texto. Foram aprovados 40 testes, incluindo separador com e sem permissão de mapa; não exige atualização de DLL nem mudança no banco.

Não digitar os prefixos nativos de horário/Discord/Lumo no corpo da resposta da assistente. Mensagens locais, de tribo e de aliados não entram no hub. Texto recebido do Discord, inclusive `/pm` ou RCON, permanece texto e não executa comandos.

## Banco e retenção

Configuração/revisões, IDs permanentes, instâncias, eventos com TTL, mensagens/entregas transitórias e lease do publicador ficam em tabelas `chat_arkland_*`. Presença continua em `game_players` e `game_player_sessions`, através da ingestão compartilhada. Licenças, usuários, permissões e vínculos não são replicados em cadastros concorrentes.

Mensagens privadas têm lease de três segundos por instância e ACK por destinatário, acompanhando transferências. Conteúdos expiram após o TTL configurado; tombstones de eventos duram um dia. A limpeza é oportunista enquanto há tráfego; não é cron nem promessa de eliminação física instantânea se o serviço estiver parado. Logs de diagnóstico exibem somente revisão, filas e contadores, sem conteúdo privado ou credenciais.
