/**
 * Adds workbooks above tables, so one workbook holds several tables shown as
 * sheet tabs along the bottom — the structure Clay uses.
 *
 * Run with:  bun run scripts/add-grid-workbooks.ts
 *
 * Re-runnable. Existing grid_tables rows are adopted into a single "Untitled
 * workbook" rather than being orphaned, which is why workbook_id is added
 * nullable, backfilled, and only then made NOT NULL.
 */
import { Client } from "pg";

const SQL = `
CREATE TABLE IF NOT EXISTS grid_workbooks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Sheet-tab ordering. Fractional, so dragging a tab rewrites one row.
ALTER TABLE grid_tables ADD COLUMN IF NOT EXISTS position double precision;
ALTER TABLE grid_tables ADD COLUMN IF NOT EXISTS workbook_id uuid;

DO $$
DECLARE
  fallback_id uuid;
BEGIN
  -- Only adopt orphans if there are any, so a re-run creates nothing.
  IF EXISTS (SELECT 1 FROM grid_tables WHERE workbook_id IS NULL) THEN
    SELECT id INTO fallback_id FROM grid_workbooks WHERE name = 'Untitled workbook' LIMIT 1;
    IF fallback_id IS NULL THEN
      INSERT INTO grid_workbooks (name) VALUES ('Untitled workbook') RETURNING id INTO fallback_id;
    END IF;
    UPDATE grid_tables SET workbook_id = fallback_id WHERE workbook_id IS NULL;
  END IF;
END $$;

UPDATE grid_tables SET position = extract(epoch FROM created_at) WHERE position IS NULL;

ALTER TABLE grid_tables ALTER COLUMN position SET NOT NULL;
ALTER TABLE grid_tables ALTER COLUMN workbook_id SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'grid_tables_workbook_fk'
  ) THEN
    ALTER TABLE grid_tables
      ADD CONSTRAINT grid_tables_workbook_fk
      FOREIGN KEY (workbook_id) REFERENCES grid_workbooks(id) ON DELETE CASCADE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS grid_tables_workbook_pos_idx
  ON grid_tables (workbook_id, position);
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
    const { rows } = await client.query<{ workbooks: string; tables: string }>(
      `SELECT
         (SELECT count(*) FROM grid_workbooks)::text AS workbooks,
         (SELECT count(*) FROM grid_tables)::text AS tables`,
    );
    console.log(`workbooks: ${rows[0].workbooks}, tables: ${rows[0].tables}`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
