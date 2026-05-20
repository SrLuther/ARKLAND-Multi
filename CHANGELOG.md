# Changelog

<!-- markdownlint-disable MD024 -->

## [1.3.17] - 2026-05-20

### Fix

- fix: **updater autodestruía-se** ao encerrar processos — `_kill_lingering` usava `taskkill /F /T /PID` que mata a árvore inteira; como o updater é filho do app principal, ele era morto junto. Corrigido para usar apenas `taskkill /F /IM` por nome de executável.
- fix: ctypes `OpenProcess`/`WaitForSingleObject` agora com `restype=c_void_p` — evita truncamento de HANDLE em sistemas 64-bit com valores de handle > 2³¹.

### Fix — Plugin CustomShop (DLL)

- fix: `ShopPerms` agora usa `CreateToolhelp32Snapshot` para enumerar todos os módulos carregados e localizar o plugin Permissions independentemente do nome do DLL — resolve aviso _"Permissions plugin not found"_ com "Permissions V2".

---

## [1.3.16] - 2026-05-20

### Performance

- perf: lista de Itens e Kits no editor do CustomShop agora usa `ttk.Treeview` nativo + painel de edição único (master-detail) — navegação instantânea entre centenas de registros sem recriação de widgets.
- perf: lista de Mods paginada (20 por página) com navegação Anterior/Próximo, evitando renderizar todos os mods de uma vez.

### Fix

- fix: processo updater desvinculado do Job Object do Windows (`CREATE_BREAKAWAY_FROM_JOB`) — encerrar o app principal não interrompe mais o updater em execução.

### Feat — Plugin CustomShop

- feat: novo tipo **"dino"** nos itens do CustomShop (Itens e Kits) — campos Blueprint, Level, Gender (Male/Female/Random) e Neutered.

### Feat — Dashboard

- feat: servidor em estado **TRAVADO** (crashed) exibe botão "💀 Forçar Enc." em vez dos botões padrão — força encerramento do processo via `taskkill /F /T`.
- feat: barra de legenda com os 6 status de servidor (Parado, Iniciando, Online, Encerrando, Travado, Desconhecido) com cores e descrições.

### Feat — Painel de Desempenho

- feat: temperatura de CPU (via psutil / ACPI WMI no Windows) e GPU (via nvidia-smi) exibidas em cada card de recurso.
- feat: nova seção "📡 Consumo por Servidor" — tabela em tempo real com CPU% e RAM de cada processo ARK em execução.

## [1.3.0] - 2026-05-20

### Folgas — Admin pode registrar sem saldo disponível

- feat: admin pode registrar uso de folga mesmo quando o colaborador não possui saldo (`folga_days = 0`); nesse caso, 7h20 são descontadas normalmente das horas e o saldo fica negativo (rastreando o "débito").
- feat: ao registrar folga sem saldo, mensagem de aviso diferenciada é exibida com saldo atual (negativo).
- feat: seção "Usar Folga" no menu de ações do histórico agora sempre visível para admin — quando sem saldo, exibe badge vermelho "sem saldo — desconto forçado".

### Meta — Mensal e Configurável por Mês

- feat: indicadores de ponto substituem **Meta da Semana** por **Meta do Mês** — valor calculado sobre todos os dias úteis (seg-sáb, excluindo feriados) do mês selecionado.
- feat: admin pode definir uma **meta personalizada** para qualquer mês via formulário "📅 Meta Mensal" no menu de ações do histórico (campo H:MM, ex: `176:00`).
- feat: nova rota `POST /admin/meta-mensal` persiste a meta no banco; se já existir entrada para o mês, atualiza o valor.
- feat: novo modelo `MonthlyMeta` armazena metas personalizadas por `(year, month)` com constraint único.
- feat: migração automática em `ensure_schema` cria a tabela `monthly_meta` em bases existentes.
- feat: helper `_get_meta_mensal(year, month)` usa valor personalizado quando disponível, ou calcula automaticamente pelos dias úteis do mês.
- feat: API `GET /api/ponto/indicadores/<id>` também usa `_get_meta_mensal` para os campos `meta_mensal` e `faltantes`.
- feat: faltantes do mês calculados como `max(0, meta - h_normais - folga_bruto - folgas_usadas_em_dias_úteis)`.

## [1.2.0] - 2026-05-11

### Banco de Folgas — Rastreabilidade e Gestão pelo Admin

