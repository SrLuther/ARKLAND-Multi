# SPIKE ASE — ArkEventHunt

Checklist técnico para validar no **ASE real** o motor partilhado dos Modos A e B.  
Spec de produto: [`PROJETO_ARK_EVENT_HUNT.md`](./PROJETO_ARK_EVENT_HUNT.md) (docs agent).  
Scaffold: `plugin/ArkEventHunt/`.

**Fora de scope deste spike:** UI web Mode A/B, prémios Âmbar automáticos, TribeLog.

Instalação TEK (DLL + config): ver [`PROJETO_ARK_EVENT_HUNT.md`](./PROJETO_ARK_EVENT_HUNT.md) §12.4.1 / `plugin/ArkEventHunt/README.md`.

---

## Premissas (produto locked)

### Modo A — `/eve <código>`
- Só o **dono** do claim (`owner_steam_id`) executa `/eve`.
- Spawn perto do **jogador** (dono).
- Arma errada → claim `FAIL` (consome tentativa do membro nesse desafio).
- Kill por outra Equipe → claim `FAIL` (também consome).
- Unicidade `(steam_id, challenge_id)`: membro não repete o mesmo desafio após terminal; membros diferentes **podem** o mesmo desafio.
- Lock one-at-a-time: **por membro**, não por team.

### Modo B — `/eveadm <código>`
- Só Equipes **inscritas** pontuam.
- Catálogo **separado** do A.
- Spawn perto do **admin**.
- Expira com avisos no chat geral (1 min + ao expirar).
- A + B podem coexistir no mesmo mapa.
- Placar Equipe + MVP; Âmbar + ranking por config do dino; tames opcionais por dino.

---

## Referências no repo / SDK

| Capacidade | Onde |
|------------|------|
| `SpawnDino(player, bp, loc, lvl, force_tame, neutered)` | `ArkApiUtils.h` — `force_tame=false` = wild |
| `GetDinoIDs(&id1, &id2)` | `ShopCryoDino.cpp` / `DinoDeliver.cpp` |
| `GetAttackerSteamID(target, killer, damage_causer, tribe_check)` | `ArkApiUtils.h` (pensado p/ TakeDamage) |
| `APrimalDinoCharacter.Die(...)` / `TakeDamage(...)` | `Actor.h` SDK |
| Chat + console | `ArkPlayer` / `CustomDinoDeliver` (`AddChatCommand`) |
| Install TEK (app) | `shop_integration.py` — `install_arkeventhunt_to_server` (padrão ArkPlayer) |

---

## Checklist (marcar no servidor de teste)

### 1. Spawn wild tagged
- [ ] Compilar e carregar `ArkEventHunt.dll` num mapa ASE.
- [ ] `/evespike spawn <BlueprintPath> [level]` (admin) → dino aparece perto do jogador.
- [ ] Confirmar `force_tame=false`: dino **wild** (não tameado / sem TamerString).
- [ ] Capturar `dino_id1` / `dino_id2` via `GetDinoIDs` e logar no chat/console.
- [ ] Registar no mapa in-memory `HuntRegistry` (id1+id2 → claim stub).
- [ ] Opcional: `TamedName` / tag visual só para debug (não confundir com tame).

**Bloqueio se falhar:** spawn ou IDs instáveis → MVP A/B parado.

### 2. Hook Die + GetAttackerSteamID
- [ ] Hook `APrimalDinoCharacter.Die(float,FDamageEvent*,AController*,AActor*)` (string exacta a confirmar no ASE/ArkApi em uso).
- [ ] Filtrar só dinos no `HuntRegistry` (ignorar resto do mapa).
- [ ] Em Die: `GetAttackerSteamID(dino, Killer, DamageCauser, /*tribe_check=*/false)` — wild não tem tribo; `tribe_check=true` pode anular ID.
- [ ] Casos a testar:
  - [ ] Kill corpo-a-corpo (melee player)
  - [ ] Kill com arma ranged
  - [ ] Kill montado em tame (SteamID do rider vs dono do tame — documentar comportamento real)
  - [ ] Kill por outra entidade (dino wild / turrets) → SteamID 0 esperado
- [ ] Alternativa se Die for insuficiente: espelhar em `TakeDamage` e ler SteamID no hit fatal.

**Bloqueio se falhar:** sem killer estável → scoring A/B impossível.

### 3. Arma no killing blow (whitelist)
- [ ] Definir 2–3 BPs de arma conhecidos no `config.json` (`SpikeWeaponWhitelist`).
- [ ] No hit fatal (Die e/ou último TakeDamage), obter classe/path do `DamageCauser` e/ou arma equipada do killer.
- [ ] Documentar qual caminho funciona no ASE 361.x do cluster:
  - [ ] `DamageCauser` é `AShooterWeapon` / projectile com owner weapon?
  - [ ] `AShooterCharacter` → current weapon item BP?
- [ ] Whitelist match → log `WEAPON_OK`; mismatch → log `WEAPON_FAIL` (Mode A: fail claim).
- [ ] Melee-only / “sem arma” se o produto precisar — provar se é detetável.

**Bloqueio se falhar:** regras de arma do cadastro não são enforceáveis in-game.

### 4. Tag / bind de IDs
- [ ] Após spawn, bind `(dino_id1, dino_id2) → { mode, code, team_id?, expires_at? }`.
- [ ] Die só processa se o par existir no registry.
- [ ] Remover do registry em COMPLETED / FAILED / EXPIRED / Destroy.
- [ ] Stress: 2+ dinos A e 1 B vivos no mesmo mapa (coexistência) — kills não cruzam claims.
- [ ] Após save/restart do mapa: registry em memória perde-se (aceitável no spike; persistência = fase posterior / web).

---

## Ordem sugerida no ASE (½–1 dia)

1. Load plugin + `/evespike` spawn + IDs no log.
2. Matar com SteamID conhecido → Die hook.
3. Matar com armas whitelist vs fora → classificação arma.
4. Dois dinos tagged → kills não misturam.

---

## Critério de saída do spike

| Resultado | Segue para |
|-----------|------------|
| Spawn wild + IDs + Die + SteamID + arma OK | MVP Mode A (HTTP claim + `/eve`) |
| Arma ou killer instável | Reavaliar regras de produto / outra fonte de hit |
| Spawn OK mas IDs 0 | Investigar timing BeginPlay / GetDinoIDs (padrão Dino Lab) |

---

## Explicitamente NÃO usar

- **TribeLog** / `TribeLog.log` / hooks de tribo in-game para scoring de Equipes do site.
- Scoring por nome de tribo ASE — Equipes = entidade web.
