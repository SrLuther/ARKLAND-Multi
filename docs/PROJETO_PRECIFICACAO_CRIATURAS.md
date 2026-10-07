# Precificação de criaturas

| Campo | Valor |
|-------|-------|
| **Status** | Fórmulas na página de economia. Catálogo de produção não regravado. |
| **Data** | 2026-10-07 |
| **Escopo** | Catálogo, P2P e encomenda. Aplicar grava só o Price, e só se o operador pedir. |

---

## Status

A página Economia — Comércio mostra as três contas e a tabela das criaturas do catálogo que a loja já abre. Aplicar grava somente o campo Price, individual ou em massa, nesse mesmo arquivo. Este registro não regravou o catálogo de produção.

As seções seguintes são as regras travadas, nesta ordem. A página usa estas contas.

## Problema

A Economia — Comércio foi feita para criatura sem tier: um papel, um piso. O Price do catálogo é digitado. R = preço ÷ nível não sugere o preço de catálogo. O Primal Fear e as expansões têm escada de tier. Vanilla também está no catálogo. O piso antigo `min(R + B×Q, teto)` e o corte em 600.000 juntavam criaturas diferentes no mesmo número. Isso não pode acontecer. A conta travada abaixo substitui esse piso.

## Origem

Base extrema = **10.000**. Tudo o que for calculado sai dela. Ela é a origem da escala. Não é uma conta reversa de 2.000 ÷ 0,2.

Preço de catálogo da criatura = **10.000 × coeficiente da família × índice**.

O dinheiro nasce nos 10.000. Coeficiente e índice só repartem essa origem.

Conta do Rex vanilla (coeficiente 1, índice 0,75): **10.000 × 1 × 0,75 = 7.500**.

## Coeficiente da família

Coeficiente = raiz da família ÷ raiz do Rex.

A raiz do Rex é **18.000** e serve só de régua da proporção. O Rex tem coeficiente 1. O dinheiro nasce dos 10.000.

A tabela 10.000 × índice é a coluna do Rex, não o preço de todas as espécies. O preço de outra família multiplica de novo pelo coeficiente.

| Família | Raiz | Coeficiente | Conta | Preço de catálogo |
|---------|------|-------------|-------|-------------------|
| Rex vanilla | 18.000 | 1 | 10.000 × 1 × 0,75 | **7.500** |
| Rex alpha | 18.000 | 1 | 10.000 × 1 × 3,75 | **37.500** |
| Giga vanilla | 22.500 | 1,25 | 10.000 × 1,25 × 0,75 | **9.375** |
| Giga alpha | 22.500 | 1,25 | 10.000 × 1,25 × 3,75 | **46.875** |
| Utilitária alpha | 800 | 800 ÷ 18.000 | 10.000 × (800 ÷ 18.000) × 3,75 | **1.667** |

Giga: 22.500 ÷ 18.000 = 1,25.

Utilitária: 10.000 × 3,75 = 37.500; 37.500 × 800 ÷ 18.000 = 1.666,67, que fecha em **1.667**.

## Índices

Mais básico → mais forte. Todos os índices ficam na mesma tabela, inclusive Noxious e Fey. A coluna de preço é o Rex (coeficiente 1). O preço de outra família é essa coluna multiplicada de novo pelo coeficiente, o mesmo que 10.000 × coeficiente × índice.

| # | Degrau | Multiplicador | Índice | Coluna do Rex (10.000 × índice) |
|---|--------|---------------|--------|----------------------------------|
| 1 | Vanilla | 1× | 0,75 | 7.500 |
| 2 | Toxic | 3 | 2,25 | 22.500 |
| 3 | Noxious (acompanha Toxic) | 3 | 2,25 | 22.500 |
| 4 | Alpha | 5 | 3,75 | 37.500 |
| 5 | Elemental Basic (Fogo, Gelo, Cáustico, Elétrico) | 7,5 | 5,625 | 56.250 |
| 6 | Apex | 10 | 7,5 | 75.000 |
| 7 | Elemental Advanced (Luz e Trevas) | 14 | 10,5 | 105.000 |
| 8 | Fabled | 16 | 12 | 120.000 |
| 9 | Omega | 13 | 9,75 | 97.500 |
| 10 | Celestial e Demonic | 27,5 | 20,625 | 206.250 |
| 11 | Fey (acompanha Celestial e Demonic) | 27,5 | 20,625 | 206.250 |
| 12 | Chaos e Spirit | 40 | 30 | 300.000 |
| — | Primal Tek (fora da linha de kibble) | 12 | 9 | 90.000 |

