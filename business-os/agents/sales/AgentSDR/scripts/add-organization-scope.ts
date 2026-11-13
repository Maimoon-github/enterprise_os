/**
 * Multi-tenancy, expand step: every existing row joins one initial
 * organization, and every scoped table gets the column that says so.
 *
 *   bun run --conditions=react-server scripts/add-organization-scope.ts           # plan only
 *   bun run --conditions=react-server scripts/add-organization-scope.ts --apply   # do it
 *
 * Needs (env): INITIAL_ORG_NAME, INITIAL_ORG_SLUG, INITIAL_OWNER_NAME,
 * INITIAL_OWNER_EMAIL, INITIAL_OWNER_PASSWORD — the organization the current
 * workspace becomes and the person who owns it (they sign in with that email
 * and password, or with Google on the same address). Run
 * scripts/create-auth-tables.ts first.
 *
 * What it does, in order, each step re-runnable:
 * 1. Creates the initial organization (metadata {"initial": true}) and its
 *    owner through Better Auth, so the owner membership and default team are
 *    exactly what a sign-up would have made.
 * 2. For every table in SCOPED_TABLES (src/lib/tenancy/registry.ts):
 *    `ADD COLUMN organization_id uuid NOT NULL DEFAULT '<initial org>'`.
 *    A constant default is stored in the catalog, not written to each row,
 *    so this is instant on any table size, and code that does not know about
 *    the column yet — the deployment that is live while this runs — keeps
 *    inserting valid rows. Then a foreign key (added NOT VALID, then
 *    validated, so writes are never blocked) and an index built
 *    CONCURRENTLY.
 * 3. The per-organization unique indexes (PER_ORG_UNIQUES), CONCURRENTLY.
 *    The old global uniques stay until the contract step.
 * 4. `custom jsonb` on people and companies — where per-organization custom
 *    lead fields live from now on, instead of ALTER TABLE ADD COLUMN.
 *
 * The contract step (scripts/finalize-organization-scope.ts, later) drops
 * the defaults and the old global uniques once all code sets the column.
 */
import postgres from "postgres";
import { auth } from "@/lib/auth/server";
import { PER_ORG_UNIQUES, SCOPED_TABLES } from "@/lib/tenancy/registry";

const apply = process.argv.includes("--apply");

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

