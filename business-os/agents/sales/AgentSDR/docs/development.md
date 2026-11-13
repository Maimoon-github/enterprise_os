---
title: "Development"
description: "Local setup, scripts, tests, database changes and code conventions."
icon: "code"
---

How to run AgentSDR locally, test it, and change it. Read
[architecture.md](architecture.md) first for the shape of the code.

## Prerequisites

- [Bun](https://bun.sh) 1.2 or newer (`packageManager` is `bun@1.3.14`). The
  repository's scripts and test runner use Bun.
- Node.js 20.9 or newer (`.nvmrc` pins 24). Next.js runs on it.
- A local PostgreSQL 16+ server and an empty database.
- `pg_dump` at least as new as your server, only if you regenerate
  `db/schema.sql`.

## Local setup

```sh
git clone https://github.com/Kandid-ai/AgentSDR.git
cd AgentSDR
bun install
createdb agentsdr                  # or any empty database
cp .env.example .env.local
```

Edit `.env.local`. For local development you need:

| Variable | Local value |
|---|---|
| `DATABASE_URL` | `postgres://user:password@localhost:5432/agentsdr` |
| `DATABASE_SSL` | `disable` (a local server rarely has TLS) |
| `BETTER_AUTH_SECRET` | any 32+ character string |
| `BETTER_AUTH_URL` | `http://localhost:3000` |
| `INTEGRATION_CREDENTIALS_KEY` | any long random string |
| `UNSUBSCRIBE_SECRET` | any random string, if you will send email |

`RESEND_API_KEY` can stay empty: sign-up and invitation emails are written to
the terminal running the dev server. The other variables
are optional ([configuration.md](configuration.md)). Third-party services are
connected in Settings once the app runs, not here.

Then create the schema and start the app:

```sh
bun run db:setup          # applies db/schema.sql + db/seed.sql to an EMPTY database
bun run db:seed:demo      # optional: demo user and a fictional organization
bun run dev               # http://localhost:3000
```

`db:seed:demo` creates `demo@example.com` with password `demo-password-123` in
"Northwind", a fictional company with three months of outbound on every
channel (scripts/db/demo/). Add `DEMO_MODE=true` to browse it the way the
public demo does: no sign-in, read-only ([Public demo](self-hosting/demo.mdx)). Without it,
sign up at `/sign-up` yourself (the verification link appears in the dev server
log) and create an organization at `/onboarding`.

`db:setup` refuses a database that already has tables. To start over, drop and
recreate the database.

## Scripts

All from `package.json`. `bun run <name>`.

| Script | What it does |
|---|---|
| `dev` | `next dev` on port 3000. Also starts the enrichment and CRM workers. The outreach scheduler is production-only. |
| `build` | `next build` (standalone output). |
| `start` | `next start`. |
| `lint` | `eslint`. |
| `typecheck` | `tsc --noEmit`. |
| `test` | `bun test --conditions=react-server` (see below). |
| `db:setup` | Create the schema in an empty database. |
| `db:schema:dump` | Regenerate `db/schema.sql` from a migrated database. |
| `db:check` | Audit the database against the tenancy registry (`scripts/check-organization-scope.ts --contract`). |
| `build:recorder` | Build the WhatsApp recorder extension into `extensions/whatsapp-recorder/dist`. |
| `rotate:integration-credentials` | Re-encrypt stored integration credentials after a key change. |
| `test:integrations:live` | Call real enrichment providers with a test person (needs `LIVE_TEST_PERSON` or `--person`); not part of the test suite. |
| `preflight:people`, `postflight:people`, `snapshot:outreach`, `audit:*`, `replay:linkedin-webhooks`, `cleanup:crm-identity`, `resolve:legacy-linkedin`, `rollback:people`, `export:people-reconciliation` | Tooling from the unified-People data migration. Run only if you are reading [design/people-migration-cutover-rollback-runbook.md](https://github.com/Kandid-ai/AgentSDR/blob/main/docs/design/people-migration-cutover-rollback-runbook.md). |

## Testing

```sh
npm test            # same as: bun test --conditions=react-server
bun test --conditions=react-server src/lib/outreach     # a subset
```

- The suite runs under **Bun**. Roughly half the files import `bun:test` and
  half import `node:test`; Bun runs both. `node --test` does not work (it fails
  on the first `bun:test` import).
- `--conditions=react-server` is required: several modules import
  `server-only`, which throws outside that condition. The scripts in `scripts/`
  that call app code pass the same flag.
- Tests that call library code which reads the organization scope run inside
  `runInOrganization("00000000-0000-0000-0000-00000000000a", ...)`.
- No test needs a database or network.

### Auth policies test

`scripts/e2e/auth-policies.ts` checks the sign-up modes (`AUTH_SIGNUP`),
organization creation and the platform operator through Better Auth against a
real database. It needs a freshly set-up empty database (`bun run db:setup`),
because it asserts on the "first account" and "first organization" rules, needs
no server, and refuses to run unless `DATABASE_URL` points at localhost. CI
runs it.

```sh
bun --conditions=react-server scripts/e2e/auth-policies.ts
```

### Tenancy isolation test

`scripts/e2e/tenancy-isolation.ts` checks, end to end, that a member of a
second organization cannot see, change or count anything of the first. It
drives a **running server** over HTTP:

```sh
# terminal 1: a server on a disposable, populated local database, with sign-up
# open so the test can create organization B (it is invite-only by default)
AUTH_SIGNUP=open bun run dev -- -p 3100
# terminal 2:
BASE_URL=http://localhost:3100 \
INITIAL_OWNER_EMAIL=... INITIAL_OWNER_PASSWORD=... \
bun run --conditions=react-server scripts/e2e/tenancy-isolation.ts
```

Organization A is the one flagged initial (an install migrated from the
single-workspace version), otherwise the first one the owner owns, so a fresh
database with `bun run db:seed:demo` works with `demo@example.com` /
`demo-password-123`. It signs in as organization A's owner, creates a second user and organization,
and fires reads and writes at A's ids, scanning every response for A's
identifiers. It **refuses to run unless `DATABASE_URL` points at localhost**
(exit code 2), because it creates users and sends mutations. Set
`ISOLATION_SKIP_WRITES=1` to skip the write phase.

## Typecheck and lint

```sh
npx tsc --noEmit      # or: bun run typecheck. Must pass before committing.
bun run lint
```

## Changing the database

The schema's history is the set of migration scripts in `scripts/`; Drizzle
definitions in `src/lib/**/schema.ts` are kept in sync by hand;
`db/schema.sql` is generated. To change the schema:

1. Write a migration as a new **TypeScript** file in `scripts/`, run with
   `bun run scripts/<name>.ts`. It loads `.env.local`, connects with
   `DATABASE_URL`, guards DDL with `IF NOT EXISTS` / `IF EXISTS`, and is safe to
   re-run. Seed scripts upsert rather than blind-insert.
2. Update the matching Drizzle schema in `src/lib/<domain>/schema.ts`.
3. Apply the migration to your local database.
4. Regenerate the snapshot: `bun run db:schema:dump`, and commit
   `db/schema.sql` together with the migration and the Drizzle change.
5. If you added a table, classify it in `src/lib/tenancy/registry.ts` (scoped,
   inherited, global, auth or legacy), and add a snake_case table to
   `OWNED_TABLES` in `drizzle.config.ts` (except the lead-database tables, see
   [database.md](database.md)). Give every scoped table an `organization_id`
   with an index.
6. Run `bun run db:check`. It fails if a table is unclassified or a scoped table
   is missing its organization column.

Reference rows every install needs go in `db/seed.sql`.
See [database.md](database.md) for the reasoning and caveats.

## Code conventions

- **TypeScript only.** New code is `.ts` / `.tsx`, including scripts. Do not add
  `.js` or `.mjs` files. (Existing older scripts are `.js`.)
- **Tenancy.** Every query of a scoped table filters with `inOrg(table)`;
  every insert sets `organizationId: currentOrganizationId()`; an id from
  another organization answers 404, not 403. API routes open the scope with
  `withOrgContext`; workers and webhooks resolve the organization from the data
  and call `runInOrganization`. Full rules:
  [multi-tenancy/conventions.md](multi-tenancy/conventions.md).
- **Integrations.** Never read a third-party key from `process.env`. Use
  `getPlatformCredentials` / `requirePlatformCredentials` from
  `src/lib/platform/credentials.ts`; user-facing routes answer 409 when it is
  not connected and background jobs return early.
- **Drizzle is the only ORM.** No Prisma.
- **`.server.ts` siblings.** `postgres` cannot be bundled for the browser. When
  a module has pure helpers a client component imports and database calls,
  put the queries in a `.server.ts` sibling (for example
  `src/lib/linkedin/inviteRetry.ts` and `inviteRetry.server.ts`). Adding a `db`
  import to a client-safe module breaks the build with `Can't resolve 'fs'`.
  `import type` from a query module is always safe.
- **Two `cn()` helpers.** `@/utils/cn` extends tailwind-merge with the AlignUI
  typography groups; `@/lib/linkedin/utils` is plain `twMerge(clsx())`. They
  are not interchangeable: keep LinkedIn components on the latter.
- **Connection pool.** Do not create another `postgres()` pool in app code; use
  `db` from `src/lib/db.ts`.
- **Commits.** One logical change per commit, with a message in the form
  `Area: summary` (for example `Outreach: skip suppressed addresses`).

## Recorder extension

```sh
bun run build:recorder
```

builds `extensions/whatsapp-recorder/src/{background,wa-hook,wa-agent,bridge}.ts`
into `extensions/whatsapp-recorder/dist/` (gitignored) and copies
`static/` (manifest and icons) next to it. Load `dist/` as an unpacked
extension at `chrome://extensions`. It imports `src/lib/calls/contract.ts`; keep
that file free of runtime imports. The origins it accepts are the built-in
ones in `src/origins.ts` (in sync with `static/manifest.json`) plus any added
on its Options page, which needs no rebuild. It depends on WhatsApp Web's English labels ("Voice call", "End call").

## Documentation

`docs/` is also a [Mintlify](https://mintlify.com) site: `docs/docs.json` holds
its navigation, and `docs/.mintignore` keeps internal records (design history,
maintainer notes, migration runbooks) off it. Pages are Markdown (`.md`) or
MDX (`.mdx`) with `title` and `description` frontmatter. A page appears in the
sidebar only once it is listed in `docs.json`.

```sh
cd docs
npx mint dev            # preview at http://localhost:3000
npx mint validate       # the build, in strict mode
npx mint broken-links
```

In MDX, `{` starts an expression: write merge fields as inline code
(`` `{{firstName}}` ``). Link between pages with relative `.md` paths in the
Markdown pages and root paths (`/email/campaigns`) in the MDX ones.
