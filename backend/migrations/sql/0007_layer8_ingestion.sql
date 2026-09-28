-- 0007_layer8_ingestion.sql
-- Establishes Layer-8 durable ingestion state: receipts, work items, and collection runs.
-- Enforces cross-timestamp idempotency on (tenant_id, source_id, source_account_id, logical_event_id, source_revision).

-- 1. Durable Telemetry Receipts Store (Immutable admission evidence)
CREATE TABLE IF NOT EXISTS telemetry_receipts (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    source_account_id VARCHAR NOT NULL,
    logical_event_id VARCHAR NOT NULL,
    source_revision VARCHAR NOT NULL DEFAULT '1',
    content_hash VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'accepted',
    minimized_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    schema_version VARCHAR NOT NULL DEFAULT '1.0',
    policy_version VARCHAR NOT NULL DEFAULT '1.0',
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_telemetry_receipts_identity UNIQUE (
        tenant_id, source_id, source_account_id, logical_event_id, source_revision
    )
);

CREATE INDEX IF NOT EXISTS idx_telemetry_receipts_tenant ON telemetry_receipts (tenant_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_receipts_status ON telemetry_receipts (tenant_id, status);

-- 2. Durable Telemetry Work Items (Processing queue with lease fencing)
CREATE TABLE IF NOT EXISTS telemetry_work_items (
    id VARCHAR PRIMARY KEY,
    receipt_id VARCHAR NOT NULL REFERENCES telemetry_receipts(id) ON DELETE CASCADE,
    tenant_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'pending',
    attempt_count INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    next_retry_at TIMESTAMPTZ,
    lease_owner VARCHAR,
    lease_expires_at TIMESTAMPTZ,
    lease_generation INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telemetry_work_tenant_status ON telemetry_work_items (tenant_id, status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_telemetry_work_receipt ON telemetry_work_items (receipt_id);

-- 3. Telemetry Collection Runs (Polling checkpoints and partition revision tracking)
CREATE TABLE IF NOT EXISTS telemetry_collection_runs (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    query_fingerprint VARCHAR NOT NULL,
    target_window_start TIMESTAMPTZ NOT NULL,
    target_window_end TIMESTAMPTZ NOT NULL,
    total_pages INT NOT NULL DEFAULT 0,
    completed_pages INT NOT NULL DEFAULT 0,
    coverage_ratio DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    generation INT NOT NULL DEFAULT 1,
    status VARCHAR NOT NULL DEFAULT 'running',
    published_revision INT,
    document JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telemetry_runs_tenant_source ON telemetry_collection_runs (tenant_id, source_id, status);

-- 4. Enable and Force Row Level Security (RLS)
ALTER TABLE telemetry_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_receipts FORCE ROW LEVEL SECURITY;

ALTER TABLE telemetry_work_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_work_items FORCE ROW LEVEL SECURITY;

ALTER TABLE telemetry_collection_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_collection_runs FORCE ROW LEVEL SECURITY;

-- 5. Tenant isolation policies matching 0005_tenant_rls_privileges.sql
DROP POLICY IF EXISTS tenant_isolation_telemetry_receipts ON telemetry_receipts;
CREATE POLICY tenant_isolation_telemetry_receipts ON telemetry_receipts
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

DROP POLICY IF EXISTS tenant_isolation_telemetry_work_items ON telemetry_work_items;
CREATE POLICY tenant_isolation_telemetry_work_items ON telemetry_work_items
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

DROP POLICY IF EXISTS tenant_isolation_telemetry_collection_runs ON telemetry_collection_runs;
CREATE POLICY tenant_isolation_telemetry_collection_runs ON telemetry_collection_runs
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

-- 6. Narrow DML grant to runtime role enterprise_runtime
DO $$
BEGIN
    GRANT SELECT, INSERT, UPDATE ON telemetry_receipts, telemetry_work_items, telemetry_collection_runs TO enterprise_runtime;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Granting runtime permissions skipped.';
END $$;
