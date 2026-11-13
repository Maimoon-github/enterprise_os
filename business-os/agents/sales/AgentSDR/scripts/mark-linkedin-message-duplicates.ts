/**
 * Preserves provider-confirmed duplicate deliveries while selecting one
 * canonical automated message for uniqueness/idempotency.
 *
 * Dry run (default):
 *   bun run scripts/mark-linkedin-message-duplicates.ts
 *
 * Apply only after schema preparation and an approved production pause:
 *   bun run scripts/mark-linkedin-message-duplicates.ts --apply \
 *     --expected-groups=46 --expected-extra-rows=48 \
 *     --confirm=preserve-provider-history
 */
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "pg";

type MessageRow = {
  id: string;
  leadId: string;
  type: string;
  text: string;
  linkedinMessageId: string | null;
  createdAt: Date;
};

type DuplicateDecision = {
  leadId: string;
  type: string;
  survivorId: string;
  duplicateIds: string[];
  providerMessageIds: string[];
  deliveryWindowMs: number;
};

const CONFIRMATION = "preserve-provider-history";

function numericArgument(name: string): number | null {
  const prefix = `--${name}=`;
  const raw = process.argv.find((argument) => argument.startsWith(prefix))?.slice(prefix.length);
  if (raw === undefined) return null;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0) throw new Error(`${prefix} requires a non-negative integer`);
  return value;
}

function confirmationArgument() {
  return process.argv.find((argument) => argument.startsWith("--confirm="))?.slice("--confirm=".length) ?? null;
}

export function decideDuplicateGroup(rows: MessageRow[]): DuplicateDecision {
  const sorted = [...rows].sort((left, right) => {
    const timeDifference = new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
    return timeDifference || left.id.localeCompare(right.id);
  });
  const texts = new Set(sorted.map((row) => row.text));
  const providerIds = sorted.map((row) => row.linkedinMessageId).filter((value): value is string => Boolean(value));
  const times = sorted.map((row) => new Date(row.createdAt).getTime());
  const deliveryWindowMs = Math.max(...times) - Math.min(...times);

  if (texts.size !== 1) throw new Error(`${rows[0].leadId}/${rows[0].type}: message bodies differ`);
  if (providerIds.length !== rows.length) throw new Error(`${rows[0].leadId}/${rows[0].type}: missing provider message ID`);
  if (new Set(providerIds).size !== rows.length) throw new Error(`${rows[0].leadId}/${rows[0].type}: provider message IDs are not distinct`);
  if (deliveryWindowMs > 10_000) throw new Error(`${rows[0].leadId}/${rows[0].type}: deliveries span more than 10 seconds`);

  return {
    leadId: rows[0].leadId,
    type: rows[0].type,
    survivorId: sorted[0].id,
    duplicateIds: sorted.slice(1).map((row) => row.id),
    providerMessageIds: providerIds,
    deliveryWindowMs,
  };
}

async function loadDuplicateRows(client: Client, forUpdate: boolean): Promise<MessageRow[]> {
  const lockClause = forUpdate ? "FOR UPDATE OF m" : "";
  const { rows } = await client.query<MessageRow>(`
    WITH duplicate_groups AS (
      SELECT "leadId", "type"
      FROM "Message"
      WHERE "leadId" IS NOT NULL
        AND "duplicateOfMessageId" IS NULL
        AND "type" IN ('INVITATION', 'ACCEPTANCE', 'FOLLOW_UP_1', 'FOLLOW_UP_2', 'FOLLOW_UP_3')
      GROUP BY "leadId", "type"
      HAVING count(*) > 1
    )
    SELECT m.id, m."leadId", m.type, m.text, m."linkedinMessageId", m."createdAt"
    FROM duplicate_groups duplicate
    JOIN "Message" m
      ON m."leadId" = duplicate."leadId"
     AND m.type = duplicate.type
     AND m."duplicateOfMessageId" IS NULL
    ORDER BY m."leadId", m.type, m."createdAt", m.id
    ${lockClause}
  `);
  return rows;
}

function buildDecisions(rows: MessageRow[]) {
  const groups = new Map<string, MessageRow[]>();
  for (const row of rows) {
    const key = `${row.leadId}\u0000${row.type}`;
    const group = groups.get(key) ?? [];
    group.push(row);
    groups.set(key, group);
  }
  return [...groups.values()].map(decideDuplicateGroup);
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const apply = process.argv.includes("--apply");
  const expectedGroups = numericArgument("expected-groups");
  const expectedExtraRows = numericArgument("expected-extra-rows");
  if (apply && (expectedGroups === null || expectedExtraRows === null || confirmationArgument() !== CONFIRMATION)) {
    throw new Error(
      `Apply requires --expected-groups, --expected-extra-rows, and --confirm=${CONFIRMATION}`,
    );
  }

  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: apply
      ? "agentsdr-mark-linkedin-message-duplicates"
      : "agentsdr-readonly-linkedin-message-duplicate-cleanup-preview",
  });
  await client.connect();
  try {
    await client.query(apply
      ? "BEGIN ISOLATION LEVEL SERIALIZABLE"
      : "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL lock_timeout = '5s'");
    await client.query("SET LOCAL statement_timeout = '2min'");
    if (apply) await client.query("SELECT pg_advisory_xact_lock(hashtext('agentsdr-linkedin-message-dedup'))");

    const rows = await loadDuplicateRows(client, apply);
    const decisions = buildDecisions(rows);
    const extraRows = decisions.reduce((sum, decision) => sum + decision.duplicateIds.length, 0);
    const summary = {
      mode: apply ? "apply" : "dry-run",
      groups: decisions.length,
      extraRows,
      allPreserved: true,
    };
    console.log(JSON.stringify(summary, null, 2));

    if (apply && (decisions.length !== expectedGroups || extraRows !== expectedExtraRows)) {
      throw new Error(
        `Audit drifted: expected ${expectedGroups} groups/${expectedExtraRows} extras, found ${decisions.length}/${extraRows}`,
      );
    }

    if (apply) {
      for (const decision of decisions) {
        const result = await client.query(
          `UPDATE "Message"
           SET "duplicateOfMessageId" = $1
           WHERE id = ANY($2::text[]) AND "duplicateOfMessageId" IS NULL`,
          [decision.survivorId, decision.duplicateIds],
        );
        if (result.rowCount !== decision.duplicateIds.length) {
          throw new Error(`${decision.leadId}/${decision.type}: expected to mark ${decision.duplicateIds.length}, marked ${result.rowCount}`);
        }
      }
      const remaining = await loadDuplicateRows(client, false);
      if (remaining.length) throw new Error(`Cleanup invariant failed: ${remaining.length} canonical duplicate rows remain`);
      await client.query("COMMIT");
    } else {
      await client.query("ROLLBACK");
    }

    const auditPath = resolve(`reports/migration/linkedin-message-duplicate-decisions-${apply ? "applied" : "preview"}.json`);
    await mkdir(resolve("reports/migration"), { recursive: true });
    await writeFile(auditPath, `${JSON.stringify({ createdAt: new Date().toISOString(), summary, decisions }, null, 2)}\n`, { mode: 0o600 });
    console.log(`Decision ledger written to ${auditPath}`);
  } catch (error) {
    try { await client.query("ROLLBACK"); } catch { /* connection may already be closed */ }
    throw error;
  } finally {
    await client.end();
  }
}

if (resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
