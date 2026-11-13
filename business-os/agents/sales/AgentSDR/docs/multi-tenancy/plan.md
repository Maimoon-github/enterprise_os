# Multi-tenancy with Better Auth — migration plan

Status: **implemented and verified on a copy of live data; production cutover pending** (1 Oct 2026). See `cutover.md` for the runbook and `conventions.md` for the rules.

AgentSDR today is one workspace behind one shared password (`AUTH_PASSWORD` →
HMAC cookie `agentsdr_auth`). There are no users, no organizations, and every
row in the database belongs to that one workspace. This plan moves it to
Better Auth with organizations and teams, where every piece of business data
belongs to exactly one organization, without losing data or taking the
running deployment down.

Sources: Better Auth 1.7.7 docs (better-auth.com/docs — installation,
integrations/next, adapters/drizzle, plugins/organization,
concepts/session-management, reference/security), the 1.7.7 package source,
and a read-only inventory of this repo and the live database (84 tables).

---

## 1. How Better Auth works, end to end (as it applies here)

**Server instance** — `betterAuth({...})` in `src/lib/auth/server.ts`:

```ts
export const auth = betterAuth({
  database: drizzleAdapter(db, { provider: "pg", schema: authSchema, usePlural: true }),
  advanced: { database: { generateId: "uuid" } },
  emailAndPassword: { enabled: true, requireEmailVerification: true, sendResetPassword },
  emailVerification: { sendVerificationEmail },
  databaseHooks: { session: { create: { before: pickInitialOrganization } } },
  plugins: [
    organization({ teams: { enabled: true }, ac, roles, sendInvitationEmail, allowUserToCreateOrganization }),
    nextCookies(), // must be last
  ],
});
```

- The Drizzle adapter **reuses our `db`** — no second pool, so the 50-slot
  connection cap is unaffected.
- Better Auth stores everything in our Postgres: `users`, `sessions`,
  `accounts` (password hashes live here, scrypt), `verifications`, and from the
  organization plugin `organizations`, `members`, `invitations`, `teams`,
  `team_members`. Ids are uuid, so they foreign-key cleanly into our tables.
- It is mounted at `src/app/api/auth/[...all]/route.ts` via `toNextJsHandler`.
- The browser uses `createAuthClient` + `organizationClient()` for sign-in,
  sign-up, sign-out, switching org, inviting, accepting invites.

**A request's life:**

