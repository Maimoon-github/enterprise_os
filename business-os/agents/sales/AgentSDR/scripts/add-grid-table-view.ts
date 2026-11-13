/**
 * Adds the saved view (hidden columns, filters, sorts) to grid_tables.
 *
 * Run with:  bun run scripts/add-grid-table-view.ts
 *
 * This is what "Default view" in the toolbar reads and writes. Re-runnable.
 */
import { Client } from "pg";

const SQL = `
ALTER TABLE grid_tables
  ADD COLUMN IF NOT EXISTS view jsonb NOT NULL DEFAULT '{}'::jsonb;
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
    const { rows } = await client.query<{ column_name: string }>(
      `SELECT column_name FROM information_schema.columns
       WHERE table_name = 'grid_tables' AND column_name = 'view'`,
    );
    console.log(rows.length ? "grid_tables.view present" : "FAILED to add grid_tables.view");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
