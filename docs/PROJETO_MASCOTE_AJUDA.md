# Projeto do mascote virtual de ajuda — ARKLAND Brasil PVE

**Estado:** primeira entrega funcional implementada localmente; não publicada.  
**Escopo desta entrega:** botão de ajuda com personagem, olhar que acompanha o ponteiro, piscada, FAQs e integração ao formulário/lista de tickets já existentes.  
**Referência original preservada:** `../ig/Gato Fantástico no Botão de Ajuda.png`.

## 1. Objetivo e continuidade

O mascote deve orientar jogadores com uma presença discreta, acolhedora e acessível, reutilizando o atendimento já existente. Este documento é o registro de continuidade: contém a arquitetura, decisões, estado verificável, limitações e a ordem segura para concluir as etapas seguintes. Mudanças futuras devem atualizar este arquivo e o item correspondente em `PENDENCIAS.md`.

Não há IA generativa nesta solução. As respostas são textos previamente escritos; situações sem solução seguem para o formulário normal de tickets. O mascote não cria um segundo sistema de atendimento nem chama serviços de terceiros.

## 2. Diagnóstico da implementação existente

- Frontend: página HTML/CSS/JavaScript servida pelo Flask em `plugin/arkshop_web/static/index.html`.
- Atendimento: widget flutuante com lista, detalhes, respostas, tradução já existente e criação por `POST /api/tickets`.
- Identidade: o objeto global `_auth` fornece `steam_persona` e `display_name` após autenticação.
- Reposicionamento: `_scheduleSupportFabAvoidAmberMeter()` evita colisão do botão com o indicador de Ambares. A nova composição conserva o mesmo `#support-fab` e sua posição fixa, mantendo essa proteção.
- Distribuição: arquivos na raiz `static/` são servidos pelo servidor WebStore; a nova arte vive nessa pasta para ser encontrada junto ao HTML.

## 3. Arte e fidelidade visual

A imagem aprovada é uma composição raster achatada, sem transparência nem camadas separadas para olhos, cabeça, orelhas ou cauda. Não é possível animar os olhos de forma convincente apenas movendo pixels da imagem inteira. A arte original não foi modificada.

Foi criada uma derivação transparente, apenas do felino, em `plugin/arkshop_web/static/arkland-help-cat-v1.png`. Ela mantém o conceito e a identidade aprovada (felino azul, detalhes âmbar, olhos dourados, colar com cristal e cauda), mas é um derivado de imagem e não uma cópia pixel a pixel da referência. A placa e o texto do botão são feitos em HTML/CSS para continuarem legíveis e acessíveis em vários tamanhos. O overlay SVG fornece olhos vetoriais animáveis sobre a arte.

**Antes de publicar:** comparar a derivação lado a lado com a imagem aprovada em resolução de desktop e telefone e ajustar escala/posicionamento. Se a correspondência visual exata for obrigatória, encomendar/preparar uma arte em camadas a partir da ilustração aprovada, com licença e aprovação visual, sem apagar a referência original.

## 4. Arquitetura entregue

O botão original conserva seu ID, semântica de botão, estado `aria-expanded` e ligação ao diálogo de atendimento. Agora apresenta a arte em escala 25% menor que a primeira prévia (143×165 px no desktop e 112×134 px no mobile) e o texto “Precisa de ajuda?”. Ao ativar, abre a aba de dúvidas rápidas. A navegação mantém “Meus tickets” e “Novo ticket”.

### Olhar e piscada

- Dois grupos de pupila no SVG são deslocados em relação à posição do ponteiro.
- Movimento limitado a 24 unidades horizontais e 17 verticais no `viewBox`, evitando que a pupila saia da íris. A origem é o centro entre os olhos e a sensibilidade usa o tamanho do rosto, tornando o olhar visível sem depender da resolução total da janela.
- Atualização agrupada com `requestAnimationFrame`, sem polling contínuo.
- Toque não tenta simular acompanhamento do cursor; tocar no botão abre ajuda.
- Ao sair do botão, ocultar a página ou ativar movimento reduzido, o olhar volta ao centro.
- Piscada ocasional tem temporizador espaçado e usa CSS.
- `prefers-reduced-motion` desativa o movimento do olhar, piscadas e animação de abertura.

