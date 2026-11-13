/**
 * Transactional assertions for the CRM configuration foundation.
 *
 * Run with:
 *   bun run scripts/test-people-crm-foundation.ts
 *
 * This test requires DATABASE_URL, but it never commits. Every fixture row,
 * including rows used to exercise constraints, is discarded by the final
 * transaction ROLLBACK.
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
const FIXTURE_SUBCATEGORY_ID = "00000000-0000-0000-0000-000000000010";

const EXPECTED_TABLES = [
  "crm_categories",
  "crm_pipelines",
  "crm_settings",
  "crm_subcategories",
] as const;

const EXPECTED_CATEGORIES = [
  { key: "customer", label: "Customer", sortOrder: 0, isSystem: true },
  { key: "interested", label: "Interested", sortOrder: 1, isSystem: true },
  { key: "not_interested", label: "Not Interested", sortOrder: 2, isSystem: true },
  { key: "other", label: "Other", sortOrder: 3, isSystem: true },
] as const;

type DatabaseError = { code?: string; constraint?: string };

function errorCode(error: unknown): string | undefined {
  return (error as DatabaseError).code;
}

/**
 * An expected PostgreSQL error aborts the current savepoint, not the enclosing
 * test transaction. Checking the SQLSTATE also avoids passing on an unrelated
 * constraint failure.
 */
async function expectRejected(
  client: Client,
  label: string,
  statement: string,
  values: readonly unknown[],
  expectedCode: string,
): Promise<void> {
  const savepoint = "crm_foundation_assertion";
  await client.query(`SAVEPOINT ${savepoint}`);

  let failure: unknown;
  try {
    await client.query(statement, [...values]);
  } catch (error) {
    failure = error;
  }

  await client.query(`ROLLBACK TO SAVEPOINT ${savepoint}`);
  await client.query(`RELEASE SAVEPOINT ${savepoint}`);

  assert(failure, `${label}: statement unexpectedly succeeded`);
  assert.equal(
    errorCode(failure),
    expectedCode,
    `${label}: expected PostgreSQL SQLSTATE ${expectedCode}, got ${errorCode(failure) ?? "unknown"}`,
  );
}

async function assertFoundation(client: Client): Promise<void> {
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
    "exactly the four expected CRM foundation tables must exist",
  );

  const { rows: pipelineRows } = await client.query<{
    id: string;
    name: string;
    is_default: boolean;
    active: boolean;
  }>(
    `SELECT id, name, is_default, active
       FROM crm_pipelines
      WHERE id = $1`,
    [DEFAULT_PIPELINE_ID],
  );
  assert.deepEqual(pipelineRows, [{
    id: DEFAULT_PIPELINE_ID,
    name: "Default",
    is_default: true,
    active: true,
  }], "the stable Default pipeline must be present and enabled");

  const { rows: defaultCountRows } = await client.query<{ count: string }>(
    "SELECT count(*)::text AS count FROM crm_pipelines WHERE is_default IS TRUE",
  );
  assert.equal(defaultCountRows[0]?.count, "1", "there must be exactly one default pipeline");

  const { rows: categoryRows } = await client.query<{
    key: string;
    label: string;
    sort_order: number;
    is_system: boolean;
  }>(
    `SELECT key, label, sort_order, is_system
       FROM crm_categories
      ORDER BY sort_order`,
  );
  assert.deepEqual(
    categoryRows.map((row) => ({
      key: row.key,
      label: row.label,
      sortOrder: row.sort_order,
      isSystem: row.is_system,
    })),
    EXPECTED_CATEGORIES,
    "CRM categories must be exactly the four fixed system categories",
  );

  const { rows: settingsRows } = await client.query<{
    pipeline_id: string;
    auto_apply_confidence: string;
    review_other: boolean;
    customer_requires_review: boolean;
    human_send_only: boolean;
  }>(
    `SELECT pipeline_id, auto_apply_confidence::text, review_other,
            customer_requires_review, human_send_only
       FROM crm_settings`,
  );
  assert.equal(settingsRows.length, 1, "the foundation must seed exactly one settings row");
  assert.equal(settingsRows[0]?.pipeline_id, DEFAULT_PIPELINE_ID);
  assert.equal(Number(settingsRows[0]?.auto_apply_confidence), 0.85);
  assert.equal(settingsRows[0]?.review_other, true);
  assert.equal(settingsRows[0]?.customer_requires_review, true);
  assert.equal(settingsRows[0]?.human_send_only, true);

  // Existing installations may already contain administrator-created
  // subcategories. The migration itself contains no subcategory INSERT; this
  // integration check therefore must not require a permanently empty table.

  await expectRejected(
    client,
    "second default pipeline",
    `INSERT INTO crm_pipelines (organization_id, id, name, is_default, active)
     VALUES ('${ORGANIZATION_ID}', $1, 'Second default fixture', true, true)`,
    [FIXTURE_PIPELINE_ID],
    "23505",
  );
  await expectRejected(
    client,
    "unknown category key",
    `INSERT INTO crm_categories (key, label, sort_order, is_system)
     VALUES ('unknown_fixture', 'Unknown fixture', 100, true)`,
    [],
    "23514",
  );
  await expectRejected(
    client,
    "system category cannot be renamed",
    "UPDATE crm_categories SET label = 'Renamed' WHERE key = 'customer'",
    [],
    "23514",
  );
  await expectRejected(
    client,
    "system category cannot be deleted",
    "DELETE FROM crm_categories WHERE key = 'customer'",
    [],
    "23514",
  );
  await expectRejected(
    client,
    "customer review cannot be disabled",
    `UPDATE crm_settings
        SET customer_requires_review = false
      WHERE pipeline_id = $1`,
    [DEFAULT_PIPELINE_ID],
    "23514",
  );
  await expectRejected(
    client,
    "human send only cannot be disabled",
    `UPDATE crm_settings
        SET human_send_only = false
      WHERE pipeline_id = $1`,
    [DEFAULT_PIPELINE_ID],
    "23514",
  );
  await expectRejected(
    client,
    "confidence cannot be below zero",
    `UPDATE crm_settings
        SET auto_apply_confidence = -0.001
      WHERE pipeline_id = $1`,
    [DEFAULT_PIPELINE_ID],
    "23514",
  );
  await expectRejected(
    client,
    "confidence cannot exceed one",
    `UPDATE crm_settings
        SET auto_apply_confidence = 1.001
      WHERE pipeline_id = $1`,
    [DEFAULT_PIPELINE_ID],
    "23514",
  );

  await client.query(
    `INSERT INTO crm_pipelines (organization_id, id, name, is_default, active)
     VALUES ('${ORGANIZATION_ID}', $1, 'Fixture pipeline', false, true)`,
    [FIXTURE_PIPELINE_ID],
  );
  await client.query(
    `INSERT INTO crm_subcategories
       (id, pipeline_id, category_key, key, name)
     VALUES ($1, $2, 'customer', 'fixture_subcategory', 'Fixture subcategory')`,
    [FIXTURE_SUBCATEGORY_ID, DEFAULT_PIPELINE_ID],
  );

  await expectRejected(
    client,
    "subcategory key is immutable",
    `UPDATE crm_subcategories SET key = 'changed_key' WHERE id = $1`,
    [FIXTURE_SUBCATEGORY_ID],
    "23514",
  );
  await expectRejected(
    client,
    "subcategory pipeline is immutable",
    `UPDATE crm_subcategories SET pipeline_id = $1 WHERE id = $2`,
    [FIXTURE_PIPELINE_ID, FIXTURE_SUBCATEGORY_ID],
    "23514",
  );
  await expectRejected(
    client,
    "subcategory category is immutable",
    `UPDATE crm_subcategories SET category_key = 'interested' WHERE id = $1`,
    [FIXTURE_SUBCATEGORY_ID],
    "23514",
  );

  await client.query(
    `UPDATE crm_subcategories
        SET name = 'Edited fixture subcategory'
      WHERE id = $1`,
    [FIXTURE_SUBCATEGORY_ID],
  );
  const { rows: editedRows } = await client.query<{ name: string; key: string; pipeline_id: string; category_key: string }>(
    `SELECT name, key, pipeline_id, category_key
       FROM crm_subcategories
      WHERE id = $1`,
    [FIXTURE_SUBCATEGORY_ID],
  );
  assert.deepEqual(editedRows, [{
    name: "Edited fixture subcategory",
    key: "fixture_subcategory",
    pipeline_id: DEFAULT_PIPELINE_ID,
    category_key: "customer",
  }], "subcategory names remain editable while immutable fields stay fixed");

}

async function main(): Promise<void> {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) throw new Error("DATABASE_URL is not set — check .env.local");

  const client = new Client({
    connectionString: databaseUrl,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: "agentsdr-test-people-crm-foundation",
  });

  ORGANIZATION_ID = (await resolveScriptOrganization()).id;
  await client.connect();
  let transactionStarted = false;
  try {
    await client.query("BEGIN");
    transactionStarted = true;
    await client.query("SET LOCAL statement_timeout = '30s'");
    await assertFoundation(client);
    console.log("CRM foundation checks passed; rolling back all test work.");
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
