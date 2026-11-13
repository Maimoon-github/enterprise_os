---
title: "Architecture"
description: "How the app is put together: request flow, background work and the data model."
icon: "blocks"
---

AgentSDR is **one Next.js 16 App Router application** (React 19, TypeScript,
Tailwind) on **one PostgreSQL database**, accessed through Drizzle ORM and the
`postgres` driver. It runs as a single Node/Bun process. There is no message
broker and no separate worker deployment: background work runs inside the app
process, plus a few HTTP endpoints that an external scheduler calls.

The product covers: a lead database (People and Companies), enrichment tables,
email, LinkedIn and WhatsApp outreach, WhatsApp calling, an AI-assisted CRM
with a master inbox, and analytics. Every piece of business data belongs to one
**organization** (a tenant).

## Overview

```
                 Browser                       External services
                    |                      Unipile (LinkedIn, WhatsApp)
                    v                      Google (Gmail, Pub/Sub push)
        +------------------------+         OpenRouter (all LLM calls)
        |  src/proxy.ts          |         Cloudflare R2 (recordings)
        |  cookie present? public|<------  Resend (auth email)
        |  paths, job secrets   |         Enrichment providers
        +-----------+------------+                 ^        |
                    |                              |        | webhooks
        pages (src/app/**)   API routes (src/app/api/**) <---+
                    |             |
                    v             v
        requireOrgContext / withOrgContext     <- session + membership + role
                    |
                    v
        runInOrganization(orgId, ...)          <- AsyncLocalStorage scope
                    |
                    v
        src/lib/<domain>  ->  Drizzle (src/lib/db.ts, one pool)  ->  PostgreSQL

   Started at boot by src/instrumentation.ts (same process):
     outreach scheduler (prod) | enrichment worker | CRM worker
     scheduled jobs (prod): daily rollover per organization, LinkedIn
     outreach, webhook replay, pruning (src/lib/scheduler)
   Also callable by hand or an external cron (optional secrets):
     /api/outreach/{build-queue,mailboxes/watch}, /api/linkedin/jobs/*
```

## Directory map

```
src/app/                 Pages (App Router) and API routes
  api/                   Route handlers, grouped by domain (see below)
  settings/              Settings pages; each has an @modal/(.)settings twin
  leads/ tables/ crm/ outreach/ campaigns/ linkedin/ calling/ analytics/ domains/
  sign-in, sign-up, onboarding, accept-invitation, ...   Auth pages
  unsubscribe/           Public unsubscribe page
src/lib/<domain>/        Business logic, schema and queries per domain
src/components/          React components, mostly one folder per domain
src/jobs/                LinkedIn jobs run by the scheduler and the job endpoints
src/functions/           LinkedIn sending steps used by the jobs
src/services/            Unipile API clients (LinkedIn and WhatsApp)
src/proxy.ts             Request gate (Next.js middleware)
src/instrumentation.ts   Starts the in-process workers
scripts/                 One-shot migrations, audits, db tooling, e2e
scripts/db/              setup.ts (fresh database), dump-schema.ts
db/                      schema.sql (generated), seed.sql (reference rows)
extensions/whatsapp-recorder/   Chrome MV3 extension that dials and records WhatsApp calls
docs/                    This documentation
```

### `src/lib/<domain>`