- feat: painel do colaborador exibe seção expansível **"Ver datas de origem"** dentro do bloco Banco de Folgas, listando cada domingo/feriado trabalhado e créditos manuais que geraram o saldo.
- feat: admin pode **Revogar** o crédito de folga de qualquer domingo ou feriado trabalhado — o dia aparece tachado e é descontado do saldo imediatamente.
- feat: admin pode **Restaurar** um crédito anteriormente revogado com um clique.
- feat: admin pode **Excluir** créditos manuais de folga (`HourEntry.gives_folga=True`) diretamente da lista.
- feat: contador do resumo exibe `(N ativos · M revogados)` quando há revogações para facilitar auditoria.
- feat: `_calc_ponto_indicadores` respeita revogações — datas revogadas não somam a `folga_bruto_min`.
- feat: novo modelo `FolgaRevogacao` armazena datas canceladas por colaborador.
- feat: migração automática em `ensure_schema` cria a tabela `folga_revogacao` em bases existentes.
- feat: novas rotas admin: `POST /colaborador/<id>/folga-ponto/revogar`, `POST /colaborador/<id>/folga-ponto/restaurar`, `POST /colaborador/<id>/folga-manual/<entry_id>/excluir`.

## [1.1.0] - 2026-05-10

### Ponto — Sistema de 4 Batidas Automático

- feat: seleção manual de tipo de batida (Entrada / Saída para Intervalo / Retorno / Saída Final) removida — o colaborador apenas confirma a foto, o sistema atribui o tipo automaticamente.
- feat: batidas do dia ficam em área de staging (pendentes) até que 4 sejam registradas; nenhum intervalo é calculado antes disso.
- feat: ao registrar a 4ª batida, tipos são atribuídos por ordem cronológica: 1ª → `entrada`, 2ª → `intervalo_saida`, 3ª → `intervalo_retorno`, 4ª → `saida_final`; batidas extras recebem tipo `extra`.
- feat: campo `gives_folga` derivado automaticamente de qualquer batida do dia com `gives_folga=True` (domingos).
- feat: tela `ponto_confirmar` exibe indicador visual de progresso do dia com 4 slots (feito / atual / pendente) e contador X/4.
- feat: painel do colaborador (`collab_history`) exibe seção "Batidas de hoje em processamento" com os horários já registrados e quantas ainda faltam.
- fix: `_try_register_interval` não incrementa `folga_days` em dobro — verificação `had_folga_before` evita múltiplos incrementos nas chamadas do mesmo dia.
- fix: `_calc_ponto_indicadores` exclui `HourEntry` com nota `LIKE 'Ponto:%'` do cálculo de créditos manuais de folga, eliminando double-counting.

## [1.0.1] - 2026-05-10

### Câmera — Tela de Carregamento

- feat: overlay de carregamento animado ao capturar foto do comprovante (modo câmera e modo galeria).
- feat: ícone de comprovante com linha de scan verde varrendo continuamente enquanto aguarda OCR.
- feat: **porcentagem de progresso real** exibida no overlay — 0→40% reflete o upload real via XHR; 40→95% simula o processamento OCR no servidor com desaceleração suave; 100% ao receber resposta.
- feat: barra de progresso troca de animação indeterminada para determinada assim que o progresso é conhecido.
- feat: botão "Capturar" reposicionado para dentro do viewport da câmera (`position: absolute; bottom: 1.1rem`), sempre visível em dispositivos móveis sem necessidade de scroll.

### Ponto — Detecção Automática de Tipo de Batida por Horário

- fix: sistema cruzava apenas a **sequência de batidas do dia** para sugerir o tipo — uma foto de saída capturada como primeira batida era classificada incorretamente como "Entrada".
- fix: `_auto_punch_type()` agora recebe o horário extraído pelo OCR e compara com a escala do colaborador; se o horário estiver a ≤ 1 h da saída prevista (ou após ela), sugere `Saída Final` diretamente.
- fix: mesmo comportamento aplicado no `ponto_confirmar` (fallback quando `punch_type` está ausente no form).

### Ponto — Banner de Domingo

- feat: quadro amarelo de domingo substituído por banner full-width com borda lateral destacada, ícone ☀️ e informações completas: jornada de 6h20, horas extra e direito a folga.
- fix: checkbox desabilitado (sem função) removido do banner — o campo oculto `gives_folga=1` permanece garantindo o valor correto no envio.

## [1.0.0] - 2026-05-10

