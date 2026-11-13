# Unified People Migration: Remediation and Cutover Plan

Status: production database migration completed on 2026-08-27; application
deployment and controlled worker canaries remain pending.

Date: 2026-08-27

Production result: the additive schema, duplicate-delivery preservation,
provider-ownership cleanup, People backfill, foreign-key validation, unique
indexes, and mandatory campaign `personId` constraints were applied
successfully. Postflight reports zero database invariants. All 1,578 Email and
18,018 LinkedIn enrollments have a Person. The 2,296 pending LinkedIn rows with
legacy source identifiers intentionally remain on the resolver path; they
cannot be invited until Unipile fills the canonical profile and provider ID.

Implementation progress: Issue 1 schema-stage separation is implemented
locally and awaits review against a non-production database. No database command
has been run. Issue 2 was audited through a read-only production transaction:
46 Leads contain 48 extra provider-confirmed acceptance deliveries, all with
identical content and a 0–6 second delivery window. The local remediation keeps
every delivery row and marks later rows through `duplicateOfMessageId`; it has
not been applied to the database. Issue 3's read-only audit found 12,985
case-insensitive legacy raw-key conflicts across 6,899 LinkedIn identities and
zero conflicts referenced by active templates. The local backfill now chooses
the newest non-empty value deterministically and archives older distinct values
under `people.raw.__legacy_conflicts`; it has not been applied.

The cross-channel audit now reports two active Email/LinkedIn overlaps and zero
unresolved identity contradictions. One Email appeared with two LinkedIn slugs,
but both rows have the same Unipile provider ID; the backfill therefore treats
the newer slug as a provider-confirmed alias update. The provider/account audit
also found one pair of active `REQUEST_SENT` Leads. Local remediation preserves
both histories, assigns future execution to the most recent request, and marks
the older enrollment as superseded; it has not been applied.

The unresolved-identifier audit currently finds 2,392 legacy rows without a
canonical profile in `leadData`: 2,364 public-slug inputs and 28 encoded/opaque
inputs. Of these, 2,314 are pending in active campaigns. Resolution now uses a
separate retry counter and backoff, so provider lookup failures cannot consume
the invitation retry budget or mark the Lead failed.

Outbound crash-window hardening is now implemented locally. Email queue rows
are unique per Lead and Email delivery claims are unique per `(lead, step)`;
an uncertain Gmail result keeps the claim and requires reconciliation instead
of retrying automatically. LinkedIn invitation, acceptance, and follow-up
claims are likewise created before provider calls and retained when a provider
outcome is ambiguous. The disposable fixture proves an Email replay makes only
one provider call. These protections still require duplicate-count review and
staging canaries before production finalization.

An isolated PostgreSQL 16 fixture rehearsal completed the full prepare,
cleanup, backfill, postflight, and finalize sequence. That rehearsal exposed
and fixed an order-dependent alias bug: provider-collision cleanup updates a
Lead's operational `updatedAt`, so backfill now selects legacy LinkedIn/raw
values using immutable `requestSentAt ?? createdAt` chronology instead. The
fixture asserts that the newer provider-confirmed slug and raw value win, and
the corrected sequence passes twice-idempotent prepare/backfill/finalize checks.
This is useful local evidence, but it does not replace the required rehearsal
on a recent staging clone or the active-campaign integration suite.

## Objective

Move active Email and LinkedIn campaign enrollments onto the shared `people.id`
identity without changing who is contacted, what is sent, campaign progress,
reply handling, bounce handling, unsubscribe handling, or LinkedIn webhook
processing.

The migration is approved only when every critical gate in this document passes
against a recent production copy. A successful typecheck or unit-test run alone
is not migration approval.

## Target model

- `people` owns reusable profile and enrichment data.
- `companies` owns company data and is connected through `people.company_id`.
- `outreach_leads` is an Email campaign enrollment. It stores execution state
  and refers to `people.id` through `person_id`.
- `Lead` is a LinkedIn campaign enrollment. It stores execution state and refers
  to `people.id` through `personId`.
- An unresolved LinkedIn search/provider value remains temporarily on the
  LinkedIn enrollment as `sourceLinkedinIdentifier` plus `sourceLinkedinApi`.