Conta de leitura da coluna: Vanilla do Rex, 10.000 × 0,75 = **7.500**. Alpha do Rex, 10.000 × 3,75 = **37.500**. Giga alpha multiplica de novo pelo coeficiente: 37.500 × 1,25 = **46.875**.

- Vanilla: Toxic é 3× o vanilla. O 1× do Vanilla é o único implícito.
- Noxious acompanha Toxic: mesmo multiplicador, índice e coluna do Rex (22.500).
- Omega fica depois de Fabled na árvore. Não unir os degraus. Não subir o 13 para passar o 16. Na mesma família a sugestão da Omega pode ficar abaixo da Fabled.
- Celestial e Demonic: mesmo nível, em paralelo. 27,5 é o meio de 25 e 30. Fey acompanha os dois: mesmo multiplicador, índice e coluna do Rex (206.250).
- Chaos e Spirit: mesmo ápice domesticável. 40 é o meio de 35–45.
- Na mesma família, Toxic fica em 60% da Alpha, porque 2,25 ÷ 3,75 = 0,6. O coeficiente cancela. No Rex: 22.500 ÷ 37.500 = 0,6.

Primal Tek: índice 9, coluna do Rex **90.000** = 10.000 × 9. Fora da linha de kibble. O 12× vale somente se a ficha Useful Info já registrar 12×. Não é herança.

Quem não tem multiplicador próprio e está no mesmo nível de quem tem, recebe esse multiplicador. Noxious e Fey entram por essa herança e já estão na tabela acima. Não aplicar essa herança em Elder, Malin, Buffoon, Corrupted, Miscellaneous nem em chefes.

## Nível fora do preço de catálogo

O nível é a ficha do produto. O catálogo vende o Megalossauro no nível 200. Ele não multiplica o preço. Multiplicar pelo nível estoura a escala.

Conta: o preço de catálogo do Megalossauro Fey é **103.125** no nível 200. 103.125 × 200 = 20.625.000, e esse número não é o preço.

O nível só voltaria se a mesma família e o mesmo tier fossem vendidos em dois níveis com preços diferentes. Aí seria um fator leve. Esse fator ainda não existe.

## Exemplo completo

Megalossauro Fey, do começo ao fim.

| Passo | Valor |
|-------|-------|
| Família vanilla | megalosaurus |
| Raiz | 9.000 |
| Papel | ataque |
| Tier | A |
| Coeficiente | 9.000 ÷ 18.000 = **0,5** |
| Índice Fey | **20,625** |
| Preço de catálogo | 10.000 × 0,5 × 20,625 = **103.125** |
| Nível de venda | 200, não altera os 103.125 |

10.000 × 0,5 = 5.000. 5.000 × 20,625 = **103.125**.

## P2P

Os status somam um adicional em cima do preço de catálogo. Não substituem esse preço.

Anúncio = preço de catálogo + adicional.

Adicional = arredondamento de B × Q.

No papel ataque, os status com peso são estes. Velocidade e comida têm peso 0 e ficam de fora.

| Status | Peso |
|--------|------|
| Vida | 0,35 |
| Dano | 0,45 |
| Peso | 0,10 |
| Energia | 0,10 |
| Velocidade | 0 |
| Comida | 0 |

pts_ref = **254**. gamma = **0,82**. Cada status entra como (pontos ÷ 254) ^ 0,82. Q é a média ponderada desses status e fica limitado a 1.

