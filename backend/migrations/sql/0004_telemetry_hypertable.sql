-- 0004_telemetry_hypertable.sql
-- Omnichannel telemetry events store with idempotent hypertable conversion.

CREATE TABLE IF NOT EXISTS telemetry_events (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('telemetry_events', 'updated_at', if_not_exists => TRUE);
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Skipping Timescale hypertable conversion.';
END $$;
