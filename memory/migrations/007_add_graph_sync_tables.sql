-- Migration 007: Add Microsoft Graph Sync Tables
-- Created: 2025-12-03
-- Description: Add tables and columns for Microsoft Graph integration

-- =====================================================
-- Graph Sync State Table
-- Stores delta links and sync state for incremental sync
-- =====================================================

CREATE TABLE IF NOT EXISTS graph_sync_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entity identification
    entity_type VARCHAR(50) NOT NULL,  -- 'planner_task', 'todo_task', 'planner_plan', 'todo_list'
    entity_id VARCHAR(255),             -- Optional: Specific entity ID for granular tracking

    -- Delta sync
    delta_link TEXT,                    -- @odata.deltaLink URL for incremental sync
    last_sync_at TIMESTAMP,             -- Last successful sync timestamp
    sync_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'in_progress', 'success', 'failed'

    -- Webhook subscription
    subscription_id VARCHAR(255),       -- Microsoft Graph subscription ID
    client_state VARCHAR(255),          -- Client state for webhook validation
    subscription_expires_at TIMESTAMP,  -- Subscription expiration time

    -- Error tracking
    error_message TEXT,                 -- Error details if sync failed
    error_count INTEGER DEFAULT 0,      -- Consecutive error count
    last_error_at TIMESTAMP,            -- Last error timestamp

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Indexes
    UNIQUE(entity_type, entity_id),
    INDEX idx_graph_sync_entity_type (entity_type),
    INDEX idx_graph_sync_status (sync_status),
    INDEX idx_graph_sync_subscription (subscription_id),
    INDEX idx_graph_sync_expires (subscription_expires_at)
);

COMMENT ON TABLE graph_sync_state IS 'Tracks Microsoft Graph delta sync state and webhook subscriptions';
COMMENT ON COLUMN graph_sync_state.delta_link IS 'Delta link for incremental sync (expires after 30 days)';
COMMENT ON COLUMN graph_sync_state.client_state IS 'Secret token for webhook validation';

-- =====================================================
-- Extend Commitments Table
-- Add Graph-specific columns to existing commitments table
-- =====================================================

-- Graph source and identification
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS graph_source VARCHAR(50);
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS graph_task_id VARCHAR(255);
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS graph_plan_id VARCHAR(255);
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS graph_bucket_id VARCHAR(255);
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS graph_list_id VARCHAR(255);

-- Conflict detection and sync
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS graph_etag VARCHAR(255);
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMP;
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS sync_direction VARCHAR(20);  -- 'graph_to_life', 'life_to_graph', 'bidirectional'
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS last_graph_update TIMESTAMP;

-- Indexes for Graph queries
CREATE INDEX IF NOT EXISTS idx_commitments_graph_source ON commitments(graph_source);
CREATE INDEX IF NOT EXISTS idx_commitments_graph_task_id ON commitments(graph_task_id);
CREATE INDEX IF NOT EXISTS idx_commitments_graph_plan_id ON commitments(graph_plan_id);
CREATE INDEX IF NOT EXISTS idx_commitments_graph_list_id ON commitments(graph_list_id);
CREATE INDEX IF NOT EXISTS idx_commitments_last_synced ON commitments(last_synced_at);

COMMENT ON COLUMN commitments.graph_source IS 'Source system: planner, todo, or null for non-Graph commitments';
COMMENT ON COLUMN commitments.graph_task_id IS 'Microsoft Graph task ID for correlation';
COMMENT ON COLUMN commitments.graph_etag IS 'ETag for optimistic concurrency control';
COMMENT ON COLUMN commitments.last_synced_at IS 'Last sync timestamp for conflict detection';

-- =====================================================
-- Graph Sync Changes Log Table
-- Audit trail of all sync operations
-- =====================================================

CREATE TABLE IF NOT EXISTS graph_sync_changes_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Change identification
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    change_type VARCHAR(20) NOT NULL,  -- 'created', 'updated', 'deleted'

    -- Sync context
    sync_direction VARCHAR(20) NOT NULL,  -- 'graph_to_life', 'life_to_graph'
    commitment_id UUID REFERENCES commitments(id) ON DELETE SET NULL,

    -- Change details
    changes JSONB,                     -- JSON object with changed fields
    graph_data JSONB,                  -- Full Graph entity data
    lifegraph_data JSONB,              -- Full Life Graph data

    -- Conflict tracking
    had_conflict BOOLEAN DEFAULT FALSE,
    conflict_resolution VARCHAR(50),   -- 'last_write_wins', 'graph_wins', 'lifegraph_wins', 'manual'
    conflict_details TEXT,

    -- Metadata
    synced_at TIMESTAMP NOT NULL DEFAULT NOW(),
    synced_by VARCHAR(100),            -- User or system that triggered sync

    -- Indexes
    INDEX idx_sync_log_entity (entity_type, entity_id),
    INDEX idx_sync_log_commitment (commitment_id),
    INDEX idx_sync_log_change_type (change_type),
    INDEX idx_sync_log_timestamp (synced_at DESC),
    INDEX idx_sync_log_conflicts (had_conflict) WHERE had_conflict = TRUE
);