No megalossauro, B = **66.000**. Esse é o premium_budget gravado. O fallback do ataque tier A dá o mesmo: alvo 75.000 − raiz 9.000 = 66.000. O tier Fey não cria outro B: papel e tier vêm da família vanilla.

A lista atual de variantes do código tira alpha, fabled e aberrante, e não tira a palavra fey. O B de 66.000 é o da família vanilla; para o adicional entrar, o anúncio precisa casar com essa família.

Caso checado, todos esses status em 254:

- Cada parcela: (254 ÷ 254) ^ 0,82 = 1.
- Q = 0,35×1 + 0,45×1 + 0,10×1 + 0,10×1 = 1. O limite 1 não reduz.
- Adicional = arredondamento de 66.000 × 1 = **66.000**.
- Anúncio = 103.125 + 66.000 = **169.125**.

R = preço ÷ nível fica de fora dessa soma.

O piso antigo `min(R + B×Q, teto)` não é esta conta. Os tetos 150.000 (código) e 600.000 (documento) pertenciam a esse piso antigo e não se aplicam em cima de 103.125 + adicional.

## Encomenda

A encomenda fica sempre acima do P2P dos mesmos status. Não há teto fixo de 275.000.

Cores = fração do catálogo. Uniforme: 8%. Se não for uniforme: 5% + 2% por região. Sem cores, a fração é zero.

Encomenda = (P2P + cores + catálogo × 0,25 + (P2P + cores) × 0,35) × 1,05.

A soma leva o P2P, as cores, 25% do catálogo e mais 35% de (P2P + cores). O 1,05 entra por último. Com preço de catálogo positivo, o resultado passa o P2P.

Caso checado, Megalossauro Fey, status em 254, sem cores:

| Passo | Valor |
|-------|-------|
| Catálogo | 103.125 |
| P2P | 169.125 |
| Cores | 0 |
| Catálogo × 0,25 | 25.781,25 |
| (P2P + cores) × 0,35 | 59.193,75 |
| Soma | 254.100 |
| × 1,05 | **266.805** |

266.805 é maior que o P2P 169.125. O nível continua de fora.

## Fora da conta automática

### Tek Strider

Tek Strider (species_key tekstrider) não é âncora, não recebe preço automático e não é o topo. Sem preço manual, o resgate continua bloqueado.

### Paralelos e utilitários

Elder, Malin, Buffoon, Corrupted, Miscellaneous e chefes não domesticáveis continuam sem índice. Sem índice, a conta 10.000 × coeficiente × índice não gera preço. Sem multiplicador inventado para esses grupos.

### Chefes não domesticáveis

Fora do cálculo, para evitar desgaste. Continuam visíveis, discriminados, com a frase:

> Não entra no cálculo. São chefes não domesticáveis. Ficam de fora para evitar desgaste na base de preço.

| Grupo | Ordem |
|-------|-------|
| Mini Bosses | 0 |
| Primals | 1 |
| Origins | 2 |
| Emperor e Empress | 3 |
| Guardians | 4 |
| Gods/Creators | 5 |
| Colossus | 6 |
| Pikkon's Revenge | 7 |

Sugestão de remoção do catálogo, para evitar problema posterior. Sem preço sugerido. A remoção só ocorre se o operador marcar. Não sai sozinho.

## Separação do catálogo

A base 10.000 é a origem de cada trilha, e o cálculo muda por tipo. A trilha de criaturas é a única com a fórmula acima.

Kits, recursos, estruturas, consumíveis, armaduras, selas, armas, ferramentas, blueprints, veículos, itens sem categoria, licenças e comandos ainda não têm conta a partir de 10.000.

Kits já têm, à parte, pacote de 10 dinos nível 1 com 25% de desconto. Licenças já têm desconto de renovação. Essas duas contas não saem da base 10.000.

