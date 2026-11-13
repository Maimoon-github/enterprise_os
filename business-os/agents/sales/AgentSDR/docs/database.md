---
title: "Database"
description: "Schema files, fresh-install tooling, migration history, the tenancy registry and the connection pool."
icon: "database"
---

PostgreSQL 16 or newer, accessed with Drizzle ORM over the `postgres` driver.
One database holds everything.

## Schema files

Drizzle table definitions live in domain-scoped files. `src/lib/schema.ts` is
the entry point (`drizzle.config.ts` points at it) and re-exports the rest.

| File | Tables |
|---|---|
| `src/lib/auth/schema.ts` | Better Auth: users, sessions, accounts, verifications, organizations, members, invitations, teams, team_members |
| `src/lib/outreach/schema.ts` | Email campaigns, leads, mailboxes, emails, send queue, suppression list |
| `src/lib/crm/schema.ts` | CRM workflow, conversations, sequences, knowledge |
| `src/lib/inbox/schema.ts` | Master Inbox and inbound-delivery diagnostics |
| `src/lib/qualification/schema.ts` | Domain qualification |
| `src/lib/grid/schema.ts` | Tables (enrichment), providers and their encrypted credentials |
| `src/lib/calls/schema.ts` | WhatsApp calls placed from the app (`call_sessions`) and call campaigns |
| `src/lib/whatsapp/schema.ts` | WhatsApp accounts, chats and messages |
| `src/lib/leads/schema.ts` | The lead database: `people`, `companies`, `entity_columns`, `import_runs` |
| `src/lib/linkedin/schema.ts` | The LinkedIn tables (quoted PascalCase) |

## Fresh installs: `db/`

- `db/schema.sql` is the complete current schema, **generated** by
  `bun run db:schema:dump` (a `pg_dump --schema-only` made deterministic and
  portable; it applies to PostgreSQL 16 and newer). Do not edit it by hand.
  Legacy tables that no code uses (`LEGACY_UNUSED` in the tenancy registry) are
  left out.
- `db/seed.sql` holds reference rows every install needs (CRM categories and
  status configuration). It uses `ON CONFLICT DO NOTHING`.
- `bun run db:setup` (`scripts/db/setup.ts`) applies both in one transaction to
  an **empty** database, and refuses a database that already has tables. A
  failure leaves the database untouched.
- `bun run db:check` audits a database against the tenancy registry (see
  below).

## Migration history: `scripts/`

`scripts/*.ts` and `scripts/*.js` are one-shot migrations, run by hand, each
loading `.env.local` and connecting with `DATABASE_URL`. Nothing in `src/`
imports them. `drizzle.config.ts` declares `out: "./drizzle"`, but no
`drizzle/` directory has ever been generated, so **these scripts are the written
record of how the schema was built**, and the way an existing install moves
forward. Do not delete them as dead code.

Conventions:

- Guard DDL with `IF NOT EXISTS` / `IF EXISTS` so re-running is safe.
- Seed scripts upsert, not blind-insert.
- New migrations are TypeScript, run with `bun run scripts/<name>.ts`.
- Adding a column means updating both the migration and the matching Drizzle
  schema; they are kept in sync by hand.
- After applying a migration, run `bun run db:schema:dump` and commit
  `db/schema.sql` with it.

The workflow is spelled out in [development.md](development.md#changing-the-database).
The people-data migration scripts (`preflight-*`, `rollback-*`, `audit-*` and
so on) belong to a one-time migration documented in [design/](https://github.com/Kandid-ai/AgentSDR/blob/main/docs/design/README.md).

## drizzle-kit and `OWNED_TABLES`

`drizzle.config.ts` sets `tablesFilter` to an allowlist, `OWNED_TABLES`, of the
application-owned snake_case tables. Without a filter drizzle-kit treats every
table it does not know as drift and offers to **drop** it.

- **When you add a snake_case table, add it to `OWNED_TABLES`**, or drizzle-kit
  will not manage it.
- **The lead database is the exception.** `people`, `companies`,
  `entity_columns` and `import_runs` are deliberately **not** in the list.
  `people` and `companies` gain columns at runtime: the column settings UI runs
  `ALTER TABLE ... ADD COLUMN` (`src/lib/leads/columns.ts`). Their Drizzle
  definitions therefore describe the core columns only. If they were in the
  allowlist, drizzle-kit would read that partial definition as the truth, see
  every user-added column as drift and offer to drop it, destroying user data on
  the next `push`. The other two are excluded so the rule stays one sentence.
  The lead database is hand-maintained through `scripts/create-lead-tables.ts`.
- `entity_columns` is the registry of those runtime columns. A column name
  reaches SQL only after matching a registry row, which is what makes dynamic
  column names safe. `bun run scripts/check-lead-column-drift.ts` verifies the
  registry and the physical schema agree.
- **The LinkedIn tables are also excluded**, for the same reason: drizzle-kit
  must have no way to alter live LinkedIn data. Change them with a one-shot
  migration in `scripts/` and update `src/lib/linkedin/schema.ts` by hand. They
  came from a former Prisma schema and keep quoted PascalCase names, with
  `text` ids (cuid) rather than `uuid`, to avoid an `ALTER TYPE` across every id
  and foreign key. New rows use `$defaultFn(createId)`. The archived Prisma
  migrations are in [prisma-history/](https://github.com/Kandid-ai/AgentSDR/blob/main/docs/prisma-history/README.md); nothing there
  runs.

In practice, do not run `drizzle-kit push` against a database you care about.
Use migration scripts.

## Tenancy registry

`src/lib/tenancy/registry.ts` classifies every table: **scoped** (own
`organization_id`; `"organizationId"` on the LinkedIn tables), **inherited**
(scoped through a NOT NULL foreign key to a parent), **global**, **auth**, or
**legacy**. It also lists the uniques that are per organization
(`PER_ORG_UNIQUES`: people email and LinkedIn URL, company domain, suppression
email, pipeline name, `grid_providers.key`, and so on). The migration scripts,
`db:check` and the isolation test all read it, so they cannot disagree. A new
table that nobody classified fails `db:check`. The rules for queries are in
[multi-tenancy/conventions.md](multi-tenancy/conventions.md).

## Connection pool

`max_connections` on the server is shared by everything that points at it. The
app has one pool, `DB_POOL_MAX` connections (default 8), in `src/lib/db.ts`;
Better Auth reuses it, so never create another pool in app code. When the server
is full every query fails at once with `remaining connection slots are reserved
for roles with the SUPERUSER attribute`: that is capacity, not a code bug.
Before raising `DB_POOL_MAX`, check `pg_stat_activity`, and remember a rolling
deploy briefly runs two containers. The connection uses TLS unless
`DATABASE_SSL=disable`.