| Folder | What it holds |
|---|---|
| `auth/` | Better Auth server and client, permissions (owner, admin, member), `requireOrgContext` and friends, auth email, auth tables |
| `tenancy/` | The organization scope (`scope.ts`) and the table registry (`registry.ts`) |
| `platform/` | Unipile, Google and R2 connections: catalog, credential store, live verification, client factories |
| `integrations/` | Enrichment providers used by Tables, encrypted credential store |
| `ai/` | OpenRouter connection, BYOK settings, model catalog, the one runtime all model calls go through |
| `leads/` | The lead database: People and Companies, identity, imports, runtime custom columns |
| `grid/` | Tables: workbooks, columns, cell runners, formulas, the enrichment worker and its queue |
| `outreach/` | Email: mailboxes, campaigns, sequences, queue building, scheduler, Gmail send and sync, unsubscribe |
| `linkedin/` | LinkedIn: accounts, campaigns, leads, search batches, webhooks ledger, job tracking (schema in `schema.ts`, PascalCase tables) |
| `whatsapp/` | WhatsApp messaging through Unipile: accounts, chats, messages, send guardrails, CRM bridge |
| `calls/` | WhatsApp calls placed from the app: sessions, campaigns, recordings, transcription, the contract shared with the extension |
| `crm/` | CRM: pipelines, records, conversations, classification and drafting jobs, sequences, knowledge, AI instructions, worker |
| `inbox/` | Master Inbox queries, notes, tasks and inbound-delivery diagnostics |
| `analytics/` | Dashboard queries per channel |
| `qualification/` | Domain qualification (prospecting); slated for removal |
| `migration/` | Kill switches (`PAUSE_*`) from the unified-People migration |
| `email/`, `format/`, `http/` | Small shared helpers (HTML to text, contact formatting, request validation) |
| `db.ts`, `schema.ts`, `queries.ts` | The single Drizzle pool; the schema entry point that re-exports every domain schema; shared queries |

### `src/app/api`

Route handlers are grouped by domain: `auth` (Better Auth), `grid`, `leads`,
`outreach`, `linkedin`, `whatsapp`, `calling`, `calls`, `call-recorder`
(the extension), `crm`, `analytics`, `ai`, `settings`, `webhooks` (Unipile),
plus a few older ones (`campaigns`, `categories`, `domains`, `qualify`,
`targeted-domains`, `apps`, `export`, `nav`, `dev`). Which of these are public
is listed at the top of `src/proxy.ts`.

## Request flow

1. **`src/proxy.ts`** runs first. It lets through a short list of public paths
   (auth pages and endpoints, Unipile and Gmail webhooks, the call-recorder
   API, unsubscribe pages, static files). For `/api/linkedin/jobs` it accepts
   `Authorization: Bearer $CRON_SECRET`. Everything else needs a Better Auth
   session cookie; without one, pages redirect to `/sign-in` and APIs answer
   401. This check is optimistic only: it does not validate the session. It also
   applies the migration kill switches.
2. **The route or page** calls `requireOrgContext(request)` /
   `withOrgContext(request, fn)` (API) or `requirePageOrgContext()` (pages)
   from `src/lib/auth/context.ts`. This validates the session, reads the active
   organization, and re-reads the member's role from the database on every call,
   so removing someone takes effect immediately. Failures become 401, 403 or 409
   JSON.
3. **`withOrgContext`** opens an `AsyncLocalStorage` scope with
   `runInOrganization(orgId, fn)`. Code in `src/lib/` never takes the session:
   it reads the organization from the scope (`currentOrganizationId()`), which
   is what lets workers and webhooks reuse it. Reading the scope outside one
   throws.
4. **Queries** filter every scoped table with `inOrg(table)`, and inserts set
   `organizationId: currentOrganizationId()`. An id from another organization is
   simply not found (404).
5. **Drizzle** sends SQL through the one pool in `src/lib/db.ts`.

The full rules are in [multi-tenancy/conventions.md](multi-tenancy/conventions.md).

## Background work

