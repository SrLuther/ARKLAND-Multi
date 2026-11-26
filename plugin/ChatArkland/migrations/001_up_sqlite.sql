-- Chat Arkland: versão de esquema 1. Sem alterações em tabelas de outros sistemas.

CREATE TABLE IF NOT EXISTS chat_arkland_config (
	id INTEGER NOT NULL,
	revision INTEGER NOT NULL,
	config_json TEXT NOT NULL,
	changed_at DATETIME NOT NULL,
	actor VARCHAR(40) NOT NULL,
	PRIMARY KEY (id)
);

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
);

CREATE INDEX ix_ca_private_recipient ON chat_arkland_deliveries (recipient, acked_at, expires_at);

CREATE TABLE IF NOT EXISTS chat_arkland_discord_lease (
	id INTEGER NOT NULL,
	owner VARCHAR(40),
	until_at DATETIME,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS chat_arkland_events (
	event_id VARCHAR(64) NOT NULL,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY (event_id)
);

CREATE TABLE IF NOT EXISTS chat_arkland_instances (
	server_key VARCHAR(100) NOT NULL,
	boot_id VARCHAR(8) NOT NULL,
	last_seen_at DATETIME NOT NULL,
	last_monitor_at DATETIME,
	revision INTEGER NOT NULL,
	plugin_version VARCHAR(32) NOT NULL,
	observer BOOLEAN NOT NULL,
	last_error VARCHAR(256) NOT NULL,
	player_count INTEGER NOT NULL,
	PRIMARY KEY (server_key)
);

CREATE TABLE IF NOT EXISTS chat_arkland_messages (
	seq INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	event_id VARCHAR(64) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	origin VARCHAR(16) NOT NULL,
	server_key VARCHAR(100) NOT NULL,
	sender_steam VARCHAR(32),
	payload_json TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	discord_state VARCHAR(16) NOT NULL,
	discord_id VARCHAR(32),
	discord_owner VARCHAR(40),
	claimed_at DATETIME,
	UNIQUE (event_id)
);

CREATE INDEX ix_ca_messages_cursor ON chat_arkland_messages (seq, expires_at);

CREATE INDEX ix_ca_messages_discord ON chat_arkland_messages (discord_state, seq);

CREATE TABLE IF NOT EXISTS chat_arkland_players (
	public_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	steam_id VARCHAR(32) NOT NULL,
	notifications BOOLEAN NOT NULL,
	reply_to VARCHAR(32),
	last_global_at DATETIME,
	UNIQUE (steam_id)
);

CREATE TABLE IF NOT EXISTS chat_arkland_revisions (
	revision INTEGER NOT NULL,
	config_json TEXT NOT NULL,
	changed_at DATETIME NOT NULL,
	actor VARCHAR(40) NOT NULL,
	PRIMARY KEY (revision)
);

CREATE TABLE IF NOT EXISTS chat_arkland_schema (
	version INTEGER NOT NULL,
	applied_at DATETIME NOT NULL,
	PRIMARY KEY (version)
);
