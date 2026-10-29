-- Migração idempotente do inventário em nuvem para slots 0..3.
-- Faça backup do banco e mantenha o CustomShop parado durante a execução.
USE arkland_shop;

-- Diagnóstico inicial: confirme dados, índices e relacionamentos.
SHOW CREATE TABLE player_cloud_inventory;
SHOW CREATE TABLE player_cloud_items;
SELECT steam_id, COUNT(*) AS linhas
FROM player_cloud_inventory
GROUP BY steam_id
HAVING COUNT(*) > 1;

-- Adiciona partição da nuvem. Registros antigos permanecem no grupo default.
SET @cloud_group_exists := (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'player_cloud_inventory'
      AND column_name = 'cloud_group'
);
SET @cloud_sql := IF(@cloud_group_exists = 0,
    'ALTER TABLE player_cloud_inventory ADD COLUMN cloud_group VARCHAR(64) NOT NULL DEFAULT ''default''',
    'SELECT ''player_cloud_inventory.cloud_group ja existe'' AS resultado');
PREPARE cloud_stmt FROM @cloud_sql; EXECUTE cloud_stmt; DEALLOCATE PREPARE cloud_stmt;
SET @cloud_group_exists := (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'player_cloud_items'
      AND column_name = 'cloud_group'
);
SET @cloud_sql := IF(@cloud_group_exists = 0,
    'ALTER TABLE player_cloud_items ADD COLUMN cloud_group VARCHAR(64) NOT NULL DEFAULT ''default''',
    'SELECT ''player_cloud_items.cloud_group ja existe'' AS resultado');
PREPARE cloud_stmt FROM @cloud_sql; EXECUTE cloud_stmt; DEALLOCATE PREPARE cloud_stmt;

-- Garante a coluna slot antes de criar a chave composta.
SET @cloud_slot_exists := (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'player_cloud_inventory'
      AND column_name = 'slot'
);
SET @cloud_sql := IF(
    @cloud_slot_exists = 0,
    'ALTER TABLE player_cloud_inventory ADD COLUMN slot TINYINT NOT NULL DEFAULT 0',
    'SELECT ''player_cloud_inventory.slot ja existe'' AS resultado'
);
PREPARE cloud_stmt FROM @cloud_sql;
EXECUTE cloud_stmt;
DEALLOCATE PREPARE cloud_stmt;

SET @cloud_slot_exists := (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'player_cloud_items'
      AND column_name = 'slot'
);
SET @cloud_sql := IF(
    @cloud_slot_exists = 0,
    'ALTER TABLE player_cloud_items ADD COLUMN slot TINYINT NOT NULL DEFAULT 0',
    'SELECT ''player_cloud_items.slot ja existe'' AS resultado'
);
PREPARE cloud_stmt FROM @cloud_sql;
EXECUTE cloud_stmt;
DEALLOCATE PREPARE cloud_stmt;

-- Remove todas as FKs antigas do relacionamento entre as duas tabelas antes
-- da troca da PK. Isso evita errno 1025, qualquer que seja o nome da constraint.
SET SESSION group_concat_max_len = 65535;
SET @cloud_fk_drops := (
    SELECT GROUP_CONCAT(
        CONCAT('DROP FOREIGN KEY `', REPLACE(constraint_name, '`', '``'), '`')
        ORDER BY constraint_name SEPARATOR ', '
    )
    FROM (
        SELECT DISTINCT constraint_name
        FROM information_schema.key_column_usage
        WHERE constraint_schema = DATABASE()
          AND table_name = 'player_cloud_items'
          AND referenced_table_name = 'player_cloud_inventory'
    ) AS legacy_cloud_fks
);
SET @cloud_sql := IF(
    @cloud_fk_drops IS NULL,
    'SELECT ''nenhuma FK antiga encontrada'' AS resultado',
    CONCAT('ALTER TABLE player_cloud_items ', @cloud_fk_drops)
);
PREPARE cloud_stmt FROM @cloud_sql;
EXECUTE cloud_stmt;
DEALLOCATE PREPARE cloud_stmt;

