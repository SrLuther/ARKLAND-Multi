# Player points migration staging

## Fonte autoritativa

Use **`tools/export_player_points_mysql.py`** — export READ-ONLY de MySQL/MariaDB.

## NÃO usar para migração

- `player_points_legacy_ibd_heuristic.csv.bak` — export heurístico de `.ibd`
  (`tools/export_legacy_points.py`). Valores uniformes (~263–766) são **incorretos**.

## Status

Nenhum export SQL bem-sucedido nesta execução. Conecte à LAN (192.168.15.51) ou use `--import-ibd` com MariaDB local.