### Domingos — Jornada e Escala Personalizada

- feat: horário de entrada aos domingos agora é configurável por colaborador (mínimo 05:00, máximo 12:20) via painel de histórico.
- feat: jornada diária aos domingos definida como **6h20** (380 min), em vez de 7h20.
- feat: horas além de 6h20 aos domingos são automaticamente contabilizadas como **horas extras**.
- feat: cálculo de indicadores (`_calc_ponto_indicadores`) usa jornada correta por dia da semana.

### Domingos — Intervalo Automático

- feat: intervalo de 30 minutos aos domingos é detectado automaticamente pela sequência de batidas (sem horário fixo).
- feat: ao registrar a saída para intervalo, o sistema inicia uma contagem regressiva de 28 minutos.
- feat: alerta WhatsApp enviado ao colaborador quando os 28 minutos expiram, lembrando de bater o retorno.
- feat: ao registrar o retorno do intervalo, o timer é cancelado automaticamente.
- feat: nova função `lembrete_retorno_intervalo_domingo()` em `notify.py`.

### Segurança — CPF

- feat: CPF armazenado como hash **HMAC-SHA256** irreversível (chave `FLUXOS_SECRET`), nunca em texto plano.
- feat: migração automática em `ensure_schema()` — converte CPFs existentes em texto plano para hash na primeira inicialização.
- feat: `mask_cpf` detecta hashes (64 chars hex) e exibe `***.***.***.***` sem tentar formatar como CPF.
- feat: colunas `collaborator.cpf` e `punch_record.raw_cpf` ampliadas para `VARCHAR(64)`, `raw_cpf` agora `nullable`.

### Fluxo de Ponto — Colaborador Logado

- feat: colaborador autenticado via sessão não precisa informar CPF — identidade já confirmada pelo login.
- feat: página de confirmação de ponto (`ponto_confirmar`) exibe banner "Registrando como: **{nome}** ✓ logado" para sessão de colaborador.
- feat: campos de CPF e seleção de colaborador ocultados no template quando `is_collab_session=True`.
- feat: JS de validação de CPF não é carregado para colaboradores logados (sem erro de `null` reference).

## [0.11.1] - 2026-05-09

### Correções de Estabilidade

- fix: todas as rotas POST do sistema agora aceitam GET com redirect gracioso, eliminando definitivamente o erro "Method Not Allowed" (405) causado por prefetch do browser, service worker do PWA ou navegação direta.
- Rotas corrigidas nesta versão: `settings/daily-rate`, `collaborators`, `collaborators/toggle`, `collaborators/update`, `collaborators/set-ponto-password`, `entries`, `entries/update`, `archive/month`, `archive/month/restore`, `whatsapp/resumo`, `whatsapp/pdf`, `ponto/logout-ponto`, `ponto/recuperar-senha`, `ponto/vincular`, `ponto/delete`, `colaborador/ponto-dia/add`, `colaborador/ponto/excluir`, `feriados/create`, `feriados/delete`, `colaborador/desconto-extra`, `colaborador/usar-folga-ponto`, `colaborador/whatsapp/teste`, `colaborador/alterar-senha`.

## [0.11.0] - 2026-05-09

### Painel Principal — Cards de Colaborador

- feat: nome do colaborador nos cards vira link clicável para o histórico.
- feat: botão `...` exibido apenas para administradores (ações Editar e Alternar status).
- feat: paginação dos cards reduzida de 10 para **3 por página**.

### Histórico do Colaborador

- feat: seção "Usar Folga" ocultada quando o colaborador não possui saldo de folga disponível (`folga_days < 1`).

### Correções de Estabilidade

- fix: rotas POST que recebiam GET (via prefetch, PWA ou browser) retornavam 405 — corrigido com redirect gracioso nas rotas: `logout`, `delete_entry`, `admin_create`, `admin_delete`, `make_collaborator_admin`, `colaborador_salvar_schedule`.

## [0.10.9] - 2026-05-09

### PWA

- feat: botão "📱 Instalar" na barra de navegação para adicionar o app à tela inicial.
- feat: detecção automática de suporte — exibido via `beforeinstallprompt` no Android/Chrome.
- feat: em dispositivos iOS, exibe instruções de "Compartilhar → Adicionar à Tela Inicial" ao clicar.
- feat: botão some automaticamente após a instalação (`appinstalled` event).

### Painel Principal

