-- 0002_layer4_core.sql
-- Core operational directives and canonical task state tables.

CREATE TABLE IF NOT EXISTS operational_directives (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_states (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
