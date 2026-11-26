# PROJETO — CHAT ARKLAND

## 1. Objetivo principal
Desenvolva um novo plugin proprietário chamado **Chat Arkland**, dedicado exclusivamente ao gerenciamento, personalização, sincronização e integração do sistema de comunicação dos servidores ARKLAND.

O objetivo é substituir o mecanismo atualmente utilizado por uma solução própria, integrada à infraestrutura existente do ARKLAND, permitindo que a administração tenha controle centralizado sobre o funcionamento do chat através do painel administrativo do site.

O plugin deverá contemplar:

- Comunicação global entre todos os mapas.
- Comunicação bidirecional entre os servidores e o Discord.
- Integração com o Lumo.
- Identificação individual dos jogadores através de IDs exibidos no chat.
- Mensagens privadas entre jogadores de diferentes mapas.
- Consulta de jogadores conectados.
- Notificações de conexão e desconexão.
- Personalização de tags e cores.
- Hierarquia de exibição de licenças e cargos administrativos.
- Filtro de palavras.
- Controle de spam.
- Gerenciamento centralizado de configurações.
- Sincronização através do banco de dados.

## 2. Investigação obrigatória do projeto existente
Antes de iniciar o desenvolvimento, realize uma análise abrangente do projeto ARKLAND.

Há algum tempo, houve uma tentativa de desenvolvimento e integração de um sistema próprio de chat, porém essa implementação não obteve êxito.

É possível que ainda existam arquivos, códigos-fonte, tabelas, endpoints, configurações ou componentes relacionados a essa tentativa.

Procure por essas implementações dentro do projeto, incluindo:

- Diretórios de plugins.
- Código-fonte do site.
- Serviços de integração.
- Implementações antigas de chat.
- Banco de dados.
- APIs.
- Serviços do Discord.
- Implementações do Lumo e do antigo Bobonic.
- Documentações.
- Histórico do Git, quando disponível.
- Configurações dos servidores.
Caso encontre a implementação anterior, analise sua arquitetura, suas limitações e os possíveis motivos pelos quais não funcionou.

Essa investigação deverá servir como referência técnica, evitando repetir erros anteriores.

Entretanto, independentemente de encontrar ou não essa implementação, a determinação é construir um plugin novo.

## 3. Desenvolvimento de um plugin independente
O Chat Arkland deverá ser um plugin independente, com seu próprio código-fonte, estrutura, compilação, configuração e ciclo de funcionamento.

**Não implemente o Chat Arkland como uma extensão, módulo interno ou incremento de outro plugin existente.**

Não utilize o CustomShop ou qualquer outro plugin como base operacional para incorporar o sistema de chat.

Também não utilize o KalsCrossChat como dependência obrigatória do novo mecanismo.

É permitido e desejável reaproveitar:

- APIs existentes.
- Serviços compartilhados.
- Infraestrutura de comunicação.
- Mecanismos de autenticação.
- Bibliotecas compatíveis.
- Consultas ao banco de dados.
- Sistemas de monitoramento.
- Informações de jogadores.
- Identificadores individuais de jogadores.
- Informações de tribos.
- Sistemas de licenças.
- Sistemas de permissões.
- Vinculação de contas.
- Integrações existentes com o Discord.
O reaproveitamento dessas funcionalidades não significa incorporar o Chat Arkland dentro de outro plugin.

O Chat Arkland deverá possuir sua própria identidade e independência operacional.

Utilize a versão do ArkServerAPI compatível com os servidores atualmente utilizados pelo ARKLAND. Verifique os padrões de compilação, carregamento e distribuição dos plugins próprios já desenvolvidos no projeto.

## 4. Arquitetura centralizada
O banco de dados deverá atuar como fonte central das configurações compartilhadas do Chat Arkland.

Fluxo esperado:

Painel administrativo → Banco de dados → Instâncias do Chat Arkland.

As alterações realizadas pelo painel administrativo deverão ser registradas no banco de dados e posteriormente sincronizadas com todas as instâncias do plugin.

Cada servidor possuirá sua própria instalação do Chat Arkland, mas todos deverão utilizar as configurações compartilhadas do sistema, respeitando as particularidades individuais de cada mapa.

O painel não deverá depender exclusivamente da edição remota de arquivos em cada servidor.

Implemente mecanismos de:

- Versionamento das configurações.
- Identificação de alterações.
- Sincronização automática.
- Validação das configurações recebidas.
- Atualização segura em tempo de execução, quando tecnicamente possível.
- Cache local da última configuração válida.
- Reconexão automática.
- Identificação individual de cada instância.
- Tratamento de falhas de comunicação.
Uma indisponibilidade temporária do banco de dados não deverá provocar o encerramento do servidor ARK.

Evite consultas desnecessárias e operações bloqueantes na thread principal do jogo.

## 5. Arquivo único de configuração
O mecanismo utilizado como referência possui dois arquivos:

- `config.json`
- `DiscordConfig.json`
O Chat Arkland deverá utilizar somente um arquivo próprio de configuração:

`config.json`

Todas as configurações aprovadas dos dois arquivos originais deverão ser reorganizadas dentro desse arquivo unificado.

Não crie um segundo arquivo exclusivo para as configurações do Discord.

Organize as configurações por blocos, mantendo uma estrutura clara, documentada e facilmente compreensível.

As configurações locais deverão ser diferenciadas das configurações compartilhadas e sincronizadas pelo banco de dados.

Não permita que uma sincronização global sobrescreva indevidamente a identificação individual de um servidor.

As chaves apresentadas neste documento são referências funcionais dos arquivos originais. O novo esquema poderá ser reorganizado tecnicamente, desde que preserve integralmente os comportamentos aprovados.

Não mantenha chaves sem utilização efetiva.

## 6. Configurações gerais do plugin

### AccountKey
Chave existente no arquivo original.

Não reproduza mecanismos de licenciamento comercial ou autenticação proprietária do plugin de referência.

O Chat Arkland será um plugin próprio do ARKLAND.

Caso seja necessária autenticação entre o plugin e os serviços internos, utilize os mecanismos seguros já existentes no projeto ou desenvolva uma solução própria compatível.

### Debug
Disponibilize um modo de diagnóstico.

Valor padrão: `false`.

Permita sua ativação administrativa para investigação de problemas.

O modo de diagnóstico não deverá registrar senhas, tokens ou outras informações sensíveis.

### DisableChat
Disponibilize controle administrativo sobre a atuação do sistema de chat.

Valor padrão: `false`.

Defina claramente a diferença entre desativar o Chat Arkland e bloquear completamente a comunicação dos jogadores.

A desativação do plugin não deverá bloquear indevidamente o chat nativo do ARK.

### DisableCrossServerChat
Permita desativar especificamente a comunicação entre servidores, preservando o funcionamento local quando possível.

Valor padrão: `false`.

