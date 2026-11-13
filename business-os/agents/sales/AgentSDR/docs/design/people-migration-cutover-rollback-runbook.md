# People Migration Cutover, Rollback, and Reconciliation Runbook

Status: **database migration completed on 2026-08-27; keep workers paused until
the matching application build is deployed and canary checks pass.**

Related plan: [pre-migration-remediation-plan.md](./pre-migration-remediation-plan.md)

## Purpose and scope

This runbook protects active Email and LinkedIn outreach while campaign
enrollments are linked to `people.id`. It covers additive schema preparation,
reviewed cleanup, People backfill, final constraints, deployment, canary
resume, rollback, and reconciliation of events received during the cutover.

The migration must preserve:

- every legacy campaign row and its execution state;
- Email recipient, rendered content, mailbox, schedule, reply, bounce,
  complaint, unsubscribe, and suppression behavior;
- LinkedIn provider target, account assignment, status, retry/backoff,
  messages, connections, and webhook routing;
- all legacy identity/profile columns and `campaign_members` throughout the
  rollback window.

Search/export alone remains out of scope and must not create People. This
runbook never authorizes destructive legacy-column cleanup.

## Known blockers as of 2026-08-27

Production cutover is not currently safe for these independent reasons:

1. No recent isolated staging clone has completed the sequence below.
2. Database integration tests and active Email/LinkedIn behavior-equivalence
   tests have not completed against PostgreSQL.
3. Environment-based pause controls are implemented locally, including the
   in-process Email tick, but they have not been deployed/backported to the
   currently running legacy-compatible runtime and rehearsed without stopping
   webhooks.
4. Exact platform commands for setting and verifying the pause flags have not
   been recorded and rehearsed.
5. Backup restore, webhook reconciliation, and rollback after simulated
   webhook traffic have not been rehearsed.
6. `WebhookEvent` records the raw payload, but the current webhook path has no
   provider-event uniqueness key or durable claim/retry worker. Persisting a
   row alone does not yet prove idempotent replay.

Do not treat a passing typecheck, unit suite, build, or read-only production
audit as satisfying these blockers.

## Roles and evidence

Assign names before a rehearsal or cutover. One person may hold multiple roles,
but the migration operator and go/no-go approver should be different people.

| Role | Required responsibility |
|---|---|
| Migration operator | Runs only the reviewed commands in this runbook |
| Database owner | Creates and verifies backup/restore; watches locks and load |
| Outreach owner | Pauses, drains, resumes, and validates Email/LinkedIn workers |
| Webhook observer | Confirms endpoints remain live and reconciles events |
| Go/no-go approver | Reviews artifacts and authorizes each write boundary |
| Rollback authority | Can stop the canary immediately and choose rollback mode |

Create an access-controlled evidence directory outside git for each run. Files
under `reports/migration/` are local and gitignored; copy them before a later
command overwrites a `*-latest.json` file.

```sh
export PEOPLE_MIGRATION_RUN_ID="YYYYMMDD-HHMM-environment"
export PEOPLE_MIGRATION_EVIDENCE="reports/migration/runs/$PEOPLE_MIGRATION_RUN_ID"
mkdir -p "$PEOPLE_MIGRATION_EVIDENCE"
git rev-parse HEAD > "$PEOPLE_MIGRATION_EVIDENCE/application-git-sha.txt"
git status --short > "$PEOPLE_MIGRATION_EVIDENCE/worktree-status.txt"
```

Never put a database URL, Email address, LinkedIn identifier, raw webhook body,
or unredacted campaign variable in the evidence directory.

## Database target guard

The repository's `.env.local` points at production. Every database command in
this runbook therefore receives an explicit `DATABASE_URL` override. Use a
dedicated shell variable; never edit `.env.local` during the run.