- After Unipile resolves it, the canonical LinkedIn identity is written to
  `people.linkedin_url`, the provider identity is written to `Lead.providerId`,
  and the unresolved source fields are cleared.
- New mapped imports write typed values to People/Company columns. Only unmapped
  extras go to `people.raw`.
- Existing campaign data is preserved in its legacy columns during the rollback
  window. It is not deleted as part of this migration.
- Sent and received message content remains in the existing message tables.
- `campaign_members` is not required by the target runtime. It is absent in the
  current schema, so migration and rollback tooling report `absent_expected`
  and must not create it. If a staging clone contains it, preserve it through
  the rollback window.

## Priority summary

| Priority | Meaning | Migration rule |
|---|---|---|
| P0 — Critical | Could contact the wrong person, duplicate a send, stop active outreach, lose events, or make the migration non-reversible | Must be fixed and verified before migration |
| P1 — High | Could corrupt profile/template data or make failures hard to diagnose | Must be fixed before production cutover |
| P2 — Medium | Improves maintainability and confidence but does not independently endanger active campaigns | May follow only if explicitly deferred |

Current audit counts such as 48, 7,226, and 45 are snapshots. The preflight must
recalculate them immediately before every rehearsal and production run.

## Execution order

1. Build read-only audit and invariant tooling.
2. Separate additive schema preparation from constraint finalization.
3. Clean duplicate message records without losing provider evidence.
4. Classify legacy raw-data conflicts and protect active template variables.
5. Reconcile Email, LinkedIn, and provider identities.
6. Resolve or safely quarantine legacy LinkedIn source identifiers.
7. Rehearse schema preparation and backfill on a recent production copy.
8. Run database integration and active-campaign smoke tests.
9. Prepare the production runbook, backup, pause controls, and rollback checks.
10. Execute only after the final go/no-go report contains zero unresolved P0 or
    P1 blockers.

## Issue 1 — Schema preparation currently creates constraints too early

**Priority: P0 — Critical**

`scripts/create-lead-tables.ts` currently adds tables and nullable reference
columns, but it also creates unique indexes. Existing duplicate data can make
the script fail halfway through and leave an unclear partial state.

### Remediation

- Split schema work into two idempotent stages:
  - `prepare`: create `people`, `companies`, registries, nullable person-ID and
    LinkedIn source columns, foreign keys, and non-unique indexes.
  - `finalize`: create uniqueness constraints and set both campaign person IDs
    to `NOT NULL` only after cleanup and backfill verification.
- Add foreign keys as `NOT VALID` during preparation, validate them only after
  backfill, and use lock/statement timeouts so unexpected table contention
  aborts instead of freezing the live application.
- Build large unique indexes with PostgreSQL's concurrent-index mechanism where
  supported. Keep those statements outside transaction blocks, detect invalid
  leftover indexes on retry, and remove only the specifically named invalid
  index before rebuilding it.
- Keep every statement repeatable and record which stage completed.
- Add a schema-state inspection command that reports missing columns,
  constraints, indexes, and nullability without changing the database.
- Do not let application startup automatically run either stage.

### Files

- Modify `scripts/create-lead-tables.ts` or split it into clearly named prepare
  and finalize scripts.
- Keep `src/lib/leads/schema.ts`, `src/lib/outreach/schema.ts`, and
  `src/lib/linkedin/schema.ts` aligned with the finalized schema.

### Acceptance gate

- Prepare succeeds twice on a staging copy, proving idempotency.
- Prepare does not require legacy rows to already be clean.
- Finalize refuses to run while any invariant or duplicate check fails.
- A schema diff after finalization matches the expected schema exactly.

### Stop condition

Stop if prepare modifies existing campaign state, drops a column, rewrites a
message, or creates a constraint before its data has passed preflight.

## Issue 2 — 48 duplicate automated LinkedIn message groups

**Priority: P0 — Critical**

The unique index on `(leadId, type)` for automated LinkedIn messages cannot be
created while duplicate groups exist. Blind deletion could discard the row that
contains the real provider message ID or delivery timestamp.

### Remediation

- Create a read-only duplicate report grouped by `leadId` and automated message
  type.
