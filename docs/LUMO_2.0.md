# Lumo 2.0 — Chat do Jogo e imagens

## Chat do Jogo

O Chat do Jogo usa o Gateway do bot Lumo e o canal Discord já ligado à ponte de chat dos servidores. O Lumo não conecta diretamente aos mapas nem cria uma segunda ponte. A integração, respostas e anúncios começam desativados. O ID do canal do jogo deve ser diferente do canal global.

Na página administrativa **Lumo — Comunicação > Chat do Jogo**, configure o ID do servidor, o canal integrado e ative a integração. Para ler mensagens encaminhadas pela ponte, habilite **Aceitar mensagens da ponte (webhooks)**. Essa permissão só vale para o canal escolhido. Os dados de nickname, licença e tribo extraídos do envelope nunca são usados para autenticar um jogador. A compatibilidade deve ser verificada primeiro com uma simulação e, depois, com o canal de teste.

O Lumo responde com texto simples. Ele publica somente o conteúdo que deve aparecer depois dos dois-pontos; o plugin de ponte acrescenta horário, origem e nome. Mensagens agrupadas que a ponte atualiza por edição são processadas apenas pelas novas linhas. Mensagens do próprio bot/Lumo, IDs já vistos, menções próprias e retransmissões reconhecidas são descartadas.

O canal possui controles independentes do canal global: ativação, respostas por gatilho, anúncios, assuntos permitidos, intervalos, apresentação global de 10 minutos, cooldown por assunto e por jogador/assunto, limite de 80–250 caracteres e aliases. Respostas dinâmicas de BetLand, votações e SeasonLand usam as fontes internas atuais; quando uma fonte falha, a resposta/anúncio é omitida. A SeasonLand só é anunciada automaticamente quando a fonte informa status ativo. Respostas que ultrapassariam o limite são omitidas em vez de truncadas.

Os anúncios gerais percorrem uma fila rotativa de assuntos habilitados a cada 30–60 minutos. BetLand e votações usam agendas independentes de 3–4 horas e só enviam dados atuais quando há atividade elegível. O estado do próximo envio fica nas configurações para sobreviver a reinicializações. O agendador envia no máximo um anúncio do Chat do Jogo por ciclo e aplica um intervalo entre anúncios.

O painel oferece simulação local de gatilhos e envio manual administrativo com confirmação. O envio manual publica uma única mensagem no canal compartilhado e pode alcançar todos os mapas ligados a ele. Nenhuma mensagem de teste é enviada automaticamente.

## Upload de imagens da Comunicação

Os campos de imagem complementar e miniatura aceitam URLs HTTPS externas como antes ou arquivos PNG, JPEG, GIF e WebP. O upload valida o conteúdo real da imagem, dimensões e limite de 8 MB, cria nomes internos aleatórios e grava os arquivos em `webstore_data/lumo_uploads` (diretório persistente de dados do aplicativo). A prévia autenticada não torna os arquivos públicos.

Ao publicar, imagens enviadas são incluídas como anexos da própria mensagem Discord e referenciadas por `attachment://...`. As mensagens publicadas mantêm os anexos no Discord mesmo após a limpeza local. O último uso é atualizado após confirmação do envio; arquivos sem uso ou referência expiram após 30 dias por padrão, configurável entre 1 e 3.650 dias. A limpeza é idempotente e é executada no acesso administrativo à lista/configuração de imagens, no máximo uma vez por dia.

## Auditoria e limites

São registrados eventos de respostas, bloqueios por cooldown, duplicatas/edições ignoradas, consultas indisponíveis, anúncios, envios manuais, uploads e remoções/limpezas. O Gateway não grava o texto de mensagens dos jogadores. Mensagens encaminhadas por webhook dependem da configuração e do comportamento do plugin de terceiros; o formato não pode ser confirmado apenas pelo código do ARKLAND.

O envio efetivo ao canal do jogo precisa ser validado pela administração no canal de teste: o conteúdo, o formato da ponte e a distribuição aos mapas variam conforme a configuração externa. Nenhum teste de produção/spam é feito durante o build.