```sh
export PEOPLE_MIGRATION_DB_URL='postgresql://REPLACE_WITH_EXPLICIT_TARGET'
export PEOPLE_MIGRATION_EXPECTED_DB='REPLACE_WITH_DATABASE_NAME'
export PEOPLE_MIGRATION_EXPECTED_HOST='REPLACE_WITH_HOST_NAME'

export PEOPLE_MIGRATION_ACTUAL_DB="$(psql "$PEOPLE_MIGRATION_DB_URL" -X -v ON_ERROR_STOP=1 -Atc \
  'select current_database()')"
test "$PEOPLE_MIGRATION_ACTUAL_DB" = "$PEOPLE_MIGRATION_EXPECTED_DB"

psql "$PEOPLE_MIGRATION_DB_URL" -X -v ON_ERROR_STOP=1 -Atc \
  "select current_database(), inet_server_addr(), inet_server_port(), current_user, pg_is_in_recovery()"
```

The operator and database owner must compare the result with the approved
environment and write the confirmation to the run log. A staging rehearsal
must stop if its host/database is production. A production run must stop if the
restored and rehearsed staging source is not recent enough for the approved
window.

Commands below use this form:

```sh
set -euo pipefail
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server SCRIPT
```

This override is mandatory even for read-only commands.

## Non-negotiable safety gates

Every gate is fail-closed. A non-zero command exit, missing artifact, changed
count, unexplained snapshot difference, uncertain database target, lock
timeout, or operator interruption means **stop**. Do not improvise a SQL fix.

Before the first write:

- The exact commit has passed `bun x tsc --noEmit`, `bun test`, and
  `bunx --bun next build`.
- The full rehearsal, including rollback, passed twice on the same staging
  clone workflow. Preparation and backfill were each idempotent.
- A provider-native, point-in-time-restorable backup has an immutable backup
  ID, creation time, source database identity, retention time, restore target,
  checksum/provider verification, measured restore duration, and successful
  smoke-test evidence. A `pg_dump` file alone is not the approved backup.
- Independent pause controls have been deployed/backported and rehearsed for the
  in-process Email scheduler, external Email queue builder, LinkedIn invitation
  and follow-up jobs, LinkedIn resolver, and search queue.
- Webhook endpoints remain deployed while outbound work and mutations are
  paused. `WebhookEvent` rows persist before processing. Duplicate replay and
  recovery of `processing`/`error` events have been tested.
- Imports, campaign creation, enrollment changes, manual sends, and destructive
  UI actions are blocked by a rehearsed migration mode.
- All in-flight jobs are drained and their IDs/checkpoints are recorded.
- Preflight has zero unapproved P0/P1 results. The expected cleanup counts were
  copied from the immediately preceding dry runs, not from an older report.

The local implementation defines these controls:

| Environment flag | Effect when true |
|---|---|
| `PEOPLE_MIGRATION_MODE` | Master pause for all five worker classes and blocks campaign/import/manual-outbound mutation routes; webhook and unsubscribe routes remain open |
| `PAUSE_CAMPAIGN_MUTATIONS` | Keeps campaign/import/manual-outbound mutation routes blocked independently during selective worker canaries |
| `PAUSE_EMAIL_OUTBOUND` | Pauses the Email send tick and Email queue builder |
| `PAUSE_LINKEDIN_OUTBOUND` | Pauses LinkedIn invitations and follow-ups |
| `PAUSE_LINKEDIN_RESOLUTION` | Pauses LinkedIn profile resolution |
| `PAUSE_LINKEDIN_SEARCH` | Pauses the LinkedIn search queue |
| `PAUSE_GRID_WORKER` | Pauses enrichment/grid worker execution |

Values `1`, `true`, `yes`, and `on` are treated as true, case-insensitively.
Before cutover, backport these controls into a legacy-schema-compatible runtime
and deploy that bridge runtime first. Verify the controls through application
logs and no-op probes; do not assume changing an environment value updates a
running process. Do not begin if applying the flags requires a period in which
the webhook endpoints are unavailable.