- feat: seção "Lançamentos de horas" exibe as **5 movimentações mais recentes** (independente do mês selecionado).
- feat: painel "Pontos em andamento hoje" mostra batidas sem par do dia (entrada sem saída correspondente) com status "aguardando par".

### Histórico do Colaborador

- feat: linhas com **Direito a Folga** (`gives_folga=True`) recebem destaque amarelo suave na tabela.
- feat: seções de ação pessoal (Desconto de Extras, Uso de Folga, Horários, WhatsApp, Alterar Senha) visíveis apenas ao próprio colaborador ou admin.
- feat: rodapé na lista de ações (`safe-area-inset-bottom`) garante acesso ao último item em aparelhos com barra de navegação inferior (iOS/Android).
- feat: painel Resumo do Colaborador com layout mais compacto — hero-metrics em 4 colunas, saldo-blocos com fontes e espaçamentos reduzidos.

### Controle de Acesso

- feat: colaborador ponto é redirecionado para o próprio histórico ao tentar acessar o de outro colaborador.
- feat: link "Histórico" nos cards da tela inicial ocultado para colaboradores sem permissão de ver o perfil alheio.

## [0.10.8] - 2026-05-08

### Feriados

- feat: coluna `ativo` no modelo `Holiday` — feriados podem ser desativados sem ser removidos.
- feat: feriados desativados são tratados como dias comuns (ponto, meta, folga não são afetados).
- feat: 13 feriados nacionais de 2026 pré-carregados automaticamente no primeiro boot.
- feat: botão **Ativo / Ignorado** em cada feriado para alternar status com um clique.
- feat: botão **Editar** inline por feriado — permite alterar data e descrição sem reload.
- feat: feriados exibidos em ordem cronológica crescente.
- feat: feriados inativos exibidos com estilo desbotado e riscado.

## [0.10.7] - 2026-05-08

### Status do Sistema

- fix: rota `/admin/sistema/backup` aceita GET+POST, evitando erro 405 após redirecionamento do Flask-Login.
- feat: botão **⟳ Atualizar** no header da página de sistema — atualiza CPU, RAM e disco via AJAX sem recarregar a página.
- feat: nova rota `GET /api/sistema/status` retorna métricas em JSON para consumo pelo botão de atualização.

## [0.10.6] - 2026-05-08

### Status do Sistema e Backups

- feat: nova página `/admin/sistema` no menu Admin com métricas de CPU, RAM e disco (requer `psutil`).
- feat: barra de progresso colorida por nível (verde → âmbar → vermelho) para cada métrica.
- feat: lista de backups do banco de dados com nome, tamanho e data.
- feat: botão para backup manual imediato na página de sistema.
- feat: backup automático diário às 03:00 via thread daemon, mantendo os últimos 3 arquivos em `.db/backups/`.
- feat: `psutil>=5.9` adicionado ao `requirements.txt`.

## [0.10.5] - 2026-05-08

### Registro de Ponto — Tela de Confirmação

- feat: detecção automática do tipo de batida (Entrada, Saída para Intervalo, Retorno, Saída Final) com tolerância de ±30 minutos baseada nos horários definidos pelo colaborador.
- feat: quando nenhum horário está configurado, exibe hint informando que o tipo pode ser definido manualmente e orientando onde configurar os horários (sem bloquear o registro).
- feat: aviso de privacidade no campo CPF — informa que o dado não é compartilhado, serve apenas para identificação e será criptografado ao confirmar.

### Jornadas Incompletas

- feat: no histórico do colaborador, cada data incompleta exibe badge "incompleto" e botão "✏ Corrigir" (admin).
- feat: modal de correção com diagnóstico textual do problema (ex: "Entrada registrada sem saída final"), lista de batidas existentes com remoção individual e formulário para adicionar batida manual.
- feat: nova rota `GET /api/colaborador/<id>/ponto-dia` — retorna batidas do dia e diagnóstico.
- feat: nova rota `POST /colaborador/<id>/ponto-dia/add` — insere batida manual (admin), NSR gerado automaticamente.
- feat: nova rota `POST /colaborador/<id>/ponto/<record_id>/excluir` — remove batida individual (admin).

## [0.10.4] - 2026-05-07

### Banco de Folgas

