# Regras do Modo Equipe — ARKLAND

| Campo | Valor |
|-------|-------|
| **Documento** | Regulamento jogador-facing do Modo Equipe |
| **Versão** | 1.0 |
| **Última atualização** | 19 de julho de 2026 |
| **Normativo interno** | `docs/PROJETO_MODO_EQUIPE.md` · Regulamento do servidor §8.14 |
| **Idioma** | Português (Brasil) |

Este texto explica as **regras do sistema** do Modo Equipe para quem joga. Valores abaixo são os **padrões do produto**; a staff pode alterar vários deles em **Configurações** da Web Store (indicado como “por omissão”). Em caso de conflito técnico, prevalece o código e as settings ativas do cluster.

O **mural / regulamento interno** de cada equipe (texto editável pelo Owner ou papéis autorizados) é **complementar** — não substitui estas regras de sistema.

---

## 1. O que é o Modo Equipe

- A **Equipe** é a casa social da Web Store (fundação, membros, banco, marcos, split de mercado, rankings).
- É **independente** da tribo in-game: não há sync automático de roster ou ownership com o ARK.
- Por omissão o Modo Equipe está **ligado** (`teams_enabled`). A staff pode desligar.

---

## 2. Filiação

| Regra | Padrão |
|-------|--------|
| Quantas equipes ACTIVE por jogador? | **1** (só podes estar numa de cada vez) |
| Sair | Sim — doações e depósitos **não** são reembolsados |
| Kick manual | **Imediato** (Owner / papéis autorizados; nunca o Owner por outro membro) |
| Kick pela staff | Sim — inclusive o Owner |

### 2.1 Auto-kick por inatividade

- Por omissão o auto-kick está **desligado**.
- O Owner pode ligar e definir o prazo (entre **24** e **720** horas; sugestão típica **168 h** = 7 dias).
- Conta como atividade: doar Â, depositar recurso (`/marco`), aplicar stock ao marco, crédito de XP TimedPoints, ou abrir **Minha Equipe** na web.
- O **Owner nunca** é auto-expulsado.

---

## 3. Fundação, nome e saída do Owner

| Situação | Regra (por omissão) |
|----------|---------------------|
| **1ª fundação** de sempre | **Grátis** |
| Fundar de novo (já foste fundador alguma vez) | **2500 Âmbares** (`teams_founding_fee`; a staff pode alterar) |
| Nome | Único (case-insensitive), **3–32** caracteres; tag opcional até **5** |
| Renomear | Cooldown **168 horas** (7 dias); custo **0 Â** por omissão (staff pode cobrar) |
| Owner sai com outros membros ACTIVE | **Obrigatório** transferir a propriedade antes |
| Owner é o **único** membro e sai | A equipe passa a **DISBANDED** (dissolvida) |

**Staff (transparência):** reativar só o status (**REATIVAR**) não restaura um Owner usável. Para recuperar uma equipe dissolvida/suspensa com Owner ACTIVE, a staff usa **ASSUMIR**.

---

## 4. Capacidade de membros

- Cap base por omissão: **5** membros (`teams_max_members`).
- Marcos podem **subir** o teto via `max_members_unlock` (só aumenta se for maior que o atual).
- A staff pode forçar o teto por equipe no painel admin.
- Pedidos de união / recrutamento público só funcionam se a equipe **aceita recrutamento** e ainda tem **vagas**.

---

## 5. Papéis especiais

- Além do **Owner**, podes ter papéis de sabor (Guardião, Arauto, Guardião do Cofre, Engenheiro de Marcos, Embaixador, Arquivista).
- Por omissão: no máximo **2** papéis especiais por membro (`teams_max_special_roles`; Owner não conta para este teto).
- Só o **Owner** confirma participação no sorteio da equipe e configura o split de mercado (papéis de Guardião **não** substituem o Owner nestes atos).

---

## 6. Banco, armazém e `/marco`

### 6.1 Banco de Âmbares

- Membros ACTIVE podem **doar** Âmbares da carteira pessoal para o banco da equipe.
- Doações **não** são reembolsáveis ao sair ou ser kickado.
- **Não há saque** de Âmbares do banco para a carteira pessoal no produto actual (anti-abuso).

### 6.2 Armazém de recursos

- Só entram os **10 recursos** do catálogo curado (Minério de Elemento, Pérola Negra, Polímero Duro, Areia, Substrato Absorvente, Pérolas de Sílica, Chifre de Deathworm, Polímero Orgânico, Bílis de Amonite, Pó de Elemento).
- Teto por recurso, por omissão: **10 000** (`teams_warehouse_cap_default`). A staff pode definir caps por recurso e marcos podem subir um piso via `warehouse_cap_unlock`.
- Depositar no armazém **não** conta sozinho como progresso do marco: Owner / Guardião do Cofre deve **aplicar** stock ao marco na web.

### 6.3 Comando in-game `/marco` → `/confirmar`