`PEOPLE_MIGRATION_MODE=true` is the safe database-mutation state. Also set
`PAUSE_CAMPAIGN_MUTATIONS=true` before clearing the master flag for selective
canaries. Keep all five worker flags true except the single worker being
canaried. This preserves the write barrier while allowing one worker class to
resume.

## Staging rehearsal

Use a recent, isolated production clone with provider calls disabled or mocked.
Never point a staging application or test at live Email/LinkedIn credentials.

### 1. Record the untouched clone

```sh
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run snapshot:outreach --write-baseline
cp reports/migration/active-outreach-baseline.json \
  "$PEOPLE_MIGRATION_EVIDENCE/clone-active-outreach-baseline.json"

set +e
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run preflight:people
PEOPLE_MIGRATION_INITIAL_PREFLIGHT_STATUS=$?
set -e
printf '%s\n' "$PEOPLE_MIGRATION_INITIAL_PREFLIGHT_STATUS" \
  > "$PEOPLE_MIGRATION_EVIDENCE/preflight-before-prepare-exit-code.txt"
cp reports/migration/preflight-latest.json \
  "$PEOPLE_MIGRATION_EVIDENCE/preflight-before-prepare.json"
```

The initial preflight may report schema-not-prepared. Archive and inspect its
exit code and report; do not waive identity, duplicate, or active-template
findings hidden behind that expected schema result. Any failure other than the
known missing additive schema is a blocker.

### 2. Prepare additively and prove idempotency

These are the first database writes:

```sh
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/create-lead-tables.ts --apply
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/create-lead-tables.ts --apply
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/check-lead-schema.ts | tee "$PEOPLE_MIGRATION_EVIDENCE/schema-after-prepare.json"
```

Require `prepared: true`, no invalid indexes, nullable campaign Person
references, and an old-runtime smoke test against this prepared schema.
`check-lead-schema.ts` may exit successfully while `finalized` is false; inspect
the JSON rather than relying only on its exit code.

### 3. Preview and apply reviewed cleanup

Preview duplicate-message decisions and provider collisions:

```sh
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/mark-linkedin-message-duplicates.ts
cp reports/migration/linkedin-message-duplicate-decisions-preview.json \
  "$PEOPLE_MIGRATION_EVIDENCE/message-duplicate-preview.json"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/resolve-linkedin-provider-collisions.ts \
  | tee "$PEOPLE_MIGRATION_EVIDENCE/provider-collision-preview.json"
```

Review every decision. Then substitute counts from these exact previews:

```sh
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/mark-linkedin-message-duplicates.ts --apply \
  --expected-groups=REVIEWED_GROUP_COUNT \
  --expected-extra-rows=REVIEWED_EXTRA_ROW_COUNT \
  --confirm=preserve-provider-history
cp reports/migration/linkedin-message-duplicate-decisions-applied.json \
  "$PEOPLE_MIGRATION_EVIDENCE/message-duplicate-applied.json"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/resolve-linkedin-provider-collisions.ts --apply \
  --expected-groups=REVIEWED_GROUP_COUNT \
  --confirm=keep-most-recent-request \
  | tee "$PEOPLE_MIGRATION_EVIDENCE/provider-collision-applied.json"
```

The duplicate script preserves all `Message` rows and marks later deliveries
with `duplicateOfMessageId`. The collision script preserves both Leads, keeps
the most recent request actionable, and marks older rows `CANCELLED` with
`supersededByLeadId`. Stop if the reviewed counts drift or either script rejects
a group's history.

### 4. Establish the authoritative behavior baseline

Cleanup intentionally changes canonical duplicate/collision state, so replace
the earlier clone baseline only after those decisions have been approved and
applied, but immediately before People backfill:

```sh
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run snapshot:outreach --write-baseline
cp reports/migration/active-outreach-baseline.json \
  "$PEOPLE_MIGRATION_EVIDENCE/pre-backfill-active-outreach-baseline.json"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run preflight:people --stage=ready
cp reports/migration/preflight-latest.json \
  "$PEOPLE_MIGRATION_EVIDENCE/preflight-ready.json"
```

