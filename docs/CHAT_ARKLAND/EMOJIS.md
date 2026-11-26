# Emojis básicos — Chat Arkland 0.1.1 / serviço 1.12.36

O ARK pode converter `:)` antes do callback em uma tag como `<img src="Chat.Image" path="/Game/PrimalEarth/Emo/Emo_Smile.Emo_Smile"/>`. O formatador anterior escapava essa tag e a apresentava literalmente. A correção normaliza as tags nativas conhecidas para Unicode e reconstitui imagens locais apenas no campo de corpo da mensagem do jogo.

Assets confirmados por SSH na pasta de conteúdo do 05: `Emo_Blank`, `Emo_Evil`, `Emo_Eyes`, `Emo_Laugh`, `Emo_Sad`, `Emo_Smile`, `Emo_Tongue` e `Emo_Wink`. A definição única está em [chat_arkland_emojis.py](../../plugin/arkshop_web/chat_arkland_emojis.py), gerando [ChatEmojis.h](../../plugin/ChatArkland/src/ChatEmojis.h). Exemplos suportados: `:)`, `:(`, `:D`, `;)`, `:P`, `>:)`, `:|` e `:O`, com variantes de nariz e Unicode indicadas no contrato.

As imagens ficam fora dos spans RichColor para que o decorador de imagem do chat possa processá-las. Trechos comuns continuam escapados; paths externos, assets desconhecidos, atributos extras e rich text arbitrário não são autorizados. URLs são preservadas. A normalização precede limite de tamanho e filtro, evitando contar o caminho do asset como texto digitado.

No Discord, mensagens do jogo usam Unicode, sem paths internos do ARK. Mensagens privadas continuam restritas aos participantes. O serviço central corrige o global dos clientes 0.1.0; mensagens privadas e fallback local precisam da DLL 0.1.1 para renderizar os ícones, porque a DLL anterior escapava toda mensagem desses caminhos.

O build do plugin usa `generate_assets.py --contract-only`: gera contrato/configuração de exemplo, preservando as migrações. Não copiar a configuração de exemplo sobre a configuração real das instâncias.

## Evidências locais

91 testes Python aprovados, incluindo 15 casos dos emojis: oito ícones, tags conhecidas/desconhecidas, atributos inválidos, URL, limites, filtro, runs de cor, cliente legado, global entre mapas, Discord e destinatários privados. Testes C++ aprovados para normalização, imagens, escapes e fallback. Não foram enviadas mensagens artificiais aos jogadores/Discord para declarar validação visual.

## Conferência após implantação

No global do 05, enviar uma mensagem nova com `:) ;) :D :( :P` e conferir que aparecem ícones. Conferir também a cópia Unicode no Discord e, com a DLL 0.1.1 instalada, uma mensagem privada entre dois jogadores. A documentação de implantação deve distinguir o que foi compilado, aplicado e efetivamente visto no jogo.