- For every group, select a survivor in this order:
  1. A row whose provider message ID is confirmed by Unipile.
  2. Otherwise, a row with a non-null provider message ID.
  3. Otherwise, the row with the strongest sent/delivered timestamp evidence.
  4. Otherwise, the earliest deterministic row by creation time and ID.
- Merge non-conflicting metadata into the survivor.
- Write every removed row and the reason for choosing the survivor to an audit
  artifact before changing data. Provider-confirmed historical deliveries are
  not deleted: later rows point to the earliest canonical row through
  `Message.duplicateOfMessageId`.
- Make cleanup transactional per duplicate group and idempotent.
- Run the cleanup first in dry-run mode, then on staging, before creating
  `Message_automated_lead_type_uq`.

### Proposed tooling

- `scripts/audit-linkedin-message-duplicates.ts`
- `scripts/cleanup-linkedin-message-duplicates.ts --dry-run|--apply`
- `reports/migration/linkedin-message-duplicates.json`

### Acceptance gate

- Zero canonical duplicate automated `(leadId, type)` groups remain; historical
  duplicate deliveries remain queryable through `duplicateOfMessageId`.
- The number of logical sent steps per Lead is unchanged.
- Every retained provider message ID still maps to the same Lead and account.
- The unique index can be created successfully.

### Stop condition

Stop and manually review any group containing different provider message IDs
that both appear valid, conflicting message bodies, or contradictory send times.

## Issue 3 — 7,226 conflicting legacy raw values

**Priority: P0 for active-template fields; P1 otherwise**

Several legacy campaign rows resolve to the same person but contain different
values for the same raw key. A simple JSON merge would silently choose one and
could change a variable in a scheduled Email or LinkedIn message.

### Remediation

- Build a conflict classifier that reports identity, raw key, all values,
  sources, campaign IDs, campaign activity, timestamps, and whether an active
  template references the key.
- Auto-resolve only safe categories:
  - identical after normalization;
  - blank versus non-blank, keeping non-blank;
  - exact aliases that map to a single typed canonical field;
  - demonstrably newer enrichment of the same fact when no active template
    depends on the older value.
- Never silently resolve contradictory Email addresses or LinkedIn identities.
- For an active legacy campaign whose template depends on conflicting values,
  keep reading that campaign row's existing legacy variable value during the
  rollback window. This is a temporary compatibility rule, not the permanent
  data model. New campaigns use People/Company plus `people.raw` only.
- Preserve all original legacy columns until every affected active campaign has
  completed or been explicitly migrated to one reviewed value.
- Send all unresolved conflicts to a deterministic review report rather than
  choosing the last row processed.

### Proposed tooling

- `scripts/classify-legacy-raw-conflicts.ts`
- `reports/migration/raw-conflicts-summary.json`
- `reports/migration/raw-conflicts-manual-review.csv`

### Acceptance gate

- Zero unresolved conflicts for identity fields.
- Zero unresolved conflicts for variables referenced by active templates.
- Re-rendering every pending active message before and after backfill produces
  byte-equivalent recipient addresses and rendered content, except for an
  explicitly reviewed allowlist.
- Every automatic winner has its rule and source recorded.

### Stop condition

Stop if a conflict changes a recipient, changes an active message, requires a
guess about which person is correct, or cannot be reversed from the audit file.

## Issue 4 — Identity matching needs one deterministic rule

**Priority: P0 — Critical**

Different import and resolver paths must not independently decide whether two
rows represent the same person.

### Remediation

Use one shared identity algorithm in `src/lib/leads/identity.ts` and
`src/lib/leads/records.ts`:

1. Normalize and match valid Email case-insensitively.
2. Normalize and match a canonical public LinkedIn slug.
3. While LinkedIn is unresolved, match the exact source identifier only through
   `Lead.sourceLinkedinIdentifier` and its API hint—not through
   `people.linkedin_url`.
4. If Email and LinkedIn resolve to different People rows, do not auto-merge.
   Create a manual-review item and block that enrollment.
5. If one Person matches, reuse its ID and merge only compatible incoming data.
6. If no Person matches, create one. A LinkedIn import may create a provisional
   Person with no canonical identity until Unipile resolves it.

All import routes—Email CSV, LinkedIn CSV, grid-to-campaign, and enrichment-to-
campaign—must call the same shared functions. Export/search alone must not
create People; campaign creation/enrollment does.

