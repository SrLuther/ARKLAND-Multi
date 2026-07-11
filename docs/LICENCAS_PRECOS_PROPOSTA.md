# PROPOSTA DE LICENÇAS — ARKLAND

## Escada Completa de 12 Tiers (ItensAlfa)

> **Tipo:** Proposta de Precificação — ✅ Direção Aprovada (pendente implementação)
> **Status:** v3.0 — Opção Aprovada (escada 6k–230k)
> **Versão:** 3.0 — Jul 2026
> *(v3.0: escada aprovada com topo em **230.000 Â** · preserva preços originais Gama/Beta/Alfa · estende 9 novos tiers até Exótico · licenças são subscrição de acesso TEK, não comparáveis 1:1 a dinos)*
> *(v2.0: incorpora planilha* `Itens Alfa.xlsx` *completa · matriz de acesso Delta-only · desconto de renovação · preços por categoria de item)*
>
> **Base:**
>
> - Sistema atual: `plugin/CustomShop/configs/config.json` — 3 licenças pagas + Nuvem
> - Planilha: `Itens Alfa.xlsx` — mapeamento completo de armaduras, armas, ferramentas, selas, estruturas, criaturas e utilitários
> - Âncoras econômicas: `[ECONOMIA_ARKLAND.md](./ECONOMIA_ARKLAND.md)` e `[PROJETO_ECONOMIA_IDEAL.md](./PROJETO_ECONOMIA_IDEAL.md)`
>
> **Referência cruzada:** `[PROJETO_ARKLAND_MASTER.md](./PROJETO_ARKLAND_MASTER.md)` · `[TABELA_PRECOS_DINOS.md](./TABELA_PRECOS_DINOS.md)`

---



## Novidades v3.0 vs v2.0 — Opção Aprovada

> **Decisão:** preços de licença devem seguir a escada **pré-recalibração Armaedron**, onde o tier máximo custava **230.000 Â**. Licenças são uma **subscrição de acesso** (TEK gear desbloqueado), não comparáveis 1:1 a preços de dino L1. O Armaedron L1 = 35k justifica o preço de um dino, não de uma licença mensal de acesso a armaduras 130× mais fortes que vanilla TEK.

| Seção                         | O que mudou                                                                                                    |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Escada aprovada**           | Topo elevado de 43k → **230.000 Â** (Exótico); Delta retorna a **6.000 Â** (original pré-v2.0)               |
| **Gama/Beta/Alfa**            | Preços originais restaurados: Gama **50k**, Beta **75k**, Alfa **100k**                                        |
| **Novos tiers superiores**    | Omega 115k → Imaterial 215k → Exótico 230k — escada de 8 tiers acima de Alfa                                  |
| **Filosofia de precificação** | Licença = subscrição de acesso TEK (não comparar com Armaedron 35k que é 1 dino, não acesso mensal)           |
| **Bônus /30min**              | Preservados para Gama/Beta/Alfa (+25/+50/+75); novos tiers estendem a +200 (Exótico)                          |

## Novidades v2.0 vs v1.1


| Seção                      | O que mudou                                                                                                          |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Matriz de acesso**       | Adicionada: Delta é o **único tier que desbloqueia apenas seu próprio tier**; todos os outros desbloqueiam `N + N-1` |
| **Delta license**          | Preço de referência: **6.000 Â** (retorna ao original pré-v2.0)                                                      |
| **Descontos de renovação** | Adicionado sistema: **20% antecipado** (antes do vencimento) / **10% recente** (até 7 dias após vencimento)          |
| **Preços de itens**        | Adicionada tabela completa de preços por categoria e tier (planilha parseada)                                        |
| **Itens especiais**        | Adicionado: criaturas TEK, estruturas Alfa, utilitários, selas — com licença mínima requerida                        |
| **Stats por tier**         | Adicionada tabela de rating de armadura / arma / sela (fonte: aba "Status dos itens")                                |
| **Contagem de itens**      | 371 itens com tier + ~~61 especiais = **~~430+ itens totais** no mod                                                 |


---



## 1. Contexto — Sistema Atual

O sistema atual tem **3 licenças pagas** (30 dias) e 1 licença de funcionalidade:


| ID Catálogo      | Grupo    | Preço     | Bônus /30min | Total /30min   |
| ---------------- | -------- | --------- | ------------ | -------------- |
| `licenca_delta`* | —        | —         | —            | —              |
| `licenca_gamma`  | Gamma    | 50.000 Â  | +25          | **50 Â**       |
| `licenca_beta`   | Beta     | 75.000 Â  | +50          | **75 Â**       |
| `licenca_alfa`   | Alfa     | 100.000 Â | +75          | **100 Â**      |
| `licenca_nuvem`  | keyvault | 5.000 Â   | —            | *(utilitária)* |


> *Gamma, Beta e Alfa já existem em produção. Não há tier Delta nem tiers acima de Alfa.*

O **mod ItensAlfa** define uma escada de **12 tiers** de equipamentos (armaduras TEK, armas, ferramentas e selas). A licença de cada tier concede ao jogador **permissão de resgate** desses itens na loja, além de um bônus de Âmbar/30min.

---



## 2. Matriz de Acesso — Licença → Tiers Desbloqueados

> ⚠️ **Regra fundamental:** A licença desbloqueia o **próprio tier + o tier imediatamente abaixo** (acesso cumulativo). **Exceção única: Delta desbloqueia APENAS seu próprio tier** — não há tier abaixo. Isso é um desequilíbrio intencional refletido no preço.


| #   | Licença           | Tiers Desbloqueados    | Qtd. Tiers | Observação                      |
| --- | ----------------- | ---------------------- | ---------- | ------------------------------- |
| 1   | **Delta**         | Delta                  | **1 tier** | ⚠️ Único tier — sem tier abaixo |
| 2   | **Gama**          | Gama + Delta           | 2 tiers    |                                 |
| 3   | **Beta**          | Beta + Gama            | 2 tiers    |                                 |
| 4   | **Alfa**          | Alfa + Beta            | 2 tiers    |                                 |
| 5   | **Omega**         | Omega + Alfa           | 2 tiers    |                                 |
| 6   | **Transcendente** | Transcendente + Omega  | 2 tiers    |                                 |
| 7   | **Etéreo**        | Etéreo + Transcendente | 2 tiers    |                                 |
| 8   | **Universal**     | Universal + Etéreo     | 2 tiers    |                                 |
| 9   | **Onipotente**    | Onipotente + Universal | 2 tiers    |                                 |
| 10  | **Surreal**       | Surreal + Onipotente   | 2 tiers    |                                 |
| 11  | **Imaterial**     | Imaterial + Surreal    | 2 tiers    |                                 |
| 12  | **Exótico**       | Exótico + Imaterial    | 2 tiers    | Tier máximo do mod              |


> **Implicação econômica:**
>
> - Um jogador Delta paga por acesso a 1 tier → license deve ser **mais barata por tier acessado**.
> - Um jogador Gama paga por acesso a 2 tiers (Gama+Delta) → representa **melhor custo-benefício**.
> - O custo por tier cresce com o tier (valor dos itens aumenta) — **exceto** Delta vs Gama: ambos têm custo/tier = 5.500 Â.



### 2.1 Custo por Tier Acessado (Análise de Valor)


| Licença       | Preço aprovado  | Tiers | Custo/tier     |
| ------------- | --------------- | ----- | -------------- |
| Delta         | 6.000 Â         | 1     | 6.000 Â/tier   |
| Gama          | 50.000 Â        | 2     | 25.000 Â/tier  |
| Beta          | 75.000 Â        | 2     | 37.500 Â/tier  |
| Alfa          | 100.000 Â       | 2     | 50.000 Â/tier  |
| Omega         | 115.000 Â       | 2     | 57.500 Â/tier  |
| Transcendente | 130.000 Â       | 2     | 65.000 Â/tier  |
| Etéreo        | 150.000 Â       | 2     | 75.000 Â/tier  |
| Universal     | 165.000 Â       | 2     | 82.500 Â/tier  |
| Onipotente    | 180.000 Â       | 2     | 90.000 Â/tier  |
| Surreal       | 195.000 Â       | 2     | 97.500 Â/tier  |
| Imaterial     | 215.000 Â       | 2     | 107.500 Â/tier |
| Exótico       | 230.000 Â       | 2     | 115.000 Â/tier |


