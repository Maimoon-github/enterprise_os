/**
 * Rollback-only PostgreSQL assertions for CRM workflow/schema invariants.
 *
 * Run after the three CRM migrations have been applied:
 *   bun run scripts/test-people-crm-workflow.ts
 *
 * Every fixture and mutation is enclosed in one transaction that is always
 * rolled back. The script never creates or alters schema.
 *
 * Fixture rows are written into ORGANIZATION_ID, or the initial organization when it is unset.
 */
import assert from "node:assert/strict";
import { Client } from "pg";
import { resolveScriptOrganization } from "./lib/organization";

// Set from ORGANIZATION_ID / the initial organization before any fixture is built.
let ORGANIZATION_ID = "";

const IDS = {
  person: "10000000-0000-0000-0000-000000000001",
  record: "10000000-0000-0000-0000-000000000002",
  subcategory: "10000000-0000-0000-0000-000000000003",
  conversation: "10000000-0000-0000-0000-000000000004",
  inbound: "10000000-0000-0000-0000-000000000005",
  outbound: "10000000-0000-0000-0000-000000000006",
  classification: "10000000-0000-0000-0000-000000000007",
  sequence: "10000000-0000-0000-0000-000000000008",
  version1: "10000000-0000-0000-0000-000000000009",
  version2: "10000000-0000-0000-0000-000000000010",
  step1: "10000000-0000-0000-0000-000000000011",
  step2: "10000000-0000-0000-0000-000000000012",
  override1: "10000000-0000-0000-0000-000000000013",
  override2: "10000000-0000-0000-0000-000000000014",
  run1: "10000000-0000-0000-0000-000000000015",
  run2: "10000000-0000-0000-0000-000000000016",
  stepRun: "10000000-0000-0000-0000-000000000017",
  draft1: "10000000-0000-0000-0000-000000000018",
  draft2: "10000000-0000-0000-0000-000000000019",
  document: "10000000-0000-0000-0000-000000000020",
  documentVersion1: "10000000-0000-0000-0000-000000000021",
  documentVersion2: "10000000-0000-0000-0000-000000000022",
} as const;

const EXPECTED_TABLES = [
  "crm_draft_knowledge_citations",
  "crm_drafts",
  "crm_jobs",
  "crm_knowledge_document_versions",
  "crm_knowledge_documents",
  "crm_record_sequence_overrides",
  "crm_send_attempts",
  "crm_sequence_runs",
  "crm_sequence_step_runs",
  "crm_sequence_steps",
  "crm_sequence_versions",
  "crm_sequences",
  "crm_subcategory_sequence_assignments",
] as const;

type DatabaseError = { code?: string };

async function expectRejected(
  client: Client,
  label: string,
  statement: string,
  values: readonly unknown[],
  expectedCode: string,
): Promise<void> {
  await client.query("SAVEPOINT crm_workflow_assertion");
  let failure: unknown;
  try {
    await client.query(statement, [...values]);
  } catch (error) {
    failure = error;
  }
  await client.query("ROLLBACK TO SAVEPOINT crm_workflow_assertion");
  await client.query("RELEASE SAVEPOINT crm_workflow_assertion");
  assert(failure, `${label}: statement unexpectedly succeeded`);
  assert.equal(
    (failure as DatabaseError).code,
    expectedCode,
    `${label}: expected SQLSTATE ${expectedCode}, got ${(failure as DatabaseError).code ?? "unknown"}`,
  );
}