Require `passed: true`. Also archive Email queue/render and LinkedIn eligibility
comparisons from the integration suite; the aggregate preflight does not prove
behavior equivalence by itself.

### 5. Backfill and prove idempotency

```sh
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/backfill-campaign-people.ts \
  | tee "$PEOPLE_MIGRATION_EVIDENCE/backfill-dry-run.txt"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/backfill-campaign-people.ts --apply \
  --expected-email=REVIEWED_EMAIL_COUNT \
  --expected-linkedin=REVIEWED_LINKEDIN_COUNT \
  | tee "$PEOPLE_MIGRATION_EVIDENCE/backfill-apply.txt"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/backfill-campaign-people.ts --apply \
  --expected-email=0 --expected-linkedin=0 \
  | tee "$PEOPLE_MIGRATION_EVIDENCE/backfill-second-apply.txt"

# For the repository's disposable legacy fixture only (not production data):
psql "$PEOPLE_MIGRATION_DB_URL" -X -v ON_ERROR_STOP=1 \
  -f tests/assert-legacy-people-migration.sql
```

The second apply must find zero unlinked Email and LinkedIn rows and make zero
changes. Stop on a missing identity, contradictory identity, duplicate planned
membership, or incomplete Person link.

With Email/LinkedIn sends still paused, keep the LinkedIn resolver enabled and
run the guarded resolver in reviewed batches. Resolver leases prevent two
accounts or job invocations from decoding the same Lead concurrently. The
command performs profile lookups only; it never sends invitations or messages:

```sh
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run resolve:legacy-linkedin

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run resolve:legacy-linkedin --apply \
  --expected-database="$PEOPLE_MIGRATION_EXPECTED_DATABASE" \
  --expected-actionable=REVIEWED_COUNT --passes=1 \
  --confirm=outbound-workers-paused
```

Repeat with the newly reported count until the audit reaches zero. Keep Email
and LinkedIn outbound paused throughout; do not enable invitations or follow-ups.

### 6. Verify behavior, then finalize

```sh
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run postflight:people
cp reports/migration/postflight-latest.json \
  "$PEOPLE_MIGRATION_EVIDENCE/postflight-before-finalize.json"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run audit:email-people-parity
cp reports/migration/email-people-parity-latest.json \
  "$PEOPLE_MIGRATION_EVIDENCE/email-people-parity.json"
LINKEDIN_PARITY_DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" \
  LINKEDIN_PARITY_EXPECTED_DATABASE="$PEOPLE_MIGRATION_EXPECTED_DATABASE" \
  bun --no-env-file --conditions=react-server scripts/audit-linkedin-migration-parity.ts
cp reports/migration/linkedin-behavior-parity.json \
  "$PEOPLE_MIGRATION_EVIDENCE/linkedin-people-parity.json"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run preflight:people --stage=cutover
cp reports/migration/preflight-latest.json \
  "$PEOPLE_MIGRATION_EVIDENCE/preflight-cutover.json"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run snapshot:outreach

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/finalize-lead-tables.ts \
  | tee "$PEOPLE_MIGRATION_EVIDENCE/finalize-check.txt"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/finalize-lead-tables.ts --apply \
  | tee "$PEOPLE_MIGRATION_EVIDENCE/finalize-apply.txt"

DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun --conditions=react-server \
  scripts/check-lead-schema.ts | tee "$PEOPLE_MIGRATION_EVIDENCE/schema-final.json"
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run postflight:people
DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" bun run audit:email-people-parity
LINKEDIN_PARITY_DATABASE_URL="$PEOPLE_MIGRATION_DB_URL" \
  LINKEDIN_PARITY_EXPECTED_DATABASE="$PEOPLE_MIGRATION_EXPECTED_DATABASE" \
  bun --no-env-file --conditions=react-server scripts/audit-linkedin-migration-parity.ts
```

