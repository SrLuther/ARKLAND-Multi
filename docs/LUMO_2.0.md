# Lumo 2.0 — Assistente interativo do Discord

O Lumo 2.0 acrescenta um bot Discord baseado no Gateway à central de comunicação já existente. A central continua usando webhook para comunicados administrativos; as duas integrações são independentes. O bot fica **desativado por padrão** e não se conecta até que a administração configure credenciais e IDs válidos.

## Criar e convidar o bot

1. No Discord Developer Portal, crie uma aplicação e adicione um bot.
2. Em **Bot → Privileged Gateway Intents**, habilite **Message Content Intent**. O Lumo precisa ler texto para reconhecer os gatilhos. Não habilite intents de membros ou presença.
3. Convide o bot apenas para o servidor ARKLAND, com as permissões mínimas no canal de interação: visualizar canal, ler histórico, enviar mensagens e incorporar links. Não conceda Administrator.
4. Copie o token do bot uma única vez e guarde-o como segredo. Nunca o publique em chats, capturas de tela, arquivos do repositório ou logs.
5. Ative o modo de desenvolvedor do Discord e copie o ID do servidor, do canal único de interação e, se necessário, do canal oficial de status.

## Configurar no ARKLAND Server Manager

Abra **Lumo → Assistente interativo**. Informe token, ID do servidor e ID do único canal onde o bot pode responder. O canal de status é separado: ao receber uma pergunta sobre servidores, Lumo apenas direciona para esse canal; não cria um segundo monitor de status.

Os quatro gatilhos podem ser ligados/desligados e receber aliases: status dos servidores, Bet Land, licenças e votações. As frases são reconhecidas sem diferenciar acentos e exigem limites de palavra para reduzir falsos positivos. Um nome de criatura isolado, como “Spirit Rex”, não deve ativar uma resposta de licença. Perguntas específicas sobre licença precisam incluir contexto de licença, compra, preço, rendimento, retorno, duração ou validade.

O painel oferece teste local para simular uma pergunta. A prévia consulta as fontes internas reais, mas não envia mensagens ao Discord nem altera o agendamento. Valide os quatro assuntos e as frases usadas pelos jogadores antes de ativar o bot.

## Dados e anúncios automáticos

- **Status:** apenas aponta para o canal configurado.
- **Bet Land:** consulta a campanha pública atual do serviço interno de sorteios. Sem campanha aberta, informa que não há sorteio aberto; falha de consulta é tratada como indisponibilidade, nunca como dado confirmado.
- **Licenças:** consulta catálogo e bônus de TimedPoints atuais. O retorno é uma estimativa baseada somente no bônus adicional informado pelo sistema; não é garantia de lucro.
- **Votações:** mostra apenas enquetes abertas retornadas pelo serviço interno.
- **Anúncios:** Bet Land e votações são categorias independentes. Quando habilitadas, cada uma agenda publicação aleatória entre 180 e 240 minutos, somente enquanto existir item aberto. A agenda é persistida; na volta após indisponibilidade não há sequência de mensagens atrasadas. Existe ainda intervalo mínimo entre anúncios das categorias.

O canal de interação também é o destino das publicações automáticas. A prévia não envia mensagens; ao ativar os anúncios, o bot poderá publicar nesse canal. O recurso não publica votos, não cria sorteios e não altera licenças.

## Proteções e limites

- Mensagens privadas, webhooks, bots e mensagens de outros servidores/canais são ignorados. O filtro de servidor e canal ocorre antes da leitura do texto.
- O Gateway usa somente intents de servidor, mensagens e conteúdo de mensagens.
- Menções automáticas são desativadas nas respostas; texto de jogador não é gravado no histórico de auditoria.
- Há limites por jogador, por gatilho, globais e por hora. Os valores podem ser ajustados na tela administrativa.
- O token é criptografado pelo armazenamento de configurações da aplicação e nunca é retornado à página. Se a chave de criptografia não estiver disponível, a API recusa salvar o token.
- Não execute duas instâncias do WebStore com o mesmo bot habilitado: o lock de instância do WebStore evita dois schedulers locais no mesmo host.

## Diagnóstico e recuperação

O estado do Gateway, o último erro sem credenciais, a última resposta e o estado do agendador são exibidos na tela administrativa. Se o bot aparecer desconectado:

1. Confirme que o bot continua no servidor e tem as permissões mínimas no canal selecionado.
2. Confirme que Message Content Intent está ligado no Portal.
3. Confira os IDs numéricos e a chave de criptografia configurada no servidor.
4. Se o token foi regenerado, salve o novo token no painel. O campo vazio preserva a credencial atual; use “Remover token salvo” para apagar.
5. Salve a configuração para reiniciar a conexão. O Lumo não enviará mensagem de verificação.

Para reverter, desative **Ativar Lumo 2.0**, salve e confirme no painel o estado “Desconectado”. Isso encerra o Gateway sem remover o editor de comunicados/webhook.

## Release e limites conhecidos

O recurso inclui teste local sem publicação real. A validação final do comportamento no Discord requer um servidor/canal de teste da comunidade e configuração administrativa: a aplicação não envia mensagens reais durante build ou teste automatizado. Os contadores de atividade do processo reiniciam quando o WebStore reinicia; os eventos de auditoria persistidos continuam disponíveis no banco.
