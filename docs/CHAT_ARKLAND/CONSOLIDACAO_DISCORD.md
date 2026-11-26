# Consolidação do canal Discord — serviço 1.12.35

## Comportamento

As mensagens novas de jogadores e do usuário real do Lumo, no servidor e canal configurados, são capturadas com seu texto inicial, horário e autoria. A apresentação é acrescentada ao bloco monoespaçado corrente do Chat Arkland. Um novo bloco é aberto ao atingir os limites do Discord, ou quando anexos/figurinhas exigem outro envio. As mensagens do jogo continuam no mesmo fluxo.

O original só é apagado após confirmar todas as partes da cópia. Edições posteriores não mudam a versão capturada. Jogadores vinculados usam seu ID público permanente; usuários não vinculados incluem o ID Discord para distinguir homônimos. O nome Lumo é reservado à identificação do bot real neste fluxo, sem confiar no apelido de um humano.

Nenhuma mensagem anterior à implantação é reconstruída ou apagada. Outros bots e webhooks continuam fora do fluxo. Mensagens privadas, canais de tribo e aliados não participam desta consolidação.

## Permissões e falhas

No canal, o Lumo precisa de Ver canal, Enviar mensagens, Ler histórico e Gerenciar mensagens; Anexar arquivos é necessário para copiar anexos. O painel Chat Arkland → Discord mostra as permissões efetivas, contagens da fila e links dos originais que exigem atenção.

Anexos são baixados diretamente dos objetos Discord e reenviados como arquivos antes da remoção, sem depender de URL temporária. Arquivos acima do limite do bot, enquetes e componentes interativos que não podem ser copiados integralmente preservam o original e registram ocorrência. Textos longos são divididos sem truncamento; delimitadores de código são neutralizados e menções são desativadas.

Falha antes de tentar publicar permite nova tentativa. Resultado de envio desconhecido fica `uncertain`: o original permanece, sem repetição automática que poderia duplicar conteúdo. Falha ao excluir mantém `copied` e repete somente a remoção. Se o original já foi removido antes da cópia, não é recriado. Não existe transação atômica entre Discord e banco; os estados persistentes evitam declarar sucesso quando a confirmação falta.

## Banco e atualização

A migração [004](../../plugin/ChatArkland/migrations/004_discord_channel_sources_mysql.sql) cria somente `chat_arkland_discord_sources` e registra a versão 4 do esquema. A inicialização aplica a mesma criação de modo idempotente. Não altera o conteúdo das tabelas de mensagens, identidades, configurações, saldos ou sessões. Cópias concluídas e fontes já removidas expiram da fila após um dia; pendências e resultados incertos são preservados.

A DLL 0.1.0 permanece compatível. Atualizar somente a WebStore central após backup consistente do banco e do executável anterior; iniciar pela tarefa persistente do Windows e conferir API, Gateway, permissões e tabela nova. Reversão do executável mantém a tabela aditiva e os dados mais recentes; não restaurar um dump antigo para reverter apenas o código.

## Validação

Os [testes](TESTES.md) documentam os 76 casos aprovados, com 15 cenários novos da consolidação. Após a implantação, usar uma mensagem real de jogador e uma resposta real do Lumo para conferir bloco, autoria, remoção do original e entrega única no jogo. Não interpretar conexão do Gateway ou testes simulados como confirmação desse último passo.

Referência da biblioteca: [discord.py — envio e mensagens](https://discordpy.readthedocs.io/en/stable/api.html#discord.abc.Messageable.send).