### RconIp e RconPortOverride
Analise como o ARKLAND atualmente identifica e acessa seus servidores.

Reaproveite o cadastro de servidores e os mecanismos de comunicação existentes.

Não replique endereços IP, portas ou credenciais desnecessariamente.

Não utilize RCON como solução obrigatória para toda a comunicação caso existam alternativas mais eficientes através do ArkServerAPI e da infraestrutura compartilhada.

### ServerKey
Identificador individual da instância do servidor.

Deverá ser associado ao cadastro existente de servidores do ARKLAND.

Não utilize o nome de exibição como único identificador permanente, pois nomes podem ser alterados.

### ClusterName
Valor padrão: `ARKLAND`.

Disponibilize uma única configuração compartilhada para o nome do cluster, editável pelo painel administrativo.

Não duplique essa configuração dentro do bloco de mensagens.

## 7. Chat global entre servidores
Implemente comunicação global entre todos os mapas participantes do ARKLAND.

Uma mensagem enviada no chat global de determinado servidor deverá ser encaminhada aos demais servidores participantes e ao canal global do Discord, quando a integração estiver habilitada.

A quantidade de servidores deverá ser dinâmica.

Não limite o funcionamento a uma quantidade fixa de mapas.

Reaproveite o cadastro e o monitoramento de servidores existentes no ARKLAND para identificar quais instâncias estão disponíveis.

### UseCrossChat
Valor padrão: `true`.

### ShowMapName
Valor padrão: `true`.

Permita configurar a exibição do nome do mapa.

### HideServerTagOnLocal
Valor padrão: `false`.

Por padrão, o identificador do mapa deverá ser exibido inclusive para jogadores conectados ao mesmo servidor de origem da mensagem.

### Formatação obrigatória
Utilize a seguinte estrutura:

`[HH:mm][MAPA] <TAG> Jogador (ID) [Tribo]: Mensagem`

Exemplo:

`[21:35][Valgero [OMEGA]] <DEMONIC> Jogador (125) [Tribo]: Olá, pessoal!`

Cada elemento possui uma finalidade específica:

- `[HH:mm]`: horário de envio.
- `[MAPA]`: identificação do mapa de origem.
- `<TAG>`: tag de licença ou cargo administrativo de maior prioridade.
- `Jogador`: nome do personagem ou nome Steam, conforme configuração.
- `(ID)`: identificador individual do jogador utilizado para direcionamento de mensagens privadas.
- `[Tribo]`: nome da tribo.
- `Mensagem`: conteúdo enviado pelo jogador.

### Identificador individual do jogador
A exibição do ID individual é obrigatória nas mensagens globais enviadas pelos jogadores.

Sua finalidade é permitir que outros jogadores utilizem o comando `/pm` sem precisar digitar nomes completos ou lidar com personagens que possuem nomes iguais.

O identificador deverá:

- Ser único em todo o cluster.
- Ser consistente entre os mapas.
- Permanecer associado ao mesmo jogador após reconexões.
- Permanecer consistente após transferências entre servidores.
- Ser suficientemente compacto para não prejudicar a legibilidade do chat.
- Permitir a localização inequívoca do destinatário.
- Não depender do nome do personagem, da tribo ou da licença.
Antes de criar um novo identificador, investigue se o ARKLAND já possui um ID individual que atenda a esses requisitos.

Não confunda automaticamente o identificador público do chat com SteamID64, ID do personagem ou ID de sessão.

Caso nenhum identificador existente seja adequado, implemente um identificador próprio, persistente e associado à identidade real do jogador no banco de dados.

Não reutilize IDs de maneira que uma mensagem privada possa ser encaminhada indevidamente a outro jogador.

O número `125` apresentado nos exemplos é ilustrativo.

### Exemplos de apresentação
Jogador com licença e tribo:

`[21:35][Valgero [OMEGA]] <DEMONIC> Jogador (125) [Tribo]: Olá!`

Jogador sem licença:

`[21:35][Valgero [OMEGA]] Jogador (125) [Tribo]: Olá!`

Jogador sem tribo:

`[21:35][Valgero [OMEGA]] <DEMONIC> Jogador (125): Olá!`

Jogador sem licença e sem tribo:

`[21:35][Valgero [OMEGA]] Jogador (125): Olá!`

A tag deverá aparecer somente quando o jogador possuir uma tag válida e autorizada.

A ausência de uma tag ou de uma tribo não deverá produzir espaços, separadores ou elementos vazios desnecessários.

O horário deverá utilizar obrigatoriamente o formato de 24 horas, com horas e minutos.

Não disponibilize opção para utilização de AM ou PM.

Utilize um fuso horário consistente entre os servidores, o site e o Discord.

### Separação dos canais nativos
Preserve a distinção entre:

- Chat global.
- Chat local.
- Chat de tribo.
- Chat de aliados.
- Mensagens privadas.
Mensagens privadas, locais, de tribo ou de aliados não deverão ser encaminhadas ao canal global do Discord ou aos demais jogadores indevidamente.

Verifique os mecanismos do ArkServerAPI responsáveis por identificar corretamente cada modalidade de chat.

## 8. CrossMapNotifications
Implemente notificações de conexão e desconexão dos jogadores entre os mapas.

Referência original:

```
"CrossMapNotifications": {
  "Enabled": true,
  "ToggleCommand": "/joinleave",
  "Display_Scale": 1.0,
  "Display_Time": 5.0,
  "JoinDifferent_ColorRGB": [255, 255, 255],
  "LeaveDifferent_ColorRGB": [255, 255, 255],
  "JoinSame_ColorRGB": [100, 180, 100],
  "LeaveSame_ColorRGB": [163, 50, 50]
}
```
Comportamento esperado:

- Notificar quando um jogador entrar em determinado mapa.
- Notificar quando um jogador sair de determinado mapa.
- Identificar o jogador e o mapa correspondente.
- Diferenciar visualmente eventos do mesmo mapa e de outros mapas.
- Permitir personalização das cores, escala e duração.
- Permitir ativação e desativação administrativa pelo site.
- Manter a funcionalidade ativa por padrão.
O comando `/joinleave` deverá permitir que o jogador controle individualmente o recebimento dessas notificações.

Essa preferência individual não deverá alterar a configuração global.

Não confunda essa funcionalidade com o antigo bloco `JoinLeaveMessages` do Discord, que foi descartado.

Reaproveite os mecanismos de identificação de sessões e jogadores conectados já existentes no ARKLAND, quando forem adequados.

## 9. OnlinePlayersCommand
Implemente um comando para consulta de jogadores conectados ao cluster.

Referência original:

```
"OnlinePlayersCommand": {
  "Enabled": true,
  "ShowTribes": true,
  "ShowOnlineTime": true,
  "Command": "/online",
  "DisplayTime": 10.0,
  "DisplayScale": 0.5,
  "AmountPerPage": 15,
  "OnlyShowMapToGroups": ["Admins"],
  "RestrictCommandToPermissions": ["Default"]
}
```
O sistema deverá permitir:

- Consultar jogadores conectados.
- Exibir a quantidade total de jogadores online.
- Exibir nomes dos jogadores.
- Exibir os IDs individuais utilizados pelo `/pm`.
- Exibir nomes das tribos, quando habilitado.
- Exibir tempo de conexão, quando habilitado.
- Organizar os resultados em páginas.
- Configurar quantidade de resultados por página.
- Configurar escala e duração da exibição.
- Controlar permissões de utilização.
- Controlar quais grupos podem visualizar o mapa de cada jogador.
Utilize `/online` como comando padrão.

O sistema deverá estar ativo por padrão, com possibilidade de desativação pelo painel administrativo.

O ARKLAND já possui mecanismos de monitoramento de jogadores conectados em cada servidor.

Localize e reaproveite esses mecanismos explicitamente, evitando criar um segundo sistema independente de monitoramento quando o existente atender aos requisitos.

O ID apresentado pelo `/online` deverá ser exatamente o mesmo apresentado nas mensagens do chat global.

A lista de jogadores dentro do jogo deverá permanecer funcional mesmo que a antiga funcionalidade de publicação de listas no Discord seja descartada.

## 10. PrivateMessages
Implemente comunicação privada entre jogadores, inclusive quando estiverem conectados em mapas diferentes.

Referência original:

```
"PrivateMessages": {
  "Enabled": true,
  "Private_Message_Command": "/pm",
  "Reply_Command": "/r"
}
```

### Comando /pm
O comando deverá utilizar o ID individual apresentado nas mensagens do chat global e na consulta de jogadores online.

Sintaxe:

`/pm ID Mensagem`

Exemplo:

Um jogador envia a seguinte mensagem global:

`[21:35][Valgero [OMEGA]] <DEMONIC> Jogador (125) [Tribo]: Alguém pode me ajudar?`

Outro jogador poderá responder de maneira privada utilizando:

`/pm 125 Posso ajudar você.`

O sistema deverá localizar o jogador de ID 125, identificar em qual servidor ele está conectado e encaminhar a mensagem exclusivamente ao destinatário.

Não deverá ser necessário informar o mapa, o nome do personagem ou o nome da tribo.

A existência de personagens com nomes iguais não deverá causar ambiguidades no encaminhamento.

### Comando /r
O comando `/r` deverá permitir responder ao último interlocutor privado sem precisar informar novamente o ID.

Sintaxe:

`/r Mensagem`

Exemplo:

`/r Obrigado pela ajuda!`

O sistema deverá manter individualmente o contexto da última conversa privada de cada jogador.

Esse contexto deverá utilizar internamente o identificador estável do interlocutor, nunca apenas seu nome.

Garanta que uma mensagem global não altere o destinatário do `/r`.

O mecanismo deverá funcionar inclusive quando os interlocutores estiverem em mapas diferentes.

Caso não exista uma conversa privada anterior, informe ao jogador que deverá iniciar uma utilizando `/pm ID Mensagem`.

### Identificação e tratamento de erros
Trate adequadamente:

- ID inexistente.
- ID inválido.
- Jogador desconectado.
- Tentativa de enviar mensagem para si mesmo.
- Ausência de uma conversa anterior.
- Sintaxe incorreta.
- Mensagem vazia.
- Desconexão durante uma conversa.
- Transferência do destinatário entre mapas.
- Falhas de encaminhamento.
- Alterações no nome do personagem.

### Privacidade
As mensagens privadas deverão ser encaminhadas exclusivamente aos participantes da conversa.

O remetente deverá receber uma confirmação ou representação privada da mensagem enviada.

Não publique essas mensagens no chat global, no Discord ou em canais acessíveis a terceiros.

O encaminhamento não deverá depender da exibição pública de SteamID64 ou de outros identificadores internos desnecessários.

Utilize identificadores estáveis para representar os jogadores internamente.

A funcionalidade deverá estar ativa por padrão e poderá ser desativada pelo painel administrativo.

## 11. Identificação dos jogadores — ShowSteamName
Disponibilize uma configuração administrativa para selecionar qual nome será exibido nas mensagens.

`ShowSteamName: false`

Comportamento:

- `false`: exibir o nome do personagem.
- `true`: exibir o nome da conta Steam.
O nome do personagem será o padrão.

Essa configuração deverá existir uma única vez no sistema, evitando duplicidade entre as configurações do jogo e do Discord.

A identificação interna dos jogadores não deverá depender do nome exibido.

A alteração entre nome Steam e nome do personagem não deverá modificar o ID individual utilizado pelo `/pm`.

## 12. Controle de spam
Implemente proteção contra envio excessivo de mensagens.

Referências originais:

```
"GlobalChatSpamDelaySec": 2.0,
"AdminImmuneToMuteAndSpamDelay": true
```
Utilize dois segundos como valor inicial de referência para o intervalo entre mensagens globais.

Disponibilize configuração administrativa do intervalo.

Analise o sistema existente de permissões para identificar corretamente os grupos administrativos autorizados a ignorar essa restrição.

Não conceda imunidade com base apenas no nome ou na tag visual do jogador.

Caso uma mensagem seja limitada, apresente uma notificação adequada em português.

A proteção contra spam deverá funcionar de maneira eficiente, sem bloquear a thread principal do servidor.

## 13. Filtro de palavras — BadWords
Implemente um sistema próprio de filtragem e censura de palavras.

Referências originais:

- `UseWordBlacklist`
- `IgnoredLettersForBadWords`
- `BadWords`
- `Word`
- `LeaveFirstAndLastLetters`
- `Color`
- `SafeWords`
- `Replacement`
- `MuteSecs`
- `ChatMuteSecForBadWord`
A funcionalidade deverá estar desativada por padrão.

No painel administrativo do Chat Arkland, disponibilize uma área específica para gerenciamento das palavras censuradas.

A administração deverá conseguir:

- Ativar ou desativar o filtro.
- Adicionar palavras.
- Editar palavras.
- Remover palavras.
- Consultar a lista cadastrada.
A lista deverá ser armazenada no banco de dados e sincronizada automaticamente com todas as instâncias do Chat Arkland.

### Comportamento obrigatório da censura
A identificação de uma palavra proibida não deverá impedir automaticamente o envio da mensagem.

A mensagem deverá continuar sendo enviada normalmente, porém a palavra identificada deverá ser substituída por asteriscos.

Exemplo:

Mensagem original:

`Essa palavra é proibida.`

Mensagem encaminhada:

`Essa ******* é proibida.`

A censura deverá acontecer antes da distribuição da mensagem aos destinatários.

Não encaminhe a versão original para outros mapas ou para o Discord quando a censura estiver ativa.

Implemente tratamento adequado para diferenças entre letras maiúsculas e minúsculas, caracteres especiais e tentativas simples de contornar o filtro.

