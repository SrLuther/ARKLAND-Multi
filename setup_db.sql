-- ============================================================
--  ARKLAND Shop — Banco de dados limpo
--  Execute como root: mysql -u root -p < setup_db.sql
-- ============================================================

-- 1) Banco de dados
CREATE DATABASE IF NOT EXISTS arkland_shop
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 2) Usuário dedicado (altere a senha abaixo antes de rodar)
CREATE USER IF NOT EXISTS 'arkland'@'localhost' IDENTIFIED BY 'SUA_SENHA_AQUI';
CREATE USER IF NOT EXISTS 'arkland'@'%'         IDENTIFIED BY 'SUA_SENHA_AQUI';

GRANT ALL PRIVILEGES ON arkland_shop.* TO 'arkland'@'localhost';
GRANT ALL PRIVILEGES ON arkland_shop.* TO 'arkland'@'%';
FLUSH PRIVILEGES;

USE arkland_shop;

-- ============================================================
--  Tabelas do plugin CustomShop
-- ============================================================

-- Jogadores: saldo de pontos e kits adquiridos
CREATE TABLE IF NOT EXISTS players (
  steam_id  VARCHAR(20)  PRIMARY KEY NOT NULL,
  points    INT          NOT NULL DEFAULT 0,
  kits      TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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

-- Jogadores VIP
CREATE TABLE IF NOT EXISTS vip_players (
  steam_id  VARCHAR(20)   PRIMARY KEY NOT NULL,
  expires   DATETIME      DEFAULT NULL,
  tier      VARCHAR(32)   NOT NULL DEFAULT 'vip',
  notes     VARCHAR(255)  DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
--  Tabelas da loja web (arkshop_web / pedidos)
--  Atenção: o SQLAlchemy cria/migra estas tabelas automaticamente.
--  Este bloco é apenas referência para instâncias manuais.
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
  order_id          VARCHAR(36)   PRIMARY KEY NOT NULL,
  steam_id          VARCHAR(20)   NOT NULL,
  server_id         VARCHAR(64)   NOT NULL DEFAULT 'default',
  item_type         VARCHAR(32)   NOT NULL DEFAULT 'shop',
  item_id           VARCHAR(128)  NOT NULL,
  amount            INT           NOT NULL DEFAULT 1,
  status            VARCHAR(20)   NOT NULL DEFAULT 'PENDENTE',
  retry_count       INT           NOT NULL DEFAULT 0,
  last_error        TEXT          DEFAULT NULL,
  contested         TINYINT(1)    NOT NULL DEFAULT 0,
  original_order_id VARCHAR(36)   DEFAULT NULL,
  created_at        DATETIME      DEFAULT NULL,
  updated_at        DATETIME      DEFAULT NULL,
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
SELECT '>>> Banco arkland_shop criado com sucesso!' AS resultado;
SHOW TABLES;
-- ============================================================