> **Conclusão:** Delta (6k/1 tier) é desproporcionalmente barato — é a porta de entrada para jogadores curiosos sobre o mod. A partir de Gama (25k/tier), o custo por tier sobe progressivamente, refletindo o valor exponencial dos stats dos itens de cada tier. **A lógica é de subscrição de acesso**, não de compra de item único: a licença Exótico (230k/mês) garante acesso a equipamentos com 130× os stats de armadura vanilla TEK.

---



## 3. Contagem de Itens por Categoria (Planilha Itens Alfa.xlsx)

> Dados parseados em Jul/2026 de `C:\Users\Ciano\Downloads\Itens Alfa.xlsx`.



### 3.1 Itens com Sistema de Tiers


| Categoria           | Nomes dos Itens                                                                                                                                                              | Qtd. Tipos   | Tiers                | Total Itens   |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | -------------------- | ------------- |
| **Armaduras TEK**   | Botas, Luvas, Capacete, Calças, Peitoral                                                                                                                                     | 5            | Delta → Exótico (12) | **60**        |
| **Armas TEK**       | Tek Shield Armor, Shoulder Cannon, Tek Bow, Tek Pistol, ElectroPod, Tek Sword, Tek Claws, Tek Rifle, Sniper, Pike, Pump-Action, Club/Clava, Grenade Launcher, Cruise Missile | 14           | Delta → Exótico (12) | **168**       |
| **Ferramentas TEK** | Chainsaw, Hatchet, Mining Drill, Pick, Sickle, Fishing Rod, Torch, Whip, Lantern Charge                                                                                      | 9            | Delta → Exótico (12) | **108**       |
| **Selas TEK**       | Sela Megalodon, Mosassauro, Rex, Rock Drake, Astrodelph, Astrocetus, Tapejara                                                                                                | 7            | Delta → Omega (5)    | **35**        |
| **SUBTOTAL**        |                                                                                                                                                                              | **35 tipos** |                      | **371 itens** |




### 3.2 Itens Especiais (Sem Sistema de Tiers)


| Categoria                    | Qtd. Itens | Licença Mínima                         | Descrição                                                              |
| ---------------------------- | ---------- | -------------------------------------- | ---------------------------------------------------------------------- |
| **Criaturas / Veículos TEK** | 7          | Alfa+                                  | HoverSkiff, HoverSail, Exo-Mek, Enforcer, Defender, Stryder, Submarine |
| **Estruturas Especiais**     | 37         | Delta+ a Universal+                    | Alfa Fabric, Criofreezer, Criogentral, Solar Panel, Mini Forge, etc.   |
| **Utilitários / Outros**     | 17         | Delta+ a Omega+                        | AlphaCryopod, CryoPistol, Spyglass, Personal Shield, CrossApex, etc.   |
| **Skins**                    | 24 cat.    | Cosméticos — preço separado ou incluso | Skins de armas, pano, couro, camuflado, etc.                           |
| **MiniCrop**                 | 6 cat.     | Delta+                                 | Sementes especiais de arbustos, cogumelos, árvores, etc.               |
| **Fantasias de Dinos**       | 2 cat.     | Beta+                                  | Com buffs e sem buffs                                                  |
| **SUBTOTAL**                 | ~93 itens  |                                        |                                                                        |


> **Total geral estimado: ~464 itens únicos** no mod ItensAlfa.

---



## 4. Stats dos Itens por Tier (Fonte: "Status dos itens")

> Valores de rating de armadura, DPS de armas e armadura de sela por tier. Escala de referência: Armadura TEK vanilla ~500 pts.


| #   | Tier              | Armadura (rating) | Armas (DPS/stat) | Selas (armor) | Ratio Armor/Delta |
| --- | ----------------- | ----------------- | ---------------- | ------------- | ----------------- |
| 1   | **Delta**         | 180               | 120              | 40            | 1.0×              |
| 2   | **Gama**          | 500               | 250              | 100           | 2.8×              |
| 3   | **Beta**          | 1.000             | 450              | 350           | 5.6×              |
| 4   | **Alfa**          | 1.900             | 750              | 600           | 10.6×             |
| 5   | **Omega**         | 3.200             | 1.300            | 790           | 17.8×             |
| 6   | **Transcendente** | 4.900             | 1.850            | —             | 27.2×             |
| 7   | **Etéreo**        | 7.000             | 2.500            | —             | 38.9×             |
| 8   | **Universal**     | 9.500             | 3.250            | —             | 52.8×             |
| 9   | **Onipotente**    | 12.400            | 4.100            | —             | 68.9×             |
| 10  | **Surreal**       | 15.700            | 4.950            | —             | 87.2×             |
| 11  | **Imaterial**     | 19.400            | 5.800            | —             | 107.8×            |
| 12  | **Exótico**       | 23.500            | 6.650            | —             | 130.6×            |


> **Nota:** Delta tier (180 pts) é abaixo da armadura TEK vanilla (~500 pts) — é literalmente um tier de entrada, mais fraco que equipamento vanilla endgame. Exótico (23.500 pts) é ~47× mais resistente que vanilla TEK. Os preços de itens devem refletir essa diferença.
>
> Selas TEK do mod só existem até o tier **Omega** (confirmado na planilha). Para tiers Transcendente→Exótico, não há sela correspondente.

---



## 5. Tabela de Preços de Itens por Tier (Catálogo de Resgate)



### 5.1 Fórmula e Filosofia

**Filosofia:** Itens são equips semi-consumíveis (quebram, são perdidos em PvP). Devem ser recompráveis regularmente. O valor da licença está no **acesso recorrente**, não em um único item.

**Fórmula base:**

```
Preço_item(tier) = Base_categoria × Multiplicador_tier
```

**Bases por categoria:**


| Categoria                   | Base (Â) | Justificativa                                   |
| --------------------------- | -------- | ----------------------------------------------- |
| Armadura (por peça)         | 400      | 5 peças por set → entry tier set = 2.000 Â      |
| Arma (por arma)             | 300      | 75% da armadura — mais numerosas e situacionais |
| Ferramenta (por ferramenta) | 240      | 60% — utilitárias, não PvP                      |
| Sela TEK (por sela)         | 350      | 87.5% — importância estratégica de montaria     |


**Multiplicadores por tier** (curva de potência com retornos crescentes, refletindo escala ~130× de stats):


| #   | Tier          | Multiplicador | Ratio do Tier Anterior |
| --- | ------------- | ------------- | ---------------------- |
| 1   | Delta         | **1.00×**     | —                      |
| 2   | Gama          | **1.75×**     | +75%                   |
| 3   | Beta          | **2.75×**     | +57%                   |
| 4   | Alfa          | **4.25×**     | +55%                   |
| 5   | Omega         | **6.00×**     | +41%                   |
| 6   | Transcendente | **8.50×**     | +42%                   |
| 7   | Etéreo        | **12.0×**     | +41%                   |
| 8   | Universal     | **16.0×**     | +33%                   |
| 9   | Onipotente    | **21.0×**     | +31%                   |
| 10  | Surreal       | **27.0×**     | +29%                   |
| 11  | Imaterial     | **34.0×**     | +26%                   |
| 12  | Exótico       | **43.0×**     | +26%                   |


> O multiplicador de preço vai de 1× a 43× (Exótico/Delta). Comparar: stats de armadura escalam 130× no mesmo intervalo. A curva de preços é **propositalmente mais suave** — itens high-tier devem ser caros, mas ainda recompráveis.

---



### 5.2 Armaduras TEK (por peça)

*5 peças por set: Botas, Luvas, Capacete, Calças, Peitoral.*


| #   | Tier              | Preço / peça (Â) | Set completo (×5) | Armor rating | Âncora comparativa       |
| --- | ----------------- | ---------------- | ----------------- | ------------ | ------------------------ |
| 1   | **Delta**         | **400**          | 2.000             | 180 pts      | < Catálogo C/utilitário  |
| 2   | **Gama**          | **700**          | 3.500             | 500 pts      | ≈ Cavalo-marinho (C)     |
| 3   | **Beta**          | **1.100**        | 5.500             | 1.000 pts    | ≈ Cryolophosaurus (B)    |
| 4   | **Alfa**          | **1.700**        | 8.500             | 1.900 pts    | ≈ Brachio + Vul. (B)     |
| 5   | **Omega**         | **2.400**        | 12.000            | 3.200 pts    | ≈ Small Moeder (B)       |
| 6   | **Transcendente** | **3.400**        | 17.000            | 4.900 pts    | ≈ Deinosuchus (B)        |
| 7   | **Etéreo**        | **4.800**        | 24.000            | 7.000 pts    | ≈ Small Dodowyvern (B→A) |
| 8   | **Universal**     | **6.400**        | 32.000            | 9.500 pts    | ≈ Desmodus (A)           |
| 9   | **Onipotente**    | **8.400**        | 42.000            | 12.400 pts   | ≈ Deinonychus (A)        |
| 10  | **Surreal**       | **10.800**       | 54.000            | 15.700 pts   | ≈ Reaper Gen2 (A)        |
| 11  | **Imaterial**     | **13.600**       | 68.000            | 19.400 pts   | ≈ Indominus (S+)         |
| 12  | **Exótico**       | **17.200**       | 86.000            | 23.500 pts   | ≈ Rex L1 (S)             |


