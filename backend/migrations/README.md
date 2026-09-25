# Layer 4 Database Migrations

Versioned SQL migrations establishing Central Enterprise Storage & System of Record (Layer 4) persistence foundations.

## Execution Sequence

Migrations are executed deterministically in ascending numerical order:

1. `sql/0001_layer4_extensions.sql` — Idempotently enables PostgreSQL extensions (`uuid-ossp`, `pgcrypto`, `vector`, `timescaledb`).
2. `sql/0002_layer4_core.sql` — Creates core operational directives and canonical task state tables.
3. `sql/0003_memory_artifact_provenance.sql` — Creates vector document embeddings, institutional memory, deliverables/evidence artifacts, and tamper-evident provenance tables.
4. `sql/0004_telemetry_hypertable.sql` — Creates telemetry events store and converts to Timescale hypertable where TimescaleDB is available.
5. `sql/0005_tenant_rls_privileges.sql` — Enables and forces PostgreSQL Row Level Security (RLS) on all tenant-scoped tables with `USING` and `WITH CHECK` policies; defines least-privilege runtime (`enterprise_runtime`) and migration (`enterprise_migration`) roles.
6. `sql/0006_layer4_indexes.sql` — Builds query-justified tenant isolation and lookup indexes.

## Privilege Separation Model

- **Migration Identity (`enterprise_migration`)**: Owns table/schema DDL and migration execution; strictly separated from application runtime.
- **Runtime Identity (`enterprise_runtime`)**: `NOBYPASSRLS`, non-superuser, non-owner; granted minimum DML (`SELECT`, `INSERT`, `UPDATE` on domain tables; `SELECT`, `INSERT` only on append-only provenance).
