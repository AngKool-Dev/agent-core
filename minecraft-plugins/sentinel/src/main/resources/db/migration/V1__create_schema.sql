-- Sentinel Audit - Initial Schema
-- Compatible with both PostgreSQL and SQLite

-- Audit records table
CREATE TABLE IF NOT EXISTS audit_records (
    id          VARCHAR(36) PRIMARY KEY,
    action      VARCHAR(50)  NOT NULL,
    source      VARCHAR(50)  NOT NULL,
    actor_id    VARCHAR(36)  NOT NULL,
    actor_name  VARCHAR(64)  NOT NULL,
    target_id   VARCHAR(36),
    target_name VARCHAR(64),
    world_name  VARCHAR(64)  NOT NULL,
    x           INTEGER      NOT NULL,
    y           INTEGER      NOT NULL,
    z           INTEGER      NOT NULL,
    timestamp   TIMESTAMP    NOT NULL,
    metadata    TEXT
);

-- Indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_records (actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor_time ON audit_records (actor_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_location ON audit_records (world_name, x, y, z);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_records (timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_records (action);

-- Block change records table
CREATE TABLE IF NOT EXISTS block_changes (
    id                VARCHAR(36) PRIMARY KEY,
    audit_event_id    VARCHAR(36) NOT NULL,
    world_name        VARCHAR(64) NOT NULL,
    x                 INTEGER     NOT NULL,
    y                 INTEGER     NOT NULL,
    z                 INTEGER     NOT NULL,
    before_material   VARCHAR(64) NOT NULL,
    before_data       TEXT        NOT NULL,
    before_tile_data  TEXT,
    after_material    VARCHAR(64) NOT NULL,
    after_data        TEXT        NOT NULL,
    after_tile_data   TEXT,
    timestamp         TIMESTAMP   NOT NULL,
    CONSTRAINT fk_block_audit FOREIGN KEY (audit_event_id)
        REFERENCES audit_records (id) ON DELETE CASCADE
);

-- Indexes for block change queries
CREATE INDEX IF NOT EXISTS idx_block_location ON block_changes (world_name, x, y, z);
CREATE INDEX IF NOT EXISTS idx_block_audit_event ON block_changes (audit_event_id);
CREATE INDEX IF NOT EXISTS idx_block_timestamp ON block_changes (timestamp);
CREATE INDEX IF NOT EXISTS idx_block_world_time ON block_changes (world_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_block_audit_time ON block_changes (audit_event_id, timestamp);

-- Inventory change records table
CREATE TABLE IF NOT EXISTS inventory_changes (
    id               VARCHAR(36) PRIMARY KEY,
    audit_event_id   VARCHAR(36) NOT NULL,
    inventory_id     VARCHAR(128) NOT NULL,
    before_contents  TEXT        NOT NULL,
    before_size      INTEGER     NOT NULL,
    before_title     VARCHAR(128),
    after_contents   TEXT        NOT NULL,
    after_size       INTEGER     NOT NULL,
    after_title      VARCHAR(128),
    timestamp        TIMESTAMP   NOT NULL,
    CONSTRAINT fk_inventory_audit FOREIGN KEY (audit_event_id)
        REFERENCES audit_records (id) ON DELETE CASCADE
);

-- Indexes for inventory change queries
CREATE INDEX IF NOT EXISTS idx_inventory_id ON inventory_changes (inventory_id);
CREATE INDEX IF NOT EXISTS idx_inventory_audit_event ON inventory_changes (audit_event_id);
CREATE INDEX IF NOT EXISTS idx_inventory_timestamp ON inventory_changes (timestamp);

-- Rollback operations table
CREATE TABLE IF NOT EXISTS rollback_operations (
    id              VARCHAR(36) PRIMARY KEY,
    actor_id        VARCHAR(36) NOT NULL,
    actor_name      VARCHAR(64) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    blocks_restored INTEGER     NOT NULL DEFAULT 0,
    total_blocks    INTEGER     NOT NULL DEFAULT 0,
    started_at      TIMESTAMP   NOT NULL,
    completed_at    TIMESTAMP
);

-- Indexes for rollback operations
CREATE INDEX IF NOT EXISTS idx_rollback_actor ON rollback_operations (actor_id);
CREATE INDEX IF NOT EXISTS idx_rollback_status ON rollback_operations (status);