COMMENT ON TABLE graph_sync_changes_log IS 'Audit trail of all Microsoft Graph sync operations';
COMMENT ON COLUMN graph_sync_changes_log.changes IS 'JSON object showing what changed (before/after)';

-- =====================================================
-- Graph Webhook Deliveries Table
-- Track webhook notification deliveries for debugging
-- =====================================================

CREATE TABLE IF NOT EXISTS graph_webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Webhook identification
    subscription_id VARCHAR(255) NOT NULL,
    change_type VARCHAR(20),           -- 'created', 'updated', 'deleted'
    resource VARCHAR(500),              -- Resource path

    -- Delivery tracking
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processing', 'success', 'failed'

    -- Payload
    notification_payload JSONB,         -- Full notification JSON
    client_state VARCHAR(255),
    validation_passed BOOLEAN DEFAULT FALSE,

    -- Processing
    processing_error TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Metadata
    tenant_id VARCHAR(255),

    -- Indexes
    INDEX idx_webhook_subscription (subscription_id),
    INDEX idx_webhook_status (processing_status),
    INDEX idx_webhook_received (received_at DESC),
    INDEX idx_webhook_unprocessed (processing_status) WHERE processing_status IN ('pending', 'failed')
);

COMMENT ON TABLE graph_webhook_deliveries IS 'Tracks webhook notification deliveries for debugging and retry';

-- =====================================================
-- Graph API Rate Limit Tracking
-- Track API usage to avoid throttling
-- =====================================================

CREATE TABLE IF NOT EXISTS graph_api_rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Window tracking
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,

    -- Usage
    request_count INTEGER NOT NULL DEFAULT 0,
    throttled_count INTEGER NOT NULL DEFAULT 0,

    -- By endpoint
    endpoint_stats JSONB,               -- {"endpoint": {"count": X, "throttled": Y}}

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Indexes
    INDEX idx_rate_limit_window (window_start, window_end),
    INDEX idx_rate_limit_recent (window_start DESC)
);

COMMENT ON TABLE graph_api_rate_limits IS 'Tracks Microsoft Graph API rate limit usage';

-- =====================================================
-- Views for Common Queries
-- =====================================================

-- View: Active Graph-synced commitments
CREATE OR REPLACE VIEW v_graph_synced_commitments AS
SELECT
    c.*,
    gss.last_sync_at as state_last_sync,
    gss.sync_status,
    gss.delta_link,
    CASE
        WHEN c.graph_source = 'planner' THEN 'Planner'
        WHEN c.graph_source = 'todo' THEN 'To Do'
        ELSE 'Unknown'
    END as source_name,
    EXTRACT(EPOCH FROM (NOW() - c.last_synced_at)) / 3600 as hours_since_sync
FROM commitments c
LEFT JOIN graph_sync_state gss ON c.graph_source = gss.entity_type
WHERE c.graph_source IS NOT NULL
  AND c.status != 'completed'
ORDER BY c.last_synced_at ASC NULLS FIRST;

COMMENT ON VIEW v_graph_synced_commitments IS 'Active commitments synced from Microsoft Graph with sync status';

-- View: Sync health dashboard
CREATE OR REPLACE VIEW v_graph_sync_health AS
SELECT
    entity_type,
    sync_status,
    COUNT(*) as count,
    MAX(last_sync_at) as most_recent_sync,
    AVG(error_count) as avg_error_count,
    SUM(CASE WHEN subscription_expires_at < NOW() THEN 1 ELSE 0 END) as expired_subscriptions
FROM graph_sync_state
GROUP BY entity_type, sync_status;

COMMENT ON VIEW v_graph_sync_health IS 'Health dashboard for Microsoft Graph sync';

-- View: Recent sync changes
CREATE OR REPLACE VIEW v_graph_recent_changes AS
SELECT
    gscl.id,
    gscl.entity_type,
    gscl.change_type,
    gscl.sync_direction,
    c.title as commitment_title,
    c.tier,
    c.status as commitment_status,
    gscl.had_conflict,
    gscl.conflict_resolution,
    gscl.synced_at,
    EXTRACT(EPOCH FROM (NOW() - gscl.synced_at)) / 60 as minutes_ago
