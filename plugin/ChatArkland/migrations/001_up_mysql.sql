-- Chat Arkland: versão de esquema 1. Sem alterações em tabelas de outros sistemas.

CREATE TABLE IF NOT EXISTS chat_arkland_config (
	id INTEGER NOT NULL AUTO_INCREMENT,
	revision INTEGER NOT NULL,
	config_json LONGTEXT NOT NULL,
	changed_at DATETIME NOT NULL,
	actor VARCHAR(40) NOT NULL,
	PRIMARY KEY (id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_arkland_deliveries (
	delivery_id VARCHAR(64) NOT NULL,
	event_id VARCHAR(64) NOT NULL,
	recipient VARCHAR(32) NOT NULL,
	lease_owner VARCHAR(100),
	lease_until DATETIME,
	acked_at DATETIME,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY (delivery_id),
	UNIQUE (event_id, recipient)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_ca_private_recipient ON chat_arkland_deliveries (recipient, acked_at, expires_at);

CREATE TABLE IF NOT EXISTS chat_arkland_discord_lease (
	id INTEGER NOT NULL AUTO_INCREMENT,
	owner VARCHAR(40),
	until_at DATETIME,
	PRIMARY KEY (id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_arkland_events (
	event_id VARCHAR(64) NOT NULL,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY (event_id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_arkland_instances (
	server_key VARCHAR(100) NOT NULL,
	boot_id VARCHAR(8) NOT NULL,
	last_seen_at DATETIME NOT NULL,
	last_monitor_at DATETIME,
	revision INTEGER NOT NULL,
	plugin_version VARCHAR(32) NOT NULL,
	observer BOOL NOT NULL,
	last_error VARCHAR(256) NOT NULL,
	player_count INTEGER NOT NULL,
	PRIMARY KEY (server_key)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_arkland_messages (
	seq BIGINT NOT NULL AUTO_INCREMENT,
	event_id VARCHAR(64) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	origin VARCHAR(16) NOT NULL,
	server_key VARCHAR(100) NOT NULL,
	sender_steam VARCHAR(32),
	payload_json LONGTEXT NOT NULL,
	created_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	discord_state VARCHAR(16) NOT NULL,
	discord_id VARCHAR(32),
	discord_owner VARCHAR(40),
	claimed_at DATETIME,
	PRIMARY KEY (seq),
	UNIQUE (event_id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE INDEX ix_ca_messages_discord ON chat_arkland_messages (discord_state, seq);

CREATE INDEX ix_ca_messages_cursor ON chat_arkland_messages (seq, expires_at);

CREATE TABLE IF NOT EXISTS chat_arkland_players (
	public_id BIGINT NOT NULL AUTO_INCREMENT,
	steam_id VARCHAR(32) NOT NULL,
	notifications BOOL NOT NULL,
	reply_to VARCHAR(32),
	last_global_at DATETIME,
	PRIMARY KEY (public_id),
	UNIQUE (steam_id)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_arkland_revisions (
	revision INTEGER NOT NULL AUTO_INCREMENT,
	config_json LONGTEXT NOT NULL,
	changed_at DATETIME NOT NULL,
	actor VARCHAR(40) NOT NULL,
	PRIMARY KEY (revision)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_arkland_schema (
	version INTEGER NOT NULL AUTO_INCREMENT,
	applied_at DATETIME NOT NULL,
	PRIMARY KEY (version)
)CHARSET=utf8mb4 ENGINE=InnoDB COLLATE utf8mb4_unicode_ci;
