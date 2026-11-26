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

## Implantação central — 26/11/2026

[Release 1.12.36](https://github.com/SrLuther/ARKLAND-Multi/releases/tag/v1.12.36) publicada com changelog e instalador completo. O pacote experimental da DLL 0.1.1 foi anexado à mesma release. DLL compilada: SHA-256 `D4345157AF9F09FB0D8E217CC74B29B9B765FD5F94A7C6FEA1A1E7CDC30D2DAC`.

WebStore 1.12.36 aplicada, SHA-256 `ABCF601E1FF8FF9EF61FED89A207D2A499070208443682A12EB6F8EBB906CB9A`. Backup privado consistente do banco (71.768.148 bytes), executável 1.12.35 e configurações preservado em `E:\ARKLAND_Backups\ChatArkland\v1.12.36-20261126`. Não houve mudança de schema ou publicação de configuração: revisão 11 mantida. O arquivo congelado foi inspecionado e seu próprio código de normalização/renderização de emojis executado localmente com resultado esperado; Pillow, módulo da fila e changelog também conferidos.

API pública/local confirmou 1.12.36; tarefa persistente `ARKLAND-WebStore-Update-1.12.36` em execução após desconectar SSH. Gateway online, consolidação pronta sem erro e cinco mapas conectados. Os cinco processos de jogo permaneceram os mesmos.

A instalação das DLLs no piloto foi **adiada automaticamente**: RCON confirmou o 05 ocupado. Nenhum arquivo instalado do plugin foi substituído nessa tentativa. As cinco DLLs Chat Arkland continuam reportando 0.1.0; a correção central do global está disponível, enquanto mensagens privadas/fallback com imagens requerem a DLL 0.1.1. A apresentação no cliente do jogo ainda aguarda confirmação do administrador com mensagem nova.
