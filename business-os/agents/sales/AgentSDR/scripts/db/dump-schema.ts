/**
 * Regenerates db/schema.sql — the complete current schema a fresh install
 * starts from — from a database that has every migration applied.
 *
 *   bun run db:schema:dump
 *
 * Workflow when you change the schema: write the migration in scripts/ (the
 * history, see CLAUDE.md), apply it to your local database, update the
 * Drizzle definition, then run this and commit db/schema.sql with the rest.
 *
 * Needs `pg_dump` at least as new as the database server (set PG_DUMP to a
 * specific binary if the one on PATH is older). The output is made
 * deterministic and portable: the server/client version banners and the
 * per-dump `\restrict` keys are removed, as is `SET transaction_timeout`
 * (PostgreSQL 17+ only), so the file applies cleanly to PostgreSQL 16+ and
 * diffs only when the schema really changes; `CREATE SCHEMA public` becomes
 * IF NOT EXISTS because every database already has it. Legacy tables no code uses
 * (LEGACY_UNUSED in src/lib/tenancy/registry.ts, which includes Prisma's old
 * migration ledger) are left out.
 */
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { LEGACY_UNUSED } from "@/lib/tenancy/registry";

const OUT = join(import.meta.dir, "..", "..", "db", "schema.sql");

const HEADER = `-- AgentSDR database schema — GENERATED, do not edit by hand.
--
-- Regenerate with \`bun run db:schema:dump\` after applying a migration;
-- apply to an empty database with \`bun run db:setup\`.
-- The migrations that built it, in order, are in scripts/ (see CLAUDE.md).
`;

/** Lines that would make the file differ between dumps, or fail on older servers. */
function normalize(dump: string): string {
  const lines = dump.split("\n").filter((line) => {
    if (/^\\(un)?restrict /.test(line)) return false;
    if (/^-- Dumped (from database|by pg_dump) version/.test(line)) return false;
    if (/^SET transaction_timeout/.test(line)) return false;
    return true;
  });
  // Every database already has `public`; keep the statement but make it idempotent.
  const text = lines.join("\n").replace(/^CREATE SCHEMA public;$/m, "CREATE SCHEMA IF NOT EXISTS public;");
  // Collapse the blank-line runs left behind.
  return text.replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

async function main() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set");
  const pgDump = process.env.PG_DUMP ?? "pg_dump";
  const excluded = LEGACY_UNUSED.map((table) => `--exclude-table=public.${table}`);

  const child = Bun.spawn(
    [pgDump, "--schema-only", "--no-owner", "--no-privileges", "--no-comments", "--schema=public", ...excluded, "--dbname", url],
    {
      env: { ...process.env, PGSSLMODE: process.env.DATABASE_SSL === "disable" ? "disable" : "require" },
      stdout: "pipe",
      stderr: "pipe",
    },
  );
  const [stdout, stderr, code] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  if (code !== 0) {
    throw new Error(`pg_dump failed (${code}): ${stderr.replace(/postgres(ql)?:\/\/\S+/g, "<url>").slice(0, 400)}`);
  }

  const schema = HEADER + "\n" + normalize(stdout);
  await writeFile(OUT, schema);
  const tables = (schema.match(/^CREATE TABLE /gm) ?? []).length;
  console.log(`db/schema.sql written — ${tables} tables, ${schema.split("\n").length} lines`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
