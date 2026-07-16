# ForceDay Seguro — Design de plugin ArkApi (ASE 361.7)

| Campo | Valor |
|-------|-------|
| **Status** | 📋 **Proposta / estudo** — decisões de produto **travadas**; sem implementação |
| **Versão do documento** | 1.1 |
| **Data** | 2026-07-16 |
| **Escopo** | Design, riscos, integração TEK, plano de testes e fases |
| **Fora de escopo** | Código do plugin, release, reativação de `SetDay` via RCON |
| **Incidente** | TEK v1.10.47 — ForceDay RCON derrubou mapas online; v1.10.48 kill-switch |
| **Referência de plugin** | `plugin/CustomShop` (ArkApi v3 ASE) |
| **Código TEK atual** | `src/force_day_on_start.py`, UI em `src/pages/global_config.py` |

> **Resumo:** `SetDay` via RCON é **inseguro em ASE 361.7** (crash em `UShooterCheatManager::SetDay` no tick RCON). A solução proposta é um **plugin ArkApi leve** que aplica `DayNumber` na **game thread** após o mundo estar pronto, opcionalmente com **patch offline** do `.ark` para alinhamento em massa. O TEK continua a ser a fonte de verdade do dia-alvo; **nunca** volta a enviar `SetDay`/`cheat SetDay` por RCON. **Produto:** em cada start → dia **20**; **só** o número de dia exibido muda — nada mais no mundo.

---

## Decisões aprovadas (produto travado)

> Fonte: aprovação do operador — «sempre que o servidor iniciasse deveria voltar ao dia 20, funcionando assim está ótimo», com invariante de segurança: **nada no mundo se perde ou altera excepto o dia exibido**.

| # | Decisão | Estado |
|---|---------|--------|
| **D1** | Em **cada start/restart** do servidor, `DayNumber` volta a **20** | ✅ **Aprovado** — modo principal; considerado suficiente |
| **D2** | Só o **contador / dia de calendário exibido** (browser, HUD, tribe logs, etc.) muda | ✅ **Aprovado** — invariante **crítica** de segurança |

### D1 — Boot → dia 20

- **Quando:** uma vez por arranque, após o mundo estar ready (BeginPlay / `ServerStatus::Ready` + delay configurável).
- **Alvo:** `TargetDay = 20` (default e valor de produto).
- **Não é:** reset contínuo em runtime, loop periódico, ou «congelar» o dia enquanto o servidor corre — a menos que se decida isso **depois**; o requisito principal é **cada start → 20**.
- **Config default:** `Enabled=true`, `TargetDay=20`, `ApplyOnBoot=true`.

### D2 — Só o dia exibido (invariante crítica)

**Nada** no mundo pode ser perdido, apagado, resetado ou alterado **exceto** o número de dia mostrado (`DayNumber` / campo de calendário equivalente).

**Proibido afetar (lista não exaustiva):**

- Bases, estruturas, foundations, beds, storage
- Dinos (wild/tamed), inventários, saddles, imprint, breeding progress
- Jogadores, personagens, levels, XP, engrams, tribais / tribe data
- Rates (XP, taming, harvest, mating, etc.)
- `DayCycleSpeedScale` / duração do ciclo dia-noite / hora do dia (time-of-day)
- Cluster transfers, uploads, obelisk data
- Qualquer wipe, rebuild ou recriação de save

**Permitido:** alterar **apenas** o campo de calendário / `DayNumber` (o «idade do mapa» no browser/HUD), no mesmo espírito do ForceDay antigo.

**Para qualquer abordagem** (plugin na game thread **ou** patch offline do `.ark`):

1. O método **só** escreve `DayNumber` (ou o campo de calendário equivalente comprovado).
2. **Backup obrigatório** antes de qualquer escrita no save.
3. **Rejeitar** abordagens que wipe/rebuild/recriem o save, ou que toquem noutros campos «por acaso».
4. Rates e duração dia/noite **permanecem intocados**.

---