Require `finalized: true`, validated foreign keys, both Person references
`NOT NULL`, all six final indexes present/valid/ready, zero postflight blockers,
and an unchanged active-outreach snapshot. Run the full database integration
suite and both active-channel smoke suites before deployment. The Email parity
report must contain zero recipient changes and zero changed pending steps.
The LinkedIn parity report must contain zero target, next-action, rendered
content, sender-eligibility, or restart-claim differences.
The cutover preflight must pass only after all active unresolved LinkedIn
identifiers are resolved and the backfill dry-run reports zero remaining rows.

### 7. Rehearse cutover and rollback

With providers mocked, simulate in this order: set
`PEOPLE_MIGRATION_MODE=true`; confirm all five worker classes report paused;
pause all
outbound workers; drain jobs; record webhook high-water mark; inject accepted-
connection and inbound-message fixtures; run migration; deploy; verify each
fixture attached exactly once; set `PAUSE_CAMPAIGN_MUTATIONS=true`, clear the
master flag while retaining every narrow worker flag, then clear only the
canary worker's flag; resume one worker
class with a one-item canary;
trigger rollback; reconcile the simulated post-backup events; verify old-runtime
compatibility and no duplicate next action.

Repeat the complete rehearsal from a fresh clone. Archive both run directories.

## Production cutover

Production uses the exact commit, scripts, reviewed decision rules, and command
order that passed staging. Replace no command during the window.

1. Announce the window and name the rollback authority.
2. Set `PEOPLE_MIGRATION_MODE=true` in the already deployed bridge runtime to
   block imports, campaign/enrollment mutations, and manual sends and to pause
   every worker. Verify the new value is active without taking webhooks down.
3. Also set `PAUSE_CAMPAIGN_MUTATIONS=true`, `PAUSE_EMAIL_OUTBOUND=true`,
   `PAUSE_LINKEDIN_OUTBOUND=true`, `PAUSE_LINKEDIN_RESOLUTION=true`,
   `PAUSE_LINKEDIN_SEARCH=true`, and `PAUSE_GRID_WORKER=true`. This makes the
   intended state explicit and permits controlled canaries after the master
   flag is cleared. Confirm the in-process Email tick, external Email queue
   builder, LinkedIn invitation/follow-up jobs, resolver, search queue, and
   grid worker each report paused.
4. Wait for in-flight jobs to finish. Record job IDs/checkpoints and verify no
   outbound provider calls continue.
5. Record the last `WebhookEvent.createdAt` and ID, processing-status counts,
   active-outreach snapshot, queue counts, and campaign state distributions.
6. Create and verify the provider-native backup. Record its immutable ID.
7. Run baseline preflight. If any unexplained P0/P1 result exists, abort.
8. Run prepare twice and inspect schema JSON.
9. Rerun cleanup previews. Apply only if every decision and count matches the
   staged/reviewed rule; archive the fresh production ledgers.
10. Write a new active-outreach baseline after cleanup and immediately before
    backfill.
11. Run ready preflight and backfill dry-run. Require success.
12. Apply backfill once, rerun it, and require zero changes.
13. Run postflight, active snapshot comparison, render/queue equivalence, and
    LinkedIn eligibility comparison.
14. Run finalization check, obtain explicit go/no-go approval, apply
    finalization, and require `finalized: true` plus a clean postflight.
15. Deploy the new runtime while webhooks remain live. Reconcile all webhook
    events after the recorded high-water mark before resuming workers.
16. Keep mutation routes blocked at ingress, set
    `PEOPLE_MIGRATION_MODE=false`, and leave all five narrow pause flags true.
    Resume one worker class at a time by clearing only its narrow flag, using a
    one-recipient canary: Email send, LinkedIn resolver, LinkedIn invitation,
    then LinkedIn follow-up. Search and grid workers remain paused through the
    rollback observation window.
17. At each canary, verify target, sender, content, one provider call, one
    message row, expected state transition, webhook lag, and error rate.
18. Resume normal workers only after the rollback authority signs off. Keep
    migration mode blocking new campaign enrollment for the agreed rollback
    window so the legacy runtime remains usable.