- fix: "Acumuladas" agora inclui créditos manuais de folga (`HourEntry.gives_folga=True`), além dos gerados por domingos/ponto.
- fix: "Utilizadas" agora é registrado corretamente via `PontoAjuste(tipo="uso_folga")` ao acionar "Usar Folga".
- fix: `grant_folga` salvava `hours=0` — corrigido para `7h20m` (440 min).
- fix: rotas `use_folga` e `grant_folga` retornavam 405 em GET (refresh/prefetch) — alteradas para aceitar GET+POST com redirect.
- fix: lançamento de horas aceita formato H:MM (ex: `7:20`) além de decimal — `parse_decimal` reescrito.

## [0.10.3] - 2026-05-07

### Painel do colaborador

- fix: `meta_semana_min` agora é reduzida pelas folgas registradas na semana (folgas abatiam apenas os faltantes, mas não a meta exibida).
- fix: `faltantes_semana_min` = `meta_semana_min` (ajustada) − horas trabalhadas.
- Regra aplicada: Meta = 44h − (feriados × 7:20) − (folgas × 7:20); Faltantes = Meta − Trabalhado.

## [0.10.2] - 2026-05-07

### WhatsApp Service

- feat: serviço Node.js (`whatsapp-service/`) com Baileys — integração real com WhatsApp via QR Code.
- feat: `notify.py` — função `boas_vindas_whatsapp()` envia mensagem de boas-vindas ao colaborador ao cadastrar número, com caminho de navegação completo para remoção.
- feat: mensagem de boas-vindas enviada apenas quando o número muda (evita reenvio ao salvar o mesmo número).
- fix: botão "✖ Remover" WhatsApp enviava número salvo em vez de remover — separado em dois formulários independentes (salvar e remover) em `collab_history.html` e `ponto_painel.html`.
- fix: rota `/colaborador/<id>/whatsapp` retornava 405 em GET (refresh) — alterada para aceitar GET+POST, com GET redirecionando para o painel.
- feat: `deploy/mmflux-whatsapp.service` — unit systemd para o serviço WhatsApp.
- feat: `deploy/install.sh` atualizado com instalação do Node 20, dependências e serviço WhatsApp.

### Painel do colaborador

- feat: link "📷 Registrar Ponto" adicionado ao dropdown do colaborador na navbar (`base.html`).
- feat: seção "Entenda como funciona" expandida em `collab_history.html` e `ponto_painel.html` — explica todos os campos, como registrar ponto, como funciona folga, domingo e cálculo de faltantes.
- fix: `faltantes_semana_min` agora desconta 7:20h por cada dia de folga usada (`uso_folga`) em dia útil da semana exibida.
- fix: mesmo desconto aplicado na API `/api/ponto/indicadores`.
- fix: texto explicativo "Meta do Mês" corrigido para "Meta da Semana" com descrição correta dos dias considerados.
- fix: "H Normais" agora informa que domingos não entram na contagem (geram direito a folga, não horas normais).
- fix: botão `+ Turno extra` nos horários de trabalho agora visível (cor `btn-ghost` corrigida fora de contexto de painel claro).

### Painel administrativo (index)

- feat: bloco "Colaboradores" removido — cards de "Resumo por colaborador" agora exibem badge Ativo/Inativo, menu `⋯` (Histórico, Editar, Alternar status) e painel de edição inline (nome, função, diária, senha, admin).
- feat: todos os colaboradores aparecem no resumo mesmo sem lançamentos no mês selecionado; ordenados por ativos primeiro.
- feat: formulário de cadastro de novo colaborador movido para o painel de resumo.
- feat: busca por nome com lupa expansível abaixo do título do painel — filtra cards em tempo real sem reload.
- feat: paginação client-side nos cards (até 10 por página) com botões ‹ 1 2 3 ›.

## [0.10.1] - 2026-05-07

- fix: Service Worker reescrito — páginas HTML sempre buscadas da rede (network-only para navegação), assets estáticos usam cache-first com atualização em background. Elimina tela branca após deploys.
- chore: cache SW atualizado para `mmflux-v7`, versão CSS atualizada para `?v=7`.

## [0.10.0] - 2026-05-06

- feat: painel do colaborador — bloco de opções reformulado em card unificado com linhas separadoras e chevron animado.
- feat: colaborador pode alterar a própria senha de ponto diretamente no painel.
- feat: recuperação de senha via WhatsApp — senha temporária de 6 caracteres gerada com `secrets` e enviada ao número cadastrado.
- feat: seção "Notificações WhatsApp" no painel do colaborador — salvar/remover número e enviar mensagem de teste.
- feat: horários de trabalho em layout 2×2 (Entrada|Saída Intervalo / Volta Intervalo|Saída Final).
- feat: botão "Meu Painel" na tela de captura de ponto agora visível (cor sólida).
- feat: botões de paginação (Anterior/Próxima) na listagem de registros agora visíveis.
- feat: tela de seleção de acesso (Administrador/Colaborador) com descrições legíveis.
- chore: arquivos de desenvolvimento `seed_ponto_test.py` e `_ocr_test.py` removidos do repositório.