## 1. Problema — por que RCON `SetDay` é inseguro

### 1.1 O que aconteceu

Na **v1.10.47**, o ForceDay do TEK enviava por RCON:

1. `SetDay N` (ex.: dia 20)
2. Opcionalmente `SaveWorld`

Isto foi disparado no **start/restart** e pelo botão **«Aplicar agora em todos os online»**, em vários mapas **em paralelo**.

Resultado em produção: **crash em todos os mapas online**.

### 1.2 Stack / causa-raiz (confirmada)

O fatal ocorre em:

```text
UShooterCheatManager::SetDay
  ← RCONClientConnection::ProcessRCONPacket
  ← URCONServer::Tick
```

Ou seja: o caminho RCON invoca o CheatManager num contexto em que ASE **361.7** não tolera `SetDay` (timing / thread / estado do mundo).

### 1.3 Por que «cheat SetDay» também não serve

`cheat SetDay N` via RCON chega ao **mesmo** `UShooterCheatManager::SetDay`. Não é alternativa segura — só muda a sintaxe do pacote RCON.

### 1.4 Kill-switch atual (v1.10.48)

| Camada | Comportamento |
|--------|----------------|
| `FORCE_DAY_RCON_ENABLED = False` | `schedule_force_day` é no-op |
| Load de config | `force_day_on_start_enabled` forçado a `False` |
| Save / UI | nunca persiste `enabled=True`; «Aplicar agora» recusado |
| Start/restart | não agenda SetDay |

Campos `force_day_on_start` / `force_day_on_start_enabled` **permanecem** na config TEK para a UI e para a futura integração com o plugin.

**Regra absoluta deste design:** o TEK **nunca** reativa `SetDay` por RCON, mesmo com o plugin instalado. O plugin é o único caminho de apply em runtime.

---

## 2. Objetivos de produto

### 2.1 Must-have

1. **Definir DayNumber** de forma estável em ASE 361.7 (sem crash).
2. **Alinhar mapas ao dia 20** em todo o cluster (**D1** — aprovado).
3. **Aplicar no boot** — uma vez após o mundo estar ready; default `ApplyOnBoot=true`, `TargetDay=20` (**D1**).
4. **Só o dia exibido** — zero perda/alteração de mundo além de `DayNumber` (**D2** — invariante crítica).
5. **Aplicar on-demand** (nice operacional) — sem RCON `SetDay` (ficheiro de pedido / comando admin do plugin / restart com config já escrita); secundário face ao boot.
6. **Opcional `SaveWorld`** — persistir **apenas** o dia após apply (só se o caminho de save for validado como seguro no PoC e **não** alterar outros dados).
7. **Dia-alvo** vindo da config TEK (global default **20**); override por servidor só se necessário depois.
8. **Fail-soft** — log claro; nunca abortar o processo do servidor por falha de ForceDay.

### 2.2 Nice-to-have

- Relatório no TEK: «mapa X → DayNumber Y (ok/falhou)».
- Modo «só se DayNumber ≠ alvo» (evitar save desnecessário).
- Delay configurável pós-load (mitigar races de init).

### 2.3 Explicitamente fora / efeitos laterais proibidos

- Qualquer `SetDay` / `cheat SetDay` via RCON.
- Blast paralelo a 6 mapas com comando crashy.
- Reset contínuo de `DayNumber` durante o runtime (não é o requisito; o modo principal é **start → 20**).
- Alterar rates, `DayCycleSpeedScale`, duração dia/noite, ou hora do dia — **fora de escopo**; ficam como estão.
- Wipe, rebuild ou recriação de `.ark`; patch que toque campos além de `DayNumber`/calendário.
- Perda ou mutação de bases, dinos, inventários, players, tribes, breeding, tames, cluster data (**D2**).
- Dependência de jogador logado (se possível; ver secção 7).

---

## 3. Opções de arquitetura (ranking opinionado)

### Ranking recomendado