> **Leitura:** Uma peça de armadura Exótico custa ~17.200 Â — comparável a um Rex L1. Faz sentido: 23.500 pts de armor é 47× vanilla TEK.
> Um set completo Exótico (86.000 Â) representa ~2,5 meses de farm para jogador Default (50Â/h, 2h/dia). Justificado para tier máximo de equipamento.

---



### 5.3 Armas TEK (por arma)

*14 tipos: Tek Shield Armor, Shoulder Cannon, Tek Bow, Tek Pistol, ElectroPod, Tek Sword, Tek Claws, Tek Rifle, Sniper, Pike, Pump-Action, Club/Clava, Grenade Launcher, Cruise Missile.*


| #   | Tier              | Preço / arma (Â) | DPS/Stat ref. | Âncora comparativa          |
| --- | ----------------- | ---------------- | ------------- | --------------------------- |
| 1   | **Delta**         | **300**          | 120           | Consumível básico           |
| 2   | **Gama**          | **525**          | 250           | ≈ Tridacna (C util.)        |
| 3   | **Beta**          | **825**          | 450           | ≈ Atum/Seahorse (C)         |
| 4   | **Alfa**          | **1.275**        | 750           | ≈ Diru-Ya-Ku (C atk)        |
| 5   | **Omega**         | **1.800**        | 1.300         | ≈ Dakosaurus (B)            |
| 6   | **Transcendente** | **2.550**        | 1.850         | ≈ Cryolophosaurus+ (B)      |
| 7   | **Etéreo**        | **3.600**        | 2.500         | ≈ Brachio (B util.)         |
| 8   | **Universal**     | **4.800**        | 3.250         | ≈ Small Moeder (B)          |
| 9   | **Onipotente**    | **6.300**        | 4.100         | ≈ Desmodus (A loco)         |
| 10  | **Surreal**       | **8.100**        | 4.950         | ≈ Megalosaurus (A)          |
| 11  | **Imaterial**     | **10.200**       | 5.800         | ≈ Abyss Rex (A raid)        |
| 12  | **Exótico**       | **12.900**       | 6.650         | ≈ Reaper Gen2/Xenomorph (A) |


---



### 5.4 Ferramentas TEK (por ferramenta)

*9 tipos: Chainsaw, Hatchet, Mining Drill, Pick, Sickle, Fishing Rod, Torch, Whip, Lantern Charge.*


| #   | Tier              | Preço / ferramenta (Â) | Categoria de uso       |
| --- | ----------------- | ---------------------- | ---------------------- |
| 1   | **Delta**         | **240**                | Coleta básica          |
| 2   | **Gama**          | **420**                | Coleta melhorada       |
| 3   | **Beta**          | **660**                | Coleta eficiente       |
| 4   | **Alfa**          | **1.020**              | Coleta avançada        |
| 5   | **Omega**         | **1.440**              | Coleta alta eficiência |
| 6   | **Transcendente** | **2.040**              | Coleta premium         |
| 7   | **Etéreo**        | **2.880**              | Coleta end-game        |
| 8   | **Universal**     | **3.840**              | Top-tier               |
| 9   | **Onipotente**    | **5.040**              | Pinnacle               |
| 10  | **Surreal**       | **6.480**              | Pinnacle+              |
| 11  | **Imaterial**     | **8.160**              | Near-max               |
| 12  | **Exótico**       | **10.320**             | Máximo                 |


---



### 5.5 Selas TEK (por sela) — Tiers Delta → Omega apenas

*7 selas: Megalodon, Mosassauro, Rex, Rock Drake, Astrodelph, Astrocetus, Tapejara.*
*Confirmado na planilha: selas só existem até o tier Omega. Tiers Transcendente→Exótico sem sela.*


| #   | Tier      | Preço / sela (Â)      | Armor ref. |
| --- | --------- | --------------------- | ---------- |
| 1   | **Delta** | **350**               | 40 pts     |
| 2   | **Gama**  | **612** → **600**     | 100 pts    |
| 3   | **Beta**  | **962** → **950**     | 350 pts    |
| 4   | **Alfa**  | **1.487** → **1.500** | 600 pts    |
| 5   | **Omega** | **2.100**             | 790 pts    |


> **Nota:** Selas TEK de dinos mais valiosos (Rock Drake, Astrodelph, Astrocetus) justificam um premium de ~20% vs selas padrão (Rex, Megalodon). Admin pode criar sub-tabelas por espécie se desejar.

---



### 5.6 Criaturas e Veículos TEK (itens sem tier)

*7 itens. Licença mínima requerida — definir via* `Permissions` *no ARK.*


| Item       | Preço (Â)  | Licença mínima | Justificativa                     |
| ---------- | ---------- | -------------- | --------------------------------- |
| HoverSkiff | **15.000** | Alfa+          | Veículo TEK de transporte premium |
| HoverSail  | **12.000** | Alfa+          | Variante leve do HoverSkiff       |
| Exo-Mek    | **20.000** | Omega+         | Meka de suporte/construção        |
| Enforcer   | **8.000**  | Beta+          | Scout/combate rápido              |
| Defender   | **8.000**  | Beta+          | Torre de defesa autônoma          |
| Stryder    | **25.000** | Universal+     | Coleta industrial high-end        |
| Submarine  | **18.000** | Omega+         | Exploração submarina premium      |


> **Âncoras:** HoverSkiff (15k) ≈ Rex Abissal (A raid). Stryder (25k) = Carcha (S+ raid). Exo-Mek (20k) ≈ mid S+.

---



### 5.7 Estruturas Especiais (itens sem tier)

*37 estruturas. Preços refletem utilidade e exclusividade.*

**Estruturas de produção:**


| Item                     | Preço (Â)  | Licença mínima |
| ------------------------ | ---------- | -------------- |
| Alfa Fabric              | **3.000**  | Delta+         |
| Alfa Tailor              | **4.000**  | Delta+         |
| Alfa Mini Crop           | **3.500**  | Delta+         |
| Alfa Mini Forge          | **5.500**  | Gama+          |
| Alfa Update Rig          | **6.000**  | Gama+          |
| Alfa Converter           | **7.500**  | Beta+          |
| Alfa Mini Tek Generator  | **12.000** | Beta+          |
| Alfa Mini Tek Replicator | **15.000** | Beta+          |
| Alfa Mini Atomic Lab     | **20.000** | Omega+         |
| Alfa CrioFreezer         | **12.000** | Alfa+          |
| Alfa CrioCentral         | **15.000** | Omega+         |


**Estruturas de infraestrutura:**


| Item                   | Preço (Â)  | Licença mínima |
| ---------------------- | ---------- | -------------- |
| Alfa Solar Light       | **1.500**  | Delta+         |
| Alfaneon               | **2.000**  | Delta+         |
| Alfa Solar Panel       | **4.000**  | Gama+          |
| Alfa Mega Box          | **7.000**  | Beta+          |
| Alfa Structure Builder | **10.000** | Alfa+          |
| Alfa Fast Travel       | **18.000** | Alfa+          |
| Alfa Ocean Platform    | **25.000** | Universal+     |
| Alfa Aquário           | **15.000** | Alfa+          |


**Estruturas de construção (BUILD STRUCTURES):**


| Tipo                                                | Preço (Â)     | Licença mínima |
| --------------------------------------------------- | ------------- | -------------- |
| Tek Barrier                                         | **3.000**     | Delta+         |
| Foundation / Floating Foundation                    | **2.000**     | Delta+         |
| Ceiling / Pillar / Wall                             | **1.500**     | Delta+         |
| Railing / Ramp / Door / Gate                        | **1.000**     | Delta+         |
| Barricade / Ladder                                  | **1.000**     | Delta+         |
| Rounded Corner                                      | **1.500**     | Delta+         |
| Furniture (Cadeira, Mesa, Note Vault, Candle Vault) | **500–1.000** | Delta+         |


