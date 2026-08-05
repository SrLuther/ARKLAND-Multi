# Changelog — ArkEventHunt

Versões sincronizadas via `plugin_version.txt` +
`python scripts/sync_plugin_versions.py --plugin ArkEventHunt`.

## [0.5.2] - 2026-08-05

- HTTP 4xx: log inclui `body=` (preview) além de `body_len` — diagnóstico de
  `dino_disabled` / sessão / instância viva sem adivinhar pelo tamanho.
- `/eveadm` reject log também imprime o body da API.

## [0.5.1] - 2026-08-05

- `/eve` e `/eveadm`: rejeições HTTP ≥400 mostram `Motivo:` com o `error` da API
  (ex.: sessão não ACTIVE, dino já vivo, catálogo off) em vez de mensagem opaca.
- `/eveadm` 404: hint de que códigos Mode A usam `/eve`, não `/eveadm`.

## [0.5.0] - 2026-08-05

- Loot on COMPLETED: `loot_on_complete` `[{blueprint, qty}]` no desafio A / dino B.
- Die válido → `GiveItem` ao inventário do killer (idempotente via `MarkOutcomeSent`).
- Inventário cheio → chat `LootInventoryFull` + log; FAIL nunca entrega loot.
- by-code / Mode B claim-summon incluem a lista; UI Catálogo A edita linhas (sem alfa nos exemplos).

## [0.4.2] - 2026-08-05

- Chat UTF-8: `SendMsg` / `BroadcastChat` convertem UTF-8→ACP/wide
  (corrige `inacess??vel` e acentos nas Messages).
- README + `config.json.example`: como apontar `WebApiUrl`/`WebApiKey` à
  mesma loja LAN do admin web; nota explícita de que ranking_blocked ≠ ACTIVE.
- TEK sync Loja: escreve `WebApiUrl`/`WebApiKey` no config ArkEventHunt.

## [0.4.1] - 2026-08-05

- `/eve`: distingue falha de membership API (`EveMembershipApiDown`) vs
  membro não ACTIVE (`EveNotActiveMember`) — HTTP 4xx/`ok:false` já não
  mostram a mensagem de “não és membro”.
- Logs mais claros no check de Equipe; Die também rejeita `ok:false`/HTTP≥400
  como falha de API (não como resposta válida).
- Nota: `ranking_blocked` (“fora do ranking”) **não** afecta membership ACTIVE.

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
