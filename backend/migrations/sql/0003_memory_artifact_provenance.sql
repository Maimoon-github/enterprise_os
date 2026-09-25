-- 0003_memory_artifact_provenance.sql
-- Vector retrieval documents, institutional memory, deliverables/evidence artifacts, and tamper-evident provenance.

CREATE TABLE IF NOT EXISTS vector_documents (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS institutional_memory (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS provenance_records (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