FROM graph_sync_changes_log gscl
LEFT JOIN commitments c ON gscl.commitment_id = c.id
ORDER BY gscl.synced_at DESC
LIMIT 100;

COMMENT ON VIEW v_graph_recent_changes IS 'Recent 100 sync changes from Microsoft Graph';

-- =====================================================
-- Functions for Common Operations
-- =====================================================

-- Function: Update sync state after successful sync
CREATE OR REPLACE FUNCTION update_graph_sync_state(
    p_entity_type VARCHAR,
    p_delta_link TEXT,
    p_subscription_id VARCHAR DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO graph_sync_state (entity_type, delta_link, last_sync_at, sync_status, subscription_id, updated_at)
    VALUES (p_entity_type, p_delta_link, NOW(), 'success', p_subscription_id, NOW())
    ON CONFLICT (entity_type, entity_id)
    DO UPDATE SET
        delta_link = EXCLUDED.delta_link,
        last_sync_at = NOW(),
        sync_status = 'success',
        error_count = 0,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_graph_sync_state IS 'Update sync state after successful delta sync';

-- Function: Record sync error
CREATE OR REPLACE FUNCTION record_graph_sync_error(
    p_entity_type VARCHAR,
    p_error_message TEXT
) RETURNS VOID AS $$
BEGIN
    UPDATE graph_sync_state
    SET
        sync_status = 'failed',
        error_message = p_error_message,
        error_count = error_count + 1,
        last_error_at = NOW(),
        updated_at = NOW()
    WHERE entity_type = p_entity_type;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION record_graph_sync_error IS 'Record sync error and increment error count';

-- Function: Clean up old webhook deliveries (keep 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_webhook_deliveries() RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM graph_webhook_deliveries
    WHERE received_at < NOW() - INTERVAL '30 days'
    AND processing_status = 'success';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_webhook_deliveries IS 'Clean up webhook deliveries older than 30 days';

-- =====================================================
-- Triggers
-- =====================================================

-- Trigger: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_graph_sync_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_graph_sync_state_updated_at
    BEFORE UPDATE ON graph_sync_state
    FOR EACH ROW
    EXECUTE FUNCTION update_graph_sync_updated_at();

-- =====================================================
-- Indexes for Performance
-- =====================================================

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_commitments_graph_sync_lookup
    ON commitments(graph_source, graph_task_id)
    WHERE graph_source IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_commitments_pending_sync
    ON commitments(last_synced_at)
    WHERE graph_source IS NOT NULL
    AND (last_synced_at IS NULL OR last_synced_at < NOW() - INTERVAL '1 hour');

CREATE INDEX IF NOT EXISTS idx_graph_sync_active_subscriptions
    ON graph_sync_state(subscription_expires_at)
    WHERE subscription_id IS NOT NULL
    AND subscription_expires_at > NOW();

-- =====================================================
-- Initial Data
-- =====================================================

-- Insert initial sync state records for each entity type
INSERT INTO graph_sync_state (entity_type, sync_status)
VALUES
    ('planner_task', 'pending'),
    ('planner_plan', 'pending'),
    ('todo_task', 'pending'),
    ('todo_list', 'pending')
ON CONFLICT (entity_type, entity_id) DO NOTHING;

-- =====================================================
-- Grants (adjust based on your user setup)
-- =====================================================

-- GRANT SELECT, INSERT, UPDATE, DELETE ON graph_sync_state TO assistant_user;
-- GRANT SELECT, INSERT, UPDATE ON commitments TO assistant_user;
-- GRANT SELECT, INSERT ON graph_sync_changes_log TO assistant_user;
-- GRANT SELECT, INSERT, UPDATE ON graph_webhook_deliveries TO assistant_user;
-- GRANT SELECT, INSERT ON graph_api_rate_limits TO assistant_user;

-- =====================================================
-- Migration Complete
-- =====================================================

-- Log migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 007: Microsoft Graph sync tables created successfully';
    RAISE NOTICE 'Tables: graph_sync_state, graph_sync_changes_log, graph_webhook_deliveries, graph_api_rate_limits';
    RAISE NOTICE 'Views: v_graph_synced_commitments, v_graph_sync_health, v_graph_recent_changes';
    RAISE NOTICE 'Functions: update_graph_sync_state, record_graph_sync_error, cleanup_old_webhook_deliveries';
END $$;
