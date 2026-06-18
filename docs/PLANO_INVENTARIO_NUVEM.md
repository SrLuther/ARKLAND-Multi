# Plano: Inventário na Nuvem (`/upload`, `/download`)

**Versão do plano:** 1.0  
**Data:** 2026-06-18  
**Escopo:** Plugin CustomShop (C++) + banco MySQL/MariaDB compartilhado do cluster  
**Release base:** v1.9.34  
**Documento para discussão:** [`PROJETO_INVENTARIO_NUVEM.md`](./PROJETO_INVENTARIO_NUVEM.md) — ler e aprovar antes de implementar.

---

## 1. Objetivo

Permitir que jogadores com **licença de nuvem ativa** salvem todo o inventário em banco de dados via `/upload` (inventário fica vazio) e recuperem os itens em **qualquer mapa do cluster** via `/download`. Um comando adicional informa quantos itens estão armazenados.

---

## 2. Requisitos funcionais

| ID | Requisito |
|----|-----------|
| R1 | `/upload` serializa **todos os itens** do inventário do jogador, grava no banco e esvazia o inventário |
| R2 | `/download` restaura os itens do banco para o inventário do jogador |
| R3 | Se já existir snapshot do jogador no banco, **novo `/upload` é recusado** (sem sobrescrever) |
| R4 | `/upload` exige licença de nuvem ativa; sem licença → mensagem clara orientando a adquirir |
| R5 | Dados são **cluster-wide** (mesmo `steam_id` em qualquer mapa do cluster) |
| R6 | Comando de consulta informa **quantidade de itens** armazenados (ex.: `/nuvem` ou `/cloud`) |
| R7 | Licença expirada: bloquear **novo upload**; definir política para download (ver §6) |

---

## 3. Arquitetura

```
┌─────────────────┐     chat commands      ┌──────────────────────┐
│  Jogador (ASE)  │ ── /upload /download ─▶│  CustomShop plugin   │
└─────────────────┘                        │  ShopCloudInventory  │
                                             └──────────┬───────────┘
                                                        │
                        GetItemBytes / CreateFromBytes  │
                        UPrimalInventoryComponent       │
                                                        ▼
                                             ┌──────────────────────┐
                                             │  MySQL/MariaDB        │
                                             │  (arkland_shop)       │
                                             │  player_cloud_*       │
                                             └──────────────────────┘
        ◀── mesmo DB em todos os mapas do cluster ──▶
```

**Por que no plugin C++ (e não só Web Store):** o inventário só existe no processo do servidor ASE; a API Ark já expõe `UPrimalItem::GetItemBytes` / `CreateFromBytes` para serialização fiel (mods, qualidade, durabilidade, carga, etc.).

**Conexão DB:** reutilizar o `MYSQL*` já aberto em `ShopPoints::Open()` — mesmo padrão de `ShopEntitlements`.

---

## 4. Modelo de dados

### 4.1 Tabelas (migração em `ShopPoints::Open()`)