const quote = (identifier: string) => `"${identifier.replace(/"/g, '""')}"`;

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set");
  const sql = postgres(process.env.DATABASE_URL, {
    ssl: process.env.DATABASE_SSL === "disable" ? false : "require",
    max: 1,
    onnotice: () => {},
  });

  try {
    const [{ present }] = await sql<{ present: boolean }[]>`select to_regclass('public.organizations') is not null as present`;
    if (!present) throw new Error("Better Auth tables are missing — run scripts/create-auth-tables.ts first");

    console.log(apply ? "Applying organization scope\n" : "Plan (pass --apply to run)\n");

    // 1. The initial organization and its owner.
    let [initial] = await sql<{ id: string; name: string }[]>`
      select id, name from organizations where metadata::jsonb ->> 'initial' = 'true' limit 1`;
    if (initial) {
      console.log(`initial organization: ${initial.name} (${initial.id}) — exists`);
    } else if (!apply) {
      console.log(`initial organization: would create "${required("INITIAL_ORG_NAME")}" owned by ${required("INITIAL_OWNER_EMAIL")}`);
    } else {
      const email = required("INITIAL_OWNER_EMAIL").toLowerCase();
      let [owner] = await sql<{ id: string }[]>`select id from users where email = ${email}`;
      if (!owner) {
        await auth.api.signUpEmail({
          body: { name: required("INITIAL_OWNER_NAME"), email, password: required("INITIAL_OWNER_PASSWORD") },
        });
        [owner] = await sql<{ id: string }[]>`select id from users where email = ${email}`;
      }
      // The owner is the person running this; their address needs no proof.
      await sql`update users set email_verified = true where id = ${owner.id}`;
      const created = await auth.api.createOrganization({
        body: {
          name: required("INITIAL_ORG_NAME"),
          slug: required("INITIAL_ORG_SLUG"),
          userId: owner.id,
          metadata: { initial: true },
        },
      });
      if (!created?.id) throw new Error("Better Auth did not create the initial organization");
      initial = { id: created.id, name: created.name };
      console.log(`initial organization: ${initial.name} (${initial.id}) — created, owner ${email}`);
    }

    // 2. organization_id on every scoped table.
    for (const { table, column } of SCOPED_TABLES) {
      const [{ exists }] = await sql<{ exists: boolean }[]>`
        select exists (select 1 from information_schema.columns
          where table_schema = 'public' and table_name = ${table} and column_name = ${column}) as exists`;
      const [{ rows }] = await sql<{ rows: number }[]>`
        select coalesce(n_live_tup, 0)::int as rows from pg_stat_user_tables where relname = ${table}`
        .then((r) => (r.length ? r : [{ rows: 0 }]));
      if (!apply) {
        console.log(`${table.padEnd(28)} ${exists ? "has column" : `would add ${column}`} (~${rows} rows)`);
        continue;
      }
      const t = quote(table);
      const c = quote(column);
      const fk = quote(`${table}_organization_fk`);
      const idx = quote(`${table}_organization_idx`);
      if (!exists) {
        await sql.begin(async (tx) => {
          await tx.unsafe(`set local lock_timeout = '5s'`);
          await tx.unsafe(`alter table ${t} add column ${c} uuid not null default '${initial!.id}'`);
        });
      }
      const [{ hasFk }] = await sql<{ hasFk: boolean }[]>`
        select exists (select 1 from pg_constraint where conname = ${`${table}_organization_fk`}) as "hasFk"`;
      if (!hasFk) {
        await sql.unsafe(`alter table ${t} add constraint ${fk} foreign key (${c}) references organizations(id) on delete restrict not valid`);
      }
      await sql.unsafe(`alter table ${t} validate constraint ${fk}`);
      await dropIfInvalid(sql, `${table}_organization_idx`);
      await sql.unsafe(`create index concurrently if not exists ${idx} on ${t} (${c})`);
      console.log(`${table.padEnd(28)} ${exists ? "column existed" : "column added"}, fk valid, indexed (~${rows} rows)`);
    }

    // 3. Per-organization uniques (the global ones stay until contract).
    for (const u of PER_ORG_UNIQUES) {
      if (!apply) {
        console.log(`unique ${u.name.padEnd(36)} would create on ${u.table} ${u.definition}`);
        continue;
      }
      await dropIfInvalid(sql, u.name);
      await sql.unsafe(`create unique index concurrently if not exists ${quote(u.name)} on ${quote(u.table)} ${u.definition}`);
      console.log(`unique ${u.name.padEnd(36)} ready`);
    }

    // 4. Custom lead fields as JSON.
    for (const table of ["people", "companies"]) {
      if (!apply) {
        console.log(`${table}.custom                 would add jsonb`);
        continue;
      }
      await sql.unsafe(`alter table ${quote(table)} add column if not exists custom jsonb not null default '{}'::jsonb`);
      console.log(`${table}.custom                 ready`);
    }

    if (apply) console.log("\nDone. Run scripts/check-organization-scope.ts to audit.");
  } finally {
    await sql.end();
  }
}

/** A CONCURRENTLY build that was interrupted leaves an INVALID index behind; rebuild it. */
async function dropIfInvalid(sql: postgres.Sql, index: string) {
  const [row] = await sql<{ valid: boolean }[]>`
    select i.indisvalid as valid from pg_index i join pg_class c on c.oid = i.indexrelid where c.relname = ${index}`;
  if (row && !row.valid) await sql.unsafe(`drop index concurrently if exists ${quote(index)}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  });