---



### 5.8 Utilitários e Outros (itens sem tier)

*17 itens especiais. Alguns são consumíveis (Gift Box, Caixa Misteriosa), outros permanentes.*


| Item                         | Preço (Â)  | Licença mínima | Tipo                 |
| ---------------------------- | ---------- | -------------- | -------------------- |
| AlphaCryopod                 | **400**    | Delta+         | Consumível           |
| AlphaCryoPistol              | **800**    | Delta+         | Durável              |
| AlphaSpyglass                | **1.500**  | Delta+         | Durável              |
| Alfa Camera Mode             | **2.000**  | Delta+         | Funcionalidade       |
| Alfa Personal Velocimeter    | **1.200**  | Delta+         | Utilitário           |
| Alfa Personal Item Collector | **3.000**  | Gama+          | Utilitário premium   |
| Alfa Personal Shield         | **8.000**  | Alfa+          | Defesa pessoal       |
| Alfa Explorer Note Finder    | **2.500**  | Delta+         | Utilitário           |
| Alfa Gift Box                | **500**    | Delta+         | Consumível           |
| Alfa Caixa Misteriosa        | **1.000**  | Delta+         | Consumível/loot      |
| Alfa Artefato Genérico       | **3.000**  | Beta+          | Consumível           |
| Alfa Skin - Charge Emitter   | **1.500**  | Gama+          | Cosmético funcional  |
| Alfa Strider Fragments       | **2.000**  | Alfa+          | Recurso especial     |
| Alfa Módulos de Mek          | **5.000**  | Omega+         | Upgrade Mek          |
| CrossApex                    | **10.000** | Omega+         | Item especial combat |
| Acessórios de Armas          | **2.500**  | Beta+          | Attachments          |
| Alfa Módulos de Submarino    | **4.000**  | Omega+         | Upgrade sub          |


---



### 5.9 Sementes MiniCrop (itens sem tier)


| Item                                 | Preço (Â) | Licença mínima |
| ------------------------------------ | --------- | -------------- |
| Sementes de Arbustos (qualquer tipo) | **300**   | Delta+         |
| Sementes de Cogumelos                | **400**   | Delta+         |
| Sementes de Árvores                  | **500**   | Gama+          |
| Sementes Vanilla                     | **200**   | Delta+         |
| Sementes Especiais de Recursos       | **800**   | Beta+          |
| Sementes Raras / Especiais           | **1.200** | Beta+          |


---



## 6. Tabela de Preços de Licenças — Opção Aprovada (v3.0)

> **Âncora de referência:** Armaedron L1 = **35.000 Â** · Rex L1 = **18.000 Â** · Carcha L1 = **25.000 Â**
>
> ⚠️ **Nota importante:** Licenças **não são comparáveis a preços de dino L1**. O Armaedron custa 35k como *um único dino*. Uma licença Gama (50k/mês) dá acesso recorrente a centenas de itens TEK. São produtos diferentes — um é uma compra de dino, o outro é uma **subscrição de acesso** a um catálogo de equipamentos (armaduras, armas, ferramentas, selas) com até 130× os stats de equipamento vanilla.
>
> **Delta:** 6.000 Â (retorna ao preço original — porta de entrada, 1 tier único sem bônus de acesso abaixo).
> **Topo:** 230.000 Â (Exótico) — escada de subscrição pré-recalibração Armaedron.



### 6.1 Tabela Principal — Opção Aprovada


| #   | Tier              | Preço (Â)   | Renovação Antecipada¹ | Renovação Recente² | Bônus /30min | Total /30min | Tiers de Acesso        |
| --- | ----------------- | ----------- | --------------------- | ------------------ | ------------ | ------------ | ---------------------- |
| 1   | **Delta**         | **6.000**   | **4.800**             | **5.400**          | +5           | 30           | Delta                  |
| 2   | **Gama**          | **50.000**  | **40.000**            | **45.000**         | +25          | 50           | Gama + Delta           |
| 3   | **Beta**          | **75.000**  | **60.000**            | **67.500**         | +50          | 75           | Beta + Gama            |
| 4   | **Alfa**          | **100.000** | **80.000**            | **90.000**         | +75          | 100          | Alfa + Beta            |
| 5   | **Omega**         | **115.000** | **92.000**            | **103.500**        | +90          | 115          | Omega + Alfa           |
| 6   | **Transcendente** | **130.000** | **104.000**           | **117.000**        | +105         | 130          | Transcendente + Omega  |
| 7   | **Etéreo**        | **150.000** | **120.000**           | **135.000**        | +120         | 145          | Etéreo + Transcendente |
| 8   | **Universal**     | **165.000** | **132.000**           | **148.500**        | +135         | 160          | Universal + Etéreo     |
| 9   | **Onipotente**    | **180.000** | **144.000**           | **162.000**        | +150         | 175          | Onipotente + Universal |
| 10  | **Surreal**       | **195.000** | **156.000**           | **175.500**        | +165         | 190          | Surreal + Onipotente   |
| 11  | **Imaterial**     | **215.000** | **172.000**           | **193.500**        | +180         | 205          | Imaterial + Surreal    |
| 12  | **Exótico**       | **230.000** | **184.000**           | **207.000**        | +200         | 225          | Exótico + Imaterial    |
| —   | *(Nuvem)*         | *(5.000)*   | *(4.000)*             | *(4.500)*          | —            | —            | *(utilitária)*         |


¹ *Renovação Antecipada: **20% de desconto** — aplicável se renovar antes do vencimento da licença atual (enquanto ainda ativa).*
² *Renovação Recente: **10% de desconto** — aplicável dentro de 7 dias após vencimento. Depois disso, preço cheio.*

---



## 7. Sistema de Descontos de Renovação



### 7.1 Estrutura do Desconto


| Situação                                          | Desconto     | Preço Base → Renovação (ex: Alfa) |
| ------------------------------------------------- | ------------ | --------------------------------- |
| Renovação antecipada (ativa, antes do vencimento) | **−20%**     | 100.000 → **80.000 Â**            |
| Renovação recente (0–7 dias após vencimento)      | **−10%**     | 100.000 → **90.000 Â**            |
| Licença expirada (> 7 dias)                       | Sem desconto | 100.000 → **100.000 Â**           |
| Upgrade de tier (ex.: Beta → Alfa)                | Sem desconto | Preço cheio do novo tier          |




### 7.2 Rationale

- **20% antecipado:** Recompensa lealdade e reduz churn. Um jogador que joga ativamente manterá a licença renovada continuamente. O desconto equivale a 20.000 Â de economia na Alfa — valor de um dino intermediário.
- **10% recente:** Janela de "graça" para jogadores que esqueceram de renovar a tempo. Incentiva retorno rápido.
- **Sem desconto para expirados:** Desistência > 7 dias é tratada como nova compra. Evita exploração do sistema.
- **Sem desconto para upgrade:** Upgrade é uma compra de progressão, não fidelidade.



### 7.3 Implementação Técnica Sugerida

**Opção A — IDs separados de renovação no config.json (mais simples):**

```json
{
  "licenca_alfa_renovacao": {
    "Category": "Licenças",
    "Description": "Renovação Licença Alfa (30 dias) — 20% off (válido enquanto ativa)",
    "Price": 20000,
    "Type": "license",
    "LicenseGrant": { "Days": 30, "Group": "Alfa" },
    "TimedPointsBonus": 35,
    "_visibility_rule": "only_if_group_active:Alfa"
  }
}
```

**Opção B — Lógica em app.py (mais elegante):**

```python
def get_license_price(group: str, player_id: str) -> int:
    base_price = LICENSE_PRICES[group]
    remaining = get_license_remaining_days(player_id, group)
    if remaining > 0:
        return int(base_price * 0.80)  # -20% antecipado
    elif get_days_since_expiry(player_id, group) <= 7:
        return int(base_price * 0.90)  # -10% recente
    return base_price
```

> **Recomendação:** Opção A é mais fácil de implementar no CustomShop sem mudança de código. Criar IDs `licenca_X_renovacao` para cada tier e controlar visibilidade via permissão de grupo.

---



## 8. Impacto da Regra Delta-Only — Análise Completa



### 8.1 O Que Muda vs. Outros Tiers


