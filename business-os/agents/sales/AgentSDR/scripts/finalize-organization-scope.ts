/**
 * Multi-tenancy, contract step — run AFTER the organization-aware code is
 * deployed (and the old single-workspace code is gone):
 *
 *   bun run scripts/finalize-organization-scope.ts           # plan only
 *   bun run scripts/finalize-organization-scope.ts --apply   # do it
 *
 * 1. Drops the old global uniques the per-organization ones replaced
 *    (PER_ORG_UNIQUES[].global). Until now they kept the deployed old code's
 *    ON CONFLICT targets valid; afterwards a second organization can hold the
 *    same email, domain, pipeline name, integration key, …
 * 2. Drops the `DEFAULT '<initial organization>'` on every organization
 *    column. The expand step put it there so old code kept inserting valid
 *    rows; from here on an insert that does not say which organization it is
 *    for fails, instead of silently landing in the initial organization.
 *
 * Re-runnable. Run scripts/check-organization-scope.ts --contract afterwards.
 */
import postgres from "postgres";
import { PER_ORG_UNIQUES, SCOPED_TABLES } from "@/lib/tenancy/registry";

const apply = process.argv.includes("--apply");
const quote = (identifier: string) => `"${identifier.replace(/"/g, '""')}"`;

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set");
  const sql = postgres(process.env.DATABASE_URL, {
    ssl: process.env.DATABASE_SSL === "disable" ? false : "require",
    max: 1,
    onnotice: () => {},
  });
  try {
    console.log(apply ? "Contract: applying\n" : "Contract: plan (pass --apply to run)\n");

    for (const u of PER_ORG_UNIQUES) {
      const [replacement] = await sql<{ valid: boolean }[]>`
        select i.indisvalid as valid from pg_index i join pg_class c on c.oid = i.indexrelid where c.relname = ${u.name}`;
      if (!replacement?.valid) throw new Error(`${u.name} is missing or invalid — run add-organization-scope.ts first`);

      const [constraint] = await sql<{ conname: string }[]>`
        select conname from pg_constraint where conname = ${u.global} and conrelid = ${u.table}::regclass`;
      const [index] = await sql<{ relname: string }[]>`select relname from pg_class where relname = ${u.global} and relkind = 'i'`;
      if (!constraint && !index) {
        console.log(`global unique ${u.global.padEnd(38)} already gone`);
        continue;
      }
      if (!apply) {
        console.log(`global unique ${u.global.padEnd(38)} would drop (${constraint ? "constraint" : "index"} on ${u.table})`);
        continue;
      }
      if (constraint) await sql.unsafe(`alter table ${quote(u.table)} drop constraint ${quote(u.global)}`);
      else await sql.unsafe(`drop index concurrently if exists ${quote(u.global)}`);
      console.log(`global unique ${u.global.padEnd(38)} dropped`);
    }

    for (const { table, column } of SCOPED_TABLES) {
      const [col] = await sql<{ hasDefault: boolean }[]>`
        select column_default is not null as "hasDefault" from information_schema.columns
        where table_schema = 'public' and table_name = ${table} and column_name = ${column}`;
      if (!col) throw new Error(`${table}.${column} is missing — run add-organization-scope.ts first`);
      if (!col.hasDefault) {
        console.log(`${table.padEnd(28)} no default`);
        continue;
      }
      if (!apply) {
        console.log(`${table.padEnd(28)} would drop the organization default`);
        continue;
      }
      await sql.begin(async (tx) => {
        await tx.unsafe(`set local lock_timeout = '5s'`);
        await tx.unsafe(`alter table ${quote(table)} alter column ${quote(column)} drop default`);
      });
      console.log(`${table.padEnd(28)} organization default dropped`);
    }
    if (apply) console.log("\nDone. Run scripts/check-organization-scope.ts --contract to audit.");
  } finally {
    await sql.end();
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  });
