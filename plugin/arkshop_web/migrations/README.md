# Migrations — arkshop_web

## Fazenda no MySQL

Arquivo: `fazenda_mysql.sql`

Cria as tabelas dedicadas para configuração mestre do site, catálogo efetivo, uploads, produção, estoque, pedidos, stacks e alocações de entrega. Plugin e Web Store usam as mesmas tabelas no mesmo MySQL. Nenhuma tabela `player_cloud_*` é compartilhada com a Fazenda. O backend também cria tabelas mapeadas via SQLAlchemy no startup; esta migração provisiona as colunas adicionais necessárias ao fluxo real.

```bash
mysql -u USER -p arkland_shop < plugin/arkshop_web/migrations/fazenda_mysql.sql
```

O plugin liga ao MySQL com as credenciais do bloco `Database` do `CustomShop/config.json`, no mesmo padrão da Nuvem. A Web Store consulta e grava essas mesmas tabelas via seu backend; credenciais nunca são enviadas ao navegador.

## ItensAlfa licenses (Delta → Exótico)

Arquivo: `itensalfa_licenses.sql`

### O que faz
- Garante `player_entitlements`
- Cria/atualiza `license_tier_catalog` com preços 6k–230k e bônus TimedPoints
- Idempotente (`ON DUPLICATE KEY UPDATE`)

### Como aplicar

```bash
# Opção A — SQL
mysql -u USER -p arkland_shop < plugin/arkshop_web/migrations/itensalfa_licenses.sql

# Opção B — Python (também imprime Permissions.AddGroup)
set ARKSHOP_DATABASE_URL=mysql+pymysql://USER:PASS@127.0.0.1:3306/arkland_shop
python tools/migrate_itensalfa_licenses.py
```

### Depois do SQL
1. Provisionar grupos Permissions (RCON ou UI Loja → Provisionar grupos):
   `Delta`, `Gamma`, `Beta`, `Alfa`, `Omega`, `Transcendente`, `Etereo`, `Universal`, `Onipotente`, `Surreal`, `Imaterial`, `Exotico`
2. Sync TEK / `Shop.Reload` nos mapas
3. Recompilar `CustomShop.dll` se o binário em produção ainda tiver só Gamma/Beta/Alfa hardcoded

### Catálogo shop
```bash
python tools/apply_itensalfa_licenses.py
```