| Aspecto                  | Delta                                                           | Todos os outros            |
| ------------------------ | --------------------------------------------------------------- | -------------------------- |
| Tiers de acesso          | 1 (apenas Delta)                                                | 2 (próprio + abaixo)       |
| Itens acessíveis         | 60 arm. + 168 arm. + 108 fer. + 35 sel. = **~90 itens Delta**   | ~90 tier N + ~90 tier N-1  |
| Custo por tier           | 6.000 Â / tier                                                  | 25.000 a 115.000 Â / tier  |
| Bônus Âmbar              | +5 / 30min (30 total)                                           | +25 a +200 / 30min         |
| Acesso a itens especiais | Maioria dos sem-tier (estruturas básicas, sementes, utilidades) | Idem + mais conforme tier  |




### 8.2 Por que Delta é "Desvantajoso"

1. **Não há tier 0 abaixo de Delta** — é o piso absoluto do mod. O acesso "bônus" que todos os outros tiers recebem simplesmente não existe para Delta.
2. **Stats Delta são abaixo do vanilla** (180 pts armor vs ~500 do TEK vanilla). Delta é literalmente um tier de aprendizado/entrada, não um tier competitivo.
3. **Conclusão:** Delta é intencionalmente o pior valor de licença **em termos de itens** — e é justamente por isso que é **o mais barato** (6.000 Â). Ele serve como porta de entrada para novos jogadores explorarem o mod.



### 8.3 Recomendação de Comunicação

> ⚠️ Deixar **explícito na descrição** do item `licenca_delta` no catálogo:
> *"Licença Delta (30 dias) — Acesso APENAS ao tier Delta. Para acesso a 2 tiers (Delta+Gama), considere a Licença Gama."*

---



## 9. Análise de ROI por Tier

> Assumindo **2h de jogo por dia** (4 blocos de 30min). Renda base: 25 Â/30min (Default).


| Tier          | Preço   | Â extra/dia¹ | ROI bônus Â²  | Valor real                                      |
| ------------- | ------- | ------------ | ------------- | ----------------------------------------------- |
| Delta         | 6.000   | +20          | ~300 dias     | Acesso Delta + boost mínimo (entrada no mod)    |
| Gama          | 50.000  | +100         | ~500 dias     | Acesso Gama+Delta — stats até 500 pts armor     |
| Beta          | 75.000  | +200         | ~375 dias     | Acesso Beta+Gama — stats até 1.000 pts armor    |
| Alfa          | 100.000 | +300         | ~333 dias     | Acesso Alfa+Beta — 1.900 pts armor + criaturas  |
| Omega         | 115.000 | +360         | ~319 dias     | Acesso Omega+Alfa — 3.200 pts + veículos TEK    |
| Transcendente | 130.000 | +420         | ~310 dias     | Acesso Trans+Omega — 4.900 pts armor            |
| Etéreo        | 150.000 | +480         | ~313 dias     | Acesso Etéreo+Trans — 7.000 pts armor           |
| Universal     | 165.000 | +540         | ~306 dias     | Acesso Uni+Etéreo — 9.500 pts + Ocean Platform  |
| Onipotente    | 180.000 | +600         | ~300 dias     | Acesso Oni+Uni — 12.400 pts armor               |
| Surreal       | 195.000 | +660         | ~295 dias     | Acesso Surreal+Oni — 15.700 pts armor           |
| Imaterial     | 215.000 | +720         | ~299 dias     | Acesso Ima+Surreal — 19.400 pts armor           |
| Exótico       | 230.000 | +800         | ~288 dias     | Acesso Exót+Ima — 23.500 pts armor (130× TEK)   |


¹ *Â extra por dia = bônus/30min × 4 blocos. Ex.: +5/30min × 4 = +20/dia.*
² *Dias para o bônus de Âmbar amortizar o preço da licença (apenas pelo bônus, sem contar o valor dos itens).*

> **Conclusão:** O ROI puramente por bônus de Âmbar é de **1–2 anos** jogando 2h/dia — **intencionalmente muito longo**. Isso é esperado e correto: licenças são **subscrições de acesso**, não investimentos em Âmbar. O produto é o acesso recorrente a centenas de itens TEK exclusivos; o bônus de Âmbar é um benefício secundário de fidelidade.
>
> Comparação: uma licença Alfa (100k/mês) custa ~4× um Rex L1 (18k). Em troca, dá acesso a armaduras com até 1.900 pts de armor por 30 dias — qualquer peça perdida em PvP pode ser resgatada novamente sem custo adicional dentro da vigência da licença.

---



## 10. Referência de Tiers do Mod ItensAlfa

> Dados da planilha `ASE - Armaduras` — custo de crafting por peça de armadura TEK:


| #   | Tier              | Custo Crafting (Botas)                                                        | Armor Rating | Mutagel |
| --- | ----------------- | ----------------------------------------------------------------------------- | ------------ | ------- |
| 1   | **Delta**         | Polímero 120 · Metal 500 · Cristal 120 · Elemento 20 · Pérola 55 · Artefato 2 | 180          | —       |
| 2   | **Gama**          | 300 · 1.000 · 300 · 100 · 200 · Artefato 3                                    | 500          | 30      |
| 3   | **Beta**          | 600 · 2.000 · 600 · 200 · 500 · Artefato 4                                    | 1.000        | 40      |
| 4   | **Alfa**          | 900 · 3.000 · 900 · 300 · 700 · Artefato 5                                    | 1.900        | 50      |
| 5   | **Omega**         | 1.500 · 4.000 · 1.950 · 500 · 1.100 · Artefato 5                              | 3.200        | 60      |
| 6   | **Transcendente** | 3.000 · 5.800 · 3.450 · 1.000 · 2.100 · Artefato 10                           | 4.900        | 70      |
| 7   | **Etéreo**        | 4.500 · 10.580 · 4.950 · 1.500 · 3.100 · Artefato 15                          | 7.000        | 80      |
| 8   | **Universal**     | 6.000 · 15.705 · 6.450 · 2.000 · 4.100 · Artefato 20                          | 9.500        | 90      |
| 9   | **Onipotente**    | 7.500 · 20.785 · 7.950 · 2.500 · 5.100 · Artefato 25                          | 12.400       | 100     |
| 10  | **Surreal**       | 9.000 · 25.830 · 9.450 · 3.000 · 6.100 · Artefato 30                          | 15.700       | 110     |
| 11  | **Imaterial**     | 10.500 · 30.860 · 10.950 · 3.500 · 7.100 · Artefato 35                        | 19.400       | 120     |
| 12  | **Exótico**       | 12.000 · 35.880 · 12.450 · 4.000 · 8.100 · Artefato 40                        | 23.500       | 130     |


> O custo de crafting escala ~100× do tier 1 ao tier 12. O custo de Mutagel (0 no Delta → 130 no Exótico) é um limitador de progressão natural.

---



## 11. Comparativo com Âncoras Econômicas

> **Nota de interpretação:** As linhas de dinos (Rex, Armaedron, etc.) representam o custo de *um único dino*. As linhas de licença representam o custo de *acesso mensal a centenas de itens*. A comparação ilustra a escala, não equivalência de produto.


| Referência                        | Preço (Â)   | Contexto                                                          |
| --------------------------------- | ----------- | ----------------------------------------------------------------- |
| Licença Nuvem *(atual)*           | 5.000       | Funcionalidade, não muda                                          |
| **Delta (aprovado)**              | **6.000**   | Entry — 1 tier, stat abaixo vanilla TEK (~180 pts armor)          |
| Rex L1 *(catálogo)*               | 18.000      | Âncora tier S ataque — *um dino*, não uma licença                 |
| Indominus Rex L1                  | 28.000      | Âncora boss S+                                                    |
| **Armaedron L1** *(recalibrado)*  | **35.000**  | Apex do servidor — *um dino* de boss                              |
| **Gama (aprovada)**               | **50.000**  | 2 tiers (Gama+Delta) — armor até 500 pts/mês                     |
| **Beta (aprovada)**               | **75.000**  | 2 tiers (Beta+Gama) — armor até 1.000 pts/mês                    |
| **Alfa (aprovada)**               | **100.000** | 2 tiers (Alfa+Beta) — 1.900 pts + HoverSkiff + Criofreezer/mês   |
| **Omega (aprovada)**              | **115.000** | 2 tiers (Omega+Alfa) — 3.200 pts + Exo-Mek + CrossApex/mês       |
| **Transcendente (aprovada)**      | **130.000** | 2 tiers — 4.900 pts armor/mês                                     |
| **Etéreo (aprovada)**             | **150.000** | 2 tiers — 7.000 pts armor/mês (Armaedron L1 = 35k como comparação)|
| **Universal (aprovada)**          | **165.000** | 2 tiers — 9.500 pts + Stryder + Ocean Platform/mês                |
| **Onipotente (aprovada)**         | **180.000** | 2 tiers — 12.400 pts armor/mês                                    |
| **Surreal (aprovada)**            | **195.000** | 2 tiers — 15.700 pts armor/mês                                    |
| **Imaterial (aprovada)**          | **215.000** | 2 tiers — 19.400 pts armor/mês                                    |
| **Exótico (aprovada)**            | **230.000** | Teto — 23.500 pts armor (47× TEK vanilla) + acesso a tudo/mês    |