| # | Opção | Veredicto | Quando usar |
|---|--------|-----------|-------------|
| **1** | **Híbrido** — offline bulk + plugin maintain-on-boot | **Preferido** | Produção cluster |
| **2** | **Plugin ArkApi only** (hook + game thread) | **PoC / dia-a-dia** | Manter dia após wipe/restart |
| **3** | **Offline `.ark` only** | **Backup / emergência** | Alinhar tudo com downtime aceite |
| ~~4~~ | RCON `SetDay` / `cheat SetDay` | **Proibido** | Nunca |

### 3.1 Opção A — Plugin ArkApi (hooks / tick único)

**Ideia:** DLL em `ArkApi/Plugins/ForceDaySafe/` (nome provisório), no mesmo modelo do CustomShop:

- `Plugin_Init` / `Plugin_Unload`
- Hook `AShooterGameMode.BeginPlay()` (padrão já usado em `plugin/CustomShop/src/Main.cpp`)
- Esperar `ArkApi::GetApiUtils().GetStatus() == ServerStatus::Ready`
- `API::Timer::Get().DelayExecute(...)` com delay configurável
- Aplicar DayNumber **na game thread**, fora do path `ProcessRCONPacket`

**Prós**

- Sem downtime para correções pós-boot.
- Integra naturalmente com ForceDay on start do TEK (só escrever config + restart).
- Logs por mapa no estilo ARKLAND (`logs/` sob a pasta do plugin).

**Contras / riscos**

- API exacta para DayNumber em ASE 361.7 é **research needed** (secção 7).
- Se a única API pública for via CheatManager, ainda pode crashar — o PoC tem de provar o contrário **num mapa só**.
- On-demand sem restart exige canal seguro (ficheiro / RCON **não-SetDay** / chat admin).

**Opinião:** caminho certo para o modo principal (**cada start → dia 20**); **não** assumir que chamar `SetDay` «de dentro do plugin» é automaticamente seguro — só o PoC decide. O PoC também tem de provar **D2** (só DayNumber muda).

### 3.2 Opção B — Edição offline do `.ark` (backup → patch → start)

**Ideia:** com o servidor **parado**, backup do save, patch do campo `DayNumber` no `.ark`, start.

**Prós**

- Não toca no CheatManager em runtime.
- Ideal para alinhamento inicial / pós-wipe / emergência.

**Contras**

- Exige downtime.
- Formato `.ark` / offset do campo: research + validação (corrupção = wipe parcial).
- Não «mantém» o dia se o jogo avançar naturalmente — só define o valor no save.
- **Só é aceite** se o patch escrever **exclusivamente** `DayNumber` (ou campo de calendário equivalente) — ver **D2**. Qualquer ferramenta que rebuild/wipe o save está **rejeitada**.

**Opinião:** ferramenta de **bulk align**, não substituto completo do plugin. Sempre **backup → patch só DayNumber → validar load**.

### 3.3 Opção C — Híbrido (recomendado para cluster)

```text
1) Downtime curto (serializado, 1 mapa de cada vez ou janela de wipe):
     backup → patch **só DayNumber** no .ark → validar load → start
2) Em cada boot seguinte (modo principal aprovado — D1):
     plugin lê config → Enabled + ApplyOnBoot + TargetDay=20
     → mundo Ready → DelayExecute → se DayNumber ≠ 20 → aplica **só** DayNumber na game thread
     → opcional SaveWorld (se PoC provar que não altera mais nada)
3) TEK:
     escreve config do plugin; NUNCA envia SetDay RCON
```

**Porquê esta ordem**

- Offline remove o risco do primeiro alinhamento massivo **sem** rebuild de save (**D2**).
- Plugin evita drift após restarts: **cada start → dia 20** sem edição manual do save (**D1**).
- Serialização (TEK) evita tempestade de applies simultâneos no primeiro rollout.
- Rates / ciclo dia-noite / conteúdo do mundo ficam intocados.

---

## 4. O que o plugin faria — passo a passo

