-- 0006_layer4_indexes.sql
-- Builds query-justified tenant isolation and lookup indexes.

CREATE INDEX IF NOT EXISTS idx_operational_directives_tenant ON operational_directives(tenant_id);
CREATE INDEX IF NOT EXISTS idx_task_states_tenant ON task_states(tenant_id);
CREATE INDEX IF NOT EXISTS idx_vector_documents_tenant ON vector_documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_institutional_memory_tenant ON institutional_memory(tenant_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_tenant ON artifacts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_tenant ON telemetry_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_provenance_records_tenant ON provenance_records(tenant_id);
