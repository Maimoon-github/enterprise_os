-- 0005_tenant_rls_privileges.sql
-- Enforces PostgreSQL Row Level Security (RLS) and separates runtime vs migration roles.

-- 1. Enable and Force RLS on all tenant-scoped tables
ALTER TABLE operational_directives ENABLE ROW LEVEL SECURITY;
ALTER TABLE operational_directives FORCE ROW LEVEL SECURITY;

ALTER TABLE task_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_states FORCE ROW LEVEL SECURITY;

ALTER TABLE vector_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE vector_documents FORCE ROW LEVEL SECURITY;

ALTER TABLE institutional_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE institutional_memory FORCE ROW LEVEL SECURITY;

ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts FORCE ROW LEVEL SECURITY;

ALTER TABLE telemetry_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_events FORCE ROW LEVEL SECURITY;

ALTER TABLE provenance_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE provenance_records FORCE ROW LEVEL SECURITY;

-- 2. Tenant isolation policies using app.current_tenant session variable
DROP POLICY IF EXISTS tenant_isolation_operational_directives ON operational_directives;
CREATE POLICY tenant_isolation_operational_directives ON operational_directives
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

DROP POLICY IF EXISTS tenant_isolation_task_states ON task_states;
CREATE POLICY tenant_isolation_task_states ON task_states
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

DROP POLICY IF EXISTS tenant_isolation_vector_documents ON vector_documents;
CREATE POLICY tenant_isolation_vector_documents ON vector_documents
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

DROP POLICY IF EXISTS tenant_isolation_institutional_memory ON institutional_memory;
CREATE POLICY tenant_isolation_institutional_memory ON institutional_memory
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

DROP POLICY IF EXISTS tenant_isolation_artifacts ON artifacts;
CREATE POLICY tenant_isolation_artifacts ON artifacts
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

DROP POLICY IF EXISTS tenant_isolation_telemetry_events ON telemetry_events;
CREATE POLICY tenant_isolation_telemetry_events ON telemetry_events
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

DROP POLICY IF EXISTS tenant_isolation_provenance_records ON provenance_records;
CREATE POLICY tenant_isolation_provenance_records ON provenance_records
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), ''));

-- 3. Provision distinct runtime and migration identities
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'enterprise_runtime') THEN
        CREATE ROLE enterprise_runtime NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'enterprise_migration') THEN
        CREATE ROLE enterprise_migration NOBYPASSRLS NOSUPERUSER CREATEDB NOCREATEROLE LOGIN;
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Role creation skipped (requires superuser/admin).';
END $$;

-- 4. Minimum DML grant to runtime role
DO $$
BEGIN
    GRANT SELECT, INSERT, UPDATE ON operational_directives, task_states, vector_documents, institutional_memory, artifacts, telemetry_events TO enterprise_runtime;
    GRANT SELECT, INSERT ON provenance_records TO enterprise_runtime;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Granting runtime permissions skipped.';
END $$;
