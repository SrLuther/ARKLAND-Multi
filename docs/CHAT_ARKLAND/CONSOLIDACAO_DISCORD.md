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

## Implantação conferida — 26/11/2026

- [Release 1.12.35](https://github.com/SrLuther/ARKLAND-Multi/releases/tag/v1.12.35) publicada com instalador completo de 129.547.770 bytes e changelog sincronizado. Nenhuma DLL nativa recompilada nesta release.
- Arquivo congelado da WebStore inspecionado: contém o módulo da fila, workers de cópia/exclusão, interface, Pillow e metadados 1.12.35. SHA-256: `F0E664EACA798D520E80DB2683D10A4D74CE5FC54752A45D14CA4A8C7520CB68`.
- Backup privado do executável 1.12.34, configurações e dump consistente de 70.689.929 bytes em `E:\ARKLAND_Backups\ChatArkland\v1.12.35-20261126`. A primeira aplicação foi revertida automaticamente por uma consulta inválida no verificador externo de processos (conversão de array no PowerShell 5); o verificador foi corrigido e a reaplicação concluiu com sucesso. Não foi necessário alterar o produto ou restaurar dados.
- Site e API local confirmaram 1.12.35; tarefa persistente `ARKLAND-WebStore-Update-1.12.35` em execução após desconectar o SSH; Gateway online sem erro. Permissões efetivas confirmadas: ver, enviar, ler histórico, gerenciar mensagens e anexar arquivos. Worker habilitado e pronto.
- Nova tabela confirmada como InnoDB/utf8mb4_unicode_ci, com chave primária e índice da fila. Esquema contém versões 1 e 4. Revisão de configuração preservada em 10; contagens conferidas antes/depois: 1 identidade permanente e 409 sessões do monitoramento.
- Cinco instâncias Chat Arkland conectadas; os processos 01=11724, 02=11816, 03=2476, 04=2616 e 05=6924 permaneceram os mesmos. Não houve troca de DLL ou reinício dos mapas durante esta atualização central.
- No primeiro checkpoint, fila vazia e nenhum erro de captura/consolidação. Ainda é necessário conferir uma mensagem real nova de jogador e uma resposta real do Lumo no canal; nenhuma mensagem artificial foi publicada para simular essa comprovação.
- Na conferência seguinte, uma mensagem real do próprio Lumo entrou naturalmente no fluxo: `lumo=1`, estado `deleted`, um recibo de cópia confirmado e nenhuma ocorrência. Isso confirma cópia e remoção do original no Discord real para esse caso. O caso de humano novo e a conferência visual pelo administrador continuam pendentes. O executável do gerenciador também foi inspecionado: o changelog congelado contém 1.12.35 e as versões intermediárias desde 1.12.26.
