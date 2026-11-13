/**
 * Adds folders above workbooks on the All Files screen, so the "New > Folder"
 * entry has somewhere to put things.
 *
 * Run with:  bun run scripts/add-grid-folders.ts
 *
 * Re-runnable. Folders nest through parent_id and cascade on delete; a
 * workbook's folder_id is ON DELETE SET NULL instead, because deleting a
 * folder should not silently destroy the tables inside it — the workbooks
 * fall back to the root listing where the user can see and re-file them.
 */
import { Client } from "pg";

const SQL = `
CREATE TABLE IF NOT EXISTS grid_folders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  -- NULL means the folder sits at the root of All Files.
  parent_id uuid REFERENCES grid_folders(id) ON DELETE CASCADE,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS grid_folders_parent_idx ON grid_folders (parent_id);

-- NULL means the workbook sits at the root, which is where every existing
-- workbook stays after this migration.
ALTER TABLE grid_workbooks ADD COLUMN IF NOT EXISTS folder_id uuid;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'grid_workbooks_folder_fk'
  ) THEN
    ALTER TABLE grid_workbooks
      ADD CONSTRAINT grid_workbooks_folder_fk
      FOREIGN KEY (folder_id) REFERENCES grid_folders(id) ON DELETE SET NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS grid_workbooks_folder_idx ON grid_workbooks (folder_id);
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
    const { rows } = await client.query<{ folders: string; rooted: string }>(
      `SELECT
         (SELECT count(*) FROM grid_folders)::text AS folders,
         (SELECT count(*) FROM grid_workbooks WHERE folder_id IS NULL)::text AS rooted`,
    );
    console.log(`folders: ${rows[0].folders}, workbooks at root: ${rows[0].rooted}`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
