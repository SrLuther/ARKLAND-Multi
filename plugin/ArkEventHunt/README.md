# ArkEventHunt — Plugin ARKLAND (Caça de Evento)

Plugin C++ **standalone** (fora de CustomShop / CustomDinoDeliver) para desafios de dino in-game:

| Modo | Chat | Resumo |
|------|------|--------|
| **A** | `/eve <código>` | Claim do **dono** → spawn → (opcional) grant arma → TakeDamage+Die: % dano / Equipe → complete ou fail |
| **B** | `/eveadm <código>` | Admin (Permissions) → Catálogo B → spawn wild perto → bind `PUBLIC` → só inscritas pontuam (Team+MVP) |

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| **[`docs/PROJETO_ARK_EVENT_HUNT.md`](../../docs/PROJETO_ARK_EVENT_HUNT.md)** | Spec de produto (docs agent) |
| **[`docs/SPIKE_ARK_EVENT_HUNT.md`](../../docs/SPIKE_ARK_EVENT_HUNT.md)** | Checklist ASE (spawn / Die / arma / IDs) |

## Estado actual

| Fase | Estado |
|------|--------|
| Spike ASE (`/evespike`) | ✅ |
| Mode A plugin (`/eve` + HTTP §9.2) | ✅ |
| Mode B plugin (`/eveadm` + HTTP §9.3) | ✅ v0.4.0 |
| UI web Mode A | ✅ |
| UI web Mode B | ❌ stub (API plugin paths prontos no DLL) |
| Install TEK empacotado | ✅ aba Plugins + botão Loja |

**Não usa TribeLog** — scoring por Equipes do site + SteamID no hook.

**Modo A (locked):** só o `owner_steam_id` usa `/eve`; ≥`MinAllowedWeaponDamageRatio` do HP com armas allowed; `OfficialWeaponsOnly` default; `ForbidTorpor` default; outra Equipe → FAIL `stolen`.

**Modo B (locked):** só `/eveadm`; A+B coexistentes; `allow_personal_tames` por dino; TTL com chat T−60s + expire/despawn; vivos sem TTL no fim do evento ficam até morte.

## Comandos

| Comando | Quem | Efeito |
|---------|------|--------|
| `/eve <código>` | Dono do claim (ACTIVE) | Valida API → spawn wild → bind → grant opcional |
| `/evespike` [spawn] [bp] [level] | Admin | Teste ASE sem HTTP |
| `/eveadm <código>` | Admin / Permissions | Mode B: resolve código → spawn → bind PUBLIC |
| `/eveadm status` | Admin | Lista vivos Mode B neste mapa |
| `EventHunt.Reload` | Console/RCON | Recarrega `config.json` |

## Config (`config.json`)

| Campo | Função |
|-------|--------|
| `Enabled` / `ModeA.Enabled` / `ModeB.Enabled` | Liga/desliga |
| `WebApiUrl` / `WebApiKey` | Bridge HTTP (`X-API-Key`) |
| `ServerId` | Gravado no bind (anti multi-mapa) |
| `ModeB.AdminGroups` | Grupos Permissions (além de `bIsAdmin`) |
| `ModeB.AllowPersonalTamesDefault` | Default se API omitir flag |
| `ModeB.TtlTickSeconds` | Intervalo do timer TTL |
| `WeaponWhitelist` / `OfficialWeaponCatalog` | Fallbacks de arma |
| `MinAllowedWeaponDamageRatio` / `ForbidTorpor` / `OfficialWeaponsOnly` | Regras de dano |

Paths plugin (spec §9.2 / §9.3):

- Mode A: `GET .../a/claims/by-code/<code>`, `POST .../spawned|complete|fail`
- Mode B: `GET .../b/codes/<code>`, `POST .../b/instances/spawned`, `POST .../b/instances/<id>/kill|expire`
- Reconcile (best-effort): `GET .../b/instances?status=ALIVE&server_id=`
- Membership: `GET /api/teams/plugin/membership/<steam_id>`

## Build

```bat
cd plugin\ArkEventHunt
build_cl.bat
```

Saída: `bin/ArkEventHunt.dll` (caminho TEK).

## Layout

```
plugin/ArkEventHunt/
  build_cl.bat
  configs/
  src/
    Main.cpp
    HuntConfig.*
    HuntHttpClient.*   # retry + PostJsonDetached
    HuntCommands.*     # /eve /eveadm /evespike
    HuntHooks.*        # TakeDamage + Die Mode A/B
    HuntRegistry.*
    HuntPerms.*
    HuntWorld.*        # despawn / broadcast / find-by-id
    HuntLifecycle.*    # TTL timer + reconcile
```
