-- Fazenda de Recursos: esquema dedicado, compartilhado por plugin e Web Store.
-- Não lê nem altera player_cloud_inventory / player_cloud_items.
-- Executar no mesmo database configurado no CustomShop e no arkshop_web.

CREATE TABLE IF NOT EXISTS farm_player_states (
  steam_id VARCHAR(32) NOT NULL PRIMARY KEY,
  stock_json LONGTEXT NOT NULL,
  server_id VARCHAR(64) NOT NULL DEFAULT 'default',
  plugin_version VARCHAR(32) NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS farm_resource_catalog (
  server_id VARCHAR(64) NOT NULL,
  resource_id VARCHAR(100) NOT NULL,
  share_key VARCHAR(64) NOT NULL DEFAULT 'default',
  category VARCHAR(40) NOT NULL DEFAULT 'default',
  resource_name VARCHAR(160) NOT NULL,
  item_class VARCHAR(255) NOT NULL DEFAULT '',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  output_quantity INT NOT NULL DEFAULT 1,
  interval_seconds INT NOT NULL DEFAULT 3600,
  stack_size INT NOT NULL DEFAULT 25,
  capacity INT NOT NULL DEFAULT 200,
  config_revision VARCHAR(64) NOT NULL DEFAULT '',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (server_id, resource_id),
  INDEX idx_farm_catalog_enabled (enabled, server_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Configuração mestre editada na Web Store e espelhada no config.json do servidor.
CREATE TABLE IF NOT EXISTS farm_share_configs (
  share_key VARCHAR(64) NOT NULL PRIMARY KEY,
  config_json LONGTEXT NOT NULL,
  revision VARCHAR(64) NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_farm_config_revision (revision)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Configuração mestre independente por servidor. FarmShareKey permanece dentro
-- do JSON para que servidores possam compartilhar (ou separar) o estoque.
CREATE TABLE IF NOT EXISTS farm_server_configs (
  server_id VARCHAR(64) NOT NULL PRIMARY KEY,
  share_key VARCHAR(64) NOT NULL DEFAULT 'default',
  config_json LONGTEXT NOT NULL,
  revision VARCHAR(64) NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_farm_server_config_share (share_key),
  INDEX idx_farm_server_config_revision (revision)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS farm_player_resources (
  share_key VARCHAR(64) NOT NULL DEFAULT 'default',
  steam_id VARCHAR(32) NOT NULL,
  resource_id VARCHAR(100) NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT FALSE,
  last_accrual_utc BIGINT NOT NULL DEFAULT 0,
  server_id VARCHAR(64) NOT NULL DEFAULT 'default',
  plugin_version VARCHAR(32) NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (share_key, steam_id, resource_id),
  INDEX idx_farm_resource_updated (resource_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS farm_uploaded_resources (
  share_key VARCHAR(64) NOT NULL DEFAULT 'default',
  steam_id VARCHAR(32) NOT NULL,
  upload_id VARCHAR(180) NOT NULL,
  resource_id VARCHAR(100) NOT NULL,
  resource_name VARCHAR(160) NOT NULL,
  item_class VARCHAR(255) NOT NULL DEFAULT '',
  display_name VARCHAR(160) NOT NULL DEFAULT '',
  item_quantity INT NOT NULL DEFAULT 1,
  blob_size INT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  server_id VARCHAR(64) NOT NULL DEFAULT 'default',
  uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  item_blob LONGBLOB NOT NULL,
  PRIMARY KEY (share_key, steam_id, upload_id),
  INDEX idx_farm_upload_resource (steam_id, resource_id, status),
  INDEX idx_farm_upload_time (steam_id, uploaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS farm_produced_items (
  id VARCHAR(180) NOT NULL PRIMARY KEY,
  share_key VARCHAR(64) NOT NULL DEFAULT 'default',
  steam_id VARCHAR(32) NOT NULL,
  resource_id VARCHAR(100) NOT NULL,
  cycle_id VARCHAR(180) NOT NULL,
  stack_index INT NOT NULL DEFAULT 0,
  quantity INT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE',
  redemption_id VARCHAR(36) NULL,
  item_blob LONGBLOB NOT NULL,
  produced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  delivered_at DATETIME NULL,
  UNIQUE KEY uq_farm_produced_cycle_stack (share_key, steam_id, resource_id, cycle_id, stack_index),
  INDEX idx_farm_produced_available (steam_id, resource_id, status),
  INDEX idx_farm_produced_redemption (redemption_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS farm_redemptions (
  id VARCHAR(36) NOT NULL PRIMARY KEY,
  steam_id VARCHAR(32) NOT NULL,
  share_key VARCHAR(64) NOT NULL DEFAULT 'default',
  resource_id VARCHAR(100) NOT NULL,
  resource_name VARCHAR(160) NOT NULL,
  amount INT NOT NULL,
  delivered_amount INT NOT NULL DEFAULT 0,
  stack_size INT NOT NULL DEFAULT 25,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDENTE',
  claimed_by VARCHAR(64) NULL,
  claimed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  INDEX idx_farm_redemption_player (steam_id, created_at),
  INDEX idx_farm_redemption_claim (steam_id, status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS farm_redemption_deliveries (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  redemption_id VARCHAR(36) NOT NULL,
  stack_index INT NOT NULL,
  quantity INT NOT NULL,
  produced_item_id VARCHAR(180) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDENTE',
  delivered_at DATETIME NULL,
  UNIQUE KEY uq_farm_redemption_stack (redemption_id, stack_index),
  INDEX idx_farm_delivery_status (redemption_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS farm_redemption_delivery_items (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  delivery_id BIGINT NOT NULL,
  produced_item_id VARCHAR(180) NOT NULL,
  quantity INT NOT NULL,
  INDEX idx_farm_delivery_item_delivery (delivery_id),
  INDEX idx_farm_delivery_item_product (produced_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Atualiza bancos nos quais as primeiras tabelas da Fazenda já foram criadas.
ALTER TABLE farm_player_resources
  ADD COLUMN IF NOT EXISTS share_key VARCHAR(64) NOT NULL DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS last_accrual_utc BIGINT NOT NULL DEFAULT 0;
ALTER TABLE farm_player_resources DROP PRIMARY KEY, ADD PRIMARY KEY (share_key, steam_id, resource_id);
ALTER TABLE farm_uploaded_resources
  ADD COLUMN IF NOT EXISTS share_key VARCHAR(64) NOT NULL DEFAULT 'default';
ALTER TABLE farm_uploaded_resources DROP PRIMARY KEY, ADD PRIMARY KEY (share_key, steam_id, upload_id);
ALTER TABLE farm_produced_items
  ADD COLUMN IF NOT EXISTS share_key VARCHAR(64) NOT NULL DEFAULT 'default';
ALTER TABLE farm_produced_items DROP INDEX uq_farm_produced_cycle_stack,
  ADD UNIQUE KEY uq_farm_produced_cycle_stack (share_key, steam_id, resource_id, cycle_id, stack_index);
ALTER TABLE farm_redemptions
  ADD COLUMN IF NOT EXISTS share_key VARCHAR(64) NOT NULL DEFAULT 'default';
ALTER TABLE farm_resource_catalog
  ADD COLUMN IF NOT EXISTS share_key VARCHAR(64) NOT NULL DEFAULT 'default';
ALTER TABLE farm_redemptions
  ADD COLUMN IF NOT EXISTS delivered_amount INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS stack_size INT NOT NULL DEFAULT 25;
