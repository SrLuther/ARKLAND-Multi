# Projeto: Inventário na Nuvem (Upload / Download)

| Campo | Valor |
|-------|-------|
| **Status** | 🟡 Aguardando discussão e aprovação — **não implementar** até decisões fechadas |
| **Versão do documento** | 1.0 |
| **Data** | 2026-06-18 |
| **Release base do app** | v1.9.34 |
| **Escopo técnico** | Plugin CustomShop (C++) + MariaDB `arkland_shop` (cluster-wide) |

---

## Resumo executivo

Jogadores com **Licença Nuvem** ativa poderão:

1. **`/upload`** — enviar todo o inventário para o banco; o inventário in-game fica vazio.
2. **`/download`** — recuperar os itens em **qualquer mapa** do cluster.
3. **`/nuvem`** — consultar quantos itens estão armazenados.

O sistema é um **cofre único por SteamID** no banco compartilhado. Não permite segundo upload enquanto já houver itens salvos.

---

## Contexto no ecossistema ARKLAND

| Componente | Papel |
|------------|-------|
| **CustomShop.dll** | Único lugar com acesso ao inventário do jogador no servidor ASE |
| **MariaDB `arkland_shop`** | Banco já usado por pontos, licenças e pedidos — mesmo host em todos os mapas |
| **Licença Nuvem** (`licenca_nuvem`) | Item da loja; hoje concede grupo Ark `keyvault` por 30 dias |
| **Web Store** | Venda da licença; documentação automática em `redeem_docs.js` |
| **TEK / Server Manager** | Deploy do plugin, sync de `config.json`, migração SQL via `setup_db.sql` |

---

## Histórias de usuário

### Jogador com licença

- Como jogador, quero usar `/upload` no chat para guardar meus itens antes de trocar de mapa, sem perder mods, qualidade ou stacks.
- Como jogador, quero usar `/download` em outro mapa do cluster e receber exatamente o que enviei.
- Como jogador, quero `/nuvem` para saber se ainda tenho itens guardados e quantos são.

### Jogador sem licença

- Como jogador sem licença, ao usar `/upload` devo ver mensagem clara de que preciso adquirir a Licença Nuvem na loja.

### Admin / operação

- Como admin, quero que um jogador não possa fazer upload duas vezes sem antes fazer download (evita duplicação).
- Como admin, quero logs no servidor para suporte (upload/download/recusa).

---

## Requisitos acordados (origem: pedido do dono do servidor)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| R1 | `/upload` salva **todos** os itens do inventário do jogador e esvazia o inventário | Obrigatório |
| R2 | `/download` devolve tudo que foi salvo | Obrigatório |
| R3 | **Não** permitir novo `/upload` se já existir snapshot do jogador no banco | Obrigatório |
| R4 | `/upload` exige licença de nuvem ativa; mensagem orientando compra na loja | Obrigatório |
| R5 | Funcionar em **qualquer mapa do cluster** (mesmo `steam_id`, mesmo DB) | Obrigatório |
| R6 | Comando que informa **quantidade de itens** no banco | Obrigatório |
| R7 | Política quando licença expira (ver decisões abaixo) | A definir |

---

## Arquitetura proposta

```
Jogador (chat)          CustomShop (C++)              MariaDB
    |                        |                          |
    |  /upload               |                          |
    |----------------------->|  GetItemBytes (cada item)  |
    |                        |------------------------->| INSERT player_cloud_*
    |                        |  RemoveItemFromInventory |
    |                        |                          |
    |  /download             |                          |
    |----------------------->|  SELECT blobs            |
    |                        |<-------------------------|
    |                        |  CreateFromBytes         |
    |                        |------------------------->| DELETE snapshot
```

**Por que C++ e não só Web Store:** o inventário só existe no processo do servidor ASE. A Ark API expõe `UPrimalItem::GetItemBytes` / `CreateFromBytes` para serialização fiel (mods, skins, durabilidade, conteúdo interno de itens).

**Conexão DB:** reutilizar `MYSQL*` de `ShopPoints::Open()` — mesmo padrão de `ShopEntitlements`.

---

## Modelo de dados

### Tabelas novas (migração em `ShopPoints::Open()` + `setup_db.sql`)

