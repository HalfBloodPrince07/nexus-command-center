-- Add Sync and Pin Tables for Nexus OS
-- Creates tables for synchronization state, sync runs, and conversation pins

-- SyncState table to track synchronization between Nexus OS and external systems
CREATE TABLE IF NOT EXISTS sync_state (
    nexus_id TEXT PRIMARY KEY,
    vault_path TEXT NOT NULL,
    content_type TEXT NOT NULL,
    last_synced_at DATETIME,
    last_local_hash TEXT(32),
    last_remote_hash TEXT(32),
    sync_status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0
);

-- SyncRun table to track individual sync operations
CREATE TABLE IF NOT EXISTS sync_runs (
    id TEXT PRIMARY KEY,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    status TEXT NOT NULL,
    files_added INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0,
    files_deleted INTEGER DEFAULT 0,
    conflicts INTEGER DEFAULT 0,
    error_message TEXT,
    config_snapshot TEXT
);

-- ConversationPin table to track pinned conversations
CREATE TABLE IF NOT EXISTS conversation_pins (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT 'default_user',
    pinned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    pinned BOOLEAN DEFAULT 1
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_sync_state_status ON sync_state(sync_status);
CREATE INDEX IF NOT EXISTS idx_sync_state_vault ON sync_state(vault_path);
CREATE INDEX IF NOT EXISTS idx_sync_runs_status ON sync_runs(status);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON sync_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_conversation_pins_user ON conversation_pins(user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_pins_state ON conversation_pins(pinned);

-- Insert initial sync run record for setup logging
INSERT OR IGNORE INTO sync_runs (id, status, started_at) 
VALUES ('setup_migration', 'success', CURRENT_TIMESTAMP);
