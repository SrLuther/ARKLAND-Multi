# Pendências - ARKLAND Multi

**Atualizado:** 20/11/2026
**Fonte única de acompanhamento:** este arquivo.
**Estado de publicação conhecido:** verificado no site público em 20/11/2026: rodapé exibe WebStore v1.12.12. Isso confirma a WebStore, não a versão instalada do gerenciador desktop nem dos plugins ARK.

## Em andamento
- [x] **Steam - listagem do mapa 04 (Ragnarok Omega) restabelecida em 20/11.** O usuário removeu `E:\Mapas\04\ShooterGame\Saved\Config\WindowsServer\RunServer.cmd` e iniciou o servidor; o processo mudou de PID 14608 para 11176. Conferi o arquivo removido na Lixeira e o recriado: SHA-256 idêntico (`9E363470...B56E9846`) e mesmos argumentos, inclusive `Ragnarok?listen?Port=7783?QueryPort=27018?MaxPlayers=35`; portanto a correção não veio de mudar mapa/configuração ou conteúdo do RunServer, e o `?Map=Ragnarok` não estava faltando. Após a inicialização limpa, A2S retornou `Ragnarok`, `0/35` em 3 consultas consecutivas; consulta no loopback, LAN e IP público e Steam GetServersAtAddress também confirmaram mapa e capacidade corretos. Diagnóstico operacional: o processo anterior estava com estado de publicação A2S/Steam inconsistente; uma inicialização limpa reconstituiu a resposta e a listagem. O gatilho interno que deixou o estado anterior inconsistente não foi identificado; se voltar a ocorrer, comparar processo/RunServer e capturar A2S no primeiro instante e após a inicialização. Correção local `[UNDEFINED]` no gerenciador permanece para não exibir `ONLINE · Steam` enquanto os metadados estiverem vazios.
- [ ] **Watchdog A2S/Steam e recuperação protegida.** Implementação local `[UNDEFINED]`: após 15 minutos do início do processo, exige 3 respostas A2S inválidas consecutivas; grava evidência JSON (PID/linha de comando, porta/hosts e cauda do `ShooterGame.log`). Só tenta reinício se RCON confirmar lista vazia, aceitar `SaveWorld` e continuar vazia após 60 segundos; respostas ambíguas, falha de RCON ou jogador conectado cancelam a ação. Uma tentativa por ocorrência; sucesso A2S encerra/rearma o ciclo. Falta instalar/empacotar a mudança e observar em servidor real; nenhum restart real foi executado por esta alteração local.
- [ ] **SSH - estado da interface após desconexão remota.** Correção implementada para limpar a conexão ativa, liberar os botões e exibir o motivo do encerramento. Próximo passo: validar visualmente após instalar a v1.12.13.
- [ ] **WebStore - Tickets: conferir nomes na lista e no detalhe administrativo.** A implementação foi publicada na v1.12.6 (contida na versão pública v1.12.12). Falta conferir o resultado com uma sessão administrativa; esta verificação não foi feita nesta auditoria.
- [ ] **Painel de jogadores para Admin/Suporte.** A correção do cálculo de tempo de jogo foi publicada na v1.12.6 (contida na versão pública v1.12.12). Próximo passo: conferir no painel autenticado se sessões recentes exibem duração correta; a página pública não expõe esse painel.
- [ ] **WebStore - administração de votações.** Os controles existem, mas ainda não foram testados em rascunho isolado. Próximo passo: validar criação/edição e as regras após o primeiro voto, sem alterar a votação ativa.
- [ ] **Fazenda - Blueprints Primal Fear.** Os 18 recursos estão configurados no grupo próprio, mas isso não comprova spawn/entrega. Próximo passo: validar configuração efetiva, estoque e resgate no servidor com o mod instalado.
- [ ] **Fazenda - Blueprints ARK Omega e resgate.** O catálogo mostra Essence, Token e Paragon, mas há itens sem estoque; falta validar carregamento de classes, produção, recuperação e entrega ponta a ponta em ambiente controlado.
- [ ] **Fazenda - aliases de caminho ARK Omega.** Implementado localmente na versão 0.1.31 e build concluído. Próximo passo: instalar, confirmar a configuração mestre carregada e validar itens reais nos dois formatos em `/fazenda`.
- [ ] **Minha Área - bônus dos marcos em Âmbares.** Implementação local considera `StackRewards`, `TimedPointsReward.Enabled` e os valores de grupo, com validação local registrada. Próximo passo: comparar o resultado visual com configurações reais e com o valor concedido no jogo.
- [ ] **Minha Área - barra lateral em telas móveis.** A home pública em viewport 390 px não tem overflow horizontal e mostra o menu compacto. Falta conferir a navegação da barra lateral dentro de Minha Área com uma conta autenticada.
- [ ] **Bot Discord - correção da identidade da tribo.** A v1.12.13 inclui CustomShop 1.10.57, que prioriza `FTribeData`. Próximo passo: instalar o plugin atualizado nos mapas, confirmar heartbeat recente e validar o apelido de outro membro. O bloqueio de permissão observado para Ciano é independente.
- [ ] **Agente remoto - acesso de outra rede.** A separação entre host público/DDNS e IP LAN está no código local. Próximo passo: validar conexão externa com TCP 32440 encaminhada/liberada e verificar CGNAT; se houver, documentar VPN/rede privada ou relay.

## Aguardando decisão
- **ArkEventHunt em produção.** A configuração observada estava `enabled=false`. A validação de evento real e Mode B depende de decidir habilitar o plugin.


## Aguardando discussao


## Concluídas / confirmadas
### Verificadas no site publicado em 20/11/2026 (inspeção somente leitura)
- [x] **WebStore - versão no rodapé.** A página pública atual exibe `WebStore v1.12.12`.
- [x] **Mascote no botão de ajuda.** O site publicado mostra o botão flutuante “Precisa de ajuda?” com imagem; a v1.12.6 registra a arte aprovada do mascote e a animação limitada ao olhar/piscadas. A pendência anterior que dizia que o mascote não estava integrado era falsa e foi removida.
- [x] **WebStore - saudação personalizada no atendimento.** A implementação consta na v1.12.6, incluída na WebStore pública v1.12.12. O texto personalizado após autenticação não foi conferido nesta visita.
- [x] **WebStore - menu móvel da home.** Em viewport 390 px, a página pública não tem overflow horizontal (`scrollWidth` e `clientWidth` 390 px) e apresenta o botão de menu. Minha Área autenticada continua pendente acima.
- [x] **WebStore - exibir nomes Steam/Discord nos tickets administrativos.** A funcionalidade consta na v1.12.6 e na linha da v1.12.4; a inspeção autenticada da lista/detalhe permanece pendente acima.

### Verificadas no site publicado em 12/11/2026 (inspeções anteriores)
- [x] **WebStore - Fazenda: navegação do catálogo.** Confirmado em produção: categorias recolhíveis, busca e grupos de recursos; em viewport de 390 px, documento e painel da Fazenda sem rolagem horizontal. Nenhum resgate foi enviado.
- [x] **WebStore - Equipes: renderizar Markdown no mural/regulamento.** Confirmado no regulamento publicado de [BøT] STAFF: títulos, parágrafos, listas, negrito e citação renderizados. Inspeção somente leitura.
- [x] **SeasonLand - trilha única de recompensas Free/Premium.** Gamma ativa, níveis 1–30 alinhados nas colunas Free/Nível/Premium e recompensas da conta autenticada indicadas como entregues. Em viewport de 390 px sem overflow horizontal.
- [x] **WebStore - Votações: formatação das descrições.** Em votação pública, títulos, negrito, lista e citação renderizados. Nenhuma edição de votação foi feita.
- [x] **WebStore - Sorteio: participantes e legenda.** Lista nominal paginada, números pessoais e de equipe separados e legenda das origens visível. Em viewport de 390 px sem overflow horizontal; nenhuma compra/contribuição foi feita.
- [x] **WebStore - Fazenda: layout do agendamento de retirada.** Em viewport de 390 px, campos e botão dentro da área visível, sem overflow horizontal global. Formulário não foi enviado.

