/**
 * Audits the database against the tenancy registry and exits non-zero on
 * any gap. Read-only.
 *
 *   bun run scripts/check-organization-scope.ts
 *
 * Checks:
 * - every live table is classified (scoped, inherited, global, auth, or
 *   legacy) — a new table nobody classified is a leak waiting to happen;
 * - every scoped table has its organization column, NOT NULL, with a valid
 *   foreign key to organizations and a valid index;
 * - every inherited table really is held by a NOT NULL foreign key to the
 *   parent the registry names;
 * - every per-organization unique index exists and is valid;
 * - people and companies have `custom jsonb`.
 * - with --contract (after scripts/finalize-organization-scope.ts): no
 *   organization column still has a default, and no replaced global unique
 *   remains.
 * It also reports how rows split across organizations.
 */
import postgres from "postgres";
import {
  AUTH_TABLES,
  GLOBAL,
  INHERITED,
  LEGACY_UNUSED,
  PER_ORG_UNIQUES,
  SCOPED_TABLES,
} from "@/lib/tenancy/registry";

const contract = process.argv.includes("--contract");
const problems: string[] = [];
const fail = (message: string) => problems.push(message);

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set");
  const sql = postgres(process.env.DATABASE_URL, {
    ssl: process.env.DATABASE_SSL === "disable" ? false : "require",
    max: 1,
  });
  try {
    const live = (await sql<{ name: string }[]>`
      select c.relname as name from pg_class c join pg_namespace n on n.oid = c.relnamespace
      where n.nspname = 'public' and c.relkind in ('r', 'p')`).map((r) => r.name);

    const known = new Set([
      ...SCOPED_TABLES.map((s) => s.table),
      ...Object.keys(INHERITED),
      ...GLOBAL,
      ...LEGACY_UNUSED,
      ...AUTH_TABLES,
    ]);
    for (const table of live) if (!known.has(table)) fail(`unclassified table: ${table} — add it to src/lib/tenancy/registry.ts`);
    for (const table of known) if (!live.includes(table) && !LEGACY_UNUSED.includes(table)) fail(`registry names a table that does not exist: ${table}`);

    for (const { table, column } of SCOPED_TABLES) {
      const [col] = await sql<{ notnull: boolean }[]>`
        select a.attnotnull as notnull from pg_attribute a join pg_class c on c.oid = a.attrelid
        where c.relname = ${table} and a.attname = ${column} and not a.attisdropped`;
      if (!col) { fail(`${table}: missing ${column}`); continue; }
      if (!col.notnull) fail(`${table}.${column} is nullable`);

      const [fk] = await sql<{ valid: boolean }[]>`
        select con.convalidated as valid from pg_constraint con
        join pg_class c on c.oid = con.conrelid
        join pg_attribute a on a.attrelid = con.conrelid and a.attnum = any(con.conkey)
        where con.contype = 'f' and c.relname = ${table} and a.attname = ${column}
          and con.confrelid = 'organizations'::regclass`;
      if (!fk) fail(`${table}.${column} has no foreign key to organizations`);
      else if (!fk.valid) fail(`${table}.${column} foreign key is NOT VALID`);

      const [idx] = await sql<{ valid: boolean }[]>`
        select bool_and(i.indisvalid) as valid from pg_index i
        join pg_class c on c.oid = i.indrelid
        join pg_attribute a on a.attrelid = i.indrelid and a.attnum = i.indkey[0]
        where c.relname = ${table} and a.attname = ${column}`;
      if (!idx || idx.valid === null) fail(`${table}.${column} is not the leading column of any index`);
      else if (!idx.valid) fail(`${table}.${column} has an INVALID index`);
    }

    for (const [child, parent] of Object.entries(INHERITED)) {
      const [link] = await sql<{ notnull: boolean }[]>`
        select bool_and(a.attnotnull) as notnull from pg_constraint con
        join pg_class c on c.oid = con.conrelid
        join pg_class p on p.oid = con.confrelid
        join pg_attribute a on a.attrelid = con.conrelid and a.attnum = any(con.conkey)
        where con.contype = 'f' and c.relname = ${child} and p.relname = ${parent}`;
      if (!link || link.notnull === null) fail(`${child}: no foreign key to ${parent}, so it does not inherit scope`);
      else if (!link.notnull) fail(`${child} → ${parent} foreign key is nullable, so rows can escape scope`);
    }

    for (const u of PER_ORG_UNIQUES) {
      const [idx] = await sql<{ valid: boolean; unique: boolean }[]>`
        select i.indisvalid as valid, i.indisunique as unique from pg_index i
        join pg_class c on c.oid = i.indexrelid where c.relname = ${u.name}`;
      if (!idx) fail(`missing unique index ${u.name} on ${u.table}`);
      else if (!idx.valid || !idx.unique) fail(`unique index ${u.name} is invalid`);
    }

    if (contract) {
      for (const { table, column } of SCOPED_TABLES) {
        const [col] = await sql<{ hasDefault: boolean }[]>`
          select column_default is not null as "hasDefault" from information_schema.columns
          where table_name = ${table} and column_name = ${column}`;
        if (col?.hasDefault) fail(`${table}.${column} still has a default (run finalize-organization-scope.ts)`);
      }
      for (const u of PER_ORG_UNIQUES) {
        const [left] = await sql`select 1 from pg_class where relname = ${u.global}`;
        if (left) fail(`old global unique ${u.global} still exists on ${u.table}`);
      }
    }

    for (const table of ["people", "companies"]) {
      const [col] = await sql`select 1 from information_schema.columns where table_name = ${table} and column_name = 'custom' and data_type = 'jsonb'`;
      if (!col) fail(`${table}.custom (jsonb) is missing`);
    }

    // Informational: rows per organization.
    const orgs = await sql<{ id: string; name: string }[]>`select id, name from organizations order by created_at`;
    console.log(`organizations: ${orgs.map((o) => o.name).join(", ") || "none"}`);
    for (const { table, column } of SCOPED_TABLES) {
      const present = await sql`select 1 from information_schema.columns where table_name = ${table} and column_name = ${column}`;
      if (!present.length) continue;
      const split = await sql.unsafe<{ org: string; n: number }[]>(
        `select o.name as org, count(*)::int as n from "${table}" t join organizations o on o.id = t."${column}" group by o.name order by 2 desc`,
      );
      console.log(`  ${table.padEnd(28)} ${split.map((s) => `${s.org}: ${s.n}`).join(", ") || "empty"}`);
    }
  } finally {
    await sql.end();
  }

  if (problems.length) {
    console.log(`\n${problems.length} problem(s):`);
    for (const problem of problems) console.log(`  ✗ ${problem}`);
    process.exit(1);
  }
  console.log("\nOrganization scope: all checks pass.");
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