```sql
CREATE TABLE IF NOT EXISTS player_cloud_inventory (
  steam_id     VARCHAR(20) PRIMARY KEY NOT NULL,
  item_count   INT NOT NULL DEFAULT 0,
  uploaded_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  source_map   VARCHAR(128) DEFAULT NULL,
  INDEX idx_uploaded (uploaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS player_cloud_items (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  steam_id     VARCHAR(20) NOT NULL,
  sort_order   INT NOT NULL,
  item_blob    MEDIUMBLOB NOT NULL,
  INDEX idx_steam_order (steam_id, sort_order),
  CONSTRAINT fk_cloud_steam
    FOREIGN KEY (steam_id) REFERENCES player_cloud_inventory(steam_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- **Uma linha por jogador** em `player_cloud_inventory` — sem coluna de mapa na chave (cluster-wide).
- `source_map` é apenas informativo (de qual mapa veio o upload).
- `item_blob`: serialização binária via `GetItemBytes` (até 16 MB por item — `MEDIUMBLOB`).

### Auditoria (opcional — Fase 5)

Tabela `player_cloud_log` (`action`, `steam_id`, `map`, `item_count`, `ts`) para suporte e anti-abuso.

---

## Comandos de chat

| Comando | Ação | Licença necessária |
|---------|------|-------------------|
| `/upload` | Salva inventário → DB; esvazia jogador | Sim (upload) |
| `/download` | Restaura inventário ← DB; apaga snapshot | A definir (§ decisão 1) |
| `/nuvem` | Exibe: *"Você tem N itens na nuvem"* | Não |

**Aliases opcionais:** `/cloud`, `/vault` (mesmos handlers).

**Cooldown sugerido:** 30–60 s por jogador entre operações (anti-spam / carga no DB).

---

## Licença Nuvem

### Estado atual (`configs/config.json`)

```json
"licenca_nuvem": {
  "Commands": ["Permissions.AddTimed {SteamID} keyvault 720"]
}
```

- Grupo Ark Permissions: **`keyvault`** (720 h ≈ 30 dias).
- **Falta** `LicenseGrant` (Gamma/Beta/Alfa já têm) — proposta de alinhar:

```json
"LicenseGrant": {
  "Group": "keyvault",
  "Days": 30,
  "Redeemable": true
}
```

Verificação no plugin: `ShopEntitlements::HasActive(steam_id, "keyvault")`.

### Mensagens in-game (PT-BR)

| Situação | Texto proposto |
|----------|----------------|
| Sem licença | `Você precisa de uma Licença Nuvem ativa. Adquira na loja: {WebsiteUrl}` |
| Já tem itens salvos | `Você já possui itens na nuvem. Use /download para recuperá-los antes de um novo upload.` |
| Upload OK | `Nuvem: {N} itens salvos. Seu inventário foi esvaziado.` |
| Download OK | `Nuvem: {N} itens devolvidos ao seu inventário.` |
| Consulta | `Nuvem: você tem {N} itens armazenados.` |
| Inventário cheio | `Inventário sem espaço. Libere slots e use /download novamente.` |
| Inventário vazio no upload | `Seu inventário está vazio. Nada para enviar à nuvem.` |

---

## Escopo do inventário (v1)

| Incluir | Excluir (v1) |
|---------|----------------|
| Todos os itens em `InventoryItemsField()` do jogador | Inventário de dino montado |
| Itens equipados no mesmo componente | Cofres / estruturas |
| Stacks, mods, qualidade, skins (via bytes) | Tribute / transferência Ark |

---

## Módulo C++ proposto: `ShopCloudInventory`

**Arquivos:** `ShopCloudInventory.h`, `ShopCloudInventory.cpp`

**Integração:** `Commands.cpp`, `ShopPoints.cpp` (tabelas), `Plugin.cpp` (`SetDb`).

### Fluxo upload (resumo)

1. Validar licença + ausência de snapshot existente.
2. Iterar itens → `GetItemBytes` → gravar em transação MySQL.
3. Só após `COMMIT`: remover itens do inventário (sem drop no chão).
4. Em falha: `ROLLBACK` — inventário intacto.

### Fluxo download (resumo)

1. Carregar blobs ordenados por `sort_order`.
2. Validar espaço no inventário (slots/peso).
3. `CreateFromBytes` → adicionar ao inventário.
4. Só após sucesso total: deletar snapshot (CASCADE nos itens).
5. Falha parcial: **manter** banco; jogador tenta de novo.

---

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Falha no meio do upload | Perda de itens | Transação DB; limpar inventário só após COMMIT |
| Falha no meio do download | Itens duplicados ou perdidos | Não apagar snapshot até restore 100% |
| Mod removido do servidor | Item não restaura | Log + contagem de falhas; informar jogador |
| Snapshot muito grande | DB / lag | Limite configurável de itens (ex. 300–500) |
| Dois `/upload` simultâneos | Corrupção | PK em `steam_id` + tratar duplicate como recusa |
| Licença expira com itens na nuvem | Suporte / reclamação | Definir política (decisão 1) |

---

## Decisões em aberto — **discutir antes de codar**

Preencha ou escolha uma opção em cada linha. Implementação só inicia após aprovação.

| # | Tema | Opções | Recomendação |
|---|------|--------|--------------|
| **1** | Download com licença **expirada** | **A)** Exige licença ativa também no download · **B)** Permite download dos itens já pagos mesmo sem licença | **B** — melhor UX; jogador não perde o que já guardou |
| **2** | Nome do comando de status | `/nuvem` · `/cloud` · ambos | `/nuvem` (PT) + alias `/cloud` |
| **3** | Limite de itens por upload | Sem limite · 300 · 500 · outro: ___ | **300** itens (balanceamento DB) |
| **4** | Limite de tamanho total | Sem limite · 50 MB · outro: ___ | **50 MB** por snapshot |
| **5** | Cooldown entre comandos | 0 s · 30 s · 60 s | **30 s** |
| **6** | Grupo da licença | Manter `keyvault` · renomear para `Nuvem` | Manter **`keyvault`** (já em produção) |
| **7** | Admin: limpar cofre de jogador | RCON `Shop.CloudClear <steamid>` na v1? | Sim, na **Fase 5** (não bloqueia v1) |
| **8** | Painel web admin (listar cofres) | Sim na v1 · depois | **Depois** (Fase 5) |
| **9** | Preço / duração licença nuvem | Manter atual · alterar: ___ | Manter (revisar no `config.json`) |

### Perguntas adicionais para o dono do servidor

1. Jogador morto/desmaiado pode usar `/upload` e `/download`?
2. Em mapa com **prevent download** ou wipe, o cofre na nuvem deve continuar acessível?
3. Tribo / ally pode ver status da nuvem de outro jogador? (proposta: **não**)
4. Comunicar o sistema na loja web e em anúncio Discord antes do go-live?

---

## Fases de implementação (após aprovação)

| Fase | Entrega | Estimativa |
|------|---------|------------|
| **1 — Fundação** | Tabelas SQL, `ShopCloudInventory` (leitura/contagem), `LicenseGrant` | 1–2 dias |
| **2 — Upload** | Serialização, `/upload`, mensagens, testes in-game | 2–3 dias |
| **3 — Download** | Restauração cross-map, `/download` | 2–3 dias |
| **4 — Polimento** | `/nuvem`, cooldown, logs, `setup_db.sql`, `redeem_docs.js` | 1 dia |
| **5 — Opcional** | RCON admin, painel web, métricas | 1–2 dias |

**Total estimado:** 6–9 dias úteis (sem Fase 5).

---

## Critérios de aceite (go-live)

- [ ] Sem licença → `/upload` recusado com mensagem clara.
- [ ] Com licença → upload esvazia inventário; `/nuvem` mostra N correto.
- [ ] Segundo `/upload` bloqueado até download.
- [ ] Upload no mapa A + download no mapa B → mesmos itens.
- [ ] Após download, `/nuvem` = 0 e novo upload permitido.
- [ ] Nenhum item dropado no chão no upload.
- [ ] Plugin inicia sem erro com tabelas novas em DB existente.

---

## Checklist de aprovação

Marque quando estiver de acordo para iniciar a implementação:

- [ ] Requisitos R1–R6 confirmados
- [ ] Decisão **#1** (licença no download) fechada
- [ ] Decisões **#2–#6** fechadas ou aceitas recomendações
- [ ] Escopo v1 (o que entra / não entra no inventário) aceito
- [ ] Mensagens PT-BR revisadas
- [ ] `LicenseGrant` em `licenca_nuvem` aprovado
- [ ] Janela de testes em servidor de homologação definida

**Aprovado por:** _________________ **Data:** _________

---

## Referências no repositório

| Tópico | Caminho |
|--------|---------|
| Comandos chat | `plugin/CustomShop/src/Commands.cpp` |
| Entitlements / licenças | `plugin/CustomShop/src/ShopEntitlements.cpp` |
| Permissões runtime (`keyvault`) | `plugin/CustomShop/src/ShopPerms.h` |
| Entrega de itens | `plugin/CustomShop/src/ShopStore.cpp` |
| API `GetItemBytes` / `CreateFromBytes` | `plugin/CustomShop/ArkServerAPI/.../ARK/Inventory.h` |
| Licença nuvem (catálogo) | `plugin/CustomShop/configs/config.json` → `licenca_nuvem` |
| Migração DB | `plugin/CustomShop/src/ShopPoints.cpp`, `setup_db.sql` |
| Plano técnico detalhado (complementar) | `docs/PLANO_INVENTARIO_NUVEM.md` |

---

## Histórico do documento

| Versão | Data | Alteração |
|--------|------|-----------|
| 1.0 | 2026-06-18 | Documento inicial para discussão pré-implementação |