Conta que separa as trilhas: o Rex vanilla de criatura faz 10.000 × 1 × 0,75 = **7.500**. O pacote de 10 dinos nível 1 entra com desconto de 25%, e a licença entra com desconto de renovação. Nenhuma das duas usa 10.000 × coeficiente × índice.

## Conferência

| Número | Conta |
|--------|-------|
| 7.500 | 10.000 × 1 × 0,75 |
| 103.125 | 10.000 × 0,5 × 20,625 |
| 169.125 | 103.125 + 66.000 |
| 266.805 | (169.125 + 103.125 × 0,25 + 169.125 × 0,35) × 1,05, sem cores |

## O que permanece

- A raiz da família vanilla entra como régua do coeficiente (raiz ÷ 18.000) e como insumo do B. O preço de catálogo nasce dos 10.000.
- Papel (utilitário, locomoção, ataque, raid, boss) e os pesos de Q continuam. Q é do indivíduo no anúncio, não do preço de espécie no catálogo.
- Catálogo não grava sozinho. Aplicar é ação manual, nas linhas marcadas. `catalog.json` não entra em release.

## Duas escalas, sem achatar no teto

Catálogo e anúncio são duas contas ligadas. O preço de catálogo é 10.000 × coeficiente × índice. O anúncio soma o adicional em cima desse preço.

No Megalossauro Fey: catálogo **103.125**, anúncio **169.125**, encomenda sem cores **266.805**. A encomenda fica acima do P2P. Sem teto de 275.000.

O piso antigo `min(R + B×Q, teto)` não é esta conta. Os tetos 150.000 (código), 275.000 (encomenda antiga) e 600.000 (documento) pertenciam a esse piso antigo e não se aplicam em cima de 103.125 + adicional, nem em cima da encomenda. Duas criaturas diferentes não ficam gravadas no mesmo teto.

Na mesma família, Toxic fica em 60% da Alpha (2,25 ÷ 3,75 = 0,6).

Nos dados atuais de market_species_defaults.json, a maior raiz vanilla que permanece neste cálculo é o Giga (root_value 22.500). A mais barata continua o empate em 800 das utilitárias tier C. Esses valores são fato desses dados, não o preço final do catálogo. O Tek Strider não é o topo.

## Transparência do reajuste

Antes de gravar, cada linha que entra na conta mostra: família, tier, índice, raiz, coeficiente, nível da ficha, preço de catálogo sugerido, adicional, anúncio, preço atual e a diferença. O nível da ficha aparece e não multiplica o preço.

- Quem não tem multiplicador: sem sugestão, com o motivo.
- Chefe: sugestão de remoção, sem preço.
- Aplicar só nas linhas marcadas. A linha guarda a base que gerou o preço.

## Resgate

Sem preço, resgate bloqueado. Vale para sem sugestão, chefe ainda no catálogo e linha com preço limpo.

Valor manual libera o resgate dessa linha. A sugestão de remover o chefe continua visível. Se gravarem preço manual no chefe, o resgate abre mesmo assim.

## Decisões ainda não fechadas

A fórmula do preço de catálogo, a do anúncio e a da encomenda estão fechadas nas seções acima. A encomenda fica sempre acima do P2P dos mesmos status e não usa teto de 275.000. O fator de nível leve ainda não existe. Ele só entra se a mesma família e o mesmo tier forem vendidos em dois níveis com preços diferentes.

## Fora deste projeto

Não misturar:

- `/loot` parado
- número de dano adiado
- dino selvagem com status personalizado não feito

## Onde isso aparece

Economia — Comércio, aba Precificação. No topo estão as três fórmulas, com 7.500, 103.125, 169.125 e 266.805. Abaixo, as criaturas do catálogo que a loja abre: família, coeficiente, índice, preço calculado, preço atual e ajuste manual.

Aplicar grava só o Price. A massa faz cópia ao lado do catálogo e não apaga `catalog.json.bak-antes-itens-pf` nem `catalog.json.bak-antes-ajuste-precos`. Tek Strider, sem família e sem índice não recebem preço automático; o ajuste manual, se preenchido, grava.