### Acceptance gate

- Unit tests cover Email-only, LinkedIn-only, both matching, neither matching,
  source-identifier reuse, concurrent imports, and contradictory cross-matches.
- Concurrent duplicate imports produce one Person and one enrollment per
  campaign.
- Contradictory identity input produces no partial writes.

### Stop condition

Stop if any route has its own identity-matching implementation or can bypass the
transaction and unique constraints.

## Issue 5 — Cross-channel identity conflicts

**Priority: P0 — Critical**

The audit found cross-channel overlap, including two People participating in
both Email and LinkedIn activity. They may be correct shared identities or
accidental merges; either case affects active outreach.

### Remediation

- Produce an identity graph with People, Email enrollments, LinkedIn
  enrollments, normalized Email, canonical LinkedIn slug, unresolved source ID,
  and provider/account ID.
- Classify each connected component as:
  - confirmed same person;
  - harmless shared Person with compatible data;
  - duplicate People that can be merged;
  - contradictory identity requiring manual review.
- For an approved merge, choose one canonical `people.id`, relink both channel
  enrollments in one transaction, merge compatible profile data, and retain an
  old-ID-to-new-ID audit ledger.
- Do not alter campaign status, sequence position, assigned sender, timestamps,
  thread IDs, suppression state, or message rows.

### Proposed tooling

- `scripts/reconcile-campaign-identities.ts --dry-run|--apply`
- `reports/migration/cross-channel-identities.json`
- `reports/migration/person-id-aliases.json`

### Acceptance gate

- Every reviewed component has one explicit disposition.
- No active enrollment changes recipient identity without manual approval.
- Counts and state distributions for both channels are identical before and
  after relinking.

### Stop condition

Stop on any Email/LinkedIn disagreement, one-to-many identity mapping, or Person
merge that would violate a campaign uniqueness constraint.

## Issue 6 — 45 encoded or internal LinkedIn identifiers

**Priority: P0 for actionable Leads; P1 for inactive records**

These identifiers are not canonical LinkedIn public slugs. Writing them into
`people.linkedin_url` would pollute identity matching and could target the wrong
profile.

### Remediation

- Classify each value as public LinkedIn URL/slug, Sales Navigator identifier,
  Recruiter identifier, or opaque provider identifier.
- Create/reuse the Person immediately, but keep the unresolved value only in
  `Lead.sourceLinkedinIdentifier`; store `sales_navigator` or `recruiter` in
  `Lead.sourceLinkedinApi` where needed.
- Resolve through Unipile `GET /users/{identifier}` with the correct account and
  API hint.
- Use a resumable ledger containing Lead ID, account, input identifier, attempt
  count, response classification, resolved provider ID, canonical slug, and
  error.
- In one transaction, enrich or relink the Person, write canonical
  `people.linkedin_url`, write `Lead.providerId`, then clear the two source
  fields.
- Map returned common fields into typed People/Company columns; put only
  unmapped provider payload fields into `people.raw`.
- Keep failures unresolved and ineligible for sending; never guess a slug.

### Proposed tooling

- Extend `src/functions/resolveProfiles.ts` and
  `src/services/unipile.service.ts` only through their shared resolver path.
- Add `scripts/resolve-legacy-linkedin-identifiers.ts` with dry-run, retry,
  resume, rate-limit, and failure-report support.

### Acceptance gate

- Every active/actionable LinkedIn Lead has `personId`, `providerId`, a canonical
  Person LinkedIn slug, and cleared source fields.
- Every remaining unresolved Lead is non-actionable and visibly quarantined.
- Resolver retries do not create duplicate People or repeat completed work.

### Stop condition

Stop if Unipile returns an identity already owned by an incompatible Person, the
account/API context is uncertain, or a resolver result would change an active
Lead's provider target.

## Issue 7 — One provider/account collision affects two actionable Leads

**Priority: P0 — Critical**

Two actionable LinkedIn Leads resolving to the same provider identity/account
can produce duplicate outreach or route a webhook to the wrong Lead.

### Remediation

- Report collisions using the actual provider identity scope. Treat
  `(providerId, linkedinAccountId)` as the safety key unless verified provider
  behavior establishes a stricter global identity.
