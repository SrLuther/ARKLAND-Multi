# Testes — entrega experimental 0.1.0

## Executados neste ambiente

Em 26/11/2026, no worktree feature/chat-arkland, a partir da versão publicada 1.12.32:

- **50 testes Python aprovados** no conjunto Chat Arkland, rotas/transportes, monitoramento de jogadores compartilhado, Central de Status e componentes existentes do Lumo. Execução com Python 3.12.13; houve avisos de depreciação das bibliotecas, sem falhas. Fixtures SQLite temporárias; não equivale a teste de concorrência em MariaDB de produção.
- **Build MSVC x64 aprovado** da DLL independente com headers/biblioteca reais do ArkServerAPI ASE. Link sem CustomShop.dll e sem biblioteca MySQL do cliente.
- **Testes C++ do núcleo aprovados**: UTF-8/Unicode, censura por caixa/acentos/evasão simples, limites de palavras, PollRate decimal/limites, formato com ID, ausência de tribo vazia, RGBA e UUIDs. O executável de teste não carrega o mundo ARK.
- **Fluxo em navegador Edge headless aprovado** na prévia Flask local: todas as nove abas, rejeição de PollRate zero, valor decimal, prévia com ID/cores, ausência de interpretação de HTML, descoberta de três referências fictícias e adição sem aprovação automática, participação de mapas, publicação com CAS, histórico/rollback como nova revisão e tela de 390 px sem rolagem horizontal. Nenhuma mensagem real ao Discord ou jogo foi enviada.
- **Importação real da aplicação web aprovada**, com ARKSHOP_SKIP_DB_BOOT=1, conferindo registro das novas rotas e importação das dependências sem iniciar o Gateway ou abrir uma porta pública.
- **Cinco testes Node de regressão aprovados** para renderização dos membros por mapa e sessão administrativa da Central de Status.
- **Consulta SSH de leitura**: mapa 05 executando, KalsCrossChat e demais plugins existentes presentes. Não foi instalada esta DLL nem reiniciado qualquer mapa nesta entrega.

## Cobertura dos testes do hub

- Validação estrita de tipos, cores, configurações desconhecidas, templates e ID obrigatório.
- Uma tag por jogador; prioridade administrativa e rejeição de grupo pago sem licença vigente; aprovação administrativa obrigatória.
- IDs diferentes para pessoas com nomes iguais, associação estável após consultas/reinício, recusa de duas instâncias com mesma chave e preservação do ID ao transferir.
- Deduplicação de evento global, controle de spam, formato sem espaços/elementos vazios e preservação de Unicode.
- Mensagem privada cruzada com cópia somente ao remetente, destinatário específico, separação do terceiro jogador, ausência de fila Discord, lease transferido e ACK por destinatário. `/r` só passa a apontar ao remetente após confirmação de recebimento pelo destino.
- Erros de ID inválido/inexistente, destino desconectado, próprio ID, uso incompleto, mensagem vazia e `/r` sem conversa; respostas individuais.
- `/joinleave` vale já na mesma resposta; observação não retransmite conversas nem grava presença no monitoramento.
- `/online` usa os mesmos IDs, paginação e restrição de visualização do mapa; desconexão usa nome do jogador.
- Controle entre mapas preserva o global local. Configuração com revisão antiga é recusada sem sobrescrever a atual.
- Publicador único do Discord, envio ambíguo sem repetição automática, ausência de eco de bot, validação por guild/canal/ID real e recusa de webhooks/outros bots. Mensagens humanas com aparência de comando continuam texto.
- APIs administrativas exigem administração; API da DLL exige chave interna sem aceitar apenas sessão administrativa; bootstrap é protegido e não revela token Discord. Prévia não aloca IDs reais.
- Central de Status registra desenvolvimento e diferencia contato de transporte de homologação funcional; não classifica o plugin como finalizado por receber heartbeat.

## Ainda não executados — homologação obrigatória

Não declarar produção validada antes de registrar os resultados seguintes:

1. Carregar/descarregar a DLL no ASE real; observar crash, callbacks, tempo de tick e latência da API Permissions efetivamente instalada.
2. Dois jogadores no mesmo mapa: confirmar ID no global e /online, PM sem exposição a terceiros, /r, filtros, tribo ausente, caracteres portugueses, cores e próprio nome.
3. Dois mapas autorizados: global uma vez em cada mapa, PM nos dois sentidos, nomes iguais e ID persistente após transferir, renomear, reconectar e reiniciar.
4. Enviar mensagens nos canais local, tribo e aliados: confirmar que nunca aparecem no hub global, Discord nem outro mapa. Verificar que nenhum callback legado retransmite esses canais.
5. Discord real: Jogo → Discord com ID correto; humano vinculado/não vinculado → jogo; mensagem do próprio Lumo → jogo uma vez; outro bot/webhook recusado; Lumo responde apenas ao corpo original sem eco ou ciclo.
6. /joinleave, entrada/saída, mapas diferentes, paginação de /online e permissões para mostrar localização.
7. Publicar novas cores/tags em duas instâncias, expirar licença e remover grupo; confirmar revisão aplicada e ausência de privilégio derivado de texto/apelido.
8. Interromper somente o transporte de homologação: confirmar fallback nativo, filas limitadas, expiração, PM sem falsa confirmação, recuperação e ausência de replay antigo. Não interromper banco compartilhado de produção como teste.
9. Indisponibilidade e reconexão real do Discord; comparar envios ambíguos antes de qualquer repetição manual.
10. Incluir/remover um mapa no cadastro; conferir identidade permanente, observação inicial e ausência de dependência da quantidade fixa de servidores.
11. Concorrência no MySQL/MariaDB, geração de IDs, CAS de revisão e leases com duas conexões/processos. As migrações foram geradas para esse dialeto, mas isso não comprova execução real nem concorrência InnoDB.
12. Backup e reversão: restaurar o legado somente no piloto parado e confirmar integridade dos registros permanentes de IDs. Sem exclusão de saves.

## Limites conhecidos

- Não há certificação de entrega exatamente uma vez em caso de crash entre exibição e gravação do ACK. O protocolo usa UUID, retenção limitada, lease, ACK e cache; envios Discord ambíguos não são repetidos às cegas.
- Falta de heartbeat não prova que o jogador desconectou. Notificações de saída são geradas por snapshots explícitos de ausência; uma queda de processo/rede não inventa uma saída confirmada.
- Os comandos de outros plugins são executados antes do callback público do SDK. Colisões de comandos e callbacks precisam ser isoladas no piloto. Detectar Kals carregado força observação, mas não identifica toda implementação de terceiros possível.
- A interface e o backend existem no código desta branch e na prévia; não foram publicados no site de produção. A DLL sozinha não fornece a API central.
- O pacote é experimental. A Central de Status permanece Em desenvolvimento / Não disponibilizado até avaliação administrativa respaldada pela homologação.

## Reprodução

No ambiente Python do projeto, executar pytest para os arquivos `test_chat_arkland.py`, `test_chat_arkland_transport.py`, `test_player_monitoring_routes.py`, `test_system_status_center.py`, `test_lumo_routes.py`, `test_lumo_assistant.py` e `test_lumo_assets.py` de `plugin/arkshop_web/tests`.

Para a interface, iniciar `tools/chat_arkland_preview.py` em loopback e executar `chat-arkland-browser.test.cjs` com Node/Playwright e Edge. O teste verifica explicitamente a identificação de dados fictícios e usa somente 127.0.0.1:5188. Nunca apontá-lo para produção.

Compilação: `plugin/ChatArkland/build_cl.bat`, configurando CHAT_PYTHON e CHAT_SDK_ROOT. Verificar saída zero e resultado dos testes C++. O manifesto do pacote registra hashes/tamanhos dos arquivos de runtime e documentação para conferência posterior.