---



## 12. Histórico de Opções de Precificação

> **v3.0 — Jul/2026:** A escada abaixo ("Opção B histórica / backward-compatible") foi **escolhida como a aprovada**. Ela preserva os preços originais das 3 licenças existentes (Gama 50k, Beta 75k, Alfa 100k) e estende os novos tiers até 230k. A "Opção A" com 43k no topo (v2.0) foi descartada por precificar licenças comparáveis a dinos L1, o que não reflete o valor de subscrição do produto.

### 12.1 Opção Aprovada (v3.0) — Resumo de Escolha

| Critério                          | Opção A (v2.0, descartada) | Opção Aprovada (v3.0)          |
| --------------------------------- | -------------------------- | ------------------------------ |
| Topo da escada                    | 43.000 Â (Exótico)         | **230.000 Â (Exótico)**        |
| Gama                              | 11.000 Â                   | **50.000 Â** (original)        |
| Beta                              | 18.000 Â                   | **75.000 Â** (original)        |
| Alfa                              | 100.000 Â → 25.000 Â       | **100.000 Â** (original)       |
| Referência Armaedron (35k)        | Etéreo = Armaedron         | Armaedron muito abaixo de Gama |
| Filosofia                         | Preço comparável a dinos   | **Subscrição de acesso TEK**   |
| Migração de jogadores existentes  | Redução de preço (bagunça) | Extensão (sem impacto)         |

### 12.2 Opção A (v2.0) — Mantida como Referência Histórica

> *(descartada — preços 5.5k → 43k, calibrados vs Armaedron 35k)*

| #   | Tier              | Preço v2.0 (Â) | Notas                                        |
| --- | ----------------- | -------------- | -------------------------------------------- |
| 1   | Delta             | 5.500          | Entrada                                      |
| 2   | Gama              | 11.000         | 2× Delta                                     |
| 3   | Beta              | 18.000         | = Rex L1                                     |
| 4   | Alfa              | 25.000         | = Carcha L1                                  |
| 5   | Omega             | 30.000         | —                                            |
| 6   | Transcendente     | 33.000         | —                                            |
| 7   | Etéreo            | 35.000         | = Armaedron L1 (conflito conceitual)         |
| 8   | Universal         | 37.000         | —                                            |
| 9   | Onipotente        | 38.500         | —                                            |
| 10  | Surreal           | 40.000         | —                                            |
| 11  | Imaterial         | 41.500         | —                                            |
| 12  | Exótico           | 43.000         | Teto (descartado — muito baixo para acesso TEK máximo) |

> **Por que descartada:** Colocar Etéreo (tier 7 de 12) ao mesmo preço do Armaedron (dino apex) criava confusão de valor. Mais importante: uma licença mensal que desbloqueia 23.500 pts de armor por 43.000 Â seria absurdamente barata — um único dino Rex custa 18.000 Â e não dá acesso recorrente a nada.

---



## 13. Retrocompatibilidade — Migração dos Jogadores Existentes

> ✅ **v3.0 facilita muito a retrocompat:** Os preços das 3 licenças existentes em produção (Gama 50k, Beta 75k, Alfa 100k) são **preservados sem alteração**. Não há redução de preço — os jogadores continuam pagando o mesmo. A expansão adiciona Delta (novo, 6k) e 8 tiers superiores (Omega 115k → Exótico 230k) sem tocar no que já existe.

| Estratégia                  | Descrição                                                                                                           | Impacto                              |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| **Sem impacto nos atuais**  | Gama/Beta/Alfa mantêm preços originais — jogadores existentes não percebem mudança                                  | ✅ Zero impacto nas licenças ativas  |
| **Comunicação dos novos**   | Anunciar os 9 novos tiers (Delta + Omega→Exótico) como expansão do sistema                                         | Operacional                          |
| **Upgrade path voluntary**  | Jogadores podem fazer upgrade de Alfa (100k) para Omega (115k) para ter acesso a 2 tiers de alta performance        | Voluntário, diferença de apenas 15k  |
| **Grandfathering se houver** | Se admin quiser recompensar jogadores existentes, bônus cosmético ou 1 semana extra de licença como celebração de lançamento | Opcional                        |

**Recomendação:** **Lançamento como expansão silenciosa** — os preços atuais não mudam, então não é necessária nenhuma comunicação urgente. Anunciar os novos tiers como novidade positiva.

---



## 14. Parâmetros de Implementação (Referência Técnica)



### 14.1 IDs sugeridos para config.json

```json
{
  "licenca_delta": {
    "Category": "Licenças",
    "Description": "Licença Delta (30 dias) — Acesso itens Delta. ATENÇÃO: desbloqueia apenas tier Delta (sem tier abaixo).",
    "LicenseGrant": { "Days": 30, "Group": "Delta", "Redeemable": true },
    "TimedPointsBonus": 5,
    "Price": 6000,
    "Type": "license"
  },
  "licenca_delta_renovacao": {
    "Category": "Licenças",
    "Description": "Renovação Licença Delta (30 dias) — 20% desconto (requer licença ativa)",
    "LicenseGrant": { "Days": 30, "Group": "Delta", "Redeemable": true },
    "TimedPointsBonus": 5,
    "Price": 4800,
    "Type": "license",
    "_visibility": "requires_active_group:Delta"
  }
}
```

> Padrão similar para todos os 12 tiers + 12 IDs de renovação = 24 IDs de licença totais.



### 14.2 Grupos de permissão ARK necessários

```
Grupos a criar: Delta, Omega, Transcendente, Etereo, Universal, Onipotente, Surreal, Imaterial, Exotico
Grupos existentes: Gamma, Beta, Alfa
```



### 14.3 Atualização do LICENSE_TIMED_BONUS ([app.py](http://app.py))

```python
LICENSE_TIMED_BONUS = {
    "Default": 25,         # sem alteração
    "Delta": 5,            # novo (porta de entrada)
    "Gamma": 25,           # original preservado
    "Beta": 50,            # original preservado
    "Alfa": 75,            # original preservado
    "Omega": 90,           # novo
    "Transcendente": 105,  # novo
    "Etereo": 120,         # novo
    "Universal": 135,      # novo
    "Onipotente": 150,     # novo
    "Surreal": 165,        # novo
    "Imaterial": 180,      # novo
    "Exotico": 200,        # novo (topo)
    "Moderacao": 500,      # sem alteração
}
PAID_LICENSE_GROUPS = frozenset({
    "Delta", "Gamma", "Beta", "Alfa", "Omega",
    "Transcendente", "Etereo", "Universal",
    "Onipotente", "Surreal", "Imaterial", "Exotico"
})
```



### 14.4 Lógica de permissão de itens por tier

No `config.json`, cada item do ItensAlfa deve ter um campo de permissão indicando o tier mínimo de licença requerido. Exemplo:

```json
{
  "itensalfa_botas_gama": {
    "Category": "ItensAlfa — Armaduras",
    "Description": "Botas TEK Gama (Licença Gama+ requerida)",
    "Price": 700,
    "Type": "item",
    "BlueprintPath": "/Game/Mods/ItensAlfa/Armadura/Gama/AlfaItemArmor_TekBoots_G_V2.AlfaItemArmor_TekBoots_G_V2",
    "RequiredPermissions": ["Gama", "Beta", "Alfa", "Omega", "Transcendente", "Etereo", "Universal", "Onipotente", "Surreal", "Imaterial", "Exotico"]
  }
}
```

> **Nota:** Como Gama desbloqueia Gama+Delta, os itens Delta devem listar: `["Delta", "Gama", "Beta", ...]` (todos os tiers acima, pois todos têm acesso ao Delta).