- Temporarily mark both colliding Leads ineligible for automated work while they
  are reviewed.
- Determine whether they are duplicate enrollments, the same Person in separate
  campaigns, or incorrect provider resolution.
- Preserve the valid campaign enrollment. Merge/delete only when campaign and
  message history proves one row is redundant.
- Make webhook lookup deterministic and reject ambiguous matches instead of
  updating both Leads.

### Acceptance gate

- Zero ambiguous actionable provider/account collisions.
- A fixture webhook updates exactly one expected Lead.
- An ambiguous fixture is recorded for review and changes no campaign state.

### Stop condition

Stop if both rows have distinct valid message/thread histories or if the
provider identity scope cannot be established.

## Issue 8 — Every legacy campaign row needs a valid Person

**Priority: P0 — Critical**

The new runtime expects every Email and LinkedIn enrollment to resolve profile
data through a Person. A missing or incorrect reference can stop sends or target
the wrong recipient.

### Remediation

- Make `scripts/backfill-campaign-people.ts` fully resumable and idempotent.
- Add an immutable per-row decision report: legacy row ID, matched identity,
  selected/created Person ID, match rule, conflicts, and result.
- Process bounded batches in transactions and support restarting after failure.
- Preserve all legacy identity/profile columns during the rollback window.
- For Email, require a normalized Email on the linked Person.
- For LinkedIn:
  - actionable non-pending states require canonical Person LinkedIn identity and
    provider identity;
  - unresolved pending Leads require `personId` plus a source identifier and
    remain send-ineligible.
- Run post-backfill invariants before setting either reference `NOT NULL`.

### Acceptance gate

- `outreach_leads.person_id IS NULL`: zero.
- `Lead.personId IS NULL`: zero.
- Orphaned person references: zero.
- Duplicate Person/campaign memberships: zero.
- Every Email enrollment's Person has a valid Email.
- Every actionable LinkedIn enrollment has a resolved target.
- Row counts and campaign-state counts are unchanged.

### Stop condition

Stop if any row cannot be assigned deterministically, any campaign loses a row,
or applying the backfill twice produces additional changes.

## Issue 9 — Duplicate campaign membership constraints need cleanup

**Priority: P0 — Critical**

After People are linked, two legacy enrollment rows can collapse to the same
`(personId, campaignId)` and prevent unique-index creation or duplicate a send.

### Remediation

- Audit duplicate Email and LinkedIn memberships after identity decisions are
  simulated but before writes.
- Never deduplicate by profile data alone. Compare campaign state, assigned
  sender, sequence position, next-send time, message history, reply status,
  suppression state, and provider/thread IDs.
- Auto-merge only when one row is demonstrably empty/redundant.
- Manually decide groups with activity on both rows.
- Record survivor and merged row IDs in the migration ledger.

### Acceptance gate

- Zero duplicate `(personId, campaignId)` groups in either channel.
- No sent message, reply, bounce, unsubscribe, or provider thread becomes
  orphaned.
- Both campaign-membership unique indexes build successfully.

### Stop condition

Stop when both duplicate rows contain conflicting execution or conversation
history.

## Issue 10 — Database integration coverage is incomplete

**Priority: P0 — Critical**

The current unit tests and typecheck do not prove that real database constraints,
transactions, schedulers, and webhook handlers work together after backfill.

### Remediation

Create an isolated database integration suite covering:

- Email CSV mapping, typed fields, extras in `people.raw`, Person reuse, and
  campaign enrollment.
- LinkedIn CSV mapping, provisional Person creation, source identifier storage,
  Unipile resolution, Person relinking, and send eligibility.
- Grid/enrichment campaign creation, while confirming export/search alone does
  not create People.
- Re-import/update behavior and contradictory identity rollback.
- Email queue building, variable rendering, send recording, reply ingestion,
  bounce suppression, complaint/unsubscribe handling, and subsequent-send
  prevention.
- LinkedIn invitation, acceptance, follow-ups, retries, reply webhook, manual
  messaging, and ambiguous-provider handling.
- Concurrent imports and concurrent resolver workers.
- Backfill idempotency and post-migration invariant checks.
- Crash immediately before/after each provider call; an existing or uncertain
  delivery claim must prevent a second Email or LinkedIn provider action.

