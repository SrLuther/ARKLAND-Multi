# Chat Arkland e Lumo — implantação 1.12.34

Data: 26/11/2026.

## Entrega

- Release completo: https://github.com/SrLuther/ARKLAND-Multi/releases/tag/v1.12.34
- Interface e backend da WebStore atualizados. Changelog incluído no gerenciador, no repositório e na API de versão publicada.
- Mensagens de jogo no Discord passam a blocos monoespaçados agrupados, com edição do bloco corrente e preservação de histórico.
- Avisos automáticos do Chat do Jogo compartilham pausa persistente aleatória de 15–20 minutos; apenas um aviso por ciclo, priorizando o pendente mais antigo.
- Eventos autenticados do hub alimentam a Lumo uma vez, em fila própria, sem reprocessar ecos/edições do bot.

## Evidências

- 61 testes Python e 5 regressões JavaScript passaram. Verificação sintática de `lumo.js` aprovada.
- Arquivo congelado PyInstaller conferido: contém o formatador de bloco e a chave persistente de espaçamento.
- WebStore instalada: SHA-256 `726F5CA818C4676D0B25FCE13F23D8F388734F17CC36675363E6E6AF2B9DB6F6`.
- API pública respondeu HTTP 200 e versão 1.12.34 depois da troca.
- Tarefa persistente `ARKLAND-WebStore-Update-1.12.34` permaneceu em execução após terminar a conexão SSH de implantação.
- Gateway Lumo conectado; scheduler ativo; `last_error` vazio; API administrativa expõe intervalo `[15,20]` e instante persistente de liberação.
- Consulta pública de jogadores voltou a responder depois da indisponibilidade breve da troca de processo.

Não foram enviadas mensagens artificiais ao Discord ou aos jogadores. A apresentação final depende de uma próxima mensagem real no servidor de teste. A espera completa entre dois avisos será observada pelo uso normal; os testes de relógio e reinício cobrem a regra sem publicar mensagens reais.

## Escopo operacional

Somente o processo da WebStore foi substituído. Nenhum mapa ARK foi reiniciado para esta entrega. A DLL Chat Arkland 0.1.0 do piloto 05 e a revisão central 3 foram preservadas; o ajuste é central. Nenhuma migração de banco foi necessária.

Foi preservado backup protegido do executável 1.12.33 e das configurações. O procedimento restaura a versão e a tarefa anteriores caso a nova API não fique pronta. O processo é mantido por tarefa agendada, para sobreviver ao encerramento do SSH.