Evite censurar indevidamente palavras legítimas que contenham sequências semelhantes às palavras proibidas.

As configurações adicionais presentes no arquivo original, como substituições personalizadas, cores e punições automáticas, não deverão ser introduzidas automaticamente como requisitos obrigatórios.

O comportamento prioritário aprovado é a censura por asteriscos. Qualquer mecanismo punitivo adicional deverá ser apresentado separadamente para avaliação administrativa antes de ser habilitado.

Não importe automaticamente a lista de palavras de exemplo do plugin original.

A lista inicial poderá permanecer vazia até que a administração cadastre as palavras desejadas.

## 14. RandomTips — funcionalidade descartada
Não implemente o sistema `RandomTips` no Chat Arkland.

Isso inclui:

- `ShowRandomTips`
- `IntervalMins`
- `HideTipsCommand`
- `ShowTipsCommand`
- `TipTitle`
- `ShowAsNotification`
- `NotificationColor`
- `NotificationScale`
- `NotificationDisplayTime`
- `Tips`
A responsabilidade por dicas, orientações, lembretes e comunicações automáticas deverá permanecer com o Lumo.

Não crie um segundo mecanismo concorrente de notificações automáticas.

## 15. Sistema de tags
Implemente um sistema centralizado de tags, integrado às licenças e permissões existentes no ARKLAND.

O arquivo original utiliza a seguinte estrutura como referência:

```
{
  "Tag": "SPIRIT",
  "ForAdmin": false,
  "Color": "1, 0.84, 0, 0.8",
  "PermissionGroups": ["l_spirit"],
  "Amount": 1015,
  "TribeIds": [],
  "SteamIds": []
}
```
O novo sistema deverá permitir que a administração gerencie as tags através do painel administrativo.

### Hierarquia obrigatória
Em nenhuma hipótese um jogador deverá exibir duas ou mais tags simultaneamente.

Cada jogador deverá exibir somente a tag válida de maior prioridade.

As tags administrativas deverão possuir prioridade superior às tags de licenças.

A hierarquia inicial de referência é:

Prioridade | Tag | Grupo original | Amount original

1 | STAFF | STAFF | —

2 | Moderador | Mod | —

3 | SPIRIT | l_spirit | 1015

4 | CHAOS | l_chaos | 985

5 | FEY | l_fey | 950

6 | DEMONIC | l_demonic | 915

7 | CELESTIAL | l_celestial | 885

8 | CORRUPTED | l_corrupted | 850

9 | ELDER | l_elder | 815

10 | BUFFOON | l_buffoon | 785

11 | PRIMAL_TEK | l_primal_tek | 685

12 | OMEGA | l_omega | 585

13 | FABLED | l_fabled | 485

14 | APEX | l_apex | 385

15 | ELEMENTAL | l_elemental | 285

16 | ALPHA | l_alpha | 185

17 | TOXIC | l_toxic | 85
Essa tabela representa os dados encontrados no arquivo original e deverá servir como referência inicial, não como cadastro definitivo das licenças atualmente comercializadas.

Não utilize o campo `Amount` como substituto automático de uma prioridade administrativa explicitamente definida.

Consulte as licenças reais cadastradas no ARKLAND.

### Descoberta e aprovação administrativa
O sistema poderá consultar automaticamente as licenças e os grupos de permissões existentes para facilitar o cadastro das tags.

Entretanto, uma tag descoberta automaticamente não deverá entrar em funcionamento sem confirmação administrativa.

O painel deverá permitir:

- Consultar tags identificadas.
- Confirmar tags.
- Ativar ou desativar tags.
- Editar o nome de exibição.
- Definir a cor.
- Associar grupos de permissões.
- Associar licenças.
- Organizar a ordem de prioridade.
- Visualizar a hierarquia final.
- Identificar tags pendentes de aprovação.
A administração deverá confirmar a ordem de exibição antes de sua aplicação.

A prioridade dos cargos administrativos sobre as licenças deverá ser preservada.

### Exemplos obrigatórios
Jogador com FEY, CHAOS e SPIRIT:

Exibir somente SPIRIT.

Jogador com SPIRIT e Moderador:

Exibir somente Moderador.

Jogador com SPIRIT, Moderador e STAFF:

Exibir somente STAFF.

Jogador sem nenhuma tag válida:

Exibir o nome normalmente, sem tag.

Uma licença expirada não deverá continuar concedendo uma tag indevidamente.

A tag deverá ser recalculada quando houver alterações nas licenças ou permissões do jogador.

Não utilize a tag visual para conceder permissões administrativas. A tag representa uma condição já autorizada pelo sistema de permissões.

## 16. Icons — funcionalidade descartada
Não implemente o bloco `Icons` nesta versão.

Não associe ícones às licenças.

Não importe caminhos de assets do jogo utilizados pelo plugin original.

Não implemente ícones administrativos, de tribos ou de jogadores como parte desta entrega.

A diferenciação visual das licenças deverá acontecer através das tags textuais e de suas respectivas cores.

A funcionalidade poderá ser considerada futuramente, mas não deverá aumentar a complexidade desta implementação.

## 17. ChatColors
Implemente gerenciamento centralizado das cores utilizadas pelo chat.

Referência original:

```
"ChatColors": [
  {
    "ForAdmin": true,
    "ForEveryone": false,
    "HideTribeName": false,
    "MessageColor": "1, 1, 1, 1",
    "NameColor": "0.18, 0.8, 0.44, 1",
    "TribeNameColor": "0.90, 0.49, 0.13, 1",
    "OverrideGraySelfNameColor": true,
    "PermissionGroups": [],
    "TribeIds": [],
    "SteamIds": []
  },
  {
    "ForAdmin": false,
    "ForEveryone": true,
    "HideTribeName": false,
    "MessageColor": "1, 1, 1, 1",
    "NameColor": "0.18, 0.8, 0.44, 1",
    "TribeNameColor": "0.90, 0.49, 0.13, 1",
    "OverrideGraySelfNameColor": true,
    "PermissionGroups": [],
    "TribeIds": [],
    "SteamIds": []
  }
]
```
Disponibilize gerenciamento visual das cores através do painel administrativo.

Permita personalizar:

- Cor da mensagem.
- Cor do nome do jogador.
- Cor do nome da tribo.
- Cor das tags.
- Cor da identificação dos mapas.
- Cor da identificação do Discord.
O ID individual deverá permanecer legível e visualmente integrado à apresentação do nome do jogador.

Utilize seletores visuais de cores, evitando exigir que a administração informe manualmente valores RGBA.

O sistema deverá converter os valores para o formato exigido pelo jogo.

Valide os intervalos aceitos pela API utilizada.

Não copie valores inválidos encontrados no arquivo original.

A definição das cores não deverá interferir na hierarquia de tags.

As mensagens vindas do Discord deverão utilizar o mesmo mecanismo central de personalização, evitando configurações duplicadas.