Use transaction-scoped fixtures or a disposable database. Provider calls must be
recorded fixtures/mocks except for a separately approved credentialed smoke test.

### Files to exercise

- `src/lib/outreach/leadImport.ts`, `render.ts`, `buildQueue.ts`, `scheduler.ts`,
  `replyBridge.ts`, and the Email webhook/unsubscribe routes.
- `src/lib/linkedin/importLeads.ts`, `campaignLeads.ts`,
  `leadOutreachEligibility.ts`, `src/functions/resolveProfiles.ts`,
  `sendInvitations.ts`, `sendFollowUps.ts`, and LinkedIn webhook routes.
- `src/lib/leads/records.ts`, `identity.ts`, `variables.ts`, and
  `campaignAssignments.ts`.
- Extend `scripts/test-lead-campaign-bridge.ts` or replace it with an automated
  integration suite that fails with a non-zero exit code.

### Acceptance gate

- All unit and database integration tests pass repeatedly.
- TypeScript and production build pass.
- Existing build warnings are documented separately and do not hide a new
  migration warning.
- Repository-wide lint debt is recorded, but changed files introduce no new
  lint errors.

### Stop condition

Stop on any flaky identity test, any provider call not isolated from production,
or any test that leaves database state behind.

## Issue 11 — Active Email campaigns need behavior-equivalence proof

**Priority: P0 — Critical**

The migration must not change pending recipients, rendered messages, schedule,
reply counts, bounce state, or suppression behavior.

### Remediation

- On a production copy, snapshot each active Email campaign's enrollment IDs,
  Person candidates, recipient Email, state, sequence step, assigned mailbox,
  next-send time, message count, reply state, bounce state, and suppression.
- Render every pending message with the old and new variable loaders without
  sending it.
- Run `bun run audit:email-people-parity` after backfill and before any worker
  resumes. It fails closed on an exact recipient change or a changed subject or
  body substitution in any remaining sequence step.
- Compare queue membership and ordering before and after backfill.
- Replay sanitized webhook fixtures for reply, bounce, complaint, and
  unsubscribe.
- Verify all subsequent steps read the Person Email and respect suppression.

### Acceptance gate

- Recipient set and queue order are identical.
- Rendered subject/body are identical, except reviewed allowlisted differences.
- Reply/bounce/unsubscribe fixtures update one correct enrollment and prevent
  further sends where expected.
- No active campaign counters change merely because of migration.

### Stop condition

Any unapproved recipient, content, schedule, suppression, or state difference is
a no-go.

## Issue 12 — Active LinkedIn campaigns need behavior-equivalence proof

**Priority: P0 — Critical**

The migration must preserve sender assignment, profile resolution, campaign
state, retry/backoff, messages, connections, and webhook routing.

### Remediation

- Snapshot active LinkedIn Leads and their Person candidate, source identifier,
  provider ID, sender account, state, retry count, next allowed run, messages,
  connection, and thread IDs.
- Compare invitation/follow-up eligibility and selected sender before and after
  migration without contacting Unipile.
- Run `bun run audit:linkedin-people-parity` after backfill and before any
  worker resumes; treat every reported target, next-action, rendered-content,
  account-eligibility, or restart-claim difference as a stop condition.
- Replay accepted-connection and inbound-message fixtures.
- Verify unresolved source identifiers are excluded from sends.
- Verify an existing sent step is never sent again after message deduplication
  and restart.

### Acceptance gate

- Same actionable Lead set, state, assigned account, and next-step decision.
- No duplicate invitation or follow-up is produced.
- Each webhook resolves to exactly one Lead and preserves message/thread history.
- Resolver failures keep Leads pending and retryable, never falsely resolved.

### Stop condition

Any change in provider target, sender account, state machine position, or next
automated action is a no-go.

## Issue 13 — A full application shutdown can lose webhooks

**Priority: P0 — Critical**

Unipile webhook retries are limited. Stopping the whole application during the
migration can lose connection/reply events even if outbound workers are safely
paused.

### Remediation

- Add independent controls for outbound Email scheduler, LinkedIn outreach job,
  profile resolver, and search queue.
- Add a temporary migration mode that blocks new imports, campaign creation,
  enrollment changes, and manual outbound sends while allowing webhook
  ingestion and read-only traffic. This prevents the preflight dataset from
  changing underneath the backfill.
