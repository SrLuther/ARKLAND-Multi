-- Migration ItensAlfa licenses (Delta → Exótico) — idempotente
-- Banco: arkland_shop (Web Store / player_entitlements)
-- Auto: arkshop_web boot → _migrate_schema → ensure_itensalfa_licenses_schema
-- Manual: python tools/migrate_itensalfa_licenses.py
-- Ou: mysql -u USER -p arkland_shop < plugin/arkshop_web/migrations/itensalfa_licenses.sql

CREATE TABLE IF NOT EXISTS player_entitlements (
  id INT AUTO_INCREMENT PRIMARY KEY,
  steam_id VARCHAR(20) NOT NULL,
  group_name VARCHAR(32) NOT NULL,
  expires DATETIME DEFAULT NULL,
  source VARCHAR(64) DEFAULT NULL,
  notes VARCHAR(255) DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_steam_group (steam_id, group_name),
  INDEX idx_steam_expires (steam_id, expires)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS license_tier_catalog (
  group_name VARCHAR(32) NOT NULL PRIMARY KEY,
  price_amber INT NOT NULL,
  timed_bonus INT NOT NULL,
  access_note VARCHAR(128) NOT NULL,
  renewal_discount_pct INT NOT NULL DEFAULT 20,
  recent_discount_pct INT NOT NULL DEFAULT 10,
  recent_window_days INT NOT NULL DEFAULT 7,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO license_tier_catalog
  (group_name, price_amber, timed_bonus, access_note, renewal_discount_pct, recent_discount_pct, recent_window_days)
VALUES
  ('Delta', 6000, 5, 'apenas Delta', 20, 10, 7),
  ('Gamma', 50000, 25, 'Gama + Delta', 20, 10, 7),
  ('Beta', 75000, 50, 'Beta + Gama', 20, 10, 7),
  ('Alfa', 100000, 75, 'Alfa + Beta', 20, 10, 7),
  ('Omega', 115000, 90, 'Omega + Alfa', 20, 10, 7),
  ('Transcendente', 130000, 105, 'Transcendente + Omega', 20, 10, 7),
  ('Etereo', 150000, 120, 'Etereo + Transcendente', 20, 10, 7),
  ('Universal', 165000, 135, 'Universal + Etereo', 20, 10, 7),
  ('Onipotente', 180000, 150, 'Onipotente + Universal', 20, 10, 7),
  ('Surreal', 195000, 165, 'Surreal + Onipotente', 20, 10, 7),
  ('Imaterial', 215000, 180, 'Imaterial + Surreal', 20, 10, 7),
  ('Exotico', 230000, 200, 'Exotico + Imaterial', 20, 10, 7)
ON DUPLICATE KEY UPDATE
  price_amber = VALUES(price_amber),
  timed_bonus = VALUES(timed_bonus),
  access_note = VALUES(access_note),
  renewal_discount_pct = VALUES(renewal_discount_pct),
  recent_discount_pct = VALUES(recent_discount_pct),
  recent_window_days = VALUES(recent_window_days);

-- Grupos Permissions (plugin ark_permission) NÃO são criados por este SQL.
-- Use RCON: Permissions.AddGroup <Nome>
-- ou a UI da Loja → Provisionar grupos (lê LicenseGrant/TimedPoints do config.json).