```sql
-- Cabeçalho: um snapshot por jogador (cluster-wide)
CREATE TABLE IF NOT EXISTS player_cloud_inventory (
  steam_id     VARCHAR(20) PRIMARY KEY NOT NULL,
  item_count   INT NOT NULL DEFAULT 0,
  uploaded_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  source_map   VARCHAR(128) DEFAULT NULL,   -- informativo (mapa do upload)
  INDEX idx_uploaded (uploaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Itens serializados (ordem preservada)
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

**Chave única:** apenas `steam_id` — sem `map_name`, garantindo um cofre por jogador no cluster.

**Tamanho:** `MEDIUMBLOB` (16 MB por item) é suficiente para stacks complexos; monitorar tamanho médio em produção.

### 4.2 Auditoria (opcional, fase 2)

Tabela `player_cloud_log` com `action` (`upload`/`download`/`reject`), `steam_id`, `map`, `item_count`, `ts` — útil para suporte e anti-abuso.

---

## 5. Módulo C++: `ShopCloudInventory`

**Arquivos novos:**
- `plugin/CustomShop/src/ShopCloudInventory.h`
- `plugin/CustomShop/src/ShopCloudInventory.cpp`

**API proposta:**

```cpp
namespace CustomShop::CloudInventory {

void SetDb(MYSQL* db);

bool HasStoredItems(const std::string& steam_id);
int  GetStoredItemCount(const std::string& steam_id);

enum class CloudResult {
    Ok,
    NoLicense,
    AlreadyStored,
    EmptyInventory,
    DbError,
    InventoryFull,
    PartialRestore,
    NothingStored,
};

CloudResult Upload(AShooterPlayerController* controller);
CloudResult Download(AShooterPlayerController* controller);

} // namespace
```

### 5.1 Upload — algoritmo

1. Resolver `steam_id` via `Bridge::GetSteamId`.
2. `ShopEntitlements::HasActive(steam_id, kCloudLicenseGroup)` → se falso, retornar `NoLicense`.
3. `HasStoredItems(steam_id)` → se verdadeiro, retornar `AlreadyStored`.
4. Obter `UPrimalInventoryComponent*` (`controller->GetPlayerInventoryComponent()`).
5. Copiar ponteiros de `inv->InventoryItemsField()` para vetor local (evitar mutação durante iteração).
6. Se vazio → `EmptyInventory`.
7. **Transação MySQL** (`START TRANSACTION`):
   - `INSERT` em `player_cloud_inventory` (`source_map` = nome do mapa atual via API Utils).
   - Para cada item, na ordem: `GetItemBytes` → `INSERT` em `player_cloud_items`.
8. Se todos os blobs gravados: remover cada item do inventário com `RemoveItemFromInventory(true, false)` (sem drop no chão).
9. `COMMIT` ou `ROLLBACK` se qualquer passo falhar.
10. Mensagem ao jogador com total de itens salvos.

### 5.2 Download — algoritmo

1. Se `!HasStoredItems` → `NothingStored`.
2. *(Recomendado)* Verificar licença ativa — evita uso eterno após expirar; ver §6.
3. Carregar blobs ordenados por `sort_order`.
4. Verificar slots/peso disponíveis (estimativa: `item_count` vs slots livres); se insuficiente → `InventoryFull` **sem** apagar o banco.
5. Para cada blob: `UPrimalItem::CreateFromBytes` → adicionar ao inventário (`AddNewItem` ou API equivalente para item já instanciado).
6. Se **todos** restaurados com sucesso: `DELETE FROM player_cloud_inventory WHERE steam_id = ?` (CASCADE remove itens).
7. Se falha parcial: **não** apagar banco; logar erro e informar jogador para tentar novamente com espaço livre.

### 5.3 Serialização

Usar API já presente em `ArkServerAPI/.../ARK/Inventory.h`:

- `UPrimalItem::GetItemBytes(TArray<unsigned char>*)`
- `UPrimalItem::CreateFromBytes(TArray<unsigned char>*)`

Isso preserva propriedades que blueprint + quantidade não capturam (mods, skins, stats, conteúdo de containers aninhados quando aplicável).

### 5.4 Escopo do inventário

**Incluir:** todos os itens em `InventoryItemsField()` do inventário do jogador (inclui equipados no mesmo componente).

**Excluir (v1):** inventário de dinos montados, cofres, tribute upload, mãos de outro jogador.

Documentar essa decisão nas mensagens in-game se necessário.

---

## 6. Licença de nuvem

### Estado atual (`config.json`)

```json
"licenca_nuvem": {
  "Commands": ["Permissions.AddTimed {SteamID} keyvault 720"]
}
```

Grupo Ark Permissions: **`keyvault`** (720 h ≈ 30 dias).  
**Não** há `LicenseGrant` — diferente de Gamma/Beta/Alfa.

### Alinhamento proposto

1. Adicionar `LicenseGrant` em `licenca_nuvem`:

```json
"LicenseGrant": {
  "Group": "keyvault",
  "Days": 30,
  "Redeemable": true
}
```

2. Constante no plugin:

```cpp
constexpr const char* kCloudLicenseGroup = "keyvault";
```

3. Verificação: `ShopEntitlements::HasActive(steam_id, kCloudLicenseGroup)` — cobre Permissions online **e** `player_entitlements` após resgate na loja.

### Mensagens (PT-BR)

| Situação | Mensagem sugerida |
|----------|-------------------|
| Sem licença no `/upload` | `Você precisa de uma Licença Nuvem ativa para enviar itens. Adquira na loja: {WebsiteUrl}` |
| Já tem itens na nuvem | `Você já possui itens na nuvem. Use /download para recuperá-los antes de um novo upload.` |
| Upload OK | `Nuvem: {N} itens salvos. Seu inventário foi esvaziado.` |
| Download OK | `Nuvem: {N} itens devolvidos ao seu inventário.` |
| Consulta | `Nuvem: você tem {N} itens armazenados.` |
| Inventário cheio | `Inventário sem espaço suficiente. Libere slots e tente /download novamente.` |

### Política de licença no download

| Opção | Comportamento |
|-------|----------------|
| **A (recomendada)** | Download também exige licença ativa — cofre some se não renovar |
| **B** | Download liberado mesmo com licença expirada (dados já pagos) |

**Decisão pendente com o dono do servidor** — implementar via flag em `Settings` do `config.json`: `"CloudRequireLicenseForDownload": true`.

---

## 7. Comandos de chat

Registrar em `Commands.cpp` (padrão `AddChatCommand`):

| Comando | Handler | Descrição |
|---------|---------|-----------|
| `/upload` | `CmdCloudUpload` | Salva inventário na nuvem |
| `/download` | `CmdCloudDownload` | Restaura inventário |
| `/nuvem` | `CmdCloudStatus` | Mostra quantidade de itens no banco |

Alternativas de alias: `/cloud`, `/vault` — podem ser registrados como comandos extras apontando para os mesmos handlers.

**Cooldown (recomendado):** 30–60 s por jogador para evitar spam/DB — seguir padrão de rate limit se já existir no plugin.

---

## 8. Integração com código existente

| Arquivo | Alteração |
|---------|-----------|
| `ShopPoints.cpp` | Criar tabelas `player_cloud_*` no `Open()` |
| `ShopEntitlements.cpp` | Sem mudança obrigatória se usar grupo `keyvault` |
| `Commands.cpp` | Novos handlers + registro em `RegisterCommands` / `UnregisterCommands` |
| `Plugin.cpp` (ou init) | `CloudInventory::SetDb(ShopPoints::Get().DbHandle())` |
| `configs/config.json` | `LicenseGrant` em `licenca_nuvem`; opcional `CloudInventory` em `Settings` |
| `setup_db.sql` | Script manual espelhando migração (para admins) |
| `redeem_docs.js` | Doc automática da licença nuvem (já categoria Licenças) |

**CMake / vcxproj:** incluir `ShopCloudInventory.cpp` no build do CustomShop.

---

## 9. Casos de borda e riscos

| Risco | Mitigação |
|-------|-----------|
| Falha no meio do upload | Transação DB; só limpar inventário após COMMIT |
| Falha no meio do download | Não deletar snapshot; jogador tenta de novo |
| Item corrompido / mod removido | Log + pular item; informar quantos falharam |
| Jogador desconecta durante operação | Operação síncrona curta; timeout por item |
| Duplo `/upload` simultâneo | `INSERT` PK em `player_cloud_inventory` falha → tratar como `AlreadyStored` |
| Peso/slots | Pré-validar `item_count` vs capacidade |
| Tamanho total do snapshot | Limite configurável (ex. 500 itens ou 50 MB) |
| Admin quer limpar cofre | Comando RCON futuro: `Shop.CloudClear <steamid>` |

---

## 10. Fases de implementação

### Fase 1 — Fundação (1–2 dias)
- [ ] Migração SQL em `ShopPoints::Open()`
- [ ] `ShopCloudInventory` — `HasStoredItems`, `GetStoredItemCount`
- [ ] `LicenseGrant` em `licenca_nuvem`
- [ ] Testes unitários leves (mock DB) se viável; senão teste manual

### Fase 2 — Upload (2–3 dias)
- [ ] Serialização `GetItemBytes` + persistência
- [ ] Limpeza do inventário pós-commit
- [ ] `/upload` + mensagens PT-BR
- [ ] Teste in-game: item vanilla, stack, item mod, equipado

### Fase 3 — Download (2–3 dias)
- [ ] `CreateFromBytes` + restauração
- [ ] Validação de espaço
- [ ] `/download` + delete snapshot
- [ ] Teste cross-map: upload no Mapa A, download no Mapa B

### Fase 4 — Polimento (1 dia)
- [ ] `/nuvem` (status)
- [ ] Cooldown + logging
- [ ] `setup_db.sql` + entrada no CHANGELOG
- [ ] Atualizar `redeem_docs.js` com texto da licença nuvem (comandos `/upload`, `/download`)

### Fase 5 — Opcional
- [ ] RCON `Shop.CloudClear` / `Shop.CloudInfo` para admins
- [ ] Painel Web Store: visualizar cofres ativos (somente admin)
- [ ] Métricas: total de snapshots, tamanho médio

---

## 11. Critérios de aceite

1. Jogador **sem** licença recebe mensagem clara ao usar `/upload`.
2. Jogador **com** licença faz upload; inventário fica vazio; `/nuvem` mostra contagem correta.
3. Segundo `/upload` é **bloqueado** enquanto houver dados no banco.
4. `/download` em **outro mapa** do mesmo cluster devolve os mesmos itens.
5. Após download bem-sucedido, `/nuvem` retorna 0 e novo `/upload` é permitido.
6. Nenhum item é dropado no chão durante upload.

---

## 12. Decisões em aberto

1. **Download com licença expirada** — opção A ou B (§6).
2. **Nome do comando de status** — `/nuvem` vs `/cloud` vs ambos.
3. **Limite máximo** de itens por snapshot.
4. **Incluir ou não** itens na hotbar separadamente (se API expuser outro componente).

---

## 13. Referências no repositório

- Comandos chat: `plugin/CustomShop/src/Commands.cpp`
- Entitlements: `plugin/CustomShop/src/ShopEntitlements.cpp`
- Permissões runtime: `plugin/CustomShop/src/ShopPerms.h`
- Inventário / entrega: `plugin/CustomShop/src/ShopStore.cpp`
- API serialização: `plugin/CustomShop/ArkServerAPI/.../ARK/Inventory.h` (linhas `GetItemBytes`, `CreateFromBytes`, `InventoryItemsField`)
- Licença nuvem: `plugin/CustomShop/configs/config.json` → `licenca_nuvem`
- DB compartilhado: `plugin/CustomShop/src/ShopPoints.cpp`
