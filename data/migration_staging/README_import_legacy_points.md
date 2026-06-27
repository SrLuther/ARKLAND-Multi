# Import aditivo de pontos legacy → `arkland_shop.players`

Ferramenta: **`tools/import_legacy_points_additive.py`**

Somente **incrementa** pontos de jogadores que **já existem** na tabela `players` (CustomShop). Não cria linhas novas.

## CSV de entrada

Colunas esperadas (case-insensitive):

| Coluna   | Obrigatória | Exemplo |
|----------|-------------|---------|
| steam_id | sim         | `76561198000000001` |
| points   | sim         | `38320` |
| groups   | não         | `VIPBronze` (lido, não aplicado ao DB ainda) |

Arquivo padrão no servidor:

`plugin/CustomShop/configs/jogadores_pontos_grupos.csv`

**Duplicatas:** se o mesmo `steam_id` aparecer mais de uma vez, os valores de `points` são **somados** antes do UPDATE.

**Valores altos:** deltas ≥ 10M geram aviso. Use `--max-points` para ignorar ou `--cap-over-max` para limitar.

## Banco de destino

- Database: `arkland_shop`
- Tabela: `players` (`steam_id`, `points`)
- `store_users` **não** guarda saldo de pontos do CustomShop

SQL aplicado:

```sql
UPDATE players SET points = points + :delta WHERE steam_id = :sid;
```

## Conexão (ordem)

1. `--database-url` ou `--host` / `--user` / `--password`
2. Variável `ARKSHOP_DATABASE_URL`
3. `plugin/arkshop_web/settings.json`
4. `%APPDATA%\ARKLAND-ServerManager\db_server_prefs.json` → `shop_db`

No **ArkServerII** (TEK), MySQL local:

- Host: `127.0.0.1`
- User: `arkland`
- Database: `arkland_shop`

## Como rodar no ArkServerII

```powershell
cd C:\caminho\para\arkland-multi

# Simulação (recomendado primeiro)
python tools\import_legacy_points_additive.py ^
  --csv plugin\CustomShop\configs\jogadores_pontos_grupos.csv ^
  --dry-run ^
  --host 127.0.0.1 --user arkland --password "SUA_SENHA" --database arkland_shop

# Aplicar de verdade
python tools\import_legacy_points_additive.py ^
  --csv plugin\CustomShop\configs\jogadores_pontos_grupos.csv ^
  --host 127.0.0.1 --user arkland --password "SUA_SENHA" --database arkland_shop

# Ignorar deltas acima de 5M (ex.: admin 908M)
python tools\import_legacy_points_additive.py --dry-run --max-points 5000000 ...
```

Via env (sem senha na linha de comando):

```powershell
$env:ARKSHOP_DATABASE_URL = "mysql+pymysql://arkland:SENHA@127.0.0.1:3306/arkland_shop"
python tools\import_legacy_points_additive.py --dry-run
```

## Segurança / git

O CSV com dados reais de jogadores **não deve** ir para o repositório. Está listado no `.gitignore`:

`plugin/CustomShop/configs/jogadores_pontos_grupos.csv`

## Export inverso (referência)

Para extrair pontos do MySQL antes de migrar:

`tools/export_player_points_mysql.py`