Respeite as limitações de formatação do Discord. Não presuma que cores RGBA do ARK possam ser reproduzidas diretamente em mensagens comuns do Discord.

## 18. Maps — identificação dos servidores
O arquivo original utiliza um bloco `Maps` contendo configurações individuais dos mapas.

Exemplo:

```
"Maps": {
  "Ragnarok [Primal Fear]": {
    "MasterServerRunDiscordBot_OnlySetOnOneServer": true,
    "Label": "Ragnarok [Primal Fear]",
    "Color": "0.95, 0.62, 0.10, 0.8"
  }
}
```
O arquivo original apresenta os seguintes identificadores:

- Ragnarok [Primal Fear]
- Alps [Primal Fear]
- Alps [OMEGA]
- Valgero [OMEGA]
- The Island [HYBRIDOS]
- RESERVA
- Discord
Não trate essa relação como uma lista definitiva ou obrigatória de servidores.

O Chat Arkland deverá consultar o cadastro real de servidores existente no projeto.

Cada mapa deverá possuir:

- Identificador interno estável.
- Nome de exibição.
- Cor configurável.
- Associação à instância correspondente.
- Estado de participação no Chat Global.
Permita que novos mapas sejam incorporados ao sistema sem necessidade de recompilar o plugin.

Não implemente `DefaultIcon` nesta versão.

### MasterServerRunDiscordBot_OnlySetOnOneServer
O plugin original utiliza essa chave para determinar qual servidor executará o bot do Discord.

O Chat Arkland não deverá depender obrigatoriamente de um mapa específico para manter a comunicação com o Discord.

Investigue os serviços de integração existentes no ARKLAND e reaproveite a infraestrutura centralizada, quando adequada.

Garanta que apenas um mecanismo autorizado realize cada encaminhamento ao Discord, evitando que todas as instâncias publiquem a mesma mensagem simultaneamente.

## 19. Integração com o Discord
A integração deverá utilizar o canal global do ARKLAND.

O segundo arquivo original apresenta como referência funcional:

```
"GlobalChat": {
  "Enabled": true,
  "GlobalChatChannelId": "1550610698332012724",
  "ShowMap": true,
  "AllowDiscordToIngame": true
}
```
O ID informado deverá ser conferido com o cadastro atual de canais do ARKLAND.

Não substitua automaticamente uma configuração válida já existente.

### GlobalChat.Enabled
Valor padrão: `true`.

Permite ativar ou desativar a integração global com o Discord.

### GlobalChatChannelId
Identifica o canal do Discord utilizado para comunicação global.

Deverá estar integrado à configuração de canais existente no ARKLAND e no Lumo.

Não crie configurações independentes e conflitantes para o mesmo canal.

### ShowMap
Valor padrão: `true`.

Deverá permitir a identificação do mapa de origem das mensagens encaminhadas ao Discord.

### AllowDiscordToIngame
Valor padrão: `true`.

Permite que mensagens enviadas no canal global do Discord sejam encaminhadas aos servidores ARK.

Quando desativado, o encaminhamento Discord → Jogo deverá ser interrompido sem necessariamente interromper Jogo → Discord.

### HostServerDiscordId
O arquivo original utiliza o identificador:

`1440802112601854159`

Verifique se corresponde ao servidor oficial atualmente configurado no ARKLAND.

Reaproveite o cadastro existente.

### Token
Não armazene tokens do Discord diretamente no arquivo de configuração distribuído aos servidores.

Reaproveite o serviço autorizado de integração com o Discord e seu mecanismo seguro de armazenamento de credenciais.

Não exponha tokens no painel, nos logs ou em respostas de APIs.

### ShowCodeBlocks
O arquivo original possui essa configuração de apresentação das mensagens.

Analise sua necessidade dentro do novo mecanismo de formatação.

Não introduza blocos de código que prejudiquem a legibilidade do chat ou contrariem o padrão visual definido para o ARKLAND.

### Use24HourTimeFormat
O formato de horário será sempre de 24 horas.

Não disponibilize essa chave como opção administrativa.

Não utilize AM ou PM.

### Comunicação Jogo → Discord
Preserve a identificação individual do jogador nas mensagens globais encaminhadas ao Discord.

Exemplo:

`[21:35][Valgero [OMEGA]] <DEMONIC> Jogador (125) [Tribo]: Olá, pessoal!`

O ID exibido deverá corresponder ao mesmo identificador utilizado dentro do jogo.

Isso não significa disponibilizar os comandos `/pm` e `/r` através do Discord.

## 20. Comunicação Discord → Jogo
Utilize como referência:

`[HH:mm][Discord] <TAG> Jogador: Mensagem`

Exemplo:

`[21:35][Discord] [BøT] Ciano: Olá, pessoal!`

A apresentação das mensagens deverá respeitar o mecanismo centralizado de identificação, tags, cores e hierarquia.

Reaproveite a vinculação existente entre contas Discord e contas dos jogadores.

Não implemente um novo processo de vinculação de contas.

O sistema deverá tratar adequadamente mensagens de usuários vinculados e não vinculados, respeitando as permissões e regras existentes do ARKLAND.

Não atribua IDs fictícios a usuários do Discord, bots ou ao Lumo.

Caso seja necessária a apresentação do ID de um jogador vinculado, utilize exclusivamente o identificador real já associado à sua conta.

Não conceda tags administrativas com base em nomes de usuário, apelidos ou textos enviados pelo Discord.

As mensagens deverão ser tratadas como conteúdo textual, nunca como comandos administrativos executáveis.

### DefaultChatFromDiscord
O arquivo original contém:

- `ServerTag`
- `TagColor`
- `MessageColor`
- `NameColor`
- `Icon`
Reaproveite os comportamentos necessários através do sistema central de formatação.

A identificação de origem deverá ser `Discord`.

As cores deverão utilizar o gerenciamento centralizado.

Não implemente `Icon`.

Não mantenha configurações de cores duplicadas.

### IngameChatFromDiscordConfig
Descarte integralmente esse bloco.

Não implemente uma segunda hierarquia de tags e cores exclusiva para mensagens originadas no Discord.

Utilize o sistema centralizado de tags e a vinculação de contas existente.

## 21. Integração com o Lumo
O Lumo deverá continuar sendo o assistente de comunicação e orientação do ARKLAND.

O Chat Arkland deverá atuar como infraestrutura de transporte das mensagens entre os servidores e o Discord.

Localize a implementação atual do Lumo, considerando que determinados componentes internos ainda poderão utilizar a nomenclatura Bobonic.

Reaproveite explicitamente:

- Configuração do canal global.
- Serviços de comunicação.
- Identificação do Lumo.
- Mecanismos de envio de mensagens.
- Integrações existentes com o Discord.
As mensagens do Lumo deverão seguir uma apresentação própria:

`[HH:mm][Discord] Lumo: Mensagem`