O olhar usa uma posição global do ponteiro, limitada pelo tamanho da janela, com o centro do rosto como repouso. Não coleta, armazena ou envia posição do ponteiro.

### Ajuda e tickets

FAQs cadastradas: catálogo/criaturas, resgates/entregas, kits, licenças/Ambares, doações e vínculo do Discord. Cada resposta permite indicar se resolveu. “Ainda preciso de ajuda” abre o formulário existente, pré-preenche um assunto e contexto editáveis e mantém autenticação, categoria e envio atuais. Não altera a API nem o modelo de ticket.

O cabeçalho usa `steam_persona`, depois `display_name`, e apresenta uma saudação genérica se o usuário não estiver autenticado. O nome é inserido por `textContent`, evitando interpretação de HTML fornecido pelo perfil.

## 5. Arquivos envolvidos

- `plugin/arkshop_web/static/index.html`: marcação, CSS, FAQs, saudação, olho/piscada e integração com as funções atuais do widget.
- `plugin/arkshop_web/static/arkland-help-cat-v1.png`: derivação transparente do mascote usada pelo botão.
- `plugin/arkshop_web/tests/test_support_mascot.py`: contratos estáticos para acessibilidade, asset, tópicos de FAQ, fluxo de ticket e limites de movimento.
- `docs/PROJETO_MASCOTE_AJUDA.md`: este plano/registro.
- `PENDENCIAS.md`: atualizar com o estado local e validação ainda pendente de publicação.
- `ig/Gato Fantástico no Botão de Ajuda.png`: referência aprovada, preservada e não alterada.

## 6. Plano do início à conclusão

### Etapa A — Base e segurança (concluída localmente)

Preservar arquivo de referência, conferir componente atual, não tocar em banco/perfis/servidores, usar o widget de tickets existente e manter respostas sem conexão externa.

**Aceite:** asset separado e servido pela pasta estática; o mesmo botão abre o mesmo diálogo; rota existente `/api/tickets` continua sendo usada.

### Etapa B — Primeira experiência funcional (implementada localmente)

Adicionar personagem ao botão, overlay de olhar, piscada, responsividade, preferência de movimento reduzido, FAQs, saudação personalizada e caminho de escalonamento para ticket.

**Aceite automático:** testes `test_support_mascot.py` passam; scripts compilam; asset existe como PNG RGBA; testes atuais de tickets não regridem.

### Etapa C — Verificação visual e de interação (parcialmente concluída)

Smoke test local concluído: asset carregou com 1294×1216; ponteiro alterou a transformação da pupila; movimento reduzido removeu a transformação e a transição; FAQ de resgate abriu resposta e formulário com assunto/contexto; saudação autenticada simulada exibiu “Olá Ciano, como podemos ajudar você?”. Ainda falta inspeção visual comparativa das coordenadas em desktop/móvel e ativação por teclado/toque em navegador com backend real. A página foi servida pelo servidor estático, então endpoints retornaram 404/501; nenhum ticket foi enviado.

**Aceite:** pupilas permanecem dentro das íris, texto visível, sem sobreposição crítica, sem erro JavaScript, fluxo de tickets existente intacto.

### Etapa D — Refinamento visual da arte (pendente)

Tentativas de recortar a cauda isoladamente e de oscilar o personagem inteiro não corresponderam ao resultado esperado e foram removidas. A direção desejada é manter o gato sentado e animar as partes articuladas (cabeça, cauda e patas), com movimentos corporais de apoio quando necessários. A arte atual é achatada; para alcançar esse comportamento sem duplicações, preparar camadas limpas ou sprites consistentes a partir da imagem aprovada. O olhar e a piscada permanecem no preview.

