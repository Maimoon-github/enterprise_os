/**
 * Groups LinkedIn search URLs into named batches ("searches"), the way
 * campaigns group leads.
 *
 *   bun run scripts/create-search-batches.ts --apply
 *
 * Creates the "SearchBatch" table and adds "SearchQuery"."batchId". Every
 * SearchQuery that predates this change is moved into one batch called
 * "Earlier searches" so the column can be NOT NULL and nothing is lost.
 *
 * Every statement is guarded so re-running is safe. Keep in sync with
 * src/lib/linkedin/schema.ts. These are LinkedIn (PascalCase) tables, so
 * they are outside drizzle-kit's OWNED_TABLES and hand-maintained here.
 *
 * Bun loads .env.local automatically.
 */
import { Client } from "pg";
import { createId } from "@paralleldrive/cuid2";

const SQL = `
DO $$ BEGIN
  CREATE TYPE "SearchBatchKind" AS ENUM ('SINGLE', 'BULK');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS "SearchBatch" (
  "id"         text PRIMARY KEY,
  "name"       text NOT NULL,
  "kind"       "SearchBatchKind" NOT NULL DEFAULT 'BULK',
  "accountIds" jsonb NOT NULL DEFAULT '[]'::jsonb,
  "createdAt"  timestamp(3) NOT NULL DEFAULT now(),
  "updatedAt"  timestamp(3) NOT NULL
);

ALTER TABLE "SearchQuery" ADD COLUMN IF NOT EXISTS "batchId" text;
CREATE INDEX IF NOT EXISTS "SearchQuery_batchId_idx" ON "SearchQuery" ("batchId");
`;

const LEGACY_BATCH_NAME = "Earlier searches";

async function main() {
  if (!process.argv.includes("--apply")) {
    throw new Error("Refusing to modify the database without --apply.");
  }
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is not set — check .env.local");
  }

  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });

  await client.connect();
  try {
    await client.query("SET lock_timeout = '5s'");
    await client.query("SET statement_timeout = '2min'");
    await client.query(SQL);

    // Fold orphaned queries into one legacy batch. Idempotent: only runs when
    // there is something to fold, and reuses the legacy batch if it exists.
    const { rows: orphans } = await client.query<{ n: string }>(
      `SELECT count(*)::text AS n FROM "SearchQuery" WHERE "batchId" IS NULL`,
    );
    if (Number(orphans[0].n) > 0) {
      const { rows: existing } = await client.query<{ id: string }>(
        `SELECT id FROM "SearchBatch" WHERE name = $1 ORDER BY "createdAt" LIMIT 1`,
        [LEGACY_BATCH_NAME],
      );
      let batchId = existing[0]?.id;
      if (!batchId) {
        batchId = createId();
        await client.query(
          `INSERT INTO "SearchBatch" (id, name, kind, "updatedAt") VALUES ($1, $2, 'BULK', now())`,
          [batchId, LEGACY_BATCH_NAME],
        );
      }
      const { rowCount } = await client.query(
        `UPDATE "SearchQuery" SET "batchId" = $1 WHERE "batchId" IS NULL`,
        [batchId],
      );
      console.log(`moved ${rowCount} earlier search(es) into "${LEGACY_BATCH_NAME}" (${batchId})`);
    }

    await client.query(`
      ALTER TABLE "SearchQuery" ALTER COLUMN "batchId" SET NOT NULL;
      DO $$ BEGIN
        ALTER TABLE "SearchQuery"
          ADD CONSTRAINT "SearchQuery_batchId_fkey"
          FOREIGN KEY ("batchId") REFERENCES "SearchBatch"(id) ON DELETE CASCADE;
      EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    `);

    const { rows: counts } = await client.query<{ batches: string; queries: string }>(
      `SELECT (SELECT count(*) FROM "SearchBatch")::text AS batches,
              (SELECT count(*) FROM "SearchQuery")::text AS queries`,
    );
    console.log(`search batches: ${counts[0].batches}, search queries: ${counts[0].queries}`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
