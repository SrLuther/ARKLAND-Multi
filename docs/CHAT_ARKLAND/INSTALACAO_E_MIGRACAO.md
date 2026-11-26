# Instalação, atualização e reversão

## Situação desta entrega

O código está na branch `feature/chat-arkland`, criada a partir da 1.12.32 em um worktree separado. O checkout de trabalho original possuía alterações e versão antiga; ele não foi sobrescrito. O backend da produção não foi substituído e nenhum mapa foi reiniciado nesta implementação. O ZIP é experimental, não um release final do gerenciador.

A consulta SSH confirmou o mapa 05 com KalsCrossChat e os plugins próprios existentes. Não removemos o legado. Instalar somente a nova DLL contra uma Web Store sem os endpoints novos não ativa o transporte.

## Pré-requisitos do piloto

1. Integrar a branch ao código atual revisado da Web Store, preservando as alterações locais. Atualizar o empacotamento pelos quatro módulos Chat Arkland já adicionados ao spec e pelos assets estáticos. Não publicar o checkout antigo do gerenciador sobre a versão mais recente.
2. Fazer backup consistente do banco central, configurações, executável e assets da Web Store. Preservar também o cadastro de servidores e as configurações do chat legado. Backups com credenciais devem permanecer privados.
3. Subir o backend atualizado em homologação, autenticado e com HTTPS. As tabelas do Chat Arkland são criadas de forma idempotente pela aplicação. As migrações SQL são alternativas para administração controlada, não comandos de limpeza automática; não executá-las em duplicidade nem aplicar `down` como tentativa de corrigir rede.
4. Conferir Administração → Chat Arkland: revisão, guild/canal do Lumo, token apenas como indicador de presença, mapas pela chave permanente e candidatos reais de licença. O sistema não substitui automaticamente um canal já configurado.
5. Escolher dois mapas de homologação para a validação cruzada. O 05 é o piloto anteriormente indicado pelo Ciano; nenhum outro mapa deve ser reiniciado sem autorização específica. Dois jogadores ou duas contas controladas são necessários para verificar privacidade, identificação e respostas entre mapas.

## Instalação observacional

1. Obter a config protegida do mapa no painel. Confirmar a ServerKey com o cadastro, ApiUrl do backend atualizado e ObserveOnly=true. Nunca copiar a ServerKey de outro mapa.
2. Verificar jogadores conectados e a janela de reinício autorizada. Salvar o mundo pelos procedimentos operacionais existentes antes de parar apenas o piloto; confirmar saída completa do processo. Não substituir DLL em uso.
3. Criar `ShooterGame/Binaries/Win64/ArkApi/Plugins/ChatArkland` e colocar apenas `ChatArkland.dll`, `PluginInfo.json` e `config.json`. Todas as dependências próprias do runtime ficam nessa pasta. Não copiar testes, objetos de compilação ou bibliotecas MySQL para Win64.
4. Iniciar somente o piloto e acompanhar o log do ArkApi. Confirmar `Chat Arkland 0.1.0 carregado`, ausência de erros de carregamento e `ChatArkland.Status`. A mensagem de Kals carregado significa observação forçada; não é defeito nem comprovação de relay.
5. No painel, confirmar contato recente, versão e revisão aplicada. O modo observacional não intercepta o chat e não substitui o mecanismo atual. Concluir a etapa de carga/desligamento seguro antes de avançar.

## Ativação isolada e homologação

1. Só depois de validar a observação e ter a janela autorizada, parar o piloto e arquivar externamente a pasta/configuração do chat legado para reversão. Não excluir permanentemente arquivos, não mexer em mapas de produção restantes e não deixar os dois encaminhamentos ativos no mesmo mapa.
2. Conferir que o chat próprio antigo do CustomShop continua desativado. Conferir outros plugins que registrem `/online`, `/pm`, `/r` ou `/joinleave`: o SDK executa comandos registrados antes dos callbacks. Conflitos devem ser isolados ou os comandos novos renomeados no painel. O Chat Arkland não remove registros de outros plugins.
3. Aprovar a participação do piloto no painel. Definir ObserveOnly=false no arquivo local do piloto parado e iniciar. Aprovar tags somente após revisar grupos, validade das licenças e hierarquia. Não inferir permissão pelo nome.
4. Executar o roteiro completo de [testes](TESTES.md), registrar horários, IDs e resultados. Não usar conversas privadas reais como conteúdo de log.
5. Validar um segundo mapa autorizado separadamente. Só considerar a substituição em produção depois de confirmar tráfego cruzado, Discord, Lumo, PM/ACK, transferência, reinício e falhas de rede sem duplicidade.

## Atualização

Preservar o `config.json` atual inteiro, banco e registro permanente de IDs. Comparar SchemaVersion e notas da versão; trocar somente a DLL/PluginInfo com processo parado. Nunca substituir o arquivo configurado pelo modelo de chave vazia incluído no ZIP. Publicações compartilhadas passam pelo painel e geram revisão nova. A atualização da DLL não deve reiniciar outros mapas.

## Reversão

- Configuração ruim: restaurar uma revisão pelo painel, que publica outra revisão. Não apagar a tabela de revisões ou IDs.
- Problema na DLL: salvar/parar apenas o piloto na janela autorizada, preservar sua config/cache, mover a pasta ChatArkland para arquivo externo, restaurar exatamente a configuração/versão do legado e iniciar o piloto. Confirmar que só um relay está ativo.
- Problema no backend: voltar ao executável/assets anteriores de forma controlada; manter tabelas e dados novos para análise. A DLL com rede indisponível preserva o chat nativo, mas isso não recupera automaticamente o relay antigo.
- Não executar `001_down.sql` rotineiramente. Ele destrói somente dados transitórios/configuração do próprio chat e preserva `chat_arkland_players`; exige backup e aprovação. Nunca misturar cópias incompatíveis do contador e associações SteamID→ID.

## Diagnóstico

- `ChatArkland.Status` no console: rede, observação, revisão e tamanhos de fila. Não executa comandos recebidos do Discord.
- Debug no painel produz contadores e estado a cada 30 segundos, sem texto das conversas, chaves ou tokens.
- Sem comunicação recente: conferir endpoint, autenticação, TLS, DNS e se o backend atualizado está publicado. Não apagar saves nem trocar portas do jogo como solução para o chat.
- Observação permanente: conferir Local.ObserveOnly, participação do mapa e KalsCrossChat.dll carregada. Alterar o arquivo de um plugin carregado não descarrega sua DLL.
- Revisão pendente: comparar revisão publicada/aplicada, esperar cache central e PollRate; checar validação e capacidade de gravar o cache local.
- Discord incerto: o envio pode ter chegado ao Discord apesar da falta de confirmação. Não reprocessar às cegas; consultar o evento no canal antes de qualquer decisão manual.
- IDs públicos: preservar banco e contador; nunca "corrigir" divergência zerando IDs. Conferir bootstrap ServerKey e identidade do cadastro antes de qualquer migração.
