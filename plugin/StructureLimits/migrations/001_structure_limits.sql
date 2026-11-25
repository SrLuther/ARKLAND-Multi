-- ARKLAND Structure Limits schema v1.
-- Apply only to a separately authorized development/staging database.
-- This script is versioned source; it has not been run against production.

CREATE TABLE IF NOT EXISTS structure_limits_instances (
    instance_key BINARY(32) NOT NULL,
    map_id VARCHAR(32) NOT NULL,
    map_name VARCHAR(128) NOT NULL,
    canonical_instance_path VARCHAR(1024) NOT NULL,
    global_primary BIGINT UNSIGNED NOT NULL DEFAULT 0,
    extra_percentage INT UNSIGNED NOT NULL DEFAULT 25,
    config_version BIGINT UNSIGNED NOT NULL DEFAULT 0,
    inventory_state VARCHAR(24) NOT NULL DEFAULT 'unvalidated',
    inventory_validated_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (instance_key),
    KEY ix_structure_limits_map_id (map_id),
    CONSTRAINT chk_structure_limits_inventory_state
        CHECK (inventory_state IN ('unvalidated', 'scanning', 'validated', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS structure_limits_owners (
    instance_key BINARY(32) NOT NULL,
    owner_key VARCHAR(96) NOT NULL,
    owner_type VARCHAR(12) NOT NULL,
    tribe_id VARCHAR(32) NULL,
    steam_id CHAR(20) NULL,
    global_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (instance_key, owner_key),
    KEY ix_structure_limits_owner_tribe (instance_key, tribe_id),
    KEY ix_structure_limits_owner_steam (instance_key, steam_id),
    CONSTRAINT fk_structure_limits_owner_instance
        FOREIGN KEY (instance_key) REFERENCES structure_limits_instances(instance_key)
        ON DELETE RESTRICT,
    CONSTRAINT chk_structure_limits_owner_type CHECK (owner_type IN ('tribe', 'solo'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS structure_limits_blueprints (
    instance_key BINARY(32) NOT NULL,
    blueprint VARCHAR(512) NOT NULL,
    leg BIGINT UNSIGNED NOT NULL,
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (instance_key, blueprint),
    CONSTRAINT fk_structure_limits_blueprint_instance
        FOREIGN KEY (instance_key) REFERENCES structure_limits_instances(instance_key)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS structure_limits_licenses (
    steam_id CHAR(20) NOT NULL,
    valid_until DATETIME(6) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'admin',
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (steam_id),
    KEY ix_structure_limits_license_expiry (valid_until, steam_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS structure_limits_counters (
    instance_key BINARY(32) NOT NULL,
    owner_key VARCHAR(96) NOT NULL,
    blueprint VARCHAR(512) NOT NULL DEFAULT '',
    structure_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    revision BIGINT UNSIGNED NOT NULL DEFAULT 0,
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (instance_key, owner_key, blueprint),
    CONSTRAINT fk_structure_limits_counter_owner
        FOREIGN KEY (instance_key, owner_key)
        REFERENCES structure_limits_owners(instance_key, owner_key)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS structure_limits_events (
    instance_key BINARY(32) NOT NULL,
    event_id CHAR(64) NOT NULL,
    occurred_at DATETIME(6) NOT NULL,
    event_type VARCHAR(24) NOT NULL,
    owner_key VARCHAR(96) NOT NULL,
    steam_id CHAR(20) NULL,
    structure_id VARCHAR(128) NULL,
    blueprint VARCHAR(512) NOT NULL DEFAULT '',
    global_before BIGINT UNSIGNED NULL,
    global_after BIGINT UNSIGNED NULL,
    specific_before BIGINT UNSIGNED NULL,
    specific_after BIGINT UNSIGNED NULL,
    payload JSON NOT NULL,
    received_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (instance_key, event_id),
    KEY ix_structure_limits_events_retention (occurred_at),
    KEY ix_structure_limits_events_owner (instance_key, owner_key, occurred_at),
    CONSTRAINT fk_structure_limits_event_instance
        FOREIGN KEY (instance_key) REFERENCES structure_limits_instances(instance_key)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS structure_limits_audits (
    instance_key BINARY(32) NOT NULL,
    audit_id CHAR(64) NOT NULL,
    started_at DATETIME(6) NOT NULL,
    completed_at DATETIME(6) NULL,
    result VARCHAR(24) NOT NULL,
    expected_payload JSON NOT NULL,
    observed_payload JSON NOT NULL,
    corrections_payload JSON NULL,
    PRIMARY KEY (instance_key, audit_id),
    KEY ix_structure_limits_audits_time (instance_key, started_at),
    CONSTRAINT fk_structure_limits_audit_instance
        FOREIGN KEY (instance_key) REFERENCES structure_limits_instances(instance_key)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