---



## 15. Hierarquia de Benefícios por Tier


| Tier              | Â/30min | Tiers de Item     | Armor máx. | Arma máx. | Sela máx. | Criaturas                   | Estruturas             |
| ----------------- | ------- | ----------------- | ---------- | --------- | --------- | --------------------------- | ---------------------- |
| Default           | 25      | —                 | —          | —         | —         | —                           | —                      |
| **Delta**         | 30      | Delta             | 180        | 120       | 40        | —                           | Básicas                |
| **Gama**          | 50      | Gama+Delta        | 500        | 250       | 100       | —                           | Mid                    |
| **Beta**          | 75      | Beta+Gama         | 1.000      | 450       | 350       | Enforcer/Defender           | Premium                |
| **Alfa**          | 100     | Alfa+Beta         | 1.900      | 750       | 600       | HoverSkiff/Sail, FastTravel | Criofreezer            |
| **Omega**         | 115     | Omega+Alfa        | 3.200      | 1.300     | 790       | Exo-Mek, Submarine          | CrioCentral, CrossApex |
| **Transcendente** | 130     | Transcend+Omega   | 4.900      | 1.850     | Omega max | —                           | —                      |
| **Etéreo**        | 145     | Etéreo+Transcend  | 7.000      | 2.500     | Omega max | —                           | —                      |
| **Universal**     | 160     | Universal+Etéreo  | 9.500      | 3.250     | Omega max | Stryder                     | Ocean Platform         |
| **Onipotente**    | 175     | Oni+Universal     | 12.400     | 4.100     | Omega max | —                           | —                      |
| **Surreal**       | 190     | Surreal+Oni       | 15.700     | 4.950     | Omega max | —                           | —                      |
| **Imaterial**     | 205     | Imaterial+Surreal | 19.400     | 5.800     | Omega max | —                           | —                      |
| **Exótico**       | 225     | Exótico+Imaterial | 23.500     | 6.650     | Omega max | Tudo                        | Tudo                   |


---



## 16. Tabela Resumo Final — Opção Aprovada (v3.0)


| Tier              | Preço (Â)   | Renovação (−20%) | Duração     | Â/30min | Tiers Item   | Notas                              |
| ----------------- | ----------- | ---------------- | ----------- | ------- | ------------ | ---------------------------------- |
| **Delta**         | **6.000**   | **4.800**        | 30 dias     | 30      | Delta only   | ⚠️ 1 tier — entrada                |
| **Gama**          | **50.000**  | **40.000**       | 30 dias     | 50      | Gama+Delta   | Original preservado                |
| **Beta**          | **75.000**  | **60.000**       | 30 dias     | 75      | Beta+Gama    | Original preservado                |
| **Alfa**          | **100.000** | **80.000**       | 30 dias     | 100     | Alfa+Beta    | Original preservado + criaturas    |
| **Omega**         | **115.000** | **92.000**       | 30 dias     | 115     | Omega+Alfa   | Veículos TEK avançados             |
| **Transcendente** | **130.000** | **104.000**      | 30 dias     | 130     | Trans+Omega  | 4.900 pts armor                    |
| **Etéreo**        | **150.000** | **120.000**      | 30 dias     | 145     | Etéreo+Trans | 7.000 pts armor                    |
| **Universal**     | **165.000** | **132.000**      | 30 dias     | 160     | Uni+Etéreo   | Stryder + Ocean Platform           |
| **Onipotente**    | **180.000** | **144.000**      | 30 dias     | 175     | Oni+Uni      | 12.400 pts armor                   |
| **Surreal**       | **195.000** | **156.000**      | 30 dias     | 190     | Surreal+Oni  | 15.700 pts armor                   |
| **Imaterial**     | **215.000** | **172.000**      | 30 dias     | 205     | Ima+Surreal  | 19.400 pts armor                   |
| **Exótico**       | **230.000** | **184.000**      | 30 dias     | 225     | Exót+Ima     | Teto — 23.500 pts (47× vanilla TEK)|
| *(Nuvem)*         | *(5.000)*   | *(4.000)*        | *(30 dias)* | —       | —            | *(sem alteração)*                  |


---



## 17. Considerações Finais



### Pontos positivos da Opção Aprovada (v3.0)

- Escada de 12 tiers clara: Delta (6k) → Exótico (230k) com progressão de longo prazo e metas desafiadoras
- Matriz de acesso explícita: jogador sabe exatamente quais itens desbloqueará com cada licença
- Delta tratado honestamente: preço justo refletindo o acesso único (1 tier), sem enganar o jogador
- Preços de itens por tier coerentes com as âncoras de dinos (Rex, Carcha, Armaedron)
- 430+ itens catalogados com preços propostos
- Sistema de renovação com desconto incentiva fidelidade
- Preços originais Gama/Beta/Alfa preservados: sem impacto em jogadores existentes
- Posicionamento claro como **subscrição de acesso TEK**, distinto de preço de dino



### Pontos de atenção

- **Retrocompatibilidade:** ✅ Gama/Beta/Alfa mantêm preços originais (50k/75k/100k) — sem impacto nos jogadores existentes
- **Selas apenas até Omega:** Não há sela TEK para tiers Transcendente→Exótico — admin pode criar versões custom ou manter como está
- **Balanceamento PvP:** Armor Exótico (23.500 pts) é extremamente poderoso — monitorar dominância se muitos jogadores atingirem o tier
- **Implementação de renovação:** Exige sistema de verificação de licença ativa — recomendado IDs separados por tier + visibilidade condicional
- **Volume de IDs:** 371+ itens com tier + 61+ especiais = pode ser grande para gerenciar manualmente — sugerir script de geração
- **Kits por tier:** Ver seção 18 para kits de resgate com desconto agrupados por tier



### Próximos passos

1. [x] ~~Admin aprova direção — **v3.0 aprovada** (escada 6k–230k)~~
2. [ ] Criar grupos de permissão ARK (Delta, Omega, Transcendente, Etereo, Universal, Onipotente, Surreal, Imaterial, Exotico)
3. [ ] Adicionar itens ItensAlfa com `RequiredPermissions` no `config.json`
4. [ ] Criar IDs de renovação (`licenca_X_renovacao`) no `config.json`
5. [ ] Atualizar `LICENSE_TIMED_BONUS` e `PAID_LICENSE_GROUPS` em `app.py`
6. [ ] Implementar kits de tier na loja (ver seção 18) — IDs `kit_delta`, `kit_gama`, …, `kit_exotico`
7. [ ] Comunicar jogadores sobre novos tiers (Delta + Omega→Exótico) como expansão positiva

---



## 18. Kits por Tier (Bundle)

> **O que é um kit:** Agrupa todos os itens *com tier* daquele nível — armaduras (5 peças) + armas (14 tipos) + ferramentas (9 tipos) + selas (7 tipos, apenas tiers Delta→Omega) — em um único resgate com desconto. O jogador resgata o kit completo de uma vez, economizando em relação à compra peça por peça.
>
> **Regra de acesso:** O kit do tier X requer licença que desbloqueia o tier X. Como cada licença desbloqueia o próprio tier + o imediatamente abaixo, o kit X é acessível a: **Licença X** (desbloqueia próprio tier) **ou Licença X+1** (desbloqueia X como tier N-1). Exemplo: kit Gama = acesso com licença Gama ou Beta. Ver detalhamento na tabela 18.1.
>
> **Selas:** Existem apenas até o tier **Omega**. Kits Transcendente→Exótico têm 28 itens (sem selas); kits Delta→Omega têm 35 itens (com 7 selas).
>
> **Preços base:** Calculados a partir de `tools/itensalfa_precos_proposta.csv` (fonte definitiva).

---

### 18.1 Tabela Principal — Kits por Tier

