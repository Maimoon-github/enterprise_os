/**
 * Rollback-only PostgreSQL assertions for the CRM Person/state core.
 *
 * Run with:
 *   bun run scripts/test-people-crm-core.ts
 *
 * The foundation/core migrations and the canonical `people` table must already
 * exist. This runner creates no schema, reads no retired CRM rows, and always
 * rolls its fixture transaction back.
 *
 * Fixture rows are written into ORGANIZATION_ID, or the initial organization when it is unset.
 */
import assert from "node:assert/strict";
import { Client } from "pg";
import { resolveScriptOrganization } from "./lib/organization";

// Set from ORGANIZATION_ID / the initial organization before any fixture is built.
let ORGANIZATION_ID = "";

const DEFAULT_PIPELINE_ID = "00000000-0000-0000-0000-000000000001";
const FIXTURE_PIPELINE_ID = "00000000-0000-0000-0000-000000000002";
const PERSON_ID = "00000000-0000-0000-0000-000000000101";
const SECOND_PERSON_ID = "00000000-0000-0000-0000-000000000102";
const RECORD_ID = "00000000-0000-0000-0000-000000000201";
const SECOND_RECORD_ID = "00000000-0000-0000-0000-000000000202";
const SUBCATEGORY_ID = "00000000-0000-0000-0000-000000000301";
const CONVERSATION_ID = "00000000-0000-0000-0000-000000000401";
const LINKEDIN_CONVERSATION_ID = "00000000-0000-0000-0000-000000000402";
const INBOUND_MESSAGE_ID = "00000000-0000-0000-0000-000000000501";
const OUTBOUND_MESSAGE_ID = "00000000-0000-0000-0000-000000000502";
const CLASSIFICATION_ID = "00000000-0000-0000-0000-000000000601";
const EVENT_ID = "00000000-0000-0000-0000-000000000701";

const EXPECTED_TABLES = [
  "crm_classifications",
  "crm_conversation_messages",
  "crm_conversations",
  "crm_events",
  "crm_identity_exceptions",
  "crm_person_contact_policies",
  "crm_records",
] as const;

type DatabaseError = { code?: string };

function errorCode(error: unknown): string | undefined {
  return (error as DatabaseError).code;
}

async function runWithSavepoint(
  client: Client,
  statement: string,
  values: readonly unknown[],
): Promise<unknown | undefined> {
  const savepoint = "crm_core_assertion";
  await client.query(`SAVEPOINT ${savepoint}`);

  let failure: unknown;
  try {
    await client.query(statement, [...values]);
  } catch (error) {
    failure = error;
  }

  await client.query(`ROLLBACK TO SAVEPOINT ${savepoint}`);
  await client.query(`RELEASE SAVEPOINT ${savepoint}`);
  return failure;
}

async function expectRejected(
  client: Client,
  label: string,
  statement: string,
  values: readonly unknown[],
  expectedCode: string,
): Promise<void> {
  const failure = await runWithSavepoint(client, statement, values);
  assert(failure, `${label}: statement unexpectedly succeeded`);
  assert.equal(
    errorCode(failure),
    expectedCode,
    `${label}: expected PostgreSQL SQLSTATE ${expectedCode}, got ${errorCode(failure) ?? "unknown"}`,
  );
}

