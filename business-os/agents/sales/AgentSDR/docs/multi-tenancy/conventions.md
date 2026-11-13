---
title: "Tenancy conventions"
description: "The rules every query, route, page, worker and webhook follows so organizations stay isolated."
icon: "shield"
---

Every piece of business data belongs to one organization. These are the
rules every query, route, page, worker and webhook follows. The plan and its
history are in `plan.md`; this file is the reference.

## The pieces

- `src/lib/auth/context.ts` — who is asking: `requireOrgContext(request)`,
  `withOrgContext(request, fn)`, `requirePageOrgContext()`, `can()`,
  `requirePermission()`, `authContextErrorResponse()`.
- `src/lib/tenancy/scope.ts` — the organization the current unit of work
  acts for: `runInOrganization(orgId, fn)`, `currentOrganizationId()`,
  `inOrg(table)`. Reading the organization outside a scope **throws**.
- `src/lib/tenancy/registry.ts` — which tables are scoped (own
  `organizationId`), inherited (scoped through a NOT NULL parent), global,
  auth or legacy; and which uniques are per organization.

## 1. Entry points open the scope — exactly once

**API routes**

```ts
export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async (ctx) => {
      // … everything here runs as ctx.organizationId
    });
  } catch (error) {
    return authContextErrorResponse(error) ?? existingErrorMapping(error);
  }
}
```

Routes that already call `requireCrmMutationContext(request)` keep it (it
also checks same-origin) and wrap the rest:

```ts
const ctx = await requireCrmMutationContext(request);
return runInOrganization(ctx.organizationId, async () => { … });
```

**Server pages** that query the database:
`const ctx = await requirePageOrgContext();` then load data inside
`runInOrganization(ctx.organizationId, …)`.

**Workers, cron routes, webhooks, public token links** have no session.
They resolve the organization **from the data** (mailbox → org, Unipile
account → org, call session → org, grid job → table → org, crm job → org)
and run each item inside `runInOrganization(item.organizationId, …)`. One
global loop is fine; each item carries its own organization. An
integration check such as `isPlatformConnected` is per organization, so it
moves inside the per-item / per-org scope.

## 2. Every read and write of a scoped table filters by organization

```ts
db.select().from(people).where(and(inOrg(people), eq(people.id, id)))
db.update(people).set({...}).where(and(inOrg(people), eq(people.id, id)))
db.delete(people).where(and(inOrg(people), eq(people.id, id)))
db.insert(people).values({ organizationId: currentOrganizationId(), ... })
```

- **Fetch by id:** the org filter goes in the same `where`, so another
  organization's id is simply *not found* (respond 404, never 403 — do not
  confirm the id exists).
- **Inherited tables** (e.g. `outreach_leads`, `crm_drafts`, `grid_rows`)
  have no column of their own. Reach them through a scoped parent: join the
  parent and filter it with `inOrg(parent)`, or filter by
  `inArray(child.parentId, db.select({ id: parent.id }).from(parent).where(inOrg(parent)))`,
  or load the parent org-filtered first and then query children by that
  parent's id.
- **Joins:** filter the scoped table you start from; a join to another
  scoped table on a foreign key needs no second filter only if the foreign
  key makes cross-organization rows impossible — when in doubt, filter both.
- **Raw SQL** (`db.execute(sql\`…\`)`): add
  `organization_id = ${currentOrganizationId()}` for every scoped table in
  the statement (`"organizationId"` on the LinkedIn tables).
- **Counts, aggregates, analytics, badges:** same rule — no number may
  include another organization's rows.

## 3. Uniques and upserts

Business uniques are per organization (`PER_ORG_UNIQUES` in the registry):
people email / LinkedIn URL, company domain, suppression email, pipeline
name and default, `grid_providers.key`, targeted domain, legacy CRM lead
email, `entity_columns (entity, key)`. Upserts on those tables target the
per-org unique:

```ts
.onConflictDoUpdate({ target: [suppressionList.organizationId, suppressionList.email], set: … })
```

Provider identities stay globally unique — a Unipile account, LinkedIn id,
Gmail mailbox, provider message id belongs to exactly one organization, and
inbound events find their organization through them.

## 4. Settings that used to be "the workspace"

Per organization: platform integrations, OpenRouter BYOK settings and AI
connections, enrichment connections, the default CRM pipeline and its
`crm_settings`, sequences, knowledge, lead categories (subcategories),
custom lead fields (`entity_columns` + `people.custom` / `companies.custom`).
A new organization gets its defaults lazily (get-or-create on first use), so
nothing depends on a sign-up hook having run.

Global and shared: the `domains` datasets, the four `crm_categories`,
LinkedIn `JobRun` / `JobLog`.

## 5. Permissions

Members use the product. Owners and admins additionally manage
integrations, AI settings, members and teams:
`requirePermission(ctx, { integrations: ["manage"] })` on the server, the
same role definitions (`src/lib/auth/permissions.ts`) in the UI.

## 6. Tests

Unit tests of lib functions that now read the scope run inside
`runInOrganization("00000000-0000-0000-0000-00000000000a", …)`. The
isolation suite signs in as a second organization and asserts it can see,
change and count nothing of the first.