| Tier | Itens no kit | Soma unitária | Desconto | Preço kit | Licença mínima |
| --- | --- | --- | --- | --- | --- |
| **Delta** | **35** (5 arm + 14 arma + 9 ferr + 7 selas) | 10.800 Â | −20% | **8.600 Â** | Licença Delta ou Gama |
| **Gama** | **35** (5 arm + 14 arma + 9 ferr + 7 selas) | 18.300 Â | −20% | **14.600 Â** | Licença Gama ou Beta |
| **Beta** | **35** (5 arm + 14 arma + 9 ferr + 7 selas) | 30.000 Â | −20% | **24.000 Â** | Licença Beta ou Alfa |
| **Alfa** | **35** (5 arm + 14 arma + 9 ferr + 7 selas) | 46.200 Â | −20% | **37.000 Â** | Licença Alfa ou Omega |
| **Omega** | **35** (5 arm + 14 arma + 9 ferr + 7 selas) | 64.500 Â | −20% | **51.600 Â** | Licença Omega ou Transcendente |
| **Transcendente** | **28** (5 arm + 14 arma + 9 ferr) | 71.400 Â | −15% | **60.700 Â** | Licença Transcendente ou Etéreo |
| **Etéreo** | **28** (5 arm + 14 arma + 9 ferr) | 100.500 Â | −15% | **85.400 Â** | Licença Etéreo ou Universal |
| **Universal** | **28** (5 arm + 14 arma + 9 ferr) | 133.400 Â | −15% | **113.400 Â** | Licença Universal ou Onipotente |
| **Onipotente** | **28** (5 arm + 14 arma + 9 ferr) | 175.200 Â | −15% | **149.000 Â** | Licença Onipotente ou Surreal |
| **Surreal** | **28** (5 arm + 14 arma + 9 ferr) | 225.900 Â | −15% | **192.000 Â** | Licença Surreal ou Imaterial |
| **Imaterial** | **28** (5 arm + 14 arma + 9 ferr) | 284.600 Â | −15% | **242.000 Â** | Licença Imaterial ou Exótico |
| **Exótico** | **28** (5 arm + 14 arma + 9 ferr) | 359.300 Â | −15% | **305.400 Â** | Licença Exótico (apenas) |

> **Justificativa dos descontos:**
>
> - **−20% (Delta→Omega):** Kits mais completos (35 itens com selas). O desconto maior incentiva a compra do set completo de uma vez, especialmente em tiers iniciais e intermediários onde a reposição de equipamentos perdidos no PvP é frequente. Omega é o último tier com selas — o kit mais "redondo" em cobertura.
> - **−15% (Transcendente→Exótico):** Kits sem selas (28 itens). Os valores unitários já são muito elevados — em Exótico, a economia de 15% representa 53.900 Â (mais do que um kit Delta inteiro). Desconto menor preserva o valor aspiracional dos tiers de topo e evita que o bundle de alta raridade seja trivialmente barato.

---

### 18.2 Composição dos Kits por Categoria (preços do CSV)

| Tier | Armaduras (5×) | Armas (14×) | Ferramentas (9×) | Selas (7×) | Total itens | Soma total |
| --- | --- | --- | --- | --- | --- | --- |
| **Delta** | 5×400 = **2.000** | 14×300 = **4.200** | 9×200 = **1.800** | 7×400 = **2.800** | 35 | **10.800** |
| **Gama** | 5×700 = **3.500** | 14×500 = **7.000** | 9×400 = **3.600** | 7×600 = **4.200** | 35 | **18.300** |
| **Beta** | 5×1.100 = **5.500** | 14×800 = **11.200** | 9×700 = **6.300** | 7×1.000 = **7.000** | 35 | **30.000** |
| **Alfa** | 5×1.700 = **8.500** | 14×1.300 = **18.200** | 9×1.000 = **9.000** | 7×1.500 = **10.500** | 35 | **46.200** |
| **Omega** | 5×2.400 = **12.000** | 14×1.800 = **25.200** | 9×1.400 = **12.600** | 7×2.100 = **14.700** | 35 | **64.500** |
| **Transcendente** | 5×3.400 = **17.000** | 14×2.600 = **36.400** | 9×2.000 = **18.000** | — | 28 | **71.400** |
| **Etéreo** | 5×4.800 = **24.000** | 14×3.600 = **50.400** | 9×2.900 = **26.100** | — | 28 | **100.500** |
| **Universal** | 5×6.400 = **32.000** | 14×4.800 = **67.200** | 9×3.800 = **34.200** | — | 28 | **133.400** |
| **Onipotente** | 5×8.400 = **42.000** | 14×6.300 = **88.200** | 9×5.000 = **45.000** | — | 28 | **175.200** |
| **Surreal** | 5×10.800 = **54.000** | 14×8.100 = **113.400** | 9×6.500 = **58.500** | — | 28 | **225.900** |
| **Imaterial** | 5×13.600 = **68.000** | 14×10.200 = **142.800** | 9×8.200 = **73.800** | — | 28 | **284.600** |
| **Exótico** | 5×17.200 = **86.000** | 14×12.900 = **180.600** | 9×10.300 = **92.700** | — | 28 | **359.300** |

> **Itens incluídos em cada kit:**
>
> - **Armaduras (5 peças):** Botas TEK · Luvas TEK · Capacete TEK · Calças TEK · Peitoral TEK
> - **Armas (14 tipos):** Tek Shield Armor · Shoulder Cannon · Tek Bow · Tek Pistol · ElectroPod · Tek Sword · Tek Claws · Tek Rifle · Sniper · Pike · Pump-Action · Club/Clava · Grenade Launcher · Cruise Missile
> - **Ferramentas (9 tipos):** Chainsaw · Hatchet · Mining Drill · Pick · Sickle · Fishing Rod · Torch · Whip · Lantern Charge
> - **Selas (7 tipos, apenas Delta→Omega):** Sela TEK Megalodon · Mosassauro · Rex · Rock Drake · Astrodelph · Astrocetus · Tapejara

---

### 18.3 Comparativo — Itens Avulsos vs Kit

| Tier | Total avulso | Preço kit | Economia (Â) | % real economizado |
| --- | --- | --- | --- | --- |
| **Delta** | 10.800 Â | 8.600 Â | **2.200 Â** | ~20% |
| **Gama** | 18.300 Â | 14.600 Â | **3.700 Â** | ~20% |
| **Beta** | 30.000 Â | 24.000 Â | **6.000 Â** | 20% |
| **Alfa** | 46.200 Â | 37.000 Â | **9.200 Â** | ~20% |
| **Omega** | 64.500 Â | 51.600 Â | **12.900 Â** | 20% |
| **Transcendente** | 71.400 Â | 60.700 Â | **10.700 Â** | ~15% |
| **Etéreo** | 100.500 Â | 85.400 Â | **15.100 Â** | ~15% |
| **Universal** | 133.400 Â | 113.400 Â | **20.000 Â** | ~15% |
| **Onipotente** | 175.200 Â | 149.000 Â | **26.200 Â** | ~15% |
| **Surreal** | 225.900 Â | 192.000 Â | **33.900 Â** | ~15% |
| **Imaterial** | 284.600 Â | 242.000 Â | **42.600 Â** | ~15% |
| **Exótico** | 359.300 Â | 305.400 Â | **53.900 Â** | ~15% |

> **Perspectiva de valor:** A economia do kit Exótico (53.900 Â) é superior ao custo de um kit Delta inteiro (8.600 Â). Em tiers de topo, a conveniência do bundle vai além do desconto percentual — evita 28 transações individuais separadas.

---

### 18.4 IDs sugeridos para config.json (kits)

```json
{
  "kit_delta": {
    "Category": "ItensAlfa — Kits por Tier",
    "Description": "Kit Delta completo — 35 itens (5 arm + 14 armas + 9 ferr + 7 selas) do tier Delta. Licença Delta ou Gama requerida. Desconto 20% vs avulso.",
    "Price": 8600,
    "Type": "bundle",
    "RequiredPermissions": ["Delta", "Gama"]
  },
  "kit_gama": {
    "Category": "ItensAlfa — Kits por Tier",
    "Description": "Kit Gama completo — 35 itens do tier Gama. Licença Gama ou Beta requerida. Desconto 20% vs avulso.",
    "Price": 14600,
    "Type": "bundle",
    "RequiredPermissions": ["Gama", "Beta"]
  }
}
```

> Padrão similar para todos os 12 kits. CSV auxiliar: `tools/itensalfa_kits_por_tier.csv`.

---



*Proposta v3.0 gerada em Jul/2026 — direção de preços aprovada. Escada 6k–230k (Delta→Exótico).*
*Não altera* `config.json` *até implementação explícita solicitada pelo admin.*
*Arquivo CSV auxiliar com todos os itens:* `tools/itensalfa_precos_proposta.csv`
*Kits por tier:* `tools/itensalfa_kits_por_tier.csv`
*Referência técnica:* `[ECONOMIA_ARKLAND.md](./ECONOMIA_ARKLAND.md)` *— seções 7 (Licenças) e 8 (Progressão).*