Nome de trabalho: **`ForceDaySafe`** (pasta = `ArkApi/Plugins/ForceDaySafe/`).

### 4.1 Layout (espelhar CustomShop)

```text
<ServerRoot>/ShooterGame/Binaries/Win64/ArkApi/Plugins/ForceDaySafe/
├── ForceDaySafe.dll
├── PluginInfo.json
├── config.json
└── logs/                    # opcional, padrão ARKLAND
    └── arkland_debug.log
```

`PluginInfo.json` (exemplo, alinhado a CustomShop):

```json
{
  "FullName": "ForceDaySafe",
  "Description": "Aplica DayNumber com segurança (sem RCON SetDay) — ARKLAND",
  "Version": 1.0,
  "MinApiVersion": 0.0,
  "Dependencies": [],
  "VersionLabel": "0.1.0"
}
```

### 4.2 `config.json` proposto

```json
{
  "Enabled": true,
  "TargetDay": 20,
  "ApplyOnBoot": true,
  "ApplyOnlyIfDifferent": true,
  "SaveWorldAfterSet": true,
  "DelaySecondsAfterWorldReady": 15,
  "MaxAttempts": 3,
  "AttemptBackoffSeconds": 10,
  "ServerId": "",
  "RequestFile": "force_day_request.json",
  "Debug": {
    "Enabled": false,
    "Level": "INFO"
  }
}
```

| Campo | Papel |
|-------|--------|
| `Enabled` | Master switch; **default `true`** no design do plugin (TEK só liga em produção quando o plugin está instalado e validado) |
| `TargetDay` | DayNumber desejado — **default e produto: `20`** (**D1**); espelha `force_day_on_start` do TEK |
| `ApplyOnBoot` | **Default `true`** — aplicar uma vez após BeginPlay / Ready (**D1**); não implica reset contínuo em runtime |
| `ApplyOnlyIfDifferent` | Skip se já estiver no alvo |
| `SaveWorldAfterSet` | Persistir só se PoC confirmar save seguro **e** sem efeitos laterais além de DayNumber (**D2**) |
| `DelaySecondsAfterWorldReady` | Mitigar init incompleto |
| `RequestFile` | Pedido on-demand sem RCON SetDay (ver 4.5); secundário face ao boot |

Caminho de leitura (padrão CustomShop):

```text
ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/ForceDaySafe/config.json"
```

### 4.3 Fluxo de boot (sequência)

Modo principal (**D1**): **cada start → TargetDay (20)**, uma aplicação após ready — não um loop em runtime.

```text
Plugin_Init
  → Load config.json (fail-soft se inválido: Enabled=false implícito + log)
  → SetHook AShooterGameMode.BeginPlay (ou Timer se já Ready)

BeginPlay / Ready
  → se !Enabled || !ApplyOnBoot → return
  → DelayExecute(DelaySecondsAfterWorldReady)

Callback (game thread) — uma vez por boot
  → revalidar World / GameMode / status Ready
  → ler DayNumber atual (API TBD — research)
  → se ApplyOnlyIfDifferent && atual == TargetDay → log INFO + return
  → aplicar **apenas** TargetDay / DayNumber (API TBD — NÃO via RCON; NÃO tocar rates/ciclo/conteúdo — D2)
  → se falhou → log ERROR, retry até MaxAttempts, NUNCA crashar
  → se ok && SaveWorldAfterSet → SaveWorld (só se PoC provar que não altera mais que o dia)
  → log sucesso (antes/depois)
  → fim (sem timer periódico de reset)
```

### 4.4 Requisitos de threading

| Fazer | Não fazer |
|-------|-----------|
| Aplicar DayNumber no callback do Timer / hook (game thread) | Chamar SetDay a partir de thread RCON / worker TEK |
| Guardas null em World / GameMode / PlayerController | Assumir CheatManager válido no tick 0 |
| try/catch + log em falhas esperáveis | `abort` / exceções não tratadas que matem o processo |

### 4.5 On-demand (sem `SetDay` RCON)

Opções, por ordem de preferência neste design:

1. **Ficheiro de pedido** — TEK (ou admin) escreve `force_day_request.json` na pasta do plugin; o plugin faz poll leve no Timer (ex. 5–10 s) e consome o pedido.
2. **Restart com config já atualizada** — TEK escreve `TargetDay` + `Enabled` e reinicia o mapa (mais simples, menos «ao vivo»).
3. **Comando RCON inocente** — ex. `ForceDay.Reload` / `ForceDay.Apply` implementado pelo plugin (como `Shop.Reload`), que **não** chama CheatManager `SetDay` pelo path RCON nativo — o handler do plugin agenda `DelayExecute` na game thread.
4. ~~`SetDay` / `cheat SetDay` RCON~~ — **proibido**.

### 4.6 Logging

- INFO: apply skipped / success (antes → depois).
- WARN: retry.
- ERROR: falha definitiva; mapa continua a correr.
- Espelhar categorias no estilo `docs/ARKLAND_PLUGIN_DEBUG.md` se o plugin for oficializado.

---

## 5. Integração com ARKLAND TEK

### 5.1 Estado atual da UI / config

- Global: `force_day_on_start` (int, default 20), `force_day_on_start_enabled` (bool, forçado OFF).
- UI (`global_config.py`): checkbox + dia + «Aplicar agora» — **bloqueados** com mensagem até existir alternativa segura.
- `force_day_on_start.py`: kill-switch permanente no caminho RCON.

### 5.2 Modelo futuro (quando o plugin existir)

```text
┌─────────────┐     escreve config.json      ┌──────────────────┐
│  TEK UI     │ ───────────────────────────► │ ForceDaySafe     │
│  ForceDay   │     (por mapa, como Shop)    │ plugin no mapa   │
└─────────────┘                              └────────┬─────────┘
       │                                              │
       │  deteta PluginInfo / DLL                     │ aplica DayNumber
       │  → desbloqueia UI                            │ na game thread
       ▼                                              ▼
  Nunca SetDay RCON                            Mundo ASE 361.7
```

### 5.3 Como o TEK escreveria a config do plugin

Espelhar o padrão CustomShop (`shop_integration.install_customshop_to_server`, painel «Instalar»):

1. **Deploy:** copiar `ForceDaySafe.dll` + `PluginInfo.json` para  
   `ShooterGame/Binaries/Win64/ArkApi/Plugins/ForceDaySafe/`  
   (preservar `config.json` existente, como no Shop).
2. **Sync de config:** ao guardar Configurações Globais / ForceDay:
   - Mapear `force_day_on_start` → `TargetDay`
   - Mapear `force_day_on_start_enabled` → `Enabled` **somente se** plugin detectado em todos os alvos (ou por servidor).
3. **Detecção de presença:** `PluginInfo.json` / DLL em  
   `.../ArkApi/Plugins/ForceDaySafe/`  
   (reutilizar ideias de `src/plugin_versions.py` — adicionar `ForceDaySafe` a `OFFICIAL_PLUGINS` no futuro).
4. **UI:**
   - Sem plugin → manter UI bloqueada (estado 1.10.48).
   - Com plugin → permitir enable + «Aplicar» via **escrita de config / request file / restart**, nunca via `SetDay` RCON.
5. **Start/restart:** em vez de `schedule_force_day` RCON, apenas garantir que o `config.json` do plugin está atualizado **antes** do start; o plugin aplica sozinho no boot.

### 5.4 Serialização de mapas (obrigatório no TEK)

No incidente, o blast paralelo amplificou o dano. Regras:

| Operação | Política |
|----------|----------|
| Primeiro rollout / PoC | **1 mapa de cada vez**; confirmar logs + estabilidade |
| «Aplicar agora» futuro | Serializar: mapa N só depois de ack/timeout de N−1 |
| Offline patch | Servidor **parado**; backup antes; um mapa de cada vez |
| Cluster completo | Só após PoC verde num mapa «canário» |

### 5.5 Deploy path (paridade CustomShop)

Referência existente:

```text
<install_dir>/ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomShop/
  CustomShop.dll, PluginInfo.json, config.json, …
```

ForceDaySafe seguiria o mesmo contrato; bundle no repo em `plugin/ForceDaySafe/bin/` + instalador TEK análogo a `install_customshop_to_server`.

---

## 6. Requisitos de segurança (não negociáveis)

1. **Zero** `SetDay` / `cheat SetDay` via RCON no TEK e no plugin (o plugin não deve reenviar o comando RCON a si próprio).
2. **Não** blastar 6 mapas com qualquer apply experimental.
3. **Serializar** applies on-demand e rollouts.
4. **Backup** obrigatório antes de patch offline de `.ark`; escrita **só** em `DayNumber`/calendário (**D2**).
5. **Fail-soft:** falha de ForceDay ≠ crash do servidor.
6. **Feature flag** no TEK: ForceDay enabled só com plugin presente e versão mínima conhecida.
7. **Kill-switch RCON** permanece no código TEK mesmo após o plugin estar em produção (defesa em profundidade).
8. PoC e testes **sempre** num mapa isolado primeiro.
9. **Invariante D2:** nenhuma abordagem aceite pode wipe/rebuild o save ou alterar bases, dinos, players, tribes, rates, ciclo dia-noite, etc. — só o dia exibido.
10. Rejeitar candidatos de API/ferramenta que, no PoC, mostrem efeitos laterais além de `DayNumber`.

---

## 7. Riscos e desconhecidos (research needed)

| # | Risco | Impacto | Mitigação |
|---|--------|---------|-----------|
| R1 | **API exacta de DayNumber em ASE 361.7 desconhecida** | Bloqueia implementação | Research no SDK ArkApi / headers ASE; dump UFunctions; comparar com ASA se útil só como pista |
| R2 | Chamar `UShooterCheatManager::SetDay` **mesmo na game thread** ainda crasha | Plugin inútil / perigoso | PoC isolado; se falhar → priorizar offline `.ark` |
| R3 | DayNumber só acessível com PlayerController / cheat context | Apply on boot sem players falha | Delay + retry; fallback offline; ou spawn de contexto admin interno (cuidado) |
| R4 | `SaveWorld` imediato após set corrompe / deadlock | Perda de progresso | PoC com e sem save; default `SaveWorldAfterSet=false` até validar |
| R5 | Patch offline do `.ark` no campo errado ou rebuild do save | Save corrompido / perda de mundo (**D2**) | Backup + dry-run; **só** campo DayNumber; rejeitar wipe/rebuild; validar load |
| R6 | Drift natural do dia entre mapas | Cluster «desalinhado» | Plugin on boot (**D1**: cada start → 20); apply periódico em runtime **não** é requisito |
| R7 | Confundir ForceDaySafe com CustomShop Reload | Operadores reativam SetDay «só mais uma vez» | UI e logs explícitos; kill-switch RCON permanente |
| R8 | Apply altera rates / ciclo / estruturas «por acidente» | Viola **D2** | PoC com checklist de não-efeitos; rejeitar API se houver side effects |

### 7.1 Research checklist (API)

Marcar como **aberto** até o PoC:

- [ ] Existe getter/setter de DayNumber em `AShooterGameMode` / `UWorld` / `AShooterGameState`?
- [ ] `UShooterCheatManager::SetDay` é seguro se chamado **fora** de `ProcessRCONPacket`?
- [ ] Há UFunction Blueprint/`UFunction` estável invocável via ArkApi helpers?
- [ ] DayNumber no save `.ark`: nome do campo, tipo, localização (ferramenta / hex / parser existente)?
- [ ] ASE 361.7 vs builds anteriores: regressão só no path RCON ou em todo SetDay?

> **Hipótese de trabalho (a invalidar no PoC):** o crash está ligado ao **contexto RCON/tick**, não ao SetDay em si. Se a hipótese falhar, o plugin **não** deve chamar SetDay — só offline patch + documentar limitação.

---

## 8. Plano de testes (um mapa antes do cluster)

### 8.1 Ambiente canário

- **1** mapa de teste (idealmente cópia / não-produção).
- ArkApi v3 carregado; sem outros experimentos no mesmo boot.
- Backup completo do save **antes** de qualquer teste.

### 8.2 Matriz mínima

| # | Caso | Pass criteria |
|---|------|----------------|
| T1 | Boot com `Enabled=false` | Sem apply; servidor estável ≥ 30 min |
| T2 | Boot com `Enabled=true`, dia já = alvo | Skip + log; estável |
| T3 | Boot com dia ≠ alvo, sem SaveWorld | DayNumber → 20; **sem** alteração de bases/dinos/inventários/rates; sem crash ≥ 30 min |
| T4 | Igual T3 + SaveWorld | Após restart, dia persiste; save abre limpo; conteúdo do mundo idêntico (exceto DayNumber) |
| T5 | Request file / comando plugin Apply | Apply na game thread; sem RCON SetDay nos logs RCON |
| T6 | Config inválida / TargetDay absurdo | Fail-soft; servidor sobe |
| T7 | Descarregar plugin a meio (Unload) | Sem crash; hooks removidos |
| T8 | **Controlo negativo** | Confirmar que TEK **ainda** não envia SetDay RCON com UI ligada |
| T9 | **D2 — side effects** | Antes/depois: rates, DayCycleSpeedScale, estruturas, dinos, player XP intactos |

### 8.3 Só depois do canário verde

- Segundo mapa (ainda serializado).
- Cluster completo com serialização e janela de observação.
- Documentar versão ASE + ArkApi + VersionLabel do plugin no relatório.

### 8.4 O que **não** testar em produção

- Reativar `FORCE_DAY_RCON_ENABLED`.
- «Aplicar agora» paralelo em 6 mapas com build experimental.

---

## 9. Perguntas em aberto (equipa)

1. Nome final do plugin (`ForceDaySafe` vs `ArklandDay` vs outro)?
2. Aceitamos **downtime** para alinhamento inicial via `.ark`, ou exigimos 100% online?
3. `SaveWorldAfterSet` default: `true` (como o ForceDay antigo) ou `false` até T4/T9 passarem?
4. On-demand preferido: **restart**, **request file**, ou **comando RCON do plugin**? (secundário — boot já cobre o modo principal)
5. ~~Dia-alvo / boot apply?~~ → **Decidido (D1):** `TargetDay=20`, `ApplyOnBoot=true` em cada start; sem reset contínuo em runtime como requisito.
6. Quem faz o research da UFunction (interno vs. comunidade ArkApi)?
7. O plugin entra no bundle oficial do Multi (`OFFICIAL_PLUGINS`) na mesma release da integração TEK, ou plugin-first / TEK depois?
8. ~~Alinhar também hora do dia / rates / ciclo?~~ → **Decidido (D2):** **não** — só `DayNumber` exibido; rates e duração dia/noite intocados.
9. Comportamento se o mapa estiver em evento / dungeon com regras especiais de tempo?
10. Política de suporte: ForceDaySafe requer ArkApi mínimo X — qual o floor do cluster?
11. Override por mapa desde o dia 1, ou sempre global TEK = 20?

---

## 10. Fases sugeridas

