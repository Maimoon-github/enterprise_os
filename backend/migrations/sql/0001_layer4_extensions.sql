-- 0001_layer4_extensions.sql
-- Enables required Layer-4 PostgreSQL extensions idempotently.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- pgvector extension for dense retrieval embeddings
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS "vector";
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector extension could not be enabled; verify extension binaries are present.';
END $$;

-- TimescaleDB extension for time-series hypertable partitioning
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'TimescaleDB extension could not be enabled; telemetry will use standard partitioning.';
END $$;