async function assertWorkflow(client: Client): Promise<void> {
  const { rows: tableRows } = await client.query<{ table_name: string }>(
    `SELECT table_name FROM information_schema.tables
      WHERE table_schema = 'public' AND table_name = ANY($1::text[])
      ORDER BY table_name`,
    [EXPECTED_TABLES],
  );
  assert.deepEqual(tableRows.map((row) => row.table_name), [...EXPECTED_TABLES]);

  const { rows: pipelineRows } = await client.query<{ id: string }>(
    "SELECT id FROM crm_pipelines WHERE is_default IS TRUE",
  );
  assert.equal(pipelineRows.length, 1, "the CRM foundation must expose exactly one default pipeline");
  const pipelineId = pipelineRows[0]!.id;

  await client.query(
    `INSERT INTO people (organization_id, id, email, first_name, last_name, full_name, source)
     VALUES ('${ORGANIZATION_ID}', $1, $2, 'Workflow', 'Fixture', 'Workflow Fixture', 'crm-workflow-test')`,
    [IDS.person, `crm-workflow-${IDS.person}@invalid.example`],
  );
  await client.query(
    `INSERT INTO crm_subcategories (id, pipeline_id, category_key, key, name)
     VALUES ($1, $2, 'interested', 'workflow_fixture', 'Workflow fixture')`,
    [IDS.subcategory, pipelineId],
  );
  await client.query(
    `INSERT INTO crm_records
       (organization_id, id, person_id, pipeline_id, category_key, subcategory_id, workflow_state,
        category_source, active_channel, context_version)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'interested', $4, 'action_required', 'ai', 'email', 1)`,
    [IDS.record, IDS.person, pipelineId, IDS.subcategory],
  );
  await client.query(
    `INSERT INTO crm_conversations
       (organization_id, id, crm_record_id, person_id, channel, account_ref, provider_thread_id)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'email', 'workflow@example.invalid', 'workflow-thread')`,
    [IDS.conversation, IDS.record, IDS.person],
  );
  await client.query(
    `INSERT INTO crm_conversation_messages
       (id, conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, body_text, sent_at)
     VALUES ($1, $2, $3, 'email', 'workflow@example.invalid', 'inbound',
             'workflow-inbound', 'Please send details', now())`,
    [IDS.inbound, IDS.conversation, IDS.person],
  );
  await client.query(
    `INSERT INTO crm_conversation_messages
       (id, conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, body_text, sent_at)
     VALUES ($1, $2, $3, 'email', 'workflow@example.invalid', 'outbound',
             'workflow-outbound', 'Here are the details', now())`,
    [IDS.outbound, IDS.conversation, IDS.person],
  );
  await client.query(
    `INSERT INTO crm_classifications
       (id, crm_record_id, message_id, expected_context_version,
        proposed_category_key, applied_category_key, confidence, status)
     VALUES ($1, $2, $3, 1, 'interested', 'interested', 0.95, 'auto_applied')`,
    [IDS.classification, IDS.record, IDS.inbound],
  );

  // The version FK is deferred so sequence + first draft version are created atomically.
  await client.query(
    `INSERT INTO crm_sequences (organization_id, id, name, draft_version_id)
     VALUES ('${ORGANIZATION_ID}', $1, 'Workflow fixture', $2)`,
    [IDS.sequence, IDS.version1],
  );
  await client.query(
    `INSERT INTO crm_sequence_versions (id, sequence_id, version, status)
     VALUES ($1, $2, 1, 'draft')`,
    [IDS.version1, IDS.sequence],
  );
  await client.query(
    `INSERT INTO crm_sequence_steps
       (id, sequence_version_id, position, step_type, name, delay_minutes, ai_instructions)
     VALUES ($1, $2, 1, 'reply', 'Immediate reply', 0, 'Respond to the inbound request'),
            ($3, $2, 2, 'follow_up', 'Follow-up 1', 1440, 'Check whether they saw the reply')`,
    [IDS.step1, IDS.version1, IDS.step2],
  );
  await expectRejected(
    client,
    "step one must be an immediate reply",
    `INSERT INTO crm_sequence_steps
       (sequence_version_id, position, step_type, name, delay_minutes, ai_instructions)
     VALUES ($1, 3, 'reply', 'Bad later reply', 0, 'invalid')`,
    [IDS.version1],
    "23514",
  );
  // Publishing freezes version 1 and creates the next mutable draft.
  await client.query(
    `UPDATE crm_sequence_versions
        SET status = 'published', published_at = now()
      WHERE id = $1`,
    [IDS.version1],
  );
  await client.query(
    `INSERT INTO crm_sequence_versions (id, sequence_id, version, status)
     VALUES ($1, $2, 2, 'draft')`,
    [IDS.version2, IDS.sequence],
  );
  await client.query(
    `UPDATE crm_sequences
        SET draft_version_id = $1, latest_published_version_id = $2
      WHERE id = $3`,
    [IDS.version2, IDS.version1, IDS.sequence],
  );
  await expectRejected(
    client,
    "published versions are immutable",
    "UPDATE crm_sequence_versions SET published_at = now() WHERE id = $1",
    [IDS.version1],
    "23514",
  );
  await expectRejected(
    client,
    "published version steps are immutable",
    "UPDATE crm_sequence_steps SET name = 'Changed' WHERE id = $1",
    [IDS.step1],
    "23514",
  );
  await client.query(
    `INSERT INTO crm_subcategory_sequence_assignments (subcategory_id, sequence_id)
     VALUES ($1, $2)`,
    [IDS.subcategory, IDS.sequence],
  );

  await client.query(
    `INSERT INTO crm_record_sequence_overrides
       (id, crm_record_id, sequence_id, source)
     VALUES ($1, $2, $3, 'human')`,
    [IDS.override1, IDS.record, IDS.sequence],
  );
  await expectRejected(
    client,
    "only one uncleared record override",
    `INSERT INTO crm_record_sequence_overrides
       (id, crm_record_id, sequence_id, source)
     VALUES ($1, $2, $3, 'integration')`,
    [IDS.override2, IDS.record, IDS.sequence],
    "23505",
  );
  await client.query(
    "UPDATE crm_record_sequence_overrides SET cleared_at = now() WHERE id = $1",
    [IDS.override1],
  );
  await client.query(
    `INSERT INTO crm_record_sequence_overrides
       (id, crm_record_id, sequence_id, source)
     VALUES ($1, $2, $3, 'integration')`,
    [IDS.override2, IDS.record, IDS.sequence],
  );

  await client.query(
    `INSERT INTO crm_sequence_runs
       (organization_id, id, crm_record_id, conversation_id, sequence_id, sequence_version_id,
        subcategory_id, started_by, trigger_message_id, last_inbound_at_start)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, $4, $5, $6, 'ai_assignment', $7, now())`,
    [IDS.run1, IDS.record, IDS.conversation, IDS.sequence, IDS.version1, IDS.subcategory, IDS.inbound],
  );
  await expectRejected(
    client,
    "one active sequence run per CRM record",
    `INSERT INTO crm_sequence_runs
       (organization_id, id, crm_record_id, conversation_id, sequence_id, sequence_version_id,
        subcategory_id, started_by, trigger_message_id, last_inbound_at_start)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, $4, $5, $6, 'human_override', $7, now())`,
    [IDS.run2, IDS.record, IDS.conversation, IDS.sequence, IDS.version1, IDS.subcategory, IDS.inbound],
    "23505",
  );
  await client.query(
    `INSERT INTO crm_sequence_step_runs
       (id, sequence_run_id, sequence_step_id, due_at, expected_context_version)
     VALUES ($1, $2, $3, now(), 1)`,
    [IDS.stepRun, IDS.run1, IDS.step1],
  );
  await client.query(
    `INSERT INTO crm_drafts
       (id, crm_record_id, conversation_id, reply_for_message_id,
        sequence_step_run_id, expected_context_version, revision, channel,
        ai_body_text, status)
     VALUES ($1, $2, $3, $4, $5, 1, 1, 'email', 'Fixture draft', 'awaiting_review')`,
    [IDS.draft1, IDS.record, IDS.conversation, IDS.inbound, IDS.stepRun],
  );
  await client.query(
    "UPDATE crm_sequence_step_runs SET draft_id = $1, status = 'awaiting_review' WHERE id = $2",
    [IDS.draft1, IDS.stepRun],
  );
  await expectRejected(
    client,
    "one draft per sequence step run",
    `INSERT INTO crm_drafts
       (id, crm_record_id, conversation_id, sequence_step_run_id,
        expected_context_version, channel, status)
     VALUES ($1, $2, $3, $4, 1, 'email', 'awaiting_review')`,
    [IDS.draft2, IDS.record, IDS.conversation, IDS.stepRun],
    "23505",
  );
  await expectRejected(
    client,
    "LinkedIn drafts cannot carry an Email subject",
    `INSERT INTO crm_drafts
       (id, crm_record_id, conversation_id, expected_context_version, channel, subject)
     VALUES ($1, $2, $3, 1, 'linkedin', 'Not allowed')`,
    [IDS.draft2, IDS.record, IDS.conversation],
    "23514",
  );

  await expectRejected(
    client,
    "send attempts are authenticated-operator only",
    `INSERT INTO crm_send_attempts
       (draft_id, idempotency_key, actor_type, request_id, provider, account_ref)
     VALUES ($1, 'bad-actor', 'system', 'request-bad', 'gmail', 'workflow@example.invalid')`,
    [IDS.draft1],
    "23514",
  );
  await client.query(
    `INSERT INTO crm_send_attempts
       (draft_id, idempotency_key, status, request_id, provider, account_ref)
     VALUES ($1, 'workflow-send-1', 'sent', 'request-1', 'gmail', 'workflow@example.invalid')`,
    [IDS.draft1],
  );
  await expectRejected(
    client,
    "successful sends cannot be downgraded and retried",
    "UPDATE crm_send_attempts SET status = 'failed', error = 'not retryable' WHERE idempotency_key = 'workflow-send-1'",
    [],
    "23514",
  );
  await expectRejected(
    client,
    "one successful or delivery-uncertain attempt per draft",
    `INSERT INTO crm_send_attempts
       (draft_id, idempotency_key, status, request_id, provider, account_ref)
     VALUES ($1, 'workflow-send-2', 'delivery_uncertain', 'request-2', 'gmail', 'workflow@example.invalid')`,
    [IDS.draft1],
    "23505",
  );

  // Knowledge creation and updates are versioned atomically.
  await client.query(
    `INSERT INTO crm_knowledge_documents (organization_id, id, title, kind, latest_version)
     VALUES ('${ORGANIZATION_ID}', $1, 'Fixture FAQ', 'faq', 1)`,
    [IDS.document],
  );
  await client.query(
    `INSERT INTO crm_knowledge_document_versions (id, document_id, version, content)
     VALUES ($1, $2, 1, 'Version one content')`,
    [IDS.documentVersion1, IDS.document],
  );
  await expectRejected(
    client,
    "Knowledge versions must be consecutive",
    `INSERT INTO crm_knowledge_document_versions (document_id, version, content)
     VALUES ($1, 3, 'Skipped version')`,
    [IDS.document],
    "23514",
  );
  await client.query(
    `INSERT INTO crm_knowledge_document_versions (id, document_id, version, content)
     VALUES ($1, $2, 2, 'Version two content')`,
    [IDS.documentVersion2, IDS.document],
  );
  await client.query(
    "UPDATE crm_knowledge_documents SET latest_version = 2 WHERE id = $1",
    [IDS.document],
  );
  await expectRejected(
    client,
    "Knowledge versions are append-only",
    "UPDATE crm_knowledge_document_versions SET content = 'Changed' WHERE id = $1",
    [IDS.documentVersion1],
    "23001",
  );
  await client.query(
    `INSERT INTO crm_draft_knowledge_citations
       (draft_id, document_version_id, excerpt, excerpt_hash, rank)
     VALUES ($1, $2, 'Version two', 'sha256:fixture', 0.9)`,
    [IDS.draft1, IDS.documentVersion2],
  );

  await client.query(
    `INSERT INTO crm_jobs
       (organization_id, kind, entity_type, entity_id, idempotency_key, payload)
     VALUES ('${ORGANIZATION_ID}', 'classification', 'message', $1, 'classification:workflow-inbound', '{"fixture":true}')`,
    [IDS.inbound],
  );
  await expectRejected(
    client,
    "job kind and entity type must agree",
    `INSERT INTO crm_jobs (organization_id, kind, entity_type, entity_id, idempotency_key)
     VALUES ('${ORGANIZATION_ID}', 'classification', 'sequence_step_run', $1, 'bad-kind-entity')`,
    [IDS.stepRun],
    "23514",
  );
  await expectRejected(
    client,
    "job entity identity is idempotent",
    `INSERT INTO crm_jobs (organization_id, kind, entity_type, entity_id, idempotency_key)
     VALUES ('${ORGANIZATION_ID}', 'classification', 'message', $1, 'classification:duplicate')`,
    [IDS.inbound],
    "23505",
  );
  await expectRejected(
    client,
    "job polymorphic entity must exist",
    `INSERT INTO crm_jobs (organization_id, kind, entity_type, entity_id, idempotency_key)
     VALUES ('${ORGANIZATION_ID}', 'classification', 'message', 'ffffffff-ffff-ffff-ffff-ffffffffffff', 'classification:missing')`,
    [],
    "23503",
  );

  const { rows: indexRows } = await client.query<{ indexname: string }>(
    `SELECT indexname FROM pg_indexes
      WHERE schemaname = 'public'
        AND indexname IN ('crm_jobs_claim_idx', 'crm_jobs_stale_claim_idx')
      ORDER BY indexname`,
  );
  assert.deepEqual(indexRows.map((row) => row.indexname), ["crm_jobs_claim_idx", "crm_jobs_stale_claim_idx"]);
}

async function main(): Promise<void> {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is not set — check .env.local");
  }
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });

  ORGANIZATION_ID = (await resolveScriptOrganization()).id;
  await client.connect();
  try {
    await client.query("SET lock_timeout = '5s'");
    await client.query("SET statement_timeout = '2min'");
    await client.query("BEGIN");
    try {
      await assertWorkflow(client);
      await client.query("SET CONSTRAINTS ALL IMMEDIATE");
      console.log("CRM workflow rollback-only assertions passed");
    } finally {
      await client.query("ROLLBACK");
    }
  } finally {
    await client.end();
  }
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