- [x] **Bot Discord - preservar e validar comandos existentes na próxima atualização.** `!faxina`, `!limpar` e `!limpezageral` estão presentes em `src/discord_bot/moderation.py`; o cog é carregado em `src/discord_bot/bot.py`. Confirmar que continuam habilitados e funcionais no pacote atualizado, junto com filtros de convite e palavrões. Não substituir nem remover o cog ao adicionar sincronização de apelido. Confirmado pelo usuario: comandos existentes testados com sucesso na atualizacao.

- [x] **WebStore - Licencas: separar bonus de Ambares por tempo das licencas especiais.** Confirmado na vitrine de producao: 15 licencas com bonus por tempo e 2 licencas especiais (Nuvem e Fazenda) aparecem em regioes distintas do catalogo.
- [x] **WebStore - Fazenda: exibir somente recursos em producao.** Confirmado em Minha Area > Fazenda na producao: a secao informa 17 recursos em producao e os cartoes apresentados estao marcados como habilitados e "Producao ativa".
- [x] **Inventário de Blueprints dos mods instalados.** O Ark_Spawn_Code_Generator foi executado dentro das pastas `WindowsNoEditor` dos 17 mods numéricos em `D:\DOC\TESTE SERVER\01\ShooterGame\Content\Mods`. Os resultados individuais ficaram nas pastas numéricas e o catálogo consolidado em `docs/SpawnCodes_InstalledMods.txt`, agrupado por ID, com 1.441 comandos de spawn. Três mods não produziram comandos de item/dino pelo gerador; seus arquivos de saída registram apenas os cabeçalhos vazios.

- [x] **Comandos de moderação do bot preservados no código-fonte.** `!faxina` (`purgeall`), `!limpar` (`clear`) e `!limpezageral` (`limparall`) continuam no cog de moderação, que faz parte dos cogs carregados pelo bot. A validação em runtime do pacote atualizado permanece aberta acima.
- [x] **WebStore - erro de schema `farm_redemptions.share_key`.** A migração idempotente de `share_key`, `delivered_amount` e `stack_size` já foi incorporada; releases posteriores incluem outras correções da Fazenda. A falha de entrega de Blueprint é uma pendência distinta e continua aberta.
- [x] **WebStore - inicialização e rota de pedidos pendentes.** As antigas tarefas de auto-start da WebStore e compatibilidade de `/api/pending` e `/api/pending/delivered` foram marcadas como concluídas no registro anterior. Não manter os detalhes de diagnóstico de junho como pendências atuais.
- [x] **Auditoria Discord - crédito manual.** Painel, rota administrativa, auditoria de ator/evento e bloqueio de repetição por ciclo já implementados; a tarefa antiga de implementação está concluída. A publicação acompanha o ciclo normal de release.

## Regra de manutenção

1. Registrar neste arquivo novas tarefas antes de iniciar a execução.
2. Usar `- [ ]` apenas para trabalho ainda aberto; mover para “Concluídas / confirmadas” somente com evidência de código ou validação correspondente.
3. Distinguir implementação local, validação em produção e publicação; uma etapa não comprova automaticamente as outras.
4. Não criar outro arquivo para acompanhar pendências.
5. Preservar `ferramentas/Ark_Spawn_Code_Generator.exe`: utilitário do projeto para gerar a lista completa de Blueprints de qualquer mod; usar a partir da pasta do mod e manter os resultados de referência, como `docs/SpawnCodes.txt`.
6. Cada pendência aberta deve ter um próximo passo verificável; consolidar duplicatas e retirar da seção ativa assim que esse passo for confirmado.