## Immediate rollback triggers

Pause all outbound workers immediately on any of these signals:

- a recipient, LinkedIn provider target, sender account, rendered message,
  sequence position, or next action differs from the approved baseline;
- any duplicate provider call or duplicate Email/LinkedIn send;
- a reply, bounce, complaint, unsubscribe, connection, or message is assigned
  to the wrong enrollment or Person;
- webhook ingestion fails, remains `processing`, is duplicated, or exceeds the
  agreed staging lag/error threshold;
- campaign counts/state distributions change outside reviewed cleanup;
- a Person reference is missing/orphaned or a uniqueness invariant fails;
- the canary differs from rehearsal, or an operator cannot explain a change.

Do not resume another worker while investigating.

## Rollback decision tree

### A. Before any database write

Abort. Keep the old runtime and webhooks live, remove migration mode, resume
workers from their recorded checkpoints, and verify one no-send scheduler tick
before normal operation.

### B. After prepare, but before cleanup/backfill

Prefer an in-place application rollback. Preparation is additive and preserves
legacy data. Run the old-runtime smoke suite against the prepared schema, then
resume from checkpoints. Leave additive objects in place for investigation;
do not drop tables/columns during an incident.

### C. After cleanup/backfill/finalization, before any worker resumes

Keep webhooks live and outbound work paused. Choose between:

- **Snapshot restore**, only if no webhook/import/manual mutation occurred
  after the backup, or if every such write has been durably captured and its
  replay has already been rehearsed.
- **In-place compatibility rollback**, preferred when webhook writes exist.
  Preserve all message, connection, and webhook rows; reverse only the exact
  migration markers from reviewed ledgers; make new Person references nullable
  before starting the old runtime; then run post-rollback invariants.

Never restore over post-backup webhooks merely because outbound workers did not
resume.

### D. After any worker resumes or provider action occurs

Do not restore the pre-migration snapshot. That could erase provider-confirmed
sends, replies, suppressions, or connections and cause a repeat send. Use
in-place compatibility rollback and reconcile every database/provider action
after the backup high-water mark. Keep imports and campaign creation blocked.

If a new-runtime enrollment has a null legacy `outreach_leads.email` or
`Lead.linkedinUrl`, the old runtime is not compatible until that exact row is
reconstructed from its Person and verified. If no canonical LinkedIn identity
exists, quarantine the enrollment and keep it ineligible; never invent a slug.

## In-place compatibility rollback procedure

This procedure must be turned into a reviewed, idempotent script and rehearsed
before production. The SQL below documents required effects; it is not an
authorization to paste ad-hoc SQL into production.

1. Pause and drain all outbound work; keep webhook ingestion live.
2. Capture a new provider-native backup and a fresh high-water mark.
3. Copy all post-backup `WebhookEvent`, `Message`, `Connection`,
   `outreach_emails`, suppression, Lead, and campaign-state changes to the
   reconciliation ledger.
4. For each duplicate-message decision ledger, clear
   `duplicateOfMessageId` only on the recorded duplicate IDs and only when it
   still equals the recorded survivor ID. Never delete a Message.
5. For each provider-collision ledger, clear `supersededByLeadId` and restore
   the prior status only if the row is still `CANCELLED`, still points to the
   recorded survivor, and gained no message/connection history. Otherwise send
   the group to manual reconciliation.
6. Drop `NOT NULL` from only `outreach_leads.person_id` and `Lead.personId` so
   the old runtime can insert legacy rows. Leave People, legacy fields, foreign
   keys, and indexes intact during the incident.
7. Verify every legacy Email enrollment has its original non-null Email and
   every old-runtime LinkedIn enrollment has its original non-null LinkedIn
   identifier. Backfill a null legacy field from the linked Person only after
   comparing it with provider/message history; unresolved rows stay paused.
8. Deploy the exact pre-cutover application commit and run read-only smoke
   tests before resuming any worker.
