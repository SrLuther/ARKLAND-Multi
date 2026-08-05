# ArkEventHunt — Plugin ARKLAND (Caça de Evento)

Plugin C++ **standalone** (fora de CustomShop / CustomDinoDeliver) para desafios de dino in-game:

| Modo | Chat | Resumo |
|------|------|--------|
| **A** | `/eve <código>` | Claim do **dono** → spawn → (opcional) grant arma → TakeDamage+Die: % dano / Equipe → complete (+ loot) ou fail |
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

**Modo A (locked):** só o `owner_steam_id` usa `/eve`; ≥`MinAllowedWeaponDamageRatio` do HP com armas allowed; `OfficialWeaponsOnly` default; `ForbidTorpor` default; outra Equipe → FAIL `stolen`; `loot_on_complete` → GiveItem ao killer só em COMPLETED.

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

Ficheiro no servidor: `ShooterGame/Binaries/Win64/ArkApi/Plugins/ArkEventHunt/config.json`

### Bridge HTTP (obrigatório)

O plugin **não** usa a sessão do browser. Precisa de alcançar a mesma loja que o admin Mode B no site:

| Campo | Função |
|-------|--------|
| `WebApiUrl` | Base URL **LAN** da arkshop_web (ex. `http://192.168.1.10:5177`). Se o ARK corre noutro PC, **não** uses `127.0.0.1` — isso aponta para o próprio mapa, não para a loja. |
| `WebApiKey` | Mesma `api_key` da loja (header `X-API-Key`). Vazia/errada → 401 e mensagens de API offline. |

Depois de editar: RCON/console `EventHunt.Reload` (ou reiniciar o mapa).

No TEK, a sync da Loja também escreve `WebApiUrl`/`WebApiKey` no config do ArkEventHunt (como no CustomDinoDeliver).

**Sintoma clássico:** UI web Mode B OK + chat `(SERVER): API Event Hunt inacessível` e/ou (versões antigas) mensagem falsa de “membro ACTIVE” → URL/chave do plugin erradas.

**Não é ranking:** `ranking_blocked` (“fora do ranking”) **não** altera `team_members.status` nem o check de membership do `/eve`.

| Campo | Função |
|-------|--------|
| `Enabled` / `ModeA.Enabled` / `ModeB.Enabled` | Liga/desliga |
| `ServerId` | Gravado no bind (anti multi-mapa) |
| `ModeB.AdminGroups` | Grupos Permissions (além de `bIsAdmin`) |
| `ModeB.AllowPersonalTamesDefault` | Default se API omitir flag |
| `ModeB.TtlTickSeconds` | Intervalo do timer TTL |
| `WeaponWhitelist` / `OfficialWeaponCatalog` | Fallbacks de arma |
| `MinAllowedWeaponDamageRatio` / `ForbidTorpor` / `OfficialWeaponsOnly` | Regras de dano |

Paths plugin (spec §9.2 / §9.3):

- Mode A: `GET .../a/claims/by-code/<code>`, `POST .../spawned|complete|fail`
- Mode B: `GET .../b/codes/<code>` (exige dino ON + sessão ACTIVE + sem ALIVE), `POST .../b/instances/spawned`, `POST .../b/instances/<id>/kill|expire`
- Admin void (re-summon stuck): `POST /api/admin/event-hunt/b/instances/<id>/void`
- Reconcile (best-effort): `GET .../b/instances?status=ALIVE&server_id=`
- Membership: `GET /api/teams/plugin/membership/<steam_id>`

Teste rápido a partir do **host do ARK** (não do PC do browser):

```bat
curl -H "X-API-Key: SUA_CHAVE" http://IP-DA-LOJA:PORTA/api/teams/plugin/membership/STEAMID
curl -H "X-API-Key: SUA_CHAVE" http://IP-DA-LOJA:PORTA/api/event-hunt/b/codes/EUSUA4
```

Se o by-code devolver `dino_disabled`, activa o dino no Catálogo B (estado **ON**). Se for `instance_alive`, void a instância na admin UI antes de `/eveadm` outra vez.
### Mensagens de erro (chat)

| Chave | Quando |
|-------|--------|
| `EveMembershipApiDown` | Membership HTTP falhou (offline / 4xx / `ok:false`) — **não** é “sem equipa” |
| `EveNotActiveMember` | API respondeu `active:false` |
| `EveApiDown` | Claim/código Event Hunt inacessível (`status==0`) |

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