| Mechanism | What | Where |
|---|---|---|
| In-process, started by `src/instrumentation.ts` | Outreach scheduler (production only; one tick a minute), enrichment worker (claims with `SKIP LOCKED`), CRM worker (durable job queue, `SKIP LOCKED`) | `src/lib/outreach/internalScheduler.ts`, `src/lib/grid/worker.ts`, `src/lib/crm/worker.ts` |
| External scheduler calling HTTP | Daily email queue rebuild, Gmail watch renewal, LinkedIn jobs | [self-hosting.md](self-hosting.md#scheduled-jobs) |
| Inbound webhooks | Unipile (LinkedIn, WhatsApp), Gmail Pub/Sub | [integrations.md](integrations.md) |

Workers and webhooks have no session. They resolve the organization **from the
data** (mailbox, Unipile account, call session, grid job, CRM job) and run each
item inside `runInOrganization`. The outreach scheduler has no distributed lock,
so the app must run as a single instance.

## Auth and tenancy

Better Auth provides email and password (verified by email), optional Google
sign-in, organizations and teams. Roles are owner, admin and member: members use
the product; owners and admins also manage integrations, AI settings, members
and teams. Better Auth tracks the active organization on the session; scoping
data to it is done by this codebase (`src/lib/tenancy`), not by the library.
Each table is classified in `src/lib/tenancy/registry.ts` as scoped (has its own
`organization_id`), inherited (scoped through a NOT NULL parent), global, auth
or legacy, and `bun run db:check` fails if a table is unclassified. See
[multi-tenancy/conventions.md](multi-tenancy/conventions.md) and
[multi-tenancy/plan.md](https://github.com/Kandid-ai/AgentSDR/blob/main/docs/multi-tenancy/plan.md).

## Integrations store

Platform integrations (Unipile, Google Workspace, R2) are one row each per
organization in `grid_providers` (key `platform-<key>`), with the credentials
encrypted in `grid_provider_credentials` using `INTEGRATION_CREDENTIALS_KEY`
(AES-256-GCM). Reads are cached 30 seconds per process. OpenRouter and the
enrichment providers use the same tables. Code that calls one of these services
asks `src/lib/platform/credentials.ts` (`getPlatformCredentials`,
`requirePlatformCredentials`, `isPlatformConnected`) inside the organization
scope, and never reads keys from `process.env`. See
[integrations.md](integrations.md).

## Data model overview

84 tables in `db/schema.sql`. By domain:

| Domain | Tables |
|---|---|
| Auth and tenancy | `users`, `sessions`, `accounts`, `verifications`, `organizations`, `members`, `invitations`, `teams`, `team_members` |
| Lead database | `people`, `companies`, `entity_columns` (the registry of runtime-added columns), `import_runs` |
| Tables (enrichment) | `grid_workbooks`, `grid_folders`, `grid_tables`, `grid_columns`, `grid_rows`, `grid_jobs`, `grid_cell_runs`, `grid_providers`, `grid_provider_credentials` |
| Email outreach | `outreach_mailboxes`, `outreach_campaigns`, `outreach_leads`, `outreach_emails`, `outreach_mailbox_queue`, `outreach_suppression_list` |
| LinkedIn (quoted PascalCase) | `Campaign`, `CampaignAccount`, `Connection`, `JobLog`, `JobRun`, `Lead`, `LinkedInAccount`, `Message`, `SearchBatch`, `SearchQuery`, `SearchResult`, `WebhookEvent` |
| WhatsApp messaging | `whatsapp_accounts`, `whatsapp_chats`, `whatsapp_messages` |
| WhatsApp calling | `call_sessions`, `call_campaigns`, `call_campaign_contacts`, `call_messages` |
| CRM | `crm_pipelines`, `crm_records`, `crm_conversations`, `crm_conversation_messages`, `crm_classifications`, `crm_drafts`, `crm_jobs`, `crm_tasks`, `crm_notes`, `crm_sequences` and its step, version and run tables, `crm_knowledge_documents` and versions, `crm_settings`, `crm_categories`, `crm_subcategories`, `crm_status_config`, `crm_person_contact_policies`, `crm_send_attempts`, `crm_events`, `crm_identity_exceptions` |
| Master Inbox | `crm_leads`, `crm_messages`, `crm_email_drafts`, `crm_lead_ccs`, `crm_webhook_events` |
| Prospecting | `campaigns`, `targeted_domains`, `qualification_jobs`, `domains`, `clean_domains` |

`people.id` is the permanent identity shared by every channel. `people` and
`companies` gain user-defined columns at runtime. Details and the rules for
changing the schema are in [database.md](database.md).

## Other parts

- **WhatsApp call recorder.** `extensions/whatsapp-recorder/` is a Chrome
  extension that dials and records calls inside web.whatsapp.com. It shares
  `src/lib/calls/contract.ts` with the app and uploads to R2 through
  presigned URLs, authenticating each call with a bearer token.
- **Formula sandbox.** Table formulas run in a QuickJS isolate
  (`src/lib/grid/runners/sandbox.ts`) with lodash, moment and formulajs loaded
  from `node_modules` at runtime (listed in `next.config.ts`
  `outputFileTracingIncludes` so the standalone build includes them).
- **Build output.** `next.config.ts` sets `output: "standalone"`; the Docker
  image runs `bun server.js` from that output.
