-- Corrige o esquema do inventario na nuvem para suportar slots 0..3.
-- Execute no MariaDB com o plugin CustomShop parado ou sem jogadores usando /upload e /download.
USE arkland_shop;

-- Confira os nomes da FK e os slots antes de alterar.
SHOW CREATE TABLE player_cloud_inventory;
SHOW CREATE TABLE player_cloud_items;

-- Remove qualquer FK antiga que referencie player_cloud_inventory.
-- Isso evita o erro 1025 ao substituir a chave primaria antiga.
SET @cloud_fk := (
    SELECT CONSTRAINT_NAME
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'player_cloud_items'
      AND REFERENCED_TABLE_NAME = 'player_cloud_inventory'
    LIMIT 1
);
SET @cloud_fk_sql := IF(
    @cloud_fk IS NULL,
    'SELECT ''Nenhuma FK antiga encontrada'' AS resultado',
    CONCAT(
        'ALTER TABLE `player_cloud_items` DROP FOREIGN KEY `',
        REPLACE(@cloud_fk, '`', '``'),
        '`'
    )
);
PREPARE cloud_fk_stmt FROM @cloud_fk_sql;
EXECUTE cloud_fk_stmt;
DEALLOCATE PREPARE cloud_fk_stmt;

-- Troca a PK de steam_id para (steam_id, slot), preservando as linhas existentes.
ALTER TABLE player_cloud_inventory
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (steam_id, slot);

-- Garante o indice composto dos blobs; evita erro se ja existir.
SET @cloud_idx_exists := (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'player_cloud_items'
      AND INDEX_NAME = 'idx_steam_slot_order'
);
SET @cloud_idx_sql := IF(
    @cloud_idx_exists = 0,
    'CREATE INDEX `idx_steam_slot_order` ON `player_cloud_items` (`steam_id`, `slot`, `sort_order`)',
    'SELECT ''Indice composto ja existe'' AS resultado'
);
PREPARE cloud_idx_stmt FROM @cloud_idx_sql;
EXECUTE cloud_idx_stmt;
DEALLOCATE PREPARE cloud_idx_stmt;

-- Recria a FK com a chave composta. ON DELETE CASCADE mantem a limpeza dos blobs.
ALTER TABLE player_cloud_items
    ADD CONSTRAINT fk_cloud_steam_slot
    FOREIGN KEY (steam_id, slot)
    REFERENCES player_cloud_inventory (steam_id, slot)
    ON DELETE CASCADE;

-- Validacao final: PK, FK e slots existentes.
SHOW INDEX FROM player_cloud_inventory;
SHOW CREATE TABLE player_cloud_items;
SELECT steam_id, slot, COUNT(*) AS linhas
FROM player_cloud_inventory
GROUP BY steam_id, slot
HAVING COUNT(*) > 1;
