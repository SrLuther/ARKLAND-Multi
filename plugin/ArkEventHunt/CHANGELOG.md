# Changelog — ArkEventHunt

Versões sincronizadas via `plugin_version.txt` +
`python scripts/sync_plugin_versions.py --plugin ArkEventHunt`.

## [0.4.0] - 2026-08-04

- **Mode B:** `/eveadm <código>` (admin `bIsAdmin` ou `ModeB.AdminGroups` via Permissions).
- HTTP §9.3: `GET /b/codes/<code>` → spawn wild → `POST /b/instances/spawned` (tag `mode=PUBLIC`).
- Die/TakeDamage Mode B: mesmas regras % arma / oficial / torpor; `allow_personal_tames`;
  kill → `POST .../kill` (Team+MVP só se inscrita — API); tame proibido → `valid=false` `tame`.
- TTL por instância: aviso chat T−60s + expire (despawn + `POST .../expire`); sem TTL → fica até morte.
- A+B coexistentes (registry por `mode`); `/eveadm status`.
- Polish: `PostJsonRetry` / `PostJsonDetached`, despawn helpers, reconcile orphan binds no load.

## [0.3.0] - 2026-08-04

- Motor de arma: rastreio HP em `TakeDamage` + golpe fatal em `Die`;
  `MinAllowedWeaponDamageRatio` (default 0.80), `ForbidTorpor`, `OfficialWeaponsOnly`.
- Arma desconhecida / mods / tames → dano **other** (anti-cheese).
- `/eve`: lê knobs do by-code; opcional `GrantWeaponOnStart` (GiveItem oficial).
- Config: catálogo oficial embutido + overrides JSON.

## [0.2.0] - 2026-08-04

- Mode A in-game: `/eve <código>` (só owner) → HTTP by-code → SpawnDino wild → bind → Die.
- Regras locked no Die: arma errada → `POST .../fail` (`weapon`); outra Equipe / sem Equipe → `fail` (`stolen`); kill válido → `.../complete`.
- Config: `Enabled`, `WebApiUrl`, `WebApiKey`, `WeaponWhitelist`, `ServerId`, `ModeA.Enabled`.
- `HuntHttpClient` (WinHTTP + `X-API-Key`); paths alinhados à spec §9.2.
- Mantém `/evespike`; `/eveadm` continua stub Mode B.

## [0.1.0] - 2026-08-03

- Scaffold spike ASE: `/evespike`, stubs `/eve` e `/eveadm`, Die hook + registry in-memory.
- Config `ArkEventHunt` + `EventHunt.Reload`.
- Instalação via TEK/Manager (aba Plugins + botão Loja), padrão ArkPlayer.