## [0.9.1] - 2026-05-02

- fix: nome do mês exibido em PT-BR ("Maio" em vez de "May").
- feat: seletor de meses do resumo reformulado — botões coloridos clicáveis (verde = incluso, vermelho = excluído) sem checkboxes.
- fix: botões de navegação de mês e semana agora com fundo navy sólido, visíveis em fundo claro.
- chore: CHANGELOG retroativo com entradas de v0.6.0, v0.7.0 e v0.8.0.

## [0.9.0] - 2026-05-02

- feat: painel administrativo dedicado no index — exportar PDF, enviar WhatsApp, arquivar mês, definir diária e lançar horas em bloco único visível apenas para admin.
- feat: botão "Exportar PDF" movido para fora do painel admin — disponível para qualquer visitante.
- feat: paginação semanal no histórico do colaborador (nav ← semana →).
- feat: paginação por mês no histórico do colaborador (nav ← Anterior / Próximo →).
- feat: métricas do histórico reordenadas e coloridas: H Bruto (verde), H Descontos (vermelho), neutros (amarelo), Valor Est. (verde + borda verde).
- feat: filtro "Meses no resumo" reposicionado como card no grid de métricas — abre painel inline abaixo do nome.
- feat: seção de lançamentos do histórico agrupada em card branco de largura igual ao hero.
- fix: tabelas em `.hist-content` ocultas pelo reset CSS global — override adicionado.
- fix: botões de navegação invisíveis em fundo claro — override de cor aplicado.
- fix: métricas duplicadas após refatoração — bloco residual removido.
- chore: CSS `.hist-content` refatorado para card único com border-radius e largura uniforme.

## [0.8.0] - 2026-05-02

- feat: campo `gives_folga` em HourEntry — lançamentos marcados como "Direito a Folga" acumulam dias de folga no colaborador.
- feat: modelo Collaborator ganha `folga_days` (contador de dias acumulados).
- feat: rota `POST /collaborators/<id>/use-folga` — desconta 1 dia de folga com data e observação.
- feat: barra de uso de folga no histórico do colaborador (botão desabilitado quando sem saldo).
- feat: tag 🌴 exibida nos lançamentos com folga nas tabelas e no PDF individual.
- feat: checkbox "D. Folga" no formulário de lançar horas e na confirmação de ponto.
- fix: migração automática das colunas `gives_folga` e `folga_days` em bases existentes.
- chore: CSS `.folga-tag`, `.btn-folga`, `.hist-folga-bar` adicionados.

## [0.7.0] - 2026-05-02

- feat: arquivo morto de lançamentos — rota `/archive` lista lançamentos arquivados com totais por mês.
- feat: rota `POST /archive/month` arquiva todos os lançamentos de um mês (remove do painel ativo).
- feat: PDF individual por colaborador (`/collaborators/<id>/pdf`) com todos os lançamentos e totais.
- feat: botão "Baixar PDF" na página de histórico do colaborador.
- feat: template `pdf_collab.html` com capa, sumário e lançamentos detalhados por mês.
- feat: promoção de colaborador a admin — cria login de acesso total a partir do cadastro.
- feat: gestão de admins — criar e remover usuários admin pelo painel.
- fix: `/ponto/associar-cpf` exigia `login_required` em vez de `ponto_required`.
- fix: confirmação OCR renderiza HTML direto em vez de redirecionar via URL externa.
- fix: rota `/ponto/upload` aceita GET para evitar erro 405 após OCR.

## [0.6.0] - 2026-05-02