```text
Fase 0 — Research API (sem deploy cluster)
  • Inventariar UFunctions / campos DayNumber no SDK ASE 361.7
  • Decidir: CheatManager game-thread vs setter directo vs só offline
  • Spike de leitura do .ark (campo DayNumber) em cópia de save

Fase 1 — PoC num mapa
  • DLL mínima: config + BeginPlay + DelayExecute + log
  • Um caminho de apply candidato
  • Matriz T1–T8; kill-switch RCON intocado no TEK

Fase 2 — Offline tool (se PoC runtime frágil)
  • Backup + patch .ark + validação de load
  • Usar para bulk align; plugin só maintain-on-boot se seguro

Fase 3 — Integração TEK
  • Install path tipo CustomShop
  • Escrita de config.json; detecção PluginInfo
  • UI: desbloquear ForceDay só com plugin presente
  • «Aplicar agora» = request/restart serializado — zero SetDay RCON
  • Testes unitários TEK: kill-switch RCON continua a passar

Fase 4 — Rollout cluster
  • Canário → 2º mapa → resto, serializado
  • Observabilidade (logs TEK + logs plugin)
  • Runbook: rollback = Enabled=false + remover DLL se necessário
```

### Critério de «pronto para produção»

- [ ] PoC T3/T4/T9 verdes em ASE 361.7 (dia 20 no boot **e** zero side effects no mundo)
- [ ] Zero ocorrências de `SetDay` nos traces RCON do TEK
- [ ] UI TEK só permite enable com plugin detectado
- [ ] Runbook de rollback testado
- [ ] Documentação de versão (plugin + ASE + ArkApi) arquivada
- [ ] Defaults de produto: `TargetDay=20`, `ApplyOnBoot=true` (D1); escopo só DayNumber (D2)

---

## Apêndice A — Mapa rápido do código TEK relevante (hoje)

| Ficheiro | Papel |
|----------|--------|
| `src/force_day_on_start.py` | Kill-switch RCON; docstring do incidente |
| `src/config_manager.py` | `force_day_on_start*`; força OFF no load |
| `src/pages/global_config.py` | UI bloqueada |
| `src/pages/save_global_config_tek.py` | Nunca persiste enabled=True |
| `src/app_tek.py` | `_maybe_apply_force_day_on_start` / `apply_force_day_now_*` no-op |
| `tests/test_force_day_on_start.py` | Garante que RCON SetDay permanece morto |

## Apêndice B — Padrões CustomShop a reutilizar

| Padrão | Onde | Reuso em ForceDaySafe |
|--------|------|------------------------|
| `Plugin_Init` / hooks BeginPlay | `plugin/CustomShop/src/Main.cpp` | Boot + apply atrasado |
| `API::Timer::DelayExecute` | idem | Delay pós-Ready |
| `ServerStatus::Ready` | idem | Guard antes de tocar no mundo |
| Path `.../ArkApi/Plugins/<Name>/config.json` | `ShopConfig.cpp` | Config por mapa |
| `PluginInfo.json` + `VersionLabel` | `bin/PluginInfo.json` | Detecção TEK / versões |
| Install TEK sem overwrite de config | `shop_integration.install_customshop_to_server` | Deploy seguro |
| Pasta `logs/` | `docs/ARKLAND_PLUGIN_DEBUG.md` | Diagnóstico |

## Apêndice C — Decisão de arquitetura (opinião + locks de produto)

**Locks de produto (não renegociar sem nova aprovação):**

- **D1:** cada start → `DayNumber = 20` (apply once when world ready).
- **D2:** só o dia exibido muda; zero perda/alteração do resto do mundo.

**Para estudar e implementar mais tarde, a posição deste doc é:**

1. **Proibido** reabrir RCON `SetDay`.
2. **Começar** pelo research + PoC de plugin num mapa (hipótese: game thread ≠ path RCON), com defaults `Enabled` / `ApplyOnBoot` / `TargetDay=20`.
3. Se SetDay/CheatManager for inseguro em qualquer contexto → **não insistir**; pivot para **offline `.ark` (só campo DayNumber + backup)** + plugin só se houver setter limpo.
4. Em cluster, preferir **híbrido** com applies **serializados** e TEK como escritor de config, não como emissor de cheats.
5. Rejeitar qualquer caminho que wipe/rebuild o save ou altere rates / ciclo / conteúdo.

---

*Documento de estudo. Decisões D1/D2 estão travadas. Nenhuma implementação, release ou reativação de ForceDay RCON está autorizada por este ficheiro.*