9. Reprocess/replay captured webhook events idempotently, then compare counts,
   state distributions, and provider IDs with both high-water snapshots.
10. Resume one worker class with a one-item canary. Stop on any mismatch.

The schema compatibility change that a rollback script must perform is:

```sql
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE outreach_leads ALTER COLUMN person_id DROP NOT NULL;
ALTER TABLE "Lead" ALTER COLUMN "personId" DROP NOT NULL;
COMMIT;
```

The reviewed rollback script must add preconditions, expected-row guards,
advisory locking, a dry-run mode, an immutable decision report, and
postconditions. Until that script and its rehearsal exist, finalization is a
production **NO-GO**.

The guarded implementation is `scripts/rollback-people-migration.ts`. Run the
same arguments for `--phase=check`, then `--phase=apply-schema --apply
--confirm=in-place-compatibility-rollback`, and finally `--phase=verify`.
Every run requires the expected database, host, deployed application SHA,
backup ID, null-legacy-identity counts, and active-job count. Reports are
created with exclusive file creation under `reports/migration/rollback`.

Before and after rollback, run
`scripts/export-people-migration-reconciliation.ts` with source and target
`(createdAt,id)` webhook cursors and reviewed webhook counts. It includes all
pre-source non-terminal webhooks and redacted interval snapshots; it does not
claim provider delivery truth, which must still be reconciled separately.

## Webhook and provider reconciliation

Use database IDs/timestamps only to find candidate changes; provider IDs are
the source of truth for whether an outbound action happened. For the interval
from backup/high-water time through rollback completion:

- Every `WebhookEvent` must have one disposition: `ok`, intentionally
  `skipped`, retryable `error`, or manual review. No row may remain silently
  `processing`.
- Replaying the same provider event must not create a second Message,
  Connection, Email reply, or campaign transition.
- Every provider-confirmed outbound Email maps to one `outreach_emails` row and
  one Lead/step; every provider-confirmed LinkedIn action maps to one canonical
  Message/Lead/account.
- Every inbound Email reply/bounce/complaint/unsubscribe and LinkedIn
  reply/connection maps to exactly one enrollment. Ambiguity changes no
  campaign state and goes to manual review.
- Suppression and replied state always win over an older queued send.
- Provider actions absent from the database are inserted/reconciled before any
  scheduler resumes. Database actions absent from the provider are not assumed
  delivered and require channel-specific review.

Archive a redacted reconciliation report containing the interval, source and
target high-water marks, counts by event/action/status, exact affected database
IDs, disposition, operator, timestamp, and provider verification result.

## Post-rollback acceptance gates

Rollback is complete only when:

- webhook endpoints stayed available and all interval events have a recorded
  disposition;
- no provider-confirmed send, reply, bounce, complaint, unsubscribe,
  connection, or message was lost or duplicated;
- old-runtime smoke tests pass against the retained additive schema;
- active Email and LinkedIn row/message counts equal the reconciled baseline;
- recipient/provider target, sender, status, sequence position, next action,
  suppression, and thread/message ownership are correct;
- one-item Email and LinkedIn canaries complete without duplicate sends;
- the incident backup and all redacted ledgers are retained.

## Rollback window and later cleanup

Keep legacy columns, `campaign_members`, People links, cleanup ledgers, backup,
and old deploy artifact until at least the agreed observation window has passed
with stable Email, LinkedIn, and webhook metrics. Do not accept new campaign
enrollments that omit legacy identities while old-runtime rollback remains a
requirement.

Dropping legacy columns/tables, removing compatibility reads, deleting
historical duplicates, or expiring rollback artifacts is a separate migration
with separate approval. It is never part of this cutover.

## Final sign-off record

The production evidence must name the database, commit, backup ID, staged run
IDs, worker checkpoints, high-water marks, cleanup counts, preflight/postflight
paths, schema state, integration/smoke results, canary results, monitor
thresholds, rollback-window end, go/no-go approver, and rollback authority.

Any blank field means **NO-GO**.
