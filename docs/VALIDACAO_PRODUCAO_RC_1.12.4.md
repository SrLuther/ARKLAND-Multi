# Roteiro de validação prática — ARKLAND 1.12.4

Este roteiro deve ser executado após instalar a versão candidata em uma cópia controlada da máquina de produção. Os testes de leitura devem vir primeiro. Nenhuma etapa inicia, para ou reinicia servidores automaticamente.

## Antes de atualizar

1. Feche o ARKLAND Server Manager.
2. Faça uma cópia byte a byte dos perfis e dados persistentes, incluindo `asm_servers.json`, arquivos auxiliares do TEK, configurações da WebStore, histórico, dados de clusters e agendamentos.
3. Faça cópias dos `Game.ini`, `GameUserSettings.ini` e INIs de mods de cada instalação. Registre os caminhos, tamanhos e SHA-256.
4. Registre a versão instalada e a versão dos plugins; confirme que nenhum servidor está em atualização ou gravação de INI.
5. Guarde o instalador da versão anterior e o novo instalador até concluir a validação.

## Etapa 1 — Inicialização e compatibilidade (somente leitura)

1. Instale a atualização sem selecionar opções que removam dados do usuário.
2. Abra o aplicativo e confirme a versão `1.12.4` em **Sobre**.
3. Confirme que os perfis existentes aparecem com os caminhos corretos e sem duplicação.
4. Confira que nenhum servidor iniciou, parou ou reiniciou por causa da abertura do gerenciador.
5. Abra as páginas SSH, configurações e diagnóstico. Confirme que a interface responde e que mensagens de diagnóstico aparecem na própria página.
6. Compare os hashes dos arquivos persistentes antes e depois de apenas abrir o aplicativo. Arquivos que não deveriam ser regravados devem permanecer byte a byte iguais.

## Etapa 2 — INIs em cópia isolada

Faça estes testes primeiro em uma cópia de uma instalação, nunca no diretório ativo:

1. Preserve uma chave de mod externa ao TEK e uma seção com comentários/chaves repetidas.
2. Adicione uma opção gerenciada, salve e confirme seção, chave e valor no INI.
3. Altere o valor e salve novamente; deve existir um único valor atualizado conforme a sintaxe daquela chave.
4. Remova a opção pela interface, salve, feche e reabra o gerenciador. A opção removida não pode reaparecer.
5. Recrie o INI a partir da cópia de teste e repita a verificação; somente opções atualmente gerenciadas podem ser reconstruídas.
6. Edite manualmente uma chave gerenciada e uma chave externa. Confirme que o conflito é informado, que existe backup recuperável e que nenhuma alteração externa é descartada silenciosamente.
7. Repita com cópias UTF-8 e UTF-16 LE. A codificação existente deve ser mantida; um INI novo deve usar UTF-16 LE com BOM.
8. Repita importação e sincronização entre duas cópias de perfis. Confirme que conteúdo externo e chaves repetidas válidas são preservados.

## Etapa 3 — Recursos administrativos, sem comandos destrutivos

1. Verifique eventos globais, buffs e clusters em modo de leitura; confirme que cada perfil continua ligado ao servidor correto.
2. Revise a tela de backups: confira escopo, destino e retenção antes de solicitar um backup individual em uma cópia de teste. Não teste restauração sobre dados ativos.
3. Confira agendamentos e broadcasts por servidor sem aguardar execução automática. Valide que selecionar um servidor não inclui outros.
4. Confira o estado BattleMetrics e o histórico TEK; confirme que o histórico não contém senhas, tokens ou credenciais.
5. Confira os campos de mods e o manifesto de propriedade. Ausência de configuração de mod não deve apagar configurações externas.

## Etapa 4 — Testes reais, somente após janela e backup

Execute apenas com autorização operacional do responsável pelo servidor e janela de manutenção:

1. Instale/atualize plugins somente após conferir versão e backup dos arquivos correspondentes.
2. Faça um backup individual e confira a existência e integridade do arquivo gerado.
3. Em um servidor de teste, altere uma configuração INI simples, valide o diff e só então grave no servidor.
4. Reinicie manualmente o servidor apenas se a opção exigir reinício; confirme o valor efetivo no jogo e nos logs.
5. Teste eventos, buffs, transferência de cluster, broadcasts, produção/retirada da Fazenda e entrega de Blueprints apenas em ambiente autorizado.
6. Para SSH externo, confirme fingerprint do host, autenticação por chave e um comando remoto somente de leitura. Não exponha a chave privada nem habilite encaminhamento/alias para terceiros sem revisar a configuração.
7. Na WebStore, valide tickets, nomes Steam/Discord, categorias de licenças e painel de jogadores com contas autorizadas.

## Critério de aprovação

- Perfis e caminhos permanecem íntegros e isolados por servidor.
- Nenhum valor gerenciado removido reaparece após salvar, reiniciar o aplicativo ou reconstruir INI.
- Conteúdo externo, comentários, chaves repetidas válidas e codificação são preservados.
- Backups são recuperáveis e operações individuais não atingem escopo global.
- Funções reais são verificadas no ARK/WebStore; testes automatizados ou smoke tests não substituem esta confirmação.

## Reversão

1. Feche o gerenciador e interrompa qualquer teste em andamento.
2. Desinstale a candidata se necessário e reinstale a versão anterior.
3. Restaure os arquivos persistentes diretamente das cópias byte a byte, sem abrir/salvar pelo gerenciador novo.
4. Compare os SHA-256 com o inventário pré-atualização e confirme os caminhos de todos os perfis antes de retomar a operação.
