# Pendências - ARKLAND Multi

**Atualizado:** 06/11/2026
**Fonte única de acompanhamento:** este arquivo.
**Publicacao:** 1.11.48 published without the rebuilt Farm DLL; fixing packaging for stable 1.11.49.

## Em andamento

- [ ] **Fazenda - validar cat?logo Omega ap?s atualiza??o de produ??o.** A vers?o est?vel 1.11.48 est? publicada. Causa corrigida: configs gerenciadas pelo site n?o recebiam padr?es novos no plugin e o cat?logo MySQL antigo ocultava recursos do config. Aplicar a atualiza??o no WebStore e nos plugins dos servidores; confirmar migra??o autom?tica dos IDs ausentes e presen?a de Essence, Paragon, Token e demais recursos no site, preservando configura??es personalizadas.

- [ ] **WebStore - Votações: identidade visual e formatação de descrições.** Editor com parágrafos, negrito, itálico, sublinhado, subtítulos, listas e citações; descrições sanitizadas no servidor. Falta revisar visualmente e validar persistência/renderização com votações formatadas.

- [ ] **WebStore - Sorteio: participantes e legenda.** Implementação local separa os números do jogador e da equipe, mostra nomes públicos na lista, pagina os participantes e explica as origens com atalhos condicionais. Falta revisão visual integrada e validação no site publicado.

- [ ] **Minha Área - bônus dos marcos no ganho de Âmbares.** Implementação local agora considera `StackRewards` (soma ou maior grupo), `TimedPointsReward.Enabled`, o valor `Default` inclusive quando zero e aplica o bônus dos marcos com divisão inteira igual ao plugin. Validação local: `py_compile` e 57 testes de licenças/equipes passaram; 10 scripts inline passaram na checagem de sintaxe antes da última alteração de texto. Falta validar visualmente com configurações reais do servidor e confirmar que o valor coincide no jogo.

- [ ] **WebStore - reformulação da barra lateral.** Preservar nome e IDs visíveis junto ao nome. Foram aplicados estilos para simplificar a marca, destacar o cartão de conta/saldo e organizar ícones e seleção do menu; o controle de Modo Staff é um indicador circular verde/vermelho ao lado de Sair. Falta revisão visual em diferentes larguras e confirmar que nome, SteamID e DiscordID permanecem legíveis sem corte. Os ícones de Catálogo e Sugestões também foram integrados aos menus e cabeçalhos.

- [ ] **Bot Discord - sincronização do apelido com personagem e tribo.** Implementação local concluída: o bot consulta, pela API interna autenticada, contas vinculadas e a identidade mais recente sincronizada do jogo; define o apelido no formato `[NomeDaTribo] NomeDoPersonagem` (exemplo `[BøT] Ciano`). Cog incluído no carregamento e permissão `manage_nicknames` no convite. Validação local registrada: 63 testes do bot e 29 testes da rota passaram. Falta validar com bot/guilda reais, permissões e hierarquia de cargos após instalação.

- [ ] **Bot Discord - preservar e validar comandos existentes na próxima atualização.** `!faxina`, `!limpar` e `!limpezageral` estão presentes em `src/discord_bot/moderation.py`; o cog é carregado em `src/discord_bot/bot.py`. Confirmar que continuam habilitados e funcionais no pacote atualizado, junto com filtros de convite e palavrões. Não substituir nem remover o cog ao adicionar sincronização de apelido.

- [ ] **Fazenda - suporte e entrega de Blueprints ARK Omega.** A comparação de `docs/SpawnCodes.txt` encontrou 11 itens adicionais de Souls, God Souls e Tokens; agora são 51 recursos nos padrões do plugin e da WebStore. Três Soul Compressor/Furnace/Grinder foram identificadas como estruturas e ficaram fora da produção de recursos. Os caminhos usam `/Game/Mods/2447186973`; migração acrescenta IDs ausentes e corrige apenas o prefixo padrão antigo, preservando outras personalizações. A normalização preserva `_C` como no CustomShop. Versão local 0.1.29 compilada com sucesso; falta validar entrega real no jogo, quantidade, estoque e retomada da produção.

- [ ] **Fazenda - fluxo integral de recuperação e resgate.** O código evoluiu após as pendências das versões 0.1.19-test e seguintes, mas os logs de entrega de Blueprint indicam que ainda falta validar recuperação, reenvio, consumo do estoque e entrega final no servidor real. Executar ciclo ponta a ponta após corrigir o carregamento de Blueprint.

- [ ] **Agente remoto - acesso de outra rede.** A correção local para separar host público/DDNS do IP LAN ainda precisa de validação de conexão externa com TCP 32440 encaminhada e liberada no firewall. Verificar também CGNAT; se houver, documentar alternativa por VPN/rede privada ou relay.

- [ ] **ArkEventHunt - evento real em produção.** O log anterior confirmou carregamento do plugin e registro dos comandos/hooks, mas a configuração estava `enabled=false`. Confirmar decisão de habilitar e, se habilitado, validar evento real e Mode B.

## Concluídas / confirmadas

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