- feat: sistema de usuários exclusivo para alimentar o ponto via câmera.
- feat: colaboradores cadastrados podem fazer login com nome + senha de ponto.
- feat: coluna `ponto_password_hash` no modelo Collaborator com migração automática.
- feat: decorator `ponto_required` — câmera/upload/confirmar exigem autenticação (admin ou colaborador).
- feat: página de login de colaborador (`/ponto/login`).
- feat: topbar exibe nome do colaborador logado com botão de sair.
- feat: função `suggest_ponto_password` — gera senha padrão por posição alfabética (ex: Luciano → L1221, Maria → M13118).
- feat: botão "Sugerir" no cadastro e edição de colaborador preenche senha automaticamente via AJAX.
- feat: rota `POST /collaborators/<id>/set-ponto-password` para admin definir/redefinir senha.
- feat: rota `GET /api/suggest-password` retorna senha sugerida para um nome.
- feat: filtro Jinja `|hhmm` — converte horas decimais para formato legível (ex: 7.38 → 7h23).
- feat: histórico de colaborador usa `|hhmm` em todos os valores de horas.
- feat: OCR via Gemini API (`gemini-flash-lite-latest`) como motor primário; Tesseract como fallback.
- chore: `.gitignore` atualizado para ignorar `uploads/` e arquivos de banco.

## [0.5.1] - 2026-05-02

- feat: fluxo de confirmação antes de registrar o ponto (página ponto_confirmar.html).
- feat: todos os campos OCR são editáveis pelo usuário antes de confirmar.
- feat: intervalo calculado automaticamente ao chegar a 2ª batida do dia (entrada/saída em qualquer ordem).
- feat: HourEntry criado automaticamente com nota "Ponto: HH:MM → HH:MM (comprovante)".
- feat: campo `processed` em PunchRecord evita duplo cálculo de intervalo.
- feat: migração automática do campo `processed` em bases existentes.
- fix: rota /ponto/uploads liberada para exibir preview do comprovante na tela de confirmação.
- fix: import `re` adicionado ao app.py.

## [0.5.0] - 2026-05-02

- feat: módulo de ponto eletrônico via OCR de comprovante fotografado.
- feat: modelo PunchRecord (data, hora, NSR, NREP, AD, CPF, colaborador).
- feat: campo `cpf` no modelo Collaborator para vinculação automática.
- feat: rota GET/POST /ponto — página mobile com captura de câmera.
- feat: deduplicação por NSR (Número Sequencial de Registro único do relógio).
- feat: vínculo manual de registros pendentes (admin).
- feat: exclusão de registros de ponto (admin).
- feat: rota `/ponto/uploads/<file>` para servir comprovantes (admin).
- chore: migração automática de schema (coluna cpf em collaborator).
- chore: pytesseract e Pillow adicionados ao requirements.txt.
- chore: MAX_CONTENT_LENGTH 15 MB para uploads de imagem.

## [0.4.8] - 2026-04-18

- fix: PDF não quebra mais no meio do bloco de um colaborador em "Lançamentos Detalhados" (evita corte entre páginas).

## [0.4.7] - 2026-04-18

- feat: diária individual por colaborador (cadastro e edição).
- feat: histórico agora mostra valor estimado que o colaborador receberá.
- feat: cálculo no histórico usa a diária do colaborador; fallback para diária global quando não definida.
- chore: migração automática de schema para adicionar coluna `daily_rate` em bases SQLite existentes.

## [0.4.6] - 2026-04-18

- feat: edição de colaborador também na página de histórico.
- ajuste: ao editar colaborador a partir do histórico, permanece na mesma página.
- fix: variáveis CSS de layout (--page-px e --max-w) definidas para corrigir cards encostando nas bordas no histórico.

## [0.4.5] - 2026-04-18

- feat: edicao de colaborador na lista principal (nome e funcao).
- novo endpoint `POST /collaborators/<id>/update` para persistir alteracoes.
- notify.py: evento de colaborador atualizado via WhatsApp.

## [0.4.4] - 2026-04-18

- fix: rodapé do PDF em duas linhas — site na primeira, número de página na segunda, ambos centralizados.

## [0.4.3] - 2026-04-18

- fix: número de página centralizado no rodapé, separado do texto da esquerda.

## [0.4.2] - 2026-04-18

- fix: remover page-break-after da capa para evitar página em branco; capa e conteúdo na mesma página.

## [0.4.1] - 2026-04-18

- fix: mover numeração de página do cabeçalho para o rodapé do PDF.

## [0.4.0] - 2026-04-18

- fix: substituir páginas nomeadas por @page/:first no PDF para eliminar página em branco no WeasyPrint.

## [0.3.9] - 2026-04-18

- fix: remover regra @page genérica que gerava página em branco antes da capa no WeasyPrint.

## [0.3.8] - 2026-04-18