Não atribua ao Lumo um ID de jogador destinado ao comando `/pm`.

O Chat Arkland deverá permitir que mensagens autorizadas do Lumo sejam encaminhadas aos servidores.

Não descarte indiscriminadamente todas as mensagens de bots do Discord, pois isso impediria a comunicação do Lumo.

Implemente identificação confiável das mensagens autorizadas.

O Chat Arkland não deverá assumir responsabilidades próprias do Lumo, como:

- Respostas automáticas por palavras-chave.
- Orientações aos jogadores.
- Lembretes do BetLand.
- Lembretes de votações.
- Dicas automáticas.
- Informações de suporte.
- Informações sobre limites.
- Apresentação de funcionalidades do site.
Esses comportamentos deverão permanecer sob responsabilidade do Lumo.

Garanta que mensagens enviadas pelo Lumo não provoquem ciclos de encaminhamento ou respostas automáticas repetidas.

## 22. PollRate
O arquivo original apresenta:

```
"PollRate": 250
```
Não preserve a unidade original automaticamente.

No Chat Arkland, a unidade deverá ser obrigatoriamente segundos.

Nova referência:

```
"PollRate": 1.0
```
Requisitos:

- Valor padrão de um segundo.
- Configurável pelo painel administrativo.
- Aceitar valores decimais.
- Não utilizar milissegundos como unidade administrativa.
- Validar valores inválidos.
- Realizar consultas de maneira assíncrona.
- Evitar sobrecarga no banco de dados.
- Evitar bloqueio da thread principal do jogo.
Caso sejam utilizadas estratégias complementares de comunicação orientada a eventos, documente como essa configuração se relaciona com elas.

## 23. Banco de dados
Os arquivos originais apresentam dois blocos independentes:

`Mysql`

e

`Database`

O primeiro utiliza:

- `MysqlHost`
- `MysqlUser`
- `MysqlPass`
- `MysqlPort`
- `MysqlDB`
O segundo utiliza:

- `host`
- `user`
- `port`
- `password`
- `database`
Esses blocos deverão ser consolidados em uma única configuração de banco de dados.

O ARKLAND já possui infraestrutura MySQL utilizada por outros sistemas.

Antes de criar qualquer nova estrutura:

- Identifique a conexão existente.
- Analise as tabelas atuais.
- Identifique os mecanismos de autenticação.
- Identifique os serviços que já acessam o banco.
- Identifique os registros e identificadores individuais dos jogadores.
- Reaproveite a infraestrutura autorizada.
- Determine quais informações podem ser consultadas diretamente.
- Determine quais informações deverão ser acessadas através de serviços existentes.
Caso seja necessário criar um identificador público próprio para o Chat Arkland, garanta sua unicidade no banco de dados e sua associação persistente à identidade real do jogador.

Crie somente as tabelas necessárias ao Chat Arkland.

Não altere ou remova tabelas de outros sistemas sem necessidade comprovada.

Utilize migrações versionadas e reversíveis.

Não replique credenciais reais dos arquivos originais no código-fonte, na documentação ou em arquivos públicos.

Utilize consultas parametrizadas, permissões adequadas e mecanismos seguros de conexão.

## 24. Funcionalidades descartadas do DiscordConfig.json
As funcionalidades abaixo não deverão ser reproduzidas no Chat Arkland.

### ShowServerStatusChannels
Descartado.

O ARKLAND já possui monitoramento e publicação do status dos servidores.

Reaproveite os dados existentes quando forem necessários.

Não crie outro sistema concorrente de status.

### RconCommands
Descartado.

Não implemente execução de comandos RCON através do Discord como funcionalidade do Chat Arkland.

Isso não impede a utilização interna de mecanismos autorizados de comunicação, quando tecnicamente necessária.

### JoinLeaveMessages
Descartado.

Não implemente um canal independente no Discord para publicação de entradas e saídas de jogadores.

Preserve o `CrossMapNotifications` dentro do jogo.

### PlayerList
Descartado.

Não implemente publicação automática de listas de jogadores em canais do Discord.

Preserve o comando `/online` dentro do jogo.

### PermanentMessages
Descartado integralmente.

Não implemente painéis permanentes no Discord com botões destinados a:

- Vinculação de contas.
- Convite do bot.
- Concessão de cargos.
- Resgate de pontos diários.
- Autoexpulsão de jogadores.
- Consulta de identificadores.
- Salvamento de mundos.
- Recarregamento de plugins.
- Execução de eventos.
- Comandos administrativos.
Essas funcionalidades não fazem parte do escopo do Chat Arkland.

### SteamLink
Descartado.

O ARKLAND já possui mecanismo próprio de vinculação de contas.

Reaproveite essa vinculação.

Não crie novos códigos de vinculação, sincronização independente de apelidos ou concessão automática de cargos por esse mecanismo.

### RolePermissionSync
Descartado.

Não implemente sincronização automática independente entre cargos do Discord e grupos de permissões do ARK.

A responsabilidade pelas permissões deverá permanecer com o sistema central existente.

### TribeWebhookNames
Descartado.

Não implemente integração de chats ou registros de tribos com servidores particulares do Discord.

Não implemente comandos de vinculação ou desvinculação de tribos com canais externos.

### StatusPollRateSec
Descartado.

Valor original: cinco segundos.

Reaproveite o monitoramento existente do ARKLAND.

### PlayerListUpdateRateSecs
Descartado.

Valor original: 30 segundos.

A lista automática de jogadores no Discord não será implementada.

### JoinLeaveUpdateRateSecs
Descartado.

Valor original: 30 segundos.

Não confunda essa exclusão com as notificações entre mapas dentro do jogo.

### ResponsePollRate
Descartado, desde que a análise técnica confirme que nenhuma dependência necessária à comunicação global será removida indevidamente.

Não reproduza rotinas de consulta destinadas exclusivamente a respostas de comandos administrativos executados pelo Discord.

Caso alguma operação interna necessite de um mecanismo semelhante, implemente-o de maneira adequada à arquitetura própria do Chat Arkland e documente a necessidade.

## 25. Messages — mensagens do sistema
O Codex terá autonomia para elaborar integralmente o bloco `Messages` do novo plugin.

Não é necessário reproduzir literalmente as mensagens dos dois arquivos originais.

Crie mensagens de acordo com as funcionalidades efetivamente implementadas.

Todas as mensagens destinadas aos jogadores e à administração deverão estar em português do Brasil.

Isso inclui:

- Notificações.
- Avisos.
- Confirmações.
- Mensagens de erro.
- Instruções de utilização.
- Sintaxe dos comandos.
- Notificações de entrada e saída.
- Mensagens privadas.
- Instruções de utilização dos IDs individuais.
- Respostas do comando `/online`.
- Avisos de censura.
- Avisos de controle de spam.
- Informações de permissões.
- Mensagens relacionadas à disponibilidade do sistema.
As instruções de mensagens privadas deverão utilizar exemplos coerentes com a sintaxe `/pm ID Mensagem` e `/r Mensagem`.

