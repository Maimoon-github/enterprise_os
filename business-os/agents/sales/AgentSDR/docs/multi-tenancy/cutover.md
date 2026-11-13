# Production cutover — single workspace → organizations

The steps to move the live deployment onto Better Auth and organizations.
Rehearsed end to end on a copy of live data (1 Oct 2026): every step passed
its audit, every table kept its row count, and the database work took under
a second in total.

The order matters. The **expand** step is additive and safe while the old
code is still running (organization columns carry a default of the initial
organization, old global uniques stay). The **contract** step is safe only
once the new code is live.

## 0. Before you start

Set these on the hosting platform for the new deployment (they are read at
startup):

| Variable | Value |
|---|---|
| `BETTER_AUTH_SECRET` | 32+ random characters (`openssl rand -hex 32`). Keep it stable. |
| `BETTER_AUTH_URL` | The public origin, e.g. `https://agentsdr.example.com` |
| `RESEND_API_KEY` | From Resend. **Required in production** — sign-up, reset and invitations send email. |
| `AUTH_EMAIL_FROM` | e.g. `AgentSDR <auth@agentsdr.example.com>`, on a domain verified in Resend |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional. OAuth client with redirect `<BETTER_AUTH_URL>/api/auth/callback/google` |
| `INTEGRATION_CREDENTIALS_KEY` | **Unchanged.** It must equal the value the integrations were encrypted with. |
| `AUTH_PASSWORD`, `AUTH_SECRET` | No longer read; remove after the cutover. |

Decide the initial organization's name and URL slug, and the owner's email
and password — this person signs in first and invites everyone else.

## 1. Backup (rollback point)

```sh
pg_dump --format=custom --no-owner --no-privileges \
  --exclude-table-data=public.domains --exclude-table-data=public.clean_domains \
  --file agentsdr-before-tenancy.dump "$DATABASE_URL"
```

`pg_dump` must be at least the server's major version (18).

## 2. Expand (old code still live — safe)

From a checkout of the new code, with `DATABASE_URL` pointing at production:

```sh
bun run scripts/create-auth-tables.ts

INITIAL_ORG_NAME="…" INITIAL_ORG_SLUG="…" \
INITIAL_OWNER_NAME="…" INITIAL_OWNER_EMAIL="…" INITIAL_OWNER_PASSWORD="…" \
BETTER_AUTH_SECRET="<same as production>" \
bun run --conditions=react-server scripts/add-organization-scope.ts           # read the plan
# … then the same command with --apply

bun run scripts/check-organization-scope.ts                                   # must pass
```

Every existing row now belongs to the initial organization, including the
platform integrations and AI settings — nothing needs reconnecting.

## 3. Deploy the new code

Push `main` and let it deploy. During a rolling deploy old and new
containers briefly run together; the expanded schema serves both.

Everyone's old password cookie stops working: people sign in at
`/sign-in`. The owner from step 2 signs in first, then invites the team
from Settings → Members.

Smoke test as the owner: Analytics, Leads, CRM, Email, LinkedIn, WhatsApp,
Tables load with their data; Settings → Integrations shows Unipile, Google,
R2 connected; Settings → Members lists the owner.

## 4. Contract (new code live)

```sh
bun run scripts/finalize-organization-scope.ts           # read the plan
bun run scripts/finalize-organization-scope.ts --apply
bun run scripts/check-organization-scope.ts --contract   # must pass
```

This drops the old global uniques (so a second organization can hold the
same email, domain, …) and the initial-organization defaults (so an insert
that forgets its organization fails instead of landing in yours). Until it
runs, a second organization cannot create its CRM pipeline.

## 5. Afterwards

- Watch the logs for `MissingOrganizationScopeError` — a code path that
  runs without an organization. It fails closed (no data crosses), but the
  feature on that path is broken until fixed.
- Unipile webhooks keep working: WhatsApp and account webhooks verify the
  secret of the organization that owns the account. The LinkedIn
  `connection-accepted` / `message-received` webhooks still accept requests
  without a secret (as before) and log a warning — re-register them in the
  Unipile dashboard with `?secret=<your webhook secret>` to close that.
- Remove `AUTH_PASSWORD` / `AUTH_SECRET` from the hosting platform.

## Rollback

- **Before step 4:** redeploy the previous commit. The expanded schema still
  serves the old code (defaults and global uniques are in place). The new
  tables are harmless; drop them only if you are abandoning the migration.
- **After step 4:** first put the defaults back so the old code can insert
  again — for each table in `SCOPED_TABLES`:
  `ALTER TABLE <t> ALTER COLUMN organization_id SET DEFAULT '<initial org id>';`
  (`"organizationId"` on the LinkedIn tables) — then redeploy the previous
  commit. The old global uniques can be recreated from the backup's schema
  if a second organization has not yet created clashing rows.
- **Last resort:** restore `agentsdr-before-tenancy.dump`.
