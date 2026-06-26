-- ============================================================
--  ARKLAND — Bancos de dados (loja + permissões)
--  Execute como root: mysql -u root -p < setup_db.sql
-- ============================================================

-- 1) Bancos de dados
CREATE DATABASE IF NOT EXISTS arkland_shop
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS ark_permission
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 2) Usuário dedicado (altere a senha abaixo antes de rodar)
CREATE USER IF NOT EXISTS 'arkland'@'localhost' IDENTIFIED BY 'SUA_SENHA_AQUI';
CREATE USER IF NOT EXISTS 'arkland'@'%'         IDENTIFIED BY 'SUA_SENHA_AQUI';

GRANT ALL PRIVILEGES ON arkland_shop.* TO 'arkland'@'localhost';
GRANT ALL PRIVILEGES ON arkland_shop.* TO 'arkland'@'%';
GRANT ALL PRIVILEGES ON ark_permission.* TO 'arkland'@'localhost';
GRANT ALL PRIVILEGES ON ark_permission.* TO 'arkland'@'%';
FLUSH PRIVILEGES;

USE arkland_shop;

-- ============================================================
--  Tabelas do plugin CustomShop
-- ============================================================

-- Jogadores: saldo de pontos e kits adquiridos
CREATE TABLE IF NOT EXISTS players (
  steam_id  VARCHAR(20)  NOT NULL PRIMARY KEY
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  points    INT          NOT NULL DEFAULT 0,
  kits      TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Contas web (login Steam — painel admin de jogadores)
CREATE TABLE IF NOT EXISTS store_users (
  steam_id             VARCHAR(32)  NOT NULL PRIMARY KEY
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  display_name         VARCHAR(128) DEFAULT NULL,
  site_access_blocked  TINYINT(1)   NOT NULL DEFAULT 0,
  ban_reason           TEXT         DEFAULT NULL,
  created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at        DATETIME     DEFAULT NULL,
  INDEX idx_store_users_display (display_name),
  INDEX idx_store_users_blocked (site_access_blocked)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Histórico de transações
CREATE TABLE IF NOT EXISTS transactions (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  ts            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  type          VARCHAR(20)  NOT NULL,
  steam_id      VARCHAR(20)  NOT NULL,
  target_id     VARCHAR(20)  DEFAULT NULL,
  item_id       VARCHAR(128) DEFAULT NULL,
  amount        INT          DEFAULT 1,
  points_before INT          DEFAULT 0,
  points_after  INT          DEFAULT 0,
  INDEX idx_steam (steam_id),
  INDEX idx_ts    (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Jogadores VIP (legado — migrar para player_entitlements)
CREATE TABLE IF NOT EXISTS vip_players (
  steam_id  VARCHAR(20)   PRIMARY KEY NOT NULL,
  expires   DATETIME      DEFAULT NULL,
  tier      VARCHAR(32)   NOT NULL DEFAULT 'vip',
  notes     VARCHAR(255)  DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Licenças ativas (Gamma, Beta, Alfa, Moderacao, STAFF — múltiplas por jogador)
CREATE TABLE IF NOT EXISTS player_entitlements (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  steam_id   VARCHAR(20)   NOT NULL,
  group_name VARCHAR(32)   NOT NULL,
  expires    DATETIME      DEFAULT NULL,
  source     VARCHAR(64)   DEFAULT NULL,
  notes      VARCHAR(255)  DEFAULT NULL,
  created_at DATETIME      DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_steam_group (steam_id, group_name),
  INDEX idx_steam_expires (steam_id, expires)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Inventário na nuvem (CustomShop /upload /download)
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

-- ============================================================
--  Tabelas da loja web (arkshop_web / pedidos)
--  Atenção: o SQLAlchemy cria/migra estas tabelas automaticamente.
--  Este bloco é apenas referência para instâncias manuais.
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
  id                INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
  order_id          VARCHAR(64)   NOT NULL,
  steam_id          VARCHAR(32)   NOT NULL,
  server_id         VARCHAR(64)   NOT NULL DEFAULT 'default',
  item_type         VARCHAR(32)   NOT NULL DEFAULT 'shop',
  item_id           VARCHAR(128)  NOT NULL,
  amount            INT           NOT NULL DEFAULT 1,
  status            VARCHAR(32)   NOT NULL DEFAULT 'PENDENTE',
  retry_count       INT           NOT NULL DEFAULT 0,
  last_error        TEXT          DEFAULT NULL,
  contested         TINYINT(1)    NOT NULL DEFAULT 0,
  original_order_id VARCHAR(64)   DEFAULT NULL,
  created_at        DATETIME      DEFAULT NULL,
  updated_at        DATETIME      DEFAULT NULL,
  UNIQUE KEY ix_orders_order_id (order_id),
  INDEX idx_steam_status (steam_id, status),
  INDEX idx_server       (server_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_attempts (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  order_id      VARCHAR(36)   NOT NULL,
  success       TINYINT(1)    NOT NULL DEFAULT 0,
  command       TEXT          DEFAULT NULL,
  response      TEXT          DEFAULT NULL,
  error         TEXT          DEFAULT NULL,
  attempted_at  DATETIME      DEFAULT NULL,
  INDEX idx_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS rebuys (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  steam_id            VARCHAR(20)  NOT NULL,
  original_order_id   VARCHAR(36)  NOT NULL,
  new_order_id        VARCHAR(36)  NOT NULL,
  created_at          DATETIME     DEFAULT NULL,
  INDEX idx_steam (steam_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS disputes (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  order_id  VARCHAR(36)   NOT NULL,
  steam_id  VARCHAR(20)   NOT NULL,
  reason    TEXT          DEFAULT NULL,
  status    VARCHAR(20)   NOT NULL DEFAULT 'ABERTO',
  created_at DATETIME     DEFAULT NULL,
  INDEX idx_order  (order_id),
  INDEX idx_steam  (steam_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_admins (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  steam_id  VARCHAR(20)  NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
--  Mercado de Dinos (P2P cryopod)
-- ============================================================

CREATE TABLE IF NOT EXISTS market_species (
  id                   INT AUTO_INCREMENT PRIMARY KEY,
  species_key          VARCHAR(64)  NOT NULL,
  catalog_item_id      VARCHAR(128) DEFAULT NULL,
  display_name         VARCHAR(128) NOT NULL,
  blueprint_path       VARCHAR(512) NOT NULL DEFAULT '',
  reference_level      INT          NOT NULL DEFAULT 1,
  root_value           INT          NOT NULL DEFAULT 0,
  tier                 VARCHAR(8)   NOT NULL DEFAULT 'B',
  breeding_difficulty  VARCHAR(32)  DEFAULT NULL,
  breeding_notes       TEXT         DEFAULT NULL,
  status               VARCHAR(32)  NOT NULL DEFAULT 'PRE_REGISTERED',
  shop_price_synced_at DATETIME     DEFAULT NULL,
  activated_at         DATETIME     DEFAULT NULL,
  activated_by         VARCHAR(32)  DEFAULT NULL,
  created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_market_species_key (species_key),
  INDEX idx_market_species_status (status),
  INDEX idx_market_species_catalog (catalog_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS market_species_stat_multipliers (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  species_id  INT         NOT NULL,
  stat_key    VARCHAR(32) NOT NULL,
  multiplier  INT         NOT NULL DEFAULT 0,
  enabled     TINYINT(1)  NOT NULL DEFAULT 1,
  UNIQUE KEY uq_market_species_stat (species_id, stat_key),
  INDEX idx_market_mult_species (species_id),
  CONSTRAINT fk_market_mult_species
    FOREIGN KEY (species_id) REFERENCES market_species(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS market_player_profile (
  steam_id             VARCHAR(32)  NOT NULL PRIMARY KEY
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  market_display_name  VARCHAR(32)  NOT NULL,
  name_updated_at      DATETIME     DEFAULT NULL,
  commerce_enabled     TINYINT(1)   NOT NULL DEFAULT 0,
  created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS market_cryopod_vault (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  seller_steam_id  VARCHAR(32)  NOT NULL,
  item_blob        MEDIUMBLOB   NOT NULL,
  blob_hash        CHAR(64)     NOT NULL,
  metadata_json    JSON         NOT NULL,
  species_key      VARCHAR(64)  DEFAULT NULL,
  market_trace_id  VARCHAR(64)  DEFAULT NULL,
  parser_version   VARCHAR(32)  DEFAULT NULL,
  uploaded_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_market_vault_seller (seller_steam_id),
  INDEX idx_market_vault_hash (blob_hash),
  INDEX idx_market_vault_species (species_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS market_listings (
  id                   INT AUTO_INCREMENT PRIMARY KEY,
  vault_id             INT          NOT NULL,
  seller_steam_id      VARCHAR(32)  NOT NULL,
  species_key          VARCHAR(64)  DEFAULT NULL,
  status               VARCHAR(32)  NOT NULL DEFAULT 'DRAFT',
  price_mode           VARCHAR(16)  NOT NULL DEFAULT 'ABSOLUTE',
  price_absolute       INT          DEFAULT NULL,
  price_offset_percent INT          DEFAULT NULL,
  computed_base_value  INT          NOT NULL DEFAULT 0,
  effective_price      INT          NOT NULL DEFAULT 0,
  buyer_steam_id       VARCHAR(32)  DEFAULT NULL,
  market_trace_id      VARCHAR(64)  DEFAULT NULL,
  dino_display_name    VARCHAR(128) DEFAULT NULL,
  stat_health          INT          NOT NULL DEFAULT 0,
  stat_melee           INT          NOT NULL DEFAULT 0,
  stat_weight          INT          NOT NULL DEFAULT 0,
  stat_stamina         INT          NOT NULL DEFAULT 0,
  stat_oxygen          INT          NOT NULL DEFAULT 0,
  stat_food            INT          NOT NULL DEFAULT 0,
  stat_speed           INT          NOT NULL DEFAULT 0,
  mutations_male       INT          NOT NULL DEFAULT 0,
  mutations_female     INT          NOT NULL DEFAULT 0,
  dino_level           INT          NOT NULL DEFAULT 0,
  imprint_pct          FLOAT        NOT NULL DEFAULT 0,
  is_female            TINYINT(1)   NOT NULL DEFAULT 0,
  is_neutered          TINYINT(1)   NOT NULL DEFAULT 0,
  metadata_json        JSON         DEFAULT NULL,
  created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  sold_at              DATETIME     DEFAULT NULL,
  INDEX idx_market_listing_status (status, species_key, effective_price),
  INDEX idx_market_listing_seller (seller_steam_id, status),
  INDEX idx_market_listing_buyer (buyer_steam_id, status),
  CONSTRAINT fk_market_listing_vault
    FOREIGN KEY (vault_id) REFERENCES market_cryopod_vault(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS market_transactions (
  id                   INT AUTO_INCREMENT PRIMARY KEY,
  listing_id           INT          NOT NULL,
  buyer_steam_id       VARCHAR(32)  NOT NULL,
  seller_steam_id      VARCHAR(32)  NOT NULL,
  price_paid           INT          NOT NULL DEFAULT 0,
  base_value_at_sale   INT          NOT NULL DEFAULT 0,
  fee_amount           INT          NOT NULL DEFAULT 0,
  buyer_points_before  INT          DEFAULT NULL,
  buyer_points_after   INT          DEFAULT NULL,
  seller_points_before INT          DEFAULT NULL,
  seller_points_after  INT          DEFAULT NULL,
  market_trace_id      VARCHAR(64)  DEFAULT NULL,
  created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_market_tx_listing (listing_id),
  INDEX idx_market_tx_buyer (buyer_steam_id),
  CONSTRAINT fk_market_tx_listing
    FOREIGN KEY (listing_id) REFERENCES market_listings(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS market_claims (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  listing_id          INT          NOT NULL,
  recipient_steam_id  VARCHAR(32)  NOT NULL,
  claim_type          VARCHAR(32)  NOT NULL DEFAULT 'BUYER',
  status              VARCHAR(32)  NOT NULL DEFAULT 'PENDENTE',
  retry_count         INT          NOT NULL DEFAULT 0,
  last_error          TEXT         DEFAULT NULL,
  market_trace_id     VARCHAR(64)  DEFAULT NULL,
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  delivered_at        DATETIME     DEFAULT NULL,
  INDEX idx_market_claim_recipient (recipient_steam_id, status),
  INDEX idx_market_claim_listing (listing_id),
  CONSTRAINT fk_market_claim_listing
    FOREIGN KEY (listing_id) REFERENCES market_listings(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS market_audit_events (
  id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
  market_trace_id       VARCHAR(64)  DEFAULT NULL,
  event_type            VARCHAR(64)  NOT NULL,
  severity              VARCHAR(16)  NOT NULL DEFAULT 'INFO',
  steam_id              VARCHAR(32)  DEFAULT NULL,
  counterparty_steam_id VARCHAR(32)  DEFAULT NULL,
  market_display_name   VARCHAR(32)  DEFAULT NULL,
  listing_id            INT          DEFAULT NULL,
  vault_id              INT          DEFAULT NULL,
  claim_id              INT          DEFAULT NULL,
  blob_hash             CHAR(64)     DEFAULT NULL,
  computed_base_value   INT          DEFAULT NULL,
  effective_price       INT          DEFAULT NULL,
  points_delta          INT          DEFAULT NULL,
  points_before         INT          DEFAULT NULL,
  points_after          INT          DEFAULT NULL,
  parser_version        VARCHAR(32)  DEFAULT NULL,
  plugin_version        VARCHAR(32)  DEFAULT NULL,
  web_version           VARCHAR(32)  DEFAULT NULL,
  source                VARCHAR(16)  NOT NULL DEFAULT 'web',
  metadata_json         JSON         DEFAULT NULL,
  created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_market_audit_trace (market_trace_id),
  INDEX idx_market_audit_type (event_type, created_at),
  INDEX idx_market_audit_steam (steam_id, created_at),
  INDEX idx_market_audit_listing (listing_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
--  ark_permission: tabelas criadas pelo Permissions.dll no primeiro start
-- ============================================================

SELECT '>>> Bancos arkland_shop e ark_permission criados com sucesso!' AS resultado;
USE arkland_shop;
SHOW TABLES;
-- ============================================================