Centralize os textos em um único bloco `Messages` dentro do `config.json`.

Permita sua personalização através do painel administrativo e sincronização com todas as instâncias.

Documente as variáveis dinâmicas aceitas em cada mensagem.

Valide os parâmetros antes de aplicar alterações.

Não inclua mensagens relacionadas a funcionalidades descartadas.

Não mantenha textos de exemplo em inglês.

Não utilize o bloco de mensagens como local para duplicar configurações operacionais, como `ClusterName`.

## 26. Painel administrativo — Chat Arkland
Crie uma área própria no painel administrativo do site denominada **Chat Arkland**.

Utilize os padrões visuais, mecanismos de autenticação e estrutura de navegação já existentes no ARKLAND.

Não crie um painel externo independente.

A área deverá organizar as configurações de maneira clara, evitando apresentar diretamente um arquivo JSON extenso como única forma de gerenciamento.

### Configurações gerais
Disponibilize:

- Estado do sistema.
- Nome do cluster.
- Configurações de comunicação global.
- Identificação dos jogadores.
- Intervalo de consultas.
- Controle de spam.
- Configurações de exibição.
A apresentação do ID individual dos jogadores deverá ser considerada parte integrante do formato do chat, e não uma funcionalidade dispensável de personalização visual.

### Funcionalidades
Disponibilize controles individuais de ativação e desativação.

Estados iniciais:

Funcionalidade | Estado padrão

Chat Global | Ativado

Comunicação entre mapas | Ativada

Integração com Discord | Ativada

Discord → Jogo | Ativada

CrossMapNotifications | Ativada

OnlinePlayersCommand | Ativada

PrivateMessages | Ativada

BadWords | Desativada

Debug | Desativado

### Tags e licenças
Disponibilize:

- Descoberta de licenças existentes.
- Confirmação administrativa.
- Gerenciamento das tags.
- Ordenação de prioridades.
- Personalização das cores.
- Associação às permissões.
- Ativação e desativação.
- Prévia da apresentação.
A prévia deverá incluir o ID individual do jogador, seguindo a estrutura oficial do chat.

Não disponibilize gerenciamento de ícones nesta versão.

### Mapas
Exiba os servidores cadastrados no ARKLAND.

Permita gerenciar sua participação no Chat Global, nome de exibição e cores.

A quantidade de servidores deverá ser dinâmica.

### Filtro de palavras
Disponibilize uma interface específica para cadastrar, editar e excluir palavras censuradas.

Apresente claramente se o filtro está ativo ou desativado.

### Discord
Exiba as configurações necessárias à integração global.

Reaproveite as configurações compartilhadas com o Lumo e os serviços existentes.

Não exponha credenciais sensíveis.

### Mensagens
Disponibilize gerenciamento das mensagens utilizadas pelo plugin.

Apresente as variáveis dinâmicas disponíveis para cada mensagem.

### Sincronização
Disponibilize informações suficientes para a administração identificar:

- Última atualização das configurações.
- Versão atual das configurações.
- Instâncias conectadas.
- Instâncias sincronizadas.
- Instâncias com configurações desatualizadas.
- Falhas de sincronização.
- Última comunicação de cada instância.
As alterações deverão ser validadas antes de serem publicadas.

## 27. Prevenção de mensagens duplicadas e ciclos
A comunicação entre múltiplos servidores, banco de dados, Discord e Lumo exige mecanismos confiáveis de identificação das mensagens.

Implemente:

- Identificadores únicos de mensagens.
- Identificação da origem.
- Identificação do tipo de mensagem.
- Controle de encaminhamento.
- Deduplicação.
- Tratamento de reconexões.
- Controle de mensagens já processadas.
- Expiração adequada de mensagens pendentes.
Não confunda o identificador único de uma mensagem com o identificador individual e persistente do jogador.

Uma mensagem recebida de outro mapa não deverá ser interpretada como uma nova mensagem local e reenviada novamente ao cluster.

Uma mensagem originada no Discord não deverá retornar ao Discord como uma nova mensagem do jogo.

Uma mensagem enviada pelo Lumo não deverá provocar encaminhamentos infinitos.

Não permita que múltiplas instâncias publiquem simultaneamente a mesma mensagem no Discord.

Documente o mecanismo adotado para garantir essas condições.

## 28. Desempenho e estabilidade
O Chat Arkland deverá ser desenvolvido considerando o funcionamento contínuo dos servidores ARK.

Requisitos técnicos:

- Operações de rede assíncronas.
- Consultas ao banco de dados não bloqueantes.
- Filas de processamento controladas.
- Limites de memória.
- Tratamento de exceções.
- Reconexão automática.
- Encerramento seguro.
- Remoção adequada de hooks e callbacks.
- Validação de ponteiros e referências do jogo.
- Compatibilidade com reinicializações dos servidores.
- Tratamento de caracteres Unicode e acentuação.
- Proteção contra injeção de comandos e formatação indevida.
- Proteção contra mensagens excessivamente grandes.
- Proteção contra colisões e associações incorretas de IDs individuais.
Respeite as restrições de acesso às APIs do jogo a partir de threads secundárias.

Caso determinada operação precise ser executada na thread principal, utilize um mecanismo seguro de encaminhamento para essa thread.

O Chat Arkland não deverá provocar travamentos, quedas ou degradação significativa do desempenho dos servidores.

## 29. Compatibilidade com os sistemas existentes
Não desenvolva funcionalidades paralelas quando o ARKLAND já possuir mecanismos adequados.

Reaproveite explicitamente:

- Cadastro de servidores.
- Monitoramento de jogadores.
- Monitoramento de sessões.
- Identificação individual de jogadores.
- Informações de tribos.
- Licenças.
- Permissões.
- Vinculação Discord e Steam.
- Infraestrutura do Discord.
- Lumo.
- Banco de dados.
- Autenticação administrativa.
- Estrutura do painel administrativo.
Para cada integração reaproveitada, documente:

1. Qual componente existente foi localizado.
2. Onde está implementado.
3. Como funciona.
4. Como o Chat Arkland irá consumi-lo.
5. Quais adaptações foram necessárias.
6. Quais dependências foram introduzidas.
Não considere uma integração concluída apenas porque existe uma função com nome semelhante.

Verifique efetivamente seu comportamento e sua compatibilidade.

## 30. Testes obrigatórios
Realize testes individuais e integrados.

Valide, no mínimo:

- Carregamento do plugin.
- Encerramento seguro.
- Comunicação dentro do mesmo mapa.
- Comunicação entre dois ou mais mapas.
- Encaminhamento Jogo → Discord.
- Encaminhamento Discord → Jogo.
- Encaminhamento de mensagens do Lumo.
- Ausência de duplicidade.
- Ausência de ciclos de mensagens.
- Notificações de conexão.
- Notificações de desconexão.
- Funcionamento do `/joinleave`.
- Funcionamento do `/online`.
- Paginação de jogadores.
- Exibição correta dos IDs individuais no chat.
- Exibição dos mesmos IDs individuais no `/online`.
- Unicidade dos IDs em todo o cluster.
- Persistência dos IDs após reconexões.
- Persistência dos IDs após reinicializações.
- Persistência dos IDs após transferências entre mapas.
- Persistência dos IDs após alteração do nome do personagem.
- Funcionamento do `/pm ID Mensagem`.
- Funcionamento do `/r Mensagem`.
- Mensagens privadas entre jogadores do mesmo mapa.
- Mensagens privadas entre jogadores de mapas diferentes.
- Mensagens privadas entre jogadores com nomes iguais.
- Tratamento de IDs inexistentes ou inválidos.
- Tratamento de destinatários desconectados.
- Tratamento de tentativas de enviar mensagens para si mesmo.
- Funcionamento do `/r` sem conversa anterior.
- Preservação da privacidade das mensagens privadas.
- Censura por asteriscos.
- Controle de spam.
- Alteração de configurações pelo painel.
- Sincronização entre instâncias.
- Alteração das cores.
- Alteração de tags.
- Hierarquia entre licenças.
- Prioridade de Moderador e STAFF.
- Expiração de licenças.
- Indisponibilidade temporária do banco de dados.
- Indisponibilidade temporária do Discord.
- Reinicialização de servidores.
- Inclusão e remoção de mapas.
- Preservação da privacidade dos canais não globais.
Não considere uma funcionalidade validada apenas porque o código compilou.

Diferencie testes unitários, testes simulados e testes realizados efetivamente dentro dos servidores ARK.

## 31. Migração e substituição do sistema atual
O Chat Arkland deverá ser preparado para substituir o mecanismo de chat atualmente utilizado.

Entretanto, não desative ou remova imediatamente o plugin atual antes de validar o funcionamento do novo sistema.

Elabore um procedimento seguro de migração.

Inclua:

- Backup das configurações atuais.
- Identificação das dependências do sistema antigo.
- Ambiente ou servidor de testes.
- Validação isolada do Chat Arkland.
- Verificação de conflitos entre hooks.
- Verificação de duplicidade de mensagens.
- Verificação da integridade dos identificadores individuais.
- Procedimento de implantação.
- Procedimento de reversão.
Não mantenha dois mecanismos ativos realizando simultaneamente o mesmo encaminhamento de mensagens em produção.

Não remova arquivos antigos ou dados necessários a uma eventual reversão sem autorização administrativa.

## 32. Integração com a Central de Status do ARKLAND
Caso a Central de Status das funcionalidades do ARKLAND já esteja implementada, registre o Chat Arkland nela.

Apresente o estado real do sistema e de suas funcionalidades.

Diferencie funcionalidades:

- Em desenvolvimento.
- Em testes.
- Parcialmente funcionais.
- Funcionais.
- Finalizadas.
- Temporariamente indisponíveis.
Não apresente uma funcionalidade como finalizada quando ela ainda não tiver sido validada.

## 33. Documentação e entregáveis
Ao concluir o desenvolvimento, disponibilize:

- Código-fonte completo do Chat Arkland.
- Estrutura independente do plugin.
- Arquivos necessários à compilação.
- Binário compilado, quando o ambiente permitir.
- Arquivo único `config.json`.
- Esquema documentado das configurações.
- Migrações do banco de dados.
- Integração com o painel administrativo.
- Integração com os serviços existentes.
- Documentação dos comandos.
- Documentação do sistema de identificação individual dos jogadores.
- Documentação do formato oficial das mensagens.
- Documentação do funcionamento do `/pm` e `/r`.
- Documentação das mensagens.
- Documentação das permissões.
- Documentação das integrações.
- Instruções de instalação.
- Instruções de atualização.
- Instruções de diagnóstico.
- Procedimento de reversão.
- Relatório dos testes realizados.
Produza também uma matriz de correspondência entre as chaves dos arquivos originais e o novo sistema, classificando cada uma como:

- Mantida.
- Reorganizada.
- Unificada.
- Reaproveitada através de sistema existente.
- Substituída.
- Descartada.
Essa matriz deverá permitir verificar que nenhuma funcionalidade aprovada foi esquecida e nenhuma funcionalidade descartada foi implementada indevidamente.

## 34. Diretrizes finais de execução
Não se limite a elaborar um planejamento teórico.

Realize a investigação do projeto, identifique os componentes existentes, desenvolva a implementação e execute os testes tecnicamente disponíveis.

Não invente APIs, funções, tabelas, hooks ou serviços sem verificar sua existência.

Não presuma que uma integração funciona sem validá-la.

Não introduza funcionalidades adicionais que contrariem as decisões deste documento.

Caso encontre uma limitação técnica que impeça determinado comportamento, documente:

- A funcionalidade afetada.
- A causa da limitação.
- As evidências encontradas.
- As alternativas possíveis.
- Os impactos de cada alternativa.
Não modifique silenciosamente um requisito aprovado.

Não realize alterações irreversíveis nos servidores de produção sem autorização.

O resultado esperado é um sistema próprio, independente, estável, integrado, centralizado e administrável, construído especificamente para as necessidades do ARKLAND.

## Resumo das definições obrigatórias
**Nome oficial do plugin:** Chat Arkland.

**Arquivo de configuração:** config.json.

**Idioma das interfaces e mensagens:** português do Brasil.

**Fonte central das configurações compartilhadas:** banco de dados.

**Gerenciamento administrativo:** painel do site ARKLAND.

**Integração de comunicação:** servidores ARK, Discord e Lumo.

**Formato oficial do chat global:**

`[HH:mm][MAPA] <TAG> Jogador (ID) [Tribo]: Mensagem`

**Identificação individual:** ID único, persistente e compartilhado entre todos os mapas.

**Mensagem privada:** `/pm ID Mensagem`.

**Resposta privada:** `/r Mensagem`.

**Consulta de jogadores:** `/online`.

**Notificações de conexão e desconexão:** `/joinleave`.

**PollRate padrão:** 1 segundo, configurável e com suporte a valores decimais.

**Horário:** obrigatoriamente 24 horas.

**Nome padrão do jogador:** nome do personagem.

**Hierarquia de tags:** somente a tag de maior prioridade, com cargos administrativos acima das licenças.

**Ícones:** não implementar nesta versão.

**Filtro de palavras:** censura por asteriscos, sem impedir automaticamente o envio da mensagem.

**Mensagens do sistema:** elaboradas pelo Codex em português do Brasil, conforme as funcionalidades efetivamente implementadas.

**Independência:** construir um plugin inteiramente novo, sem incorporar o mecanismo de chat dentro de outro plugin existente.