/**
 * Creates the enrichment grid tables — see docs/design/enrichment-plan.md.
 *
 * Run with:  bun run scripts/create-grid-tables.ts
 *
 * Bun loads .env.local automatically, which is why this file has none of the
 * hand-rolled dotenv parsing the older scripts/*.js migrations carry.
 *
 * Every statement is guarded so re-running is safe. Keep in sync with
 * src/lib/grid/schema.ts and the OWNED_TABLES allowlist in drizzle.config.ts.
 */
import { Client } from "pg";

const SQL = `
-- One shared sequence for row versions, NOT a per-row counter. Polling asks
-- "give me rows changed since cursor N", which only works if writes are
-- globally ordered. See the comment on gridRows in src/lib/grid/schema.ts.
CREATE SEQUENCE IF NOT EXISTS grid_row_version_seq;

CREATE TABLE IF NOT EXISTS grid_tables (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  auto_run boolean NOT NULL DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS grid_columns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  table_id uuid NOT NULL REFERENCES grid_tables(id) ON DELETE CASCADE,
  -- Stable JSONB key, generated once and never renamed. The display label
  -- is "name"; splitting them keeps a rename from rewriting every row.
  key text NOT NULL,
  name text NOT NULL,
  type text NOT NULL,
  config jsonb NOT NULL DEFAULT '{}',
  -- The DAG edges. Derived from config by the runner, never hand-set.
  depends_on text[] NOT NULL DEFAULT '{}',
  position double precision NOT NULL,
  auto_run boolean NOT NULL DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  CONSTRAINT grid_columns_table_key_uq UNIQUE (table_id, key)
);

CREATE INDEX IF NOT EXISTS grid_columns_table_pos_idx
  ON grid_columns (table_id, position);

CREATE TABLE IF NOT EXISTS grid_rows (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  table_id uuid NOT NULL REFERENCES grid_tables(id) ON DELETE CASCADE,
  position double precision NOT NULL,
  -- The value plane.
  cells jsonb NOT NULL DEFAULT '{}',
  -- The metadata plane: status/error/provider/cost per cell. Kept separate so
  -- the value plane stays clean and JSONB size doesn't triple.
  cell_meta jsonb NOT NULL DEFAULT '{}',
  version bigint NOT NULL DEFAULT nextval('grid_row_version_seq'),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS grid_rows_table_pos_idx
  ON grid_rows (table_id, position);
-- The polling query: WHERE table_id = $1 AND version > $2.
CREATE INDEX IF NOT EXISTS grid_rows_table_version_idx
  ON grid_rows (table_id, version);

CREATE TABLE IF NOT EXISTS grid_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  table_id uuid NOT NULL REFERENCES grid_tables(id) ON DELETE CASCADE,
  row_id uuid NOT NULL REFERENCES grid_rows(id) ON DELETE CASCADE,
  column_key text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  priority integer NOT NULL DEFAULT 0,
  attempts integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 3,
  run_after timestamptz DEFAULT now(),
  locked_at timestamptz,
  provider_state jsonb,
  error text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  -- A cell can be queued only once; re-running updates the existing job
  -- rather than stacking duplicates.
  CONSTRAINT grid_jobs_cell_uq UNIQUE (row_id, column_key)
);

-- Supports the FOR UPDATE SKIP LOCKED claim query.
CREATE INDEX IF NOT EXISTS grid_jobs_claim_idx ON grid_jobs (status, run_after);
CREATE INDEX IF NOT EXISTS grid_jobs_table_status_idx ON grid_jobs (table_id, status);

CREATE TABLE IF NOT EXISTS grid_cell_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  table_id uuid NOT NULL REFERENCES grid_tables(id) ON DELETE CASCADE,
  row_id uuid NOT NULL REFERENCES grid_rows(id) ON DELETE CASCADE,
  column_key text NOT NULL,
  provider text,
  -- 'hit' | 'miss' | 'error' | 'skipped'. Misses are recorded because they
  -- are billed too, and because hit-rate is what makes waterfalls tunable.
  outcome text NOT NULL,
  -- numeric, not integer: per-call costs are fractions of a cent.
  cost_cents numeric(12, 6) NOT NULL DEFAULT 0,
  latency_ms integer,
  request jsonb,
  response jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS grid_cell_runs_cell_idx
  ON grid_cell_runs (row_id, column_key);
CREATE INDEX IF NOT EXISTS grid_cell_runs_table_created_idx
  ON grid_cell_runs (table_id, created_at);

CREATE TABLE IF NOT EXISTS grid_providers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key text NOT NULL UNIQUE,
  name text NOT NULL,
  base_url text,
  -- The NAME of an env var, never the credential itself: this row ends up in
  -- database dumps that self-hosters share.
  auth_env_var text,
  default_cost_cents numeric(12, 6) NOT NULL DEFAULT 0,
  rate_limit_per_min integer,
  config jsonb NOT NULL DEFAULT '{}',
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS grid_provider_credentials (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id uuid NOT NULL UNIQUE REFERENCES grid_providers(id) ON DELETE CASCADE,
  encrypted_payload text NOT NULL,
  encryption_version text NOT NULL DEFAULT 'v1',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
`;

async function main() {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is not set — check .env.local");
  }

  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
  });

  await client.connect();
  try {
    await client.query(SQL);
    const { rows } = await client.query<{ table_name: string }>(
      `SELECT table_name FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name LIKE 'grid\\_%'
       ORDER BY table_name`,
    );
    console.log("grid tables present:", rows.map((r) => r.table_name).join(", "));
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
