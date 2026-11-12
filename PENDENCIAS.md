# Pendências - ARKLAND Multi

**Atualizado:** 12/11/2026
**Fonte única de acompanhamento:** este arquivo.
**Publicação:** candidata 1.12.5 em preparação sobre a base 1.12.4 publicada. O site publicado respondeu versão 1.12.4 em 12/11/2026; a exibição no rodapé depende desta atualização e a validação visual ocorrerá após publicação.

## Em andamento
- [ ] **WebStore - versão no rodapé.** O backend publicado já oferece `/api/version`, alimentado por `version.json`; em 12/11/2026 retornou `1.12.4`. O frontend local agora consulta esse endpoint e mostra `WebStore vX` junto ao status da loja. Pendente testar após publicar e decidir se o número deve ser igualado ao gerenciador em cada release.
- [ ] **Mascote virtual da ajuda.** O site publicado ainda mostra o botão “Precisa de ajuda?” com envelope e o título “Atendimento ARKLAND”; nenhum mascote aparece integrado. O projeto investigativo segue sem implementação; preservar a imagem de referência aprovada.
- [ ] **WebStore - Fazenda: Blueprints Primal Fear.** O site lista o grupo de retirada Primal Fear (18 recursos), mas isso não comprova que o plugin produza ou entregue os itens. Validar configuração, estoque e entrega em ambiente autorizado.

- [ ] **SSH - feedback visual ao desconectar.** Correção implementada localmente na versão candidata: ao desconectar, a interface atualiza o estado, informa o host da sessão encerrada, mostra um aviso no terminal e habilita/desabilita os botões conforme o estado. Testes focados: 3 aprovados. Pendente validar visualmente no aplicativo instalado e incluir em uma atualização publicada.

- [ ] **WebStore - saudação personalizada no atendimento.** A versão local tem a saudação com nome Steam e fallback; no site publicado, em 12/11/2026, o cabeçalho ainda mostrava “Atendimento ARKLAND”. Falta publicar e conferir com conta autenticada.

- [ ] **WebStore - Tickets: exibir nick Steam e Discord dos autores.** A implementação local e 51 testes relacionados constam concluídos; na lista administrativa publicada, verificada em 12/11/2026, a coluna Jogador ainda mostra SteamID numérico, embora a coluna Discord apresente nomes vinculados. Falta publicar e validar lista e detalhe.

- [ ] **Painel de jogadores do servidor para Admin/Suporte.** Em 12/11/2026, os 15 registros da tela publicada mostravam `0h 0min`, apesar de sessões contadas de 1 a 7. A correção local ainda precisa ser publicada e validada com novos heartbeats; os dados observados não provam por si só a causa nem duração histórica correta.




- [ ] **WebStore - administração de votações.** A página publicada mostra a votação ativa, os controles de edição e as ações administrativas. Não salvei alterações em votação real (havia 5 participantes); falta testar criação/edição em rascunho isolado e validar as regras após o primeiro voto.

- [ ] **Fazenda - validar catálogo Omega em produção.** O site publicado mostra os grupos de retirada Default (1), Omega (51) e Primal Fear (18), além de Paragon Breaker e Paragon Shard na produção ativa. Vários itens Omega de Essence/Token estavam com estoque zero; a presença no catálogo não comprova carregamento dos Blueprints nem entrega no jogo. Falta validar configuração do plugin e ciclo real de produção/resgate.



- [ ] **Minha Área - bônus dos marcos no ganho de Âmbares.** Implementação local agora considera `StackRewards` (soma ou maior grupo), `TimedPointsReward.Enabled`, o valor `Default` inclusive quando zero e aplica o bônus dos marcos com divisão inteira igual ao plugin. Validação local: `py_compile` e 57 testes de licenças/equipes passaram; 10 scripts inline passaram na checagem de sintaxe antes da última alteração de texto. Falta validar visualmente com configurações reais do servidor e confirmar que o valor coincide no jogo.

- [ ] **WebStore - reformulação da barra lateral.** Na produção em 12/11/2026, nome, SteamID e DiscordID estavam visíveis em desktop sem corte. Falta conferir a legibilidade/abertura do menu nas larguras móveis e concluir a revisão visual.

- [ ] **Bot Discord - sincronização do apelido com personagem e tribo.** Implementação local atualizada: prioriza a identidade da sessão ativa no servidor/mapa atual; consulta a cada minuto e usa o último registro conhecido como fallback quando o jogador está offline ou a consulta online falha. O fallback informa a origem e o horário da última atualização; falhas técnicas da consulta ativa são registradas com detalhes no log. Formato padronizado: `[Tribo] | NickDoJogador` (exemplo `[BøT] | Ciano`); sem tribo, o padrão usa o marcador literal `[Tribo] | Ciano`. O bot também diagnostica falta de permissão `manage_nicknames` e hierarquia insuficiente. Testes focados atuais: 29 do bot aprovados; nesta rodada, 33 testes combinados de bot e monitoramento passaram. Pendente: instalar e validar com bot, plugin e guilda reais; confirmar atualização ao trocar de mapa e observar os logs de fallback/erro.


- [ ] **Fazenda - suporte e entrega de Blueprints ARK Omega.** O site publicado mostra o grupo Omega e recursos como Essence, Token e Paragon; isso comprova a configuração visível, não a entrega. Permanecem pendentes a validação do plugin, dos Blueprints, estoque e resgate em servidor de teste/produção controlada.
- [ ] **Fazenda - reconhecer aliases de caminho dos itens ARK Omega.** Implementado localmente na versão 0.1.31: a comparação de inventário aceita `/Game/Mods/2447186973/` e `/Game/Mods/ArkOmega/` como aliases, sem reescrever os caminhos persistidos na migração. Build concluído com sucesso. Falta instalar no servidor, confirmar a configuração mestre efetivamente carregada e validar itens reais dos dois formatos em `/fazenda`.


- [ ] **Fazenda - fluxo integral de recuperação e resgate.** O código evoluiu após as pendências das versões 0.1.19-test e seguintes, mas os logs de entrega de Blueprint indicam que ainda falta validar recuperação, reenvio, consumo do estoque e entrega final no servidor real. Executar ciclo ponta a ponta após corrigir o carregamento de Blueprint.

- [ ] **Agente remoto - acesso de outra rede.** A correção local para separar host público/DDNS do IP LAN ainda precisa de validação de conexão externa com TCP 32440 encaminhada e liberada no firewall. Verificar também CGNAT; se houver, documentar alternativa por VPN/rede privada ou relay.

- [ ] **ArkEventHunt - evento real em produção.** O log anterior confirmou carregamento do plugin e registro dos comandos/hooks, mas a configuração estava `enabled=false`. Confirmar decisão de habilitar e, se habilitado, validar evento real e Mode B.


## Aguardando discussao


## Concluídas / confirmadas
### Verificadas no site publicado em 12/11/2026 (inspeção somente leitura)
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


- [ ] **Fazenda - validar Blueprints Primal Fear.** 18 recursos (8 Souls e 10 Hides) adicionados ao grupo de estoque próprio primal_fear nas configurações padrão e na migração do plugin/WebStore. Confirmar que os Blueprints e limites de stack criam/entregam os itens corretamente no servidor ARK com o mod instalado.