- fix: remover page-break-after duplo no .cover que gerava páginas em branco no PDF.

## [0.3.7] - 2026-04-17

- Botao "Enviar Resumo" no painel principal (visivel apenas para usuarios autenticados).
- POST /whatsapp/resumo: gera resumo mensal de todos os colaboradores e envia para o grupo WhatsApp Notify.
- Mensagem formatada com nome, horas bruto/desconto/liquido e dias por colaborador + totais gerais.
- Botao verde (#25d366) ao lado do Exportar PDF, com confirmacao antes do envio.
- notify.py: funcao resumo_geral(cards, totals).

## [0.3.6] - 2026-04-17

- Pagina de historico por colaborador (`/collaborators/<id>/history`).
- Mostra totais globais + lancamentos agrupados por mes com resumo mensal.
- Botao Historico na lista de colaboradores (visivel para todos).
- Editar/excluir lancamento do historico redireciona de volta ao historico.
- CSS: .hist-hero, .hist-month, .mstat (pos/neg/net).

## [0.3.5] - 2026-04-17

- Notificacoes WhatsApp via servico multimax.tec.br/notify.
- Eventos: novo lancamento, atualizacao, remocao, colaborador criado/toggle.
- notify.py: gateway async (thread daemon), fallback de URL, falha silenciosa.
- requests adicionado ao requirements.txt.

## [0.3.4] - 2026-04-17

- PDF com duas secoes: resumo geral por colaborador + lancamentos detalhados.
- Capa com gradiente da marca, tabela de entradas com data/horas/observacao.

## [0.3.3] - 2026-04-17

- Renomeia sistema de Fluxos Zero/MMFlux para MultiMax nos templates, manifest, service e PDF.

## [0.3.2] - 2026-04-17

- Fix: WeasyPrint atualizado para 68.x — incompatibilidade com pydyf 0.12.1 causava erro ao gerar PDF.

## [0.3.1] - 2026-04-17

- Remove h2 desnecessario do hero.

## [0.3.0] - 2026-04-17

- Fix: botao cortado na topbar no mobile (min-height, padding, flex-shrink, logo menor).
- Texto do botao encurtado para "Entrar" na topbar.

## [0.2.9] - 2026-04-17

- Fix: CSS duplicado removido (create_file havia colado CSS antigo ao novo).
- Fix: manifest.json com purpose separados (any + maskable) para habilitar PWA install no Chrome.

## [0.2.8] - 2026-04-17

- Fix: SW cache bumped para mmflux-v2 para invalidar CSS antigo.

## [0.2.7] - 2026-04-17

- Redesign visual completo: topbar navy com gradiente, hero colorido com decoracao, cards com borda teal, tipografia hierarquica.
- Logo branca na topbar escura.
- brand-text com nome e subtitulo na topbar.

## [0.2.6] - 2026-04-17

- Corrigido topbar mobile: flex-wrap para nao sobrepor o conteudo.
- padding-top do body calculado dinamicamente via JS conforme altura real da topbar.

## [0.2.5] - 2026-04-17

- Logo atualizada para MMFx2.png.

## [0.2.4] - 2026-04-17

- Corrigido erro de Service Worker: rota /sw.js serve o arquivo com header Service-Worker-Allowed para escopo raiz.

## [0.2.3] - 2026-04-17

- Logo MMFx adicionada na topbar.
- Paleta de cores atualizada com as cores da logomarca (navy, teal, azul medio).
- Gradiente dos botoes alinhado com a identidade visual.

## [0.2.2] - 2026-04-17

- Layout mobile-first: topbar fixa, coluna unica, cards de lancamento.
- Fonte trocada para Ubuntu / Ubuntu Mono.
- Brand atualizado para MultiMax com subtitulo "Sistema simplificado".
- Configuracoes do VS Code para associacao de arquivos VERSION.

## [0.2.1] - 2026-04-17

- Ajustado startup do Flask para usar `FLUXOS_HOST`/`FLUXOS_PORT`/`FLUXOS_DEBUG`.
- Host padrao alterado para `0.0.0.0`, permitindo acesso externo na VPS.

## [0.2.0] - 2026-04-17

- Adicionado script de instalacao automatica para Linux (deploy/install.sh).
- Adicionado arquivo de servico systemd (deploy/mmflux.service).
- Instrucoes de deploy no README.

## [0.1.0] - 2026-04-17

- Versao inicial do projeto Fluxos Zero.