async function assertCore(client: Client): Promise<string[]> {
  const notes: string[] = [];
  const { rows: tableRows } = await client.query<{ table_name: string }>(
    `SELECT table_name
       FROM information_schema.tables
      WHERE table_schema = 'public'
        AND table_name = ANY($1::text[])
      ORDER BY table_name`,
    [EXPECTED_TABLES],
  );
  assert.deepEqual(
    tableRows.map((row) => row.table_name),
    [...EXPECTED_TABLES],
    "exactly the seven expected CRM core tables must exist",
  );

  // Use only the canonical people columns required for a core person row.
  await client.query(
    `INSERT INTO people (organization_id, id, email, first_name, last_name, full_name, source)
     VALUES ('${ORGANIZATION_ID}', $1, $2, 'CRM', 'Core Fixture', 'CRM Core Fixture', 'crm-core-test')`,
    [PERSON_ID, `crm-core-${PERSON_ID}@invalid.example`],
  );
  await client.query(
    `INSERT INTO people (organization_id, id, email, first_name, last_name, full_name, source)
     VALUES ('${ORGANIZATION_ID}', $1, $2, 'CRM', 'Second Fixture', 'CRM Second Fixture', 'crm-core-test')`,
    [SECOND_PERSON_ID, `crm-core-${SECOND_PERSON_ID}@invalid.example`],
  );

  // The policy is global and has exactly one row per Person.
  await client.query(
    `INSERT INTO crm_person_contact_policies
       (person_id, do_not_contact, reason, source, set_at)
     VALUES ($1, true, 'fixture unsubscribe', 'inbound_request', now())`,
    [PERSON_ID],
  );
  const { rows: policyRows } = await client.query<{
    person_id: string;
    do_not_contact: boolean;
    cleared_at: string | null;
  }>(
    `SELECT person_id, do_not_contact, cleared_at
       FROM crm_person_contact_policies
      WHERE person_id = $1`,
    [PERSON_ID],
  );
  assert.deepEqual(policyRows, [{ person_id: PERSON_ID, do_not_contact: true, cleared_at: null }]);
  await expectRejected(
    client,
    "one global contact policy per person",
    `INSERT INTO crm_person_contact_policies
       (person_id, do_not_contact, source, set_at)
     VALUES ($1, true, 'human', now())`,
    [PERSON_ID],
    "23505",
  );
  await expectRejected(
    client,
    "DNC requires set_at and no cleared_at",
    `INSERT INTO crm_person_contact_policies
       (person_id, do_not_contact, source)
     VALUES ($1, true, 'human')`,
    [SECOND_PERSON_ID],
    "23514",
  );
  await expectRejected(
    client,
    "active DNC requires an attributable source",
    `INSERT INTO crm_person_contact_policies
       (person_id, do_not_contact, set_at)
     VALUES ($1, true, now())`,
    [SECOND_PERSON_ID],
    "23514",
  );
  await expectRejected(
    client,
    "cleared policy requires cleared_at",
    `INSERT INTO crm_person_contact_policies
       (person_id, do_not_contact, set_at)
     VALUES ($1, false, now())`,
    [SECOND_PERSON_ID],
    "23514",
  );
  await expectRejected(
    client,
    "contact policy source vocabulary",
    `INSERT INTO crm_person_contact_policies
       (person_id, source)
     VALUES ($1, 'crm-robot')`,
    [SECOND_PERSON_ID],
    "23514",
  );
  await client.query(
    `UPDATE crm_person_contact_policies
        SET do_not_contact = false, cleared_at = now()
      WHERE person_id = $1`,
    [PERSON_ID],
  );
  const { rows: clearedPolicyRows } = await client.query<{ do_not_contact: boolean; cleared_at: string | null }>(
    `SELECT do_not_contact, cleared_at
       FROM crm_person_contact_policies
      WHERE person_id = $1`,
    [PERSON_ID],
  );
  assert.equal(clearedPolicyRows[0]?.do_not_contact, false, "a DNC policy can be cleared without deleting it");
  assert(clearedPolicyRows[0]?.cleared_at, "a cleared policy must retain cleared_at");

  await client.query(
    `INSERT INTO crm_pipelines (organization_id, id, name, is_default, active)
     VALUES ('${ORGANIZATION_ID}', $1, 'CRM core fixture pipeline', false, true)`,
    [FIXTURE_PIPELINE_ID],
  );
  await client.query(
    `INSERT INTO crm_subcategories (id, pipeline_id, category_key, key, name)
     VALUES ($1, $2, 'interested', 'crm_core_fixture', 'CRM core fixture')`,
    [SUBCATEGORY_ID, DEFAULT_PIPELINE_ID],
  );

  await client.query(
    `INSERT INTO crm_records
       (organization_id, id, person_id, pipeline_id, category_key, subcategory_id,
        workflow_state, category_source, active_channel, context_version)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'interested', $4, 'unclassified', 'ai', 'email', 0)`,
    [RECORD_ID, PERSON_ID, DEFAULT_PIPELINE_ID, SUBCATEGORY_ID],
  );
  await expectRejected(
    client,
    "one CRM record per person and pipeline",
    `INSERT INTO crm_records (organization_id, id, person_id, pipeline_id)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3)`,
    [SECOND_RECORD_ID, PERSON_ID, DEFAULT_PIPELINE_ID],
    "23505",
  );
  await expectRejected(
    client,
    "record subcategory must match pipeline and category",
    `INSERT INTO crm_records
       (organization_id, id, person_id, pipeline_id, category_key, subcategory_id, category_source)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'customer', $4, 'human')`,
    [SECOND_RECORD_ID, SECOND_PERSON_ID, DEFAULT_PIPELINE_ID, SUBCATEGORY_ID],
    "23503",
  );
  await expectRejected(
    client,
    "record subcategory must match pipeline",
    `INSERT INTO crm_records
       (organization_id, id, person_id, pipeline_id, category_key, subcategory_id, category_source)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'interested', $4, 'human')`,
    [SECOND_RECORD_ID, SECOND_PERSON_ID, FIXTURE_PIPELINE_ID, SUBCATEGORY_ID],
    "23503",
  );
  await expectRejected(
    client,
    "record workflow-state vocabulary",
    `UPDATE crm_records SET workflow_state = 'not_a_state' WHERE id = $1`,
    [RECORD_ID],
    "23514",
  );
  await expectRejected(
    client,
    "record context version cannot be negative",
    `UPDATE crm_records SET context_version = -1 WHERE id = $1`,
    [RECORD_ID],
    "23514",
  );
  await expectRejected(
    client,
    "record channel vocabulary",
    `UPDATE crm_records SET active_channel = 'sms' WHERE id = $1`,
    [RECORD_ID],
    "23514",
  );
  await expectRejected(
    client,
    "record category source vocabulary",
    `UPDATE crm_records SET category_source = 'robot' WHERE id = $1`,
    [RECORD_ID],
    "23514",
  );
  await expectRejected(
    client,
    "only Customer records can be category locked",
    "UPDATE crm_records SET category_locked = true WHERE id = $1",
    [RECORD_ID],
    "23514",
  );
  await client.query(
    `INSERT INTO crm_records (organization_id, id, person_id, pipeline_id)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3)`,
    [SECOND_RECORD_ID, SECOND_PERSON_ID, DEFAULT_PIPELINE_ID],
  );

  await client.query(
    `INSERT INTO crm_conversations
       (organization_id, id, crm_record_id, person_id, channel, account_ref, provider_thread_id)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'email', 'fixture-mailbox@example.invalid', 'fixture-thread-email')`,
    [CONVERSATION_ID, RECORD_ID, PERSON_ID],
  );
  await client.query(
    `INSERT INTO crm_conversations
       (organization_id, id, crm_record_id, person_id, channel, account_ref, provider_thread_id)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'linkedin', 'fixture-linkedin-account', 'fixture-thread-linkedin')`,
    [LINKEDIN_CONVERSATION_ID, RECORD_ID, PERSON_ID],
  );
  await expectRejected(
    client,
    "conversation provider thread is channel/account unique",
    `INSERT INTO crm_conversations
       (organization_id, crm_record_id, person_id, channel, account_ref, provider_thread_id)
     VALUES ('${ORGANIZATION_ID}', $1, $2, 'email', 'fixture-mailbox@example.invalid', 'fixture-thread-email')`,
    [RECORD_ID, PERSON_ID],
    "23505",
  );
  await expectRejected(
    client,
    "conversation person must match record",
    `INSERT INTO crm_conversations
       (organization_id, crm_record_id, person_id, channel, account_ref)
     VALUES ('${ORGANIZATION_ID}', $1, $2, 'email', 'other-mailbox@example.invalid')`,
    [RECORD_ID, SECOND_PERSON_ID],
    "23503",
  );
  await expectRejected(
    client,
    "conversation ownership is immutable",
    "UPDATE crm_conversations SET crm_record_id = $1 WHERE id = $2",
    [SECOND_RECORD_ID, CONVERSATION_ID],
    "23514",
  );

  await client.query(
    `INSERT INTO crm_conversation_messages
       (id, conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, provider_message_id, body_text, sent_at)
     VALUES ($1, $2, $3, 'email', 'fixture-mailbox@example.invalid', 'inbound',
             'fixture-inbound-idempotency', 'fixture-inbound-provider',
             'A fixture inbound reply', now())`,
    [INBOUND_MESSAGE_ID, CONVERSATION_ID, PERSON_ID],
  );
  await client.query(
    `INSERT INTO crm_conversation_messages
       (id, conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, provider_message_id, body_text, sent_at)
     VALUES ($1, $2, $3, 'email', 'fixture-mailbox@example.invalid', 'outbound',
             'fixture-outbound-idempotency', 'fixture-outbound-provider',
             'A fixture outbound reply', now())`,
    [OUTBOUND_MESSAGE_ID, CONVERSATION_ID, PERSON_ID],
  );
  await expectRejected(
    client,
    "message idempotency is unique by channel and account",
    `INSERT INTO crm_conversation_messages
       (conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, body_text, sent_at)
     VALUES ($1, $2, 'email', 'fixture-mailbox@example.invalid', 'inbound',
             'fixture-inbound-idempotency', 'duplicate', now())`,
    [CONVERSATION_ID, PERSON_ID],
    "23505",
  );
  await expectRejected(
    client,
    "provider message id is unique by channel and account",
    `INSERT INTO crm_conversation_messages
       (conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, provider_message_id, body_text, sent_at)
     VALUES ($1, $2, 'email', 'fixture-mailbox@example.invalid', 'inbound',
             'fixture-provider-duplicate-idempotency', 'fixture-inbound-provider',
             'duplicate provider message', now())`,
    [CONVERSATION_ID, PERSON_ID],
    "23505",
  );
  await expectRejected(
    client,
    "message person must match conversation",
    `INSERT INTO crm_conversation_messages
       (conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, body_text, sent_at)
     VALUES ($1, $2, 'email', 'fixture-mailbox@example.invalid', 'inbound',
             'fixture-wrong-person', 'wrong person', now())`,
    [CONVERSATION_ID, SECOND_PERSON_ID],
    "23503",
  );
  await expectRejected(
    client,
    "message channel must match conversation",
    `INSERT INTO crm_conversation_messages
       (conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, body_text, sent_at)
     VALUES ($1, $2, 'linkedin', 'fixture-mailbox@example.invalid', 'inbound',
             'fixture-wrong-channel', 'wrong channel', now())`,
    [CONVERSATION_ID, PERSON_ID],
    "23503",
  );
  await expectRejected(
    client,
    "message account must match conversation",
    `INSERT INTO crm_conversation_messages
       (conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, body_text, sent_at)
     VALUES ($1, $2, 'email', 'other-mailbox@example.invalid', 'inbound',
             'fixture-wrong-account', 'wrong account', now())`,
    [CONVERSATION_ID, PERSON_ID],
    "23503",
  );
  await expectRejected(
    client,
    "message direction vocabulary",
    `INSERT INTO crm_conversation_messages
       (conversation_id, person_id, channel, account_ref, direction,
        idempotency_key, body_text, sent_at)
     VALUES ($1, $2, 'email', 'fixture-mailbox@example.invalid', 'unknown',
             'fixture-wrong-direction', 'wrong direction', now())`,
    [CONVERSATION_ID, PERSON_ID],
    "23514",
  );
  await expectRejected(
    client,
    "messages are append-only on update",
    "UPDATE crm_conversation_messages SET body_text = 'changed' WHERE id = $1",
    [INBOUND_MESSAGE_ID],
    "23001",
  );
  await expectRejected(
    client,
    "messages are append-only on delete",
    "DELETE FROM crm_conversation_messages WHERE id = $1",
    [INBOUND_MESSAGE_ID],
    "23001",
  );

  await client.query(
    `UPDATE crm_records
        SET latest_inbound_message_id = $2
      WHERE id = $1`,
    [RECORD_ID, INBOUND_MESSAGE_ID],
  );
  const { rows: latestRows } = await client.query<{ latest_inbound_message_id: string }>(
    "SELECT latest_inbound_message_id FROM crm_records WHERE id = $1",
    [RECORD_ID],
  );
  assert.equal(latestRows[0]?.latest_inbound_message_id, INBOUND_MESSAGE_ID);
  await expectRejected(
    client,
    "latest inbound pointer rejects outbound messages",
    `UPDATE crm_records SET latest_inbound_message_id = $2 WHERE id = $1`,
    [RECORD_ID, OUTBOUND_MESSAGE_ID],
    "23514",
  );
  notes.push("database enforces latest_inbound_message_id ownership and inbound direction");

  await client.query(
    `INSERT INTO crm_classifications
       (id, crm_record_id, message_id, expected_context_version,
        proposed_category_key, proposed_subcategory_id, confidence, reasoning,
        status, provider, model)
     VALUES ($1, $2, $3, 0, 'interested', $4, 0.94,
             'Fixture explicitly requests a demonstration.', 'auto_applied',
             'fixture', 'fixture-model')`,
    [CLASSIFICATION_ID, RECORD_ID, INBOUND_MESSAGE_ID, SUBCATEGORY_ID],
  );
  await expectRejected(
    client,
    "classification message/context is unique",
    `INSERT INTO crm_classifications
       (crm_record_id, message_id, expected_context_version, confidence, status)
     VALUES ($1, $2, 0, 0.5, 'proposed')`,
    [RECORD_ID, INBOUND_MESSAGE_ID],
    "23505",
  );
  await expectRejected(
    client,
    "classification rejects outbound messages",
    `INSERT INTO crm_classifications
       (crm_record_id, message_id, expected_context_version, confidence, status)
     VALUES ($1, $2, 2, 0.5, 'proposed')`,
    [RECORD_ID, OUTBOUND_MESSAGE_ID],
    "23514",
  );
  await expectRejected(
    client,
    "classification message must belong to its record",
    `INSERT INTO crm_classifications
       (crm_record_id, message_id, expected_context_version, confidence, status)
     VALUES ($1, $2, 2, 0.5, 'proposed')`,
    [SECOND_RECORD_ID, INBOUND_MESSAGE_ID],
    "23514",
  );
  await expectRejected(
    client,
    "classification context version cannot be negative",
    `INSERT INTO crm_classifications
       (crm_record_id, message_id, expected_context_version, confidence, status)
     VALUES ($1, $2, -1, 0.5, 'proposed')`,
    [RECORD_ID, INBOUND_MESSAGE_ID],
    "23514",
  );
  await expectRejected(
    client,
    "classification confidence cannot exceed one",
    `INSERT INTO crm_classifications
       (crm_record_id, message_id, expected_context_version, confidence, status)
     VALUES ($1, $2, 1, 1.001, 'proposed')`,
    [RECORD_ID, INBOUND_MESSAGE_ID],
    "23514",
  );
  await expectRejected(
    client,
    "classification status vocabulary",
    `INSERT INTO crm_classifications
       (crm_record_id, message_id, expected_context_version, confidence, status)
     VALUES ($1, $2, 1, 0.5, 'unknown')`,
    [RECORD_ID, INBOUND_MESSAGE_ID],
    "23514",
  );
  await expectRejected(
    client,
    "non-failed classification requires confidence",
    `INSERT INTO crm_classifications
       (crm_record_id, message_id, expected_context_version, status)
     VALUES ($1, $2, 1, 'proposed')`,
    [RECORD_ID, INBOUND_MESSAGE_ID],
    "23514",
  );

  await client.query(
    `INSERT INTO crm_events
       (organization_id, id, person_id, crm_record_id, pipeline_id, event_type, actor_type, context_version)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, $4, 'reply_received', 'system', 0)`,
    [EVENT_ID, PERSON_ID, RECORD_ID, DEFAULT_PIPELINE_ID],
  );
  await expectRejected(
    client,
    "events are append-only on update",
    "UPDATE crm_events SET event_type = 'changed' WHERE id = $1",
    [EVENT_ID],
    "23001",
  );
  await expectRejected(
    client,
    "events are append-only on delete",
    "DELETE FROM crm_events WHERE id = $1",
    [EVENT_ID],
    "23001",
  );
  await expectRejected(
    client,
    "event record/person identity must match",
    `INSERT INTO crm_events
       (organization_id, person_id, crm_record_id, pipeline_id, event_type, actor_type)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'mismatch', 'system')`,
    [SECOND_PERSON_ID, RECORD_ID, DEFAULT_PIPELINE_ID],
    "23503",
  );
  await expectRejected(
    client,
    "event record/pipeline identity must match",
    `INSERT INTO crm_events
       (organization_id, person_id, crm_record_id, pipeline_id, event_type, actor_type)
     VALUES ('${ORGANIZATION_ID}', $1, $2, $3, 'pipeline-mismatch', 'system')`,
    [PERSON_ID, RECORD_ID, FIXTURE_PIPELINE_ID],
    "23503",
  );
  await expectRejected(
    client,
    "event actor vocabulary",
    `INSERT INTO crm_events (organization_id, person_id, event_type, actor_type)
     VALUES ('${ORGANIZATION_ID}', $1, 'bad-actor', 'robot')`,
    [PERSON_ID],
    "23514",
  );
  await expectRejected(
    client,
    "record-scoped events require a pipeline",
    `INSERT INTO crm_events (organization_id, person_id, crm_record_id, event_type, actor_type)
     VALUES ('${ORGANIZATION_ID}', $1, $2, 'missing-pipeline', 'system')`,
    [PERSON_ID, RECORD_ID],
    "23514",
  );
  await expectRejected(
    client,
    "event context version cannot be negative",
    `INSERT INTO crm_events (organization_id, person_id, event_type, actor_type, context_version)
     VALUES ('${ORGANIZATION_ID}', $1, 'bad-context', 'system', -1)`,
    [PERSON_ID],
    "23514",
  );

  return notes;
}

async function main(): Promise<void> {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) throw new Error("DATABASE_URL is not set — check .env.local");

  const client = new Client({
    connectionString: databaseUrl,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: "agentsdr-test-people-crm-core",
  });

  ORGANIZATION_ID = (await resolveScriptOrganization()).id;
  await client.connect();
  let transactionStarted = false;
  try {
    await client.query("BEGIN");
    transactionStarted = true;
    await client.query("SET LOCAL statement_timeout = '30s'");
    const notes = await assertCore(client);
    console.log("CRM core checks passed; rolling back all test work.");
    for (const note of notes) console.log(`NOTE: ${note}`);
    await client.query("ROLLBACK");
    transactionStarted = false;
  } catch (error) {
    if (transactionStarted) {
      try {
        await client.query("ROLLBACK");
      } catch {
        // Preserve the assertion/connection error if rollback itself fails.
      }
    }
    throw error;
  } finally {
    await client.end();
  }
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