**Aceite:** gato continua visualmente sentado; cauda/cabeça/patas se movem articuladamente sem duplicação, halos ou deformações; olhos permanecem alinhados; movimento reduzido desativa as animações.

### Etapa E — Testes de regressão e pacote (pendente)

Rodar testes novos e existentes do widget/tickets, validar montagem de pacote estático/frozen se aplicável e confirmar cache busting. Revisar tamanho do PNG e carregamento lazy/low priority.

**Aceite:** nenhum teste regressivo; arte incluída no pacote; sem alterações de schema ou migração.

### Etapa F — Atualização e validação publicada (não autorizada nesta entrega)

Preparar release do WebStore, publicar somente após autorização específica, fazer smoke test da página publicada e validar fluxo visual com conta autenticada de teste. Reversão: restaurar versão anterior dos arquivos estáticos/release; não precisa restaurar dados do banco porque o recurso não cria schema nem migra dados.

**Aceite final:** publicação autorizada, asset carregado, gaze/reduced-motion verificados nos navegadores suportados, FAQ e tickets confirmados sem registros reais não intencionais.

## 7. Testes e validações

Resultado desta rodada: tanto o recorte isolado da cauda quanto a oscilação do personagem inteiro foram removidos após avaliação do usuário. O mascote permanece assentado; olhar e piscada continuam. `test_support_mascot.py` precisa ser repetido após a retirada da animação corporal. Os **41 testes** descritos anteriormente pertencem à validação prévia e não foram repetidos nesta rodada.

Testes automatizados não substituem a inspeção visual do SVG sobre a derivação nem o teste manual da página em navegador real. Não foi feita publicação, conexão a produção, alteração de banco, nem envio de ticket real.

## 8. Riscos e decisões abertas

1. **Fidelidade:** arte derivada com gerador não é pixel-identical à referência. Aprovação humana visual é necessária.
2. **Geometria dos olhos:** SVG usa coordenadas estimadas para o asset atual; inspeção local em escala real deve confirmar o alinhamento.
3. **Conteúdo de FAQ:** respostas são gerais e não prometem prazos, créditos ou regras específicas. Revisar conforme regras operacionais oficiais antes da publicação.
4. **Acessibilidade:** foco, contraste e leitor de tela têm marcação inicial; verificar com teclado e leitor de tela.
5. **Desempenho:** um PNG local e SVG pequeno; `requestAnimationFrame` só acompanha eventos do ponteiro. Medir no telefone de referência antes de publicar.
6. **Compatibilidade:** testar browsers suportados pelo público. Em navegadores sem SVG/CSS avançado, o HTML continua com o botão acessível e imagem estática.

## 9. Roteiro de teste local

1. Iniciar a WebStore local em modo de desenvolvimento e abrir a página inicial.
2. Confirmar carregamento de `arkland-help-cat-v1.png` sem erro 404.
3. Mover o cursor para cima, baixo, esquerda e direita; confirmar seguimento limitado e centro ao sair.
4. Aguardar uma piscada; ativar movimento reduzido no sistema e repetir, confirmando ausência de animação.
5. Usar Tab e Enter/Espaço no botão e verificar nome acessível; em telefone, tocar no botão.
6. Abrir cada FAQ, voltar, selecionar “Ainda preciso de ajuda”; conferir assunto/contexto no formulário.
7. Em ambiente de teste autenticado, enviar ticket de teste e confirmar sua presença na lista; nunca usar produção para esse teste sem autorização.
8. Validar “Meus tickets”, detalhe, resposta e fechamento para confirmar que a integração antiga não foi substituída.

## 10. Próximo passo

Rodar os testes automatizados criados e os testes focados do widget/tickets; em seguida servir a página local para ajuste visual das coordenadas dos olhos. Antes de publicar, solicitar avaliação da derivação da arte e completar validação visual de teclado/móvel. O trabalho futuro não deve reiniciar a investigação do widget: continuar a partir deste documento e do item de pendências atualizado.