- During cutover, pause outbound workers and schedulers but keep public webhook
  ingestion live.
- Make webhook ingestion durable and idempotent: persist the raw event and
  provider event ID first, acknowledge it, then process/retry internally.
- Confirm current deployed webhook URLs before cutover. Do not change them as
  part of this migration.
- Drain in-flight jobs before the database apply step and record the last job
  IDs/checkpoints.

### Acceptance gate

- A staging cutover simulation receives and processes webhooks while outbound
  work is paused.
- Replaying the same webhook does not duplicate messages or state transitions.
- Paused workers resume from recorded checkpoints without duplicate sends.

### Stop condition

Stop if webhook ingestion cannot remain live, events are not durable/idempotent,
or in-flight send jobs cannot be accounted for.

## Issue 14 — Rollback compatibility must be proven

**Priority: P0 — Critical**

A backup alone is not a usable rollback plan if the old application cannot run
against the changed schema or if post-cutover writes cannot be reconciled.

### Remediation

- Keep all legacy enrollment columns during a defined rollback window. Inventory
  `campaign_members`; preserve it if present, but do not create it when absent.
- Ensure additive schema preparation remains compatible with the currently
  deployed application.
- Define rollback boundaries:
  - restore the pre-migration snapshot only when there have been zero durable
    writes since it was taken, including webhook/import/manual writes;
  - after any durable write or provider action: pause outbound work, preserve
    the new records, and use in-place compatibility rollback plus reconciliation.
- Record schema version, application version, backup identifier, row counts,
  high-water timestamps, and worker checkpoints.
- Test rollback on staging, including rollback after simulated webhook traffic.
- Run `rollback:people` first in `check` mode with exact database, host,
  application SHA, backup ID, and observed-count guards. Its only schema apply
  action is dropping `NOT NULL` from the two Person-reference columns.
- Export the high-water interval and baseline non-terminal webhooks with
  `export:people-reconciliation`; provider reconciliation remains a separate,
  mandatory operator step.

### Acceptance gate

- Old runtime passes a smoke test against the prepared schema.
- Backup restore has been timed and verified.
- The team can account for events received after the backup.
- No destructive cleanup is included in the cutover deployment.

### Stop condition

Stop if rollback would discard inbound events, require guessing which messages
were sent, or require restoring untested code/database combinations.

## Issue 15 — Preflight and post-migration checks are fragmented

**Priority: P1 — High**

Manual SQL and separate scripts make it easy to overlook one blocker.

### Remediation

Create one read-only preflight command that aggregates:

- schema readiness;
- message duplicate groups;
- raw conflicts and active-template impact;
- invalid/missing Email identities;
- unresolved LinkedIn identifier classes;
- cross-channel contradictions;
- provider/account collisions;
- duplicate campaign memberships;
- orphaned references;
- active campaign and message-state baselines.

Create a matching post-migration invariant command. Both commands produce
machine-readable JSON and a short human summary, and both exit non-zero for any
unapproved P0/P1 result.

### Proposed tooling

- `scripts/preflight-people-migration.ts`
- `scripts/verify-people-migration.ts`
- `reports/migration/preflight-<timestamp>.json`
- `reports/migration/postflight-<timestamp>.json`

### Acceptance gate

- The same commands run locally, in staging, and during production cutover.
- A seeded bad fixture makes every corresponding check fail.
- A clean fixture returns zero blockers and exit code 0.

### Stop condition

Stop if the aggregate report cannot identify the exact failed check, if its
queries mutate data, or if its baseline changes between the final preflight and
the start of the migration without an explained webhook event.

## Issue 16 — Staging rehearsal and production operations

**Priority: P0 — Critical**

The full sequence must be proven on realistic data, not assembled for the first
time in production.

### Staging rehearsal

1. Restore a recent sanitized production copy into an isolated environment.
2. Record database version, source timestamp, active campaign counts, state
   distributions, queue counts, messages, replies, bounces, suppressions,
   connections, and webhook high-water marks.
