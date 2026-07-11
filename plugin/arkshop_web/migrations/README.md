# Migrations — arkshop_web

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