1. `/marco` mostra um **preview** (ainda não consome itens) e avisa que **não há reembolso**.
2. Só `/confirmar` dentro do TTL consome o inventário e credita o armazém.
3. TTL do preview, por omissão: **60 segundos** (`teams_marco_preview_ttl_sec`; a staff pode alterar entre limites seguros).
4. Se o TTL expirar ou o inventário deixar de bater com o preview, o envio cancela — itens ficam contigo; tens de fazer `/marco` de novo.
5. Depósitos confirmados são **definitivos** (sem reembolso).

---

## 7. Marcos e bônus de Âmbar

- Progresso cooperativo: requisitos de Âmbares, XP lifetime da equipe e recursos aplicados.
- XP da equipe é **lifetime** (não zera ao concluir um marco).
- Bônus de Âmbar TimedPoints da equipe é **aditivo** à licença pessoal e desbloqueia com marcos.
- Por omissão: **+2 pp** por marco se o campo do marco estiver vazio (`teams_amber_bonus_pp`); teto acumulado **20%** (`teams_amber_bonus_cap`). A staff define valores por marco.

---

## 8. Split do mercado P2P

- Com Modo Equipe ligado, a divisão de ganhos do mercado usa a **Equipe** (não a tribo).
- Percentagens por omissão ao criar/atualizar o split: **60%** vendedor / **40%** pool da equipe (`teams_market_split_sender_pct`).
- O Owner configura o split; membros opt-in individualmente.
- Venda mínima para entrar no split: **1 000 Âmbares**.
- Encomendas de dinos **ficam de fora** do split de equipe.

---

## 9. Sorteio — participação da equipe

| # | Regra (por omissão) |
|---|---------------------|
| 1 | Só o **Owner** confirma a participação da equipe na campanha ativa (1× por campanha) |
| 2 | Cada membro ACTIVE gera **N** números ligados à **equipe** — N = **2** (`teams_lottery_numbers_per_member`; staff pode alterar, tipicamente 1–6) |
| 3 | Novos membros **após** a confirmação: +N números automáticos (sem nova confirmação), **salvo** se a política pós-confirmação congelar o roster |
| 4 | Se a grade não tiver números livres suficientes: aloca o possível e **reembolsa o banco da equipe** **5000 Â** por cada número em falta (`teams_lottery_shortfall_refund`) |
| 5 | Prémio da equipe em Âmbares, dividido pelos membros ACTIVE no draw; resto vai ao **banco da equipe** |
| 6 | Números **individuais** e números da **equipe** podem coexistir na mesma campanha |

### 9.1 Política após confirmar (anti-abuso)

Por omissão: **`freeze`** (`teams_lottery_post_confirm_policy`). A staff pode mudar.

| Política | Efeito |
|----------|--------|
| **freeze** (padrão) | Depois de confirmar, **não** podes kickar até ao draw. Entradas novas são permitidas (+N números). Se **saíres**, a equipe **perde N números** (devolvidos à grade). |
| **forfeit_on_depart** | Kick ou saída devolvem N números à grade; kick não fica bloqueado |
| **legacy_keep** | Números ficam na equipe; kick permitido (comportamento antigo) |

---

## 10. Rankings

- **Top equipes:** marco actual (desc), depois XP/honra lifetime, depois data de criação.
- **Top jogadores:** XP lifetime (TimedPoints), mesmo sem equipe.
- A staff pode **excluir** equipes ou jogadores do ranking **sem** suspender a conta/equipe (continuam ACTIVE e mantêm XP). Bloqueados aparecem em “fora do ranking”.
- Prémios em Âmbares para o top 1–3: por omissão **desligados** (`teams_ranking_prizes_enabled`). Se a staff ligar e pagar, valores padrão de referência: **50 000 / 25 000 / 10 000 Â** (equipas → banco; jogadores → carteira). Valores e activação são configuráveis.

---

## 11. Conduta

- Nomes, tags e murais ofensivos, discriminatórios ou que imitem a staff ARKLAND são proibidos.
- Abuso económico (farm de fundação, manipulação de sorteio via kick/entrada, exploração de bugs) segue o [Regulamento do servidor](REGULAMENTO_SERVIDOR.md) (punições e tickets).
- Disputas entre membros: resolvem-se na equipe ou por **ticket** na Web Store — não por retaliação in-game.

---

## 12. O que isto não cobre

- **Presente /ajuda entre equipes** — não está disponível no produto actual.
- Sync automática com tribo in-game.
- Saque de Âmbares do banco para carteira pessoal.

---

## Glossário rápido

| Termo | Significado |
|-------|-------------|
| **Owner** | Proprietário da equipe |
| **Marco** | Etapa cooperativa da trilha da equipe |
| **Armazém** | Stock de recursos raros da equipe |
| **Honra** | XP lifetime da equipe (ranking) |
| **DISBANDED** | Equipe dissolvida (ex.: Owner solo saiu) |