3. Run read-only preflight and archive its report.
4. Run additive schema preparation twice.
5. Run all cleanup/reconciliation tools in dry-run mode.
6. Apply only reviewed cleanup decisions.
7. Run backfill dry-run; require zero blockers.
8. Apply backfill, then rerun it and require zero further changes.
9. Run schema finalization.
10. Run postflight invariants and before/after comparisons.
11. Run the Email and LinkedIn active-campaign smoke suites.
12. Simulate worker pause, webhook traffic, deployment, worker resume, and job
    checkpoint recovery.
13. Perform and verify rollback once.

### Production runbook

1. Announce a controlled cutover window; do not stop the whole application.
2. Pause outbound Email and LinkedIn workers, resolver, and search jobs.
3. Drain and record in-flight jobs while keeping webhook ingestion live.
4. Take and verify a restorable database backup.
5. Capture preflight report and operational baselines.
6. If any P0/P1 blocker exists, abort before writes.
7. Run prepare, reviewed cleanup, reconciliation, and backfill using the exact
   artifacts rehearsed in staging.
8. Run postflight and behavior-equivalence checks.
9. Finalize constraints only after all checks pass.
10. Deploy the compatible runtime.
11. Resume one worker class at a time, starting with a tiny canary batch.
12. Monitor sends, failures, replies, bounces, webhook lag, and duplicate-send
    indicators before full resume.
13. Keep legacy columns and rollback artifacts until the rollback window closes.

### Immediate rollback triggers

- Any recipient or provider target differs from the preflight snapshot.
- Any duplicate Email or LinkedIn send occurs.
- Any active campaign row loses or changes state unexpectedly.
- Webhook failures or processing lag cross the agreed threshold.
- Reply, bounce, complaint, or unsubscribe attaches to the wrong Person/Lead.
- Orphaned Person references, missing channel identities, or uniqueness failures
  appear.
- Error rate exceeds the staging baseline or the canary behaves differently.

## Required implementation work before migration approval

- [ ] Split schema preparation and finalization.
- [ ] Add the aggregated read-only preflight and postflight commands.
- [ ] Implement duplicate automated-message audit and idempotent cleanup.
- [ ] Implement raw-conflict classification and active-template compatibility.
- [ ] Implement cross-channel identity reconciliation and audit ledger.
- [ ] Implement resumable legacy LinkedIn identifier resolution.
- [ ] Resolve the provider/account collision and harden ambiguous webhook lookup.
- [ ] Make backfill resumable, idempotent, and fully reported.
- [ ] Add database integration tests for imports, resolver, sends, replies,
      bounces, complaints, unsubscribe, webhooks, concurrency, and backfill.
- [ ] Add active Email before/after equivalence checks.
- [ ] Add active LinkedIn before/after equivalence checks.
- [ ] Add independent pause controls and prove webhook-safe cutover behavior.
- [ ] Rehearse migration and rollback on a recent production copy.
- [ ] Produce a final signed go/no-go report with zero unresolved P0/P1 blockers.

## Final go/no-go rule

Migration is **NO-GO** unless all of the following are true at the same time:

- schema preparation succeeds and is idempotent;
- the backfill dry-run reports zero blockers;
- automated message duplicates and campaign-membership duplicates are zero;
- active-template raw conflicts are zero or covered by an explicitly tested
  temporary legacy compatibility path;
- identity contradictions and actionable provider collisions are zero;
- every campaign row has the correct Person reference;
- every actionable LinkedIn Lead has a resolved provider target;
- database integration tests, typecheck, and production build pass;
- active Email and LinkedIn before/after smoke comparisons pass;
- webhook ingestion remains live and idempotent while workers are paused;
- backup restore and rollback have been rehearsed successfully;
- production canary limits, monitoring thresholds, and named rollback authority
  are documented.

## Recommended defaults requiring explicit approval

1. For duplicate automated LinkedIn messages, retain the provider-confirmed row;
   otherwise use the row with the strongest provider/timestamp evidence, while
   archiving the complete duplicate group in the migration report.
2. For conflicting legacy variables used by active templates, preserve the
   enrollment-specific legacy value until that campaign completes. Do not choose
   a global Person value that changes an already-scheduled message.
3. Treat every contradictory Email/LinkedIn match as manual review. Never use
   source order or “last write wins” for identity.
4. Keep legacy columns and `campaign_members` through at least one verified
   rollback window; remove them only in a separate later change.
