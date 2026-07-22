# CustomShop centralizada — plano de configuração única no cluster

> **Status:** Fase 1 implementada (código); Fase 2+ pendente  
> **Escopo:** `{ARKLANDSERVER}/CustomShop/catalog.json` como fonte única do catálogo; `config.json` local por mapa com opções do mapa + `SharedCatalogPath`.  
> **Fora de escopo agora:** release, bump de versão, sync multi-host, poll mtime periódico (API já existe).

---

## Decisões fechadas (produto)

| # | Decisão |
|---|--------|
| 1 | Arquivo partilhado: **`{ARKLANDSERVER}/CustomShop/catalog.json`** |
| 2 | TEK / Web Store gravam **direto** no `catalog.json` (fonte da verdade do catálogo) |
| 3 | Plugin: campo **`SharedCatalogPath`** (absoluto) no `config.json` local; TEK preenche no deploy/sync; vazio → fallback monolítico legado |
| 4 | Migração 1ª vez: extrair Kits/Items/… → `catalog.json`; local fica só opções do mapa + `SharedCatalogPath` (+ `.bak` do monolítico) |
| 5 | Multi-máquina: cada host com o seu `catalog.json` no futuro — **não** implementar sync multi-host agora |

---

## 1. Objetivo e contexto

### Objetivo

Uma única pasta `CustomShop/` no host do cluster define kits, itens, licenças, TimedPoints e demais opções **iguais em todos os mapas**. Atualizar o `catalog.json` uma vez = vale para todos. Mapas (plugin C++), Web Store e TEK apontam para ela — sem cópia N× do catálogo por mapa.

### Layout do host

```
ARKLAND SERVER/
├── MAPAS/
├── CLUSTER/
├── WEBSTORE/
├── CustomShop/
│   ├── catalog.json              ← FONTE ÚNICA do catálogo (Fase 1)
│   ├── catalog.json.example
│   └── configs/config.json       ← legado monolítico (migração / fallback)
└── …

Backups (disco dedicado, default `D:\Backups` — env `ARKLAND_BACKUP_ROOT`):
D:\Backups\
├── servers/
├── saves/
├── database/
├── cloud/
└── .ini/
```

---

## 2. Estado após Fase 1

### 2.1 Plugin C++ (`plugin/CustomShop/`)

| Aspecto | Comportamento |
|--------|----------------|
| Local | `…/Win64/ArkApi/Plugins/CustomShop/config.json` |
| Shared | `SharedCatalogPath` ou env `ARKLAND_CUSTOMSHOP_CATALOG` → `catalog.json` |
| Merge | Shared traz Items/Kits/TimedPoints/…; local sobrescreve Settings TEK, CrossChat.ServerId, Database, Debug |
| Fallback | Shared ausente/inválido → monolítico local (como antes) |
| mtime | `MaybeReloadIfChanged()` — **não** chamado em `/shop` |
| Reload forçado | `Shop.Reload` e `TryReloadConfigForDelivery` (safety net) |

### 2.2 TEK / Python

| Peça | Comportamento |
|------|----------------|
| `canonical_master_catalog_path()` | `{root}/CustomShop/catalog.json` |
| `migrate_catalog_to_canonical()` | Extrai seções partilhadas do legado `configs/config.json` → `catalog.json` |
| `sync_plugin_at_path` | Grava **stub** local + `SharedCatalogPath`; backup `.bak` na 1ª conversão |
| `propagate_master_catalog` | Grava `catalog.json` + stubs nos mapas |
| `find_cross_chat_collisions` | Path `catalog.json` partilhado **não** é erro de “config único”; aponta uso errado se `customshop_config_path` = catalog |

### 2.3 Web Store

Já usa `canonical_master_catalog_path()`; no boot chama `migrate_catalog_to_canonical()`. `config_path` em `settings.json` → `catalog.json`.

---

## 3. Compartilhado vs por-mapa

| Camada | Conteúdo | Onde |
|--------|----------|------|
| **Partilhado** | `Items`, `Kits`, `TimedPointsReward`, `Messages`, `Downloads`, `PointPackages`, `FeaturedMaps`, Settings de gameplay, `CrossChat` sem ServerId | `CustomShop/catalog.json` |
| **Por-mapa** | `SharedCatalogPath`, `Settings.ServerId` / URLs TEK, `CrossChat.ServerId`, `Database`, `Debug` | `…/Plugins/CustomShop/config.json` |

### Merge runtime (plugin)

```
catalog.json (shared)
  ← overlay config.json local (Settings TEK, ServerId, Database, Debug, CrossChat.ServerId)
```

---

## 4. Fase 1 — checklist de aceite

- [x] Schema/path: `CustomShop/catalog.json` + `SharedCatalogPath` no local
- [x] Plugin C++: resolve path, merge, fallback legado, `MaybeReloadIfChanged`
- [x] TEK: canónico = `catalog.json`; sync escreve stub; migração legado
- [x] Web: aponta para o mesmo canónico (+ migrate no boot)
- [x] Collisions: mensagem atualizada (catalog partilhado ≠ erro de ServerId)
- [x] `/shop` **não** faz reload de catálogo
- [x] Testes Python atualizados (`test_shop_sync_permissions`, `test_catalog_paths`)
- [ ] Build DLL (`build_cl.bat`) — tentar no host de build
- [ ] Validação manual em mapa de teste (contagens Items/Kits, ServerId, compra)

---

## 5. Plano por fases (restante)

### Fase 2 — Full

- Poll mtime 30–60 s no plugin (usar `MaybeReloadIfChanged`)
- Deixar de espelhar catálogo em WEBSTORE/bin se possível
- Escrita atómica do `catalog.json`
- Multi-host: UNC ou “cada máquina o seu catalog.json”

### Fase 3 — Higiene

- Deprecar cópia completa legada
- Remover `configs/config.json` após rollout
- Docs ops go-live

---

## 6. Como testar (manual)

1. Garantir `{root}/CustomShop/catalog.json` (Propagar no TEK ou `migrate_catalog_to_canonical`).
2. Num mapa: `config.json` local deve ter `SharedCatalogPath` absoluto e **sem** `Items`/`Kits` grandes.
3. Boot do mapa: log `ShopConfig: shared catalog OK` + contagens.
4. Editar um kit no `catalog.json` (Web/TEK) → `Shop.Reload` (ou esperar Fase 2 poll) → kit visível.
5. Apagar/renomear `SharedCatalogPath` → arranque com fallback legado ou WARN claro.
6. `/shop` no chat **não** deve reler o JSON do disco (só cache em memória).

---

## 7. Rollback

- Restaurar `config.json.bak` monolítico no mapa.
- Remover ou esvaziar `SharedCatalogPath` → plugin usa só o local.
- Opcional: copiar `catalog.json` de volta para o monolítico local.

---

## 8. Referências de código

| Ficheiro | Relevância |
|----------|------------|
| `plugin/CustomShop/src/ShopConfig.cpp` | Load + merge + mtime |
| `src/shop_integration.py` | `catalog.json`, stub, migração, sync |
| `src/arkland_environment.py` | `customshop_master` → `catalog.json` |
| `plugin/arkshop_web/app.py` | `config_path` canónico + migrate boot |
| `docs/CUSTOM_SHOP_CONFIG_CENTRAL.md` | Este plano |

---

*Fase 1 implementada conforme decisões fechadas. Sem release nesta etapa.*
