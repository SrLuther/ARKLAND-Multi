-- Aplicação aditiva. Nunca altera nem remove as mensagens, IDs e sessões existentes.
CREATE TABLE IF NOT EXISTS chat_arkland_discord_sources (
  source_id VARCHAR(32) PRIMARY KEY,
  guild_id VARCHAR(32) NOT NULL,
  channel_id VARCHAR(32) NOT NULL,
  author_id VARCHAR(32) NOT NULL,
  lumo BOOLEAN NOT NULL,
  snapshot_json LONGTEXT NOT NULL,
  state VARCHAR(16) NOT NULL,
  copy_ids_json LONGTEXT NOT NULL,
  owner VARCHAR(40) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  claimed_at DATETIME NULL,
  retry_at DATETIME NULL,
  last_error VARCHAR(80) NOT NULL,
  INDEX ix_ca_sources_work (state, retry_at, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT IGNORE INTO chat_arkland_schema (version, applied_at) VALUES (4, UTC_TIMESTAMP());