-- Remove índices únicos legados de steam_id isolado, mantendo índices
-- compostos e o índice primário quando já está no formato correto.
SET @cloud_unique_drops := (
    SELECT GROUP_CONCAT(
        CONCAT('DROP INDEX `', REPLACE(index_name, '`', '``'), '`')
        ORDER BY index_name SEPARATOR ', '
    )
    FROM (
        SELECT index_name
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'player_cloud_inventory'
          AND non_unique = 0
          AND index_name <> 'PRIMARY'
        GROUP BY index_name
        HAVING GROUP_CONCAT(column_name ORDER BY seq_in_index SEPARATOR ',') <> 'cloud_group,steam_id,slot'
    ) AS legacy_unique_indexes
);
SET @cloud_sql := IF(
    @cloud_unique_drops IS NULL,
    'SELECT ''nenhum indice unico legado'' AS resultado',
    CONCAT('ALTER TABLE player_cloud_inventory ', @cloud_unique_drops)
);
PREPARE cloud_stmt FROM @cloud_sql;
EXECUTE cloud_stmt;
DEALLOCATE PREPARE cloud_stmt;

-- Troca a PK apenas quando ela nao for exatamente (cloud_group, steam_id, slot).
SET @cloud_pk := (
    SELECT GROUP_CONCAT(column_name ORDER BY seq_in_index SEPARATOR ',')
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'player_cloud_inventory'
      AND index_name = 'PRIMARY'
);
SET @cloud_sql := IF(
    @cloud_pk <=> 'cloud_group,steam_id,slot',
    'SELECT ''PK ja esta em (cloud_group, steam_id, slot)'' AS resultado',
    IF(
        @cloud_pk IS NULL,
        'ALTER TABLE player_cloud_inventory ADD PRIMARY KEY (cloud_group, steam_id, slot)',
        'ALTER TABLE player_cloud_inventory DROP PRIMARY KEY, ADD PRIMARY KEY (cloud_group, steam_id, slot)'
    )
);
PREPARE cloud_stmt FROM @cloud_sql;
EXECUTE cloud_stmt;
DEALLOCATE PREPARE cloud_stmt;

-- Garante índice de leitura dos blobs sem duplicar índices existentes.
SET @cloud_idx_exists := (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'player_cloud_items'
      AND index_name = 'idx_cloud_group_steam_slot_order'
);
SET @cloud_sql := IF(
    @cloud_idx_exists = 0,
    'CREATE INDEX idx_cloud_group_steam_slot_order ON player_cloud_items (cloud_group, steam_id, slot, sort_order)',
    'SELECT ''idx_cloud_group_steam_slot_order ja existe'' AS resultado'
);
PREPARE cloud_stmt FROM @cloud_sql;
EXECUTE cloud_stmt;
DEALLOCATE PREPARE cloud_stmt;

-- Recria cabecalhos ausentes sem apagar blobs que ainda podem ser restaurados.
INSERT IGNORE INTO player_cloud_inventory (cloud_group, steam_id, slot, item_count, source_map)
SELECT b.cloud_group, b.steam_id, b.slot, COUNT(*), NULL
FROM player_cloud_items b
LEFT JOIN player_cloud_inventory h
  ON h.cloud_group = b.cloud_group AND h.steam_id = b.steam_id AND h.slot = b.slot
WHERE h.steam_id IS NULL
GROUP BY b.cloud_group, b.steam_id, b.slot;

-- Recria uma única FK composta com cascade após a PK estar alinhada.
SET @cloud_fk := (
    SELECT GROUP_CONCAT(column_name ORDER BY ordinal_position SEPARATOR ',')
    FROM information_schema.key_column_usage
    WHERE constraint_schema = DATABASE()
      AND table_name = 'player_cloud_items'
      AND referenced_table_name = 'player_cloud_inventory'
      AND constraint_name = 'fk_cloud_group_steam_slot'
);
SET @cloud_sql := IF(
    @cloud_fk <=> 'cloud_group,steam_id,slot',
    'SELECT ''FK composta ja existe'' AS resultado',
    'ALTER TABLE player_cloud_items ADD CONSTRAINT fk_cloud_group_steam_slot FOREIGN KEY (cloud_group, steam_id, slot) REFERENCES player_cloud_inventory (cloud_group, steam_id, slot) ON DELETE CASCADE'
);
PREPARE cloud_stmt FROM @cloud_sql;
EXECUTE cloud_stmt;
DEALLOCATE PREPARE cloud_stmt;

-- Validação final: a consulta de duplicados deve retornar zero linhas.
SHOW INDEX FROM player_cloud_inventory;
SHOW CREATE TABLE player_cloud_items;
SELECT cloud_group, steam_id, slot, COUNT(*) AS linhas
FROM player_cloud_inventory
GROUP BY cloud_group, steam_id, slot
HAVING COUNT(*) > 1;