1. `proxy.ts` (Next 16's middleware) does only an *optimistic* check —
   `getSessionCookie(req)` — and redirects to `/sign-in` when there is no
   cookie. Better Auth's docs are explicit that this does **not** validate the
   session.
2. The page / route handler calls our `requireOrgContext()`, which calls
   `auth.api.getSession({ headers })` (one indexed lookup) and returns
   `{ userId, organizationId, role }`. `session.activeOrganizationId` is a
   column on the session row, so the org costs nothing extra; the role is one
   `members` lookup.
3. Every query filters on `organizationId`. **Better Auth does not scope our
   tables — that is entirely our code**, and the bulk of this migration.

**Organizations & teams:** a user can belong to several organizations, with a
role in each (`owner`, `admin`, `member`, customisable via
`createAccessControl`). The session carries one *active* organization, switched
with `setActiveOrganization`. With `teams.enabled`, each organization gets a
default team and its creator joins it; invitations can target a team.

**Email:** Better Auth sends nothing itself. We implement three callbacks:
verification email, password reset, invitation.

**Known gotchas (verified):** the CLI's generated Drizzle file uses
`defineRelationsPart`, which does not exist in our drizzle-orm 0.45 — we write
the auth schema by hand (or strip that block). `nextCookies()` must be the
last plugin. React Server Components cannot set cookies.

---

## 2. What the inventory found

- **84 live tables.** About **33 need their own `organization_id`**
  (people, companies, mailboxes, campaigns, CRM pipelines/sequences/knowledge,
  grid folders/workbooks, call campaigns/sessions, WhatsApp and LinkedIn
  accounts…). About **10 more children** need one directly because their
  parent link is nullable or because they are read without the parent
  (LinkedIn `Lead`/`Connection`/`Message`, `crm_records`,
  `crm_conversations`, `crm_events`, `call_messages`…). The remaining ~30
  children inherit scope through a NOT NULL foreign key.
- **Stays global:** `domains` and `clean_domains` (6 M rows of public store
  data), `crm_categories` (four fixed system categories, CHECK-enforced),
  LinkedIn `JobRun`/`JobLog`, `_prisma_migrations`.
- **Workspace singletons that become per-organization:** platform
  integrations (`grid_providers` keys `platform-*`), OpenRouter BYOK settings,
  the default CRM pipeline and its `crm_settings`, knowledge, lead categories
  (`crm_subcategories`), `entity_columns`.
- **Globally-unique values that become unique per organization:** people
  email/LinkedIn URL, company domain, suppression email, CRM pipeline name,
  "one default pipeline", `grid_providers.key`, `entity_columns (entity,key)`.
  Values that identify a provider account (Unipile account id, LinkedIn id,
  Gmail message id) **stay globally unique** — they are how inbound webhooks
  find their organization.
- **Entry points with no user** (they must derive the org from the data):
  the outreach scheduler (60 s loop), grid worker, CRM worker, LinkedIn jobs,
  Unipile webhooks, Gmail Pub/Sub push, call-recorder extension routes,
  unsubscribe links. Each has a clean path to its org (mailbox → org,
  Unipile account → org, call session → org, grid table → org).
- **Data access:** 192 API routes and 61 pages; ~550 query sites; 71 raw
  `db.execute(sql…)` sites; no server actions; `assertCrmMutationRequest`
  guards 43 mutation routes.
- **Problems found along the way that this migration must fix:**
  1. `/api/webhooks/message-received` and `/connection-accepted` have **no
     authentication** — anyone with the URL can post events, and
     `connection-accepted` sends messages.
  2. `/api/linkedin/jobs/run-search-queue` trusts `accountIds` from the body.
  3. Unsubscribe tokens carry only an email, and the suppression list is
     global.
  4. Runtime lead columns (`ALTER TABLE people ADD COLUMN`) would leak every
     organization's custom columns into every other's. The feature has **zero
     user columns today**, so it is the cheapest moment to change it.
  5. The CRM records the actor as the fixed string `authenticated_operator`
     (CHECK-enforced) — we can now record real users.
- **Shared database:** the live Postgres is shared with other deployments.
  `AgentSDR-app` (Better Auth 1.2, singular `user`/`session`/`organization`
  tables) points at the same host but **those tables do not exist** in the
  live database today. We use **plural** table names (`users`, `sessions`,
  `organizations`…), matching this app's convention and ruling out a clash.

---

## 3. Design decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Tenant column | `organization_id uuid NOT NULL REFERENCES organizations(id)` on every ROOT table and the nullable-parent children; plain children inherit. |
| D2 | Existing data | One organization, created by the migration, owns every existing row. The current operator becomes its owner. |
| D3 | Enforcement | Application-level scoping through one `requireOrgContext()` and org-aware lib functions. Postgres row-level security is **not** used in this pass (it needs a per-request `SET` on a pooled connection; revisit later as defence-in-depth). |
| D4 | Uniques | Business uniques become `(organization_id, …)`; provider-identity uniques stay global. |
| D5 | Custom lead columns | Move to a `custom jsonb` column on `people` / `companies` with a per-org `entity_columns` registry; no more runtime DDL. |
| D6 | Integrations | Per organization — each org connects its own Unipile, Google Workspace and R2: `grid_providers` gets `organization_id`, singleton keys become `(organization_id, key)`, caches key by org. Webhook URLs carry the org. |
| D7 | Roles | `owner`, `admin`, `member`. Owners/admins manage integrations, members, billing-type settings; members use the product. |
| D8 | Teams | Enabled now for membership and invitations. Data is scoped at **organization** level only in this pass; team-level visibility is a later step. |
| D9 | Auth tables | Plural (`usePlural: true`), uuid ids, hand-written Drizzle schema in `src/lib/auth/schema.ts`, added to `OWNED_TABLES`. |
| D10 | Rollout | Expand → migrate → contract. Columns are added nullable *with a database default of the initial org*, so the currently-deployed code keeps inserting valid rows until the new code ships; NOT NULL and default removal come last. |

D11 — sign-up is open and self-serve; sign-in is email + password and Google;
auth email goes through Resend. `RESEND_API_KEY`, `AUTH_EMAIL_FROM`,
`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, `BETTER_AUTH_SECRET` and
`BETTER_AUTH_URL` are platform infrastructure, so they live in env (not in
Integrations, which are per organization). Without `RESEND_API_KEY` emails are
logged to the server console (development only); without the Google pair the
Google button is hidden.

---

## 4. Execution phases

Each phase is its own set of commits; `tsc`, the test suite and the checks
listed under it pass before the next phase starts. Nothing is pushed until
the whole migration has been rehearsed (§5).

### Phase 0 — Safety net
- Install PostgreSQL 18 locally; `pg_dump` the live schema and all tenant
  data (424 MB, excluding the `domains`/`clean_domains` data) into a local
  database. **All development and the full rehearsal run against this copy.**
- Take a fresh dump of the live tenant tables immediately before the
  production migration (the rollback point).
- `.env.local` is left pointing at live; every development command and the
  second dev server get `DATABASE_URL` for the local copy explicitly.
- **The local copy is defused before anything runs against it:** platform
  integration credentials, AI keys and enrichment keys are deleted from it,
  and the outbound pause switches (`PAUSE_EMAIL_OUTBOUND`,
  `PAUSE_LINKEDIN_OUTBOUND`, …) are set, so no test can send a real email or
  LinkedIn/WhatsApp message to a real lead.

### Phase 1 — Better Auth foundation
- `bun add better-auth`; `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL` in env.
- `src/lib/auth/schema.ts` (9 tables), `src/lib/auth/server.ts`,
  `src/lib/auth/client.ts`, `src/app/api/auth/[...all]/route.ts`.
- Migration `scripts/create-auth-tables.ts` (guarded DDL, matches the schema).
- Pages: `/sign-in`, `/sign-up` (if self-serve, §8), `/forgot-password`,
  `/reset-password`, `/accept-invitation/[id]`, `/onboarding` (create first
  organization). Chromeless, public in `proxy.ts`.
- Email delivery for verification, reset, invitation (§8).
- **Tests:** sign-up → verify → sign-in → session cookie → sign-out; reset
  password; invite → accept; org create/switch. Run against the local DB.

### Phase 2 — Tenancy schema (expand)
- `scripts/add-organization-scope.ts`: creates the initial organization and
  owner, then for each scoped table `ADD COLUMN IF NOT EXISTS organization_id
  uuid DEFAULT '<initial-org>' REFERENCES organizations(id)`, backfills,
  indexes `(organization_id, …)`; swaps global uniques for per-org uniques
  (`CREATE UNIQUE INDEX CONCURRENTLY` first, drop the old after).
- Same columns added to every Drizzle schema file by hand (repo convention).
- `custom jsonb` on `people`/`companies`; `entity_columns.organization_id`.
- **Tests:** a `scripts/check-organization-scope.ts` audit that fails if any
  scoped table has a NULL `organization_id`, a missing index, or a global
  unique that should be per-org.

### Phase 3 — Request context
- `src/lib/auth/context.ts` (server-only): `getOrgContext()`,
  `requireOrgContext(request?)`, `requireRole(...)`. Replaces the cookie check
  in `assertAuthenticatedOperator` (so the 43 CRM-guarded routes get the org
  for free) and the old `/api/auth/login|logout` routes.
- `proxy.ts`: swap the HMAC check for `getSessionCookie`; API routes get 401
  JSON instead of a redirect. Keep every public carve-out.
- Root `src/app/(app)` layout resolves the org once for pages; a
  `NoActiveOrganization` state sends users to `/onboarding`.

### Phase 4 — Scope every read and write (the bulk)
Area by area, each a separate commit with its own tests: **leads, outreach,
CRM, inbox, LinkedIn, WhatsApp, calls, grid/tables, qualification/prospecting,
settings & analytics.** Rules:
- Lib functions take `organizationId` as their first argument; route handlers
  pass `ctx.organizationId`. No lib function reads the session itself (so
  workers can call them).
- Every insert sets `organizationId`; every select/update/delete of a scoped
  table filters on it (or joins through a scoped parent).
- Each of the 71 raw-SQL sites is reviewed by hand.
- Fetch-by-id routes return 404 (not 403) for another org's id.

### Phase 5 — Per-organization integrations & settings
- `src/lib/platform/credentials.ts`: every function takes `organizationId`;
  cache keyed `(org, platform)`; Unipile and R2 client caches keyed by org.
- OpenRouter BYOK settings, AI connections, enrichment connections: per org.
- CRM: one default pipeline + `crm_settings` per org (created with the org);
  knowledge, sequences, lead categories per org.
- New-organization bootstrap (`afterCreateOrganization` hook): default
  pipeline, settings, subcategories, default team.

### Phase 6 — Entry points without a user
- Workers (outreach scheduler, grid, CRM) keep one global loop but carry the
  org on every item and use that org's credentials; an org whose integration
  is not connected is skipped, not the whole tick.
- Webhooks: Unipile `notify_url` and webhook URLs include the org
  (`?org=<id>&secret=…`, verified against that org's secret); inbound events
  resolve the org from the provider account id. **Add secret checks to
  `message-received` and `connection-accepted`.**
- Gmail Pub/Sub: email address → mailbox → org.
- Unsubscribe tokens carry the outreach lead id (→ org); suppression list per
  org.
- `run-search-queue` verifies account ownership.

### Phase 7 — Organization, member and team UI
- Sidebar workspace card becomes the org switcher + user menu (name, email,
  switch org, create org, sign out). Client caches reset on switch.
- Settings → **Organization** (name, logo, slug), **Members** (invite, roles,
  remove), **Teams** — each with its `@modal/(.)settings` twin.
- Role gating: Integrations, Members, AI provider editable by owner/admin
  only (server-enforced, UI hides controls).
- CRM actor columns record the user id; the `authenticated_operator` CHECKs
  are widened.

### Phase 8 — Contract
- `organization_id` → NOT NULL, database defaults dropped, old global uniques
  removed, `AUTH_PASSWORD`/`agentsdr_auth`/`auth-token.ts` deleted.
- CLAUDE.md: a "Tenancy" section with the rules every future change follows.

---

## 5. Rehearsal and production cutover

1. Run Phases 2 and 8's scripts end-to-end against a **fresh copy** of live
   data; run the full test plan (§6) against it.
2. Freeze: pause outreach sending and workers (`PEOPLE_MIGRATION_MODE`-style
   switch already exists), take the rollback dump.
3. Run the expand migration on live (additive; the old deployment keeps
   working because of the column defaults).
4. Push and deploy the new code; sign in as the migrated owner; smoke test.
5. Unpause. After a soak period, run the contract migration.

Rollback: before step 4, drop the added columns/tables (scripted). After
step 4, redeploy the previous commit — it still works because the expand
step only added columns with defaults.

---

## 6. Test plan

- **Unit:** `requireOrgContext` (no session → 401, no active org → 409/redirect,
  role checks); token builders (unsubscribe, webhook URLs); per-org caches.
- **Isolation suite (the critical one):** a seeded fixture with two
  organizations A and B, each with people, companies, mailboxes, campaigns,
  CRM records, LinkedIn/WhatsApp accounts, grid tables, calls. A generated
  test walks **every API route** as a user of B and asserts A's ids return
  404/empty, and that list endpoints never contain A's rows. Same for pages.
- **Entry points:** each webhook with A's provider account id writes only to
  A; wrong/missing secret → 401; workers process A and B with their own
  credentials and skip an org without integrations.
- **Auth flows (browser, Playwright):** sign-up, verify, sign-in, sign-out,
  forgot/reset, invite → accept (new and existing user), switch org,
  role-restricted pages.
- **Migration:** the scope audit script passes on the rehearsal copy; row
  counts per table identical before/after; every existing row belongs to the
  initial org.
- **Regression:** existing 553 tests, `tsc`, production build.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| A missed query leaks data across orgs | Isolation suite over every route; lib functions require `organizationId` as a typed argument so a missing scope is a compile error, not a silent leak. |
| Deployed old code breaks on new columns | Expand-with-defaults; NOT NULL only after the new code is live. |
| Global unique → per-org swap locks big tables | `CREATE INDEX CONCURRENTLY` before dropping the old constraint; tenant tables are ≤ 42 k rows. |
| Connection cap (50, shared) | Better Auth reuses our pool; session lookups are one indexed query. |
| Webhooks registered at Unipile with old URLs | Accept the old URL for the initial org during transition; re-register with the org-specific URL. |
| In-flight jobs during cutover | Freeze switch, then drain. |

---

## 8. Decisions (settled 1 Oct 2026)

1. **Integrations** — each organization connects its own Unipile, Google
   Workspace and R2.
2. **Organizations** — open self-serve sign-up; anyone can create one and
   invite teammates.
3. **Sign-in** — email + password and Google; verification, reset and
   invitation emails via Resend.
4. **Teams** — grouping and invitations only; data is scoped per organization.
