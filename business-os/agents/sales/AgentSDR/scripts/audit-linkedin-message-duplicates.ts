/**
 * Read-only production-safe audit for duplicate automated LinkedIn messages.
 *
 * Run with:
 *   bun run scripts/audit-linkedin-message-duplicates.ts
 *   bun run scripts/audit-linkedin-message-duplicates.ts --report /safe/local/path.json
 *
 * The database session is REPEATABLE READ + READ ONLY. Message bodies are not
 * written to disk; only SHA-256 hashes and lengths are included for comparison.
 */
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "pg";

type AutomatedMessageType = "INVITATION" | "ACCEPTANCE" | "FOLLOW_UP_1" | "FOLLOW_UP_2" | "FOLLOW_UP_3";

type AuditRow = {
  id: string;
  leadId: string;
  type: AutomatedMessageType;
  text: string;
  linkedinMessageId: string | null;
  connectionId: string | null;
  seen: boolean;
  createdAt: Date;
  leadStatus: string | null;
  campaignId: string | null;
  linkedinAccountId: string | null;
  stageSentAt: Date | null;
};

type RedactedMessage = Omit<AuditRow, "text"> & {
  textSha256: string;
  textLength: number;
};

type Recommendation = {
  classification: "safe_candidate" | "manual_review";
  survivorId: string | null;
  reason: string;
};

const AUTOMATED_TYPES = ["INVITATION", "ACCEPTANCE", "FOLLOW_UP_1", "FOLLOW_UP_2", "FOLLOW_UP_3"] as const;

function reportArgument() {
  const index = process.argv.indexOf("--report");
  if (index < 0) return resolve("reports/migration/linkedin-message-duplicates.json");
  const value = process.argv[index + 1];
  if (!value) throw new Error("--report requires a path");
  return resolve(value);
}

function redact(row: AuditRow): RedactedMessage {
  const { text, ...metadata } = row;
  return {
    ...metadata,
    textSha256: createHash("sha256").update(text).digest("hex"),
    textLength: text.length,
  };
}

export function recommendSurvivor(messages: RedactedMessage[]): Recommendation {
  const providerIds = new Set(messages.map((message) => message.linkedinMessageId).filter(Boolean));
  const textHashes = new Set(messages.map((message) => message.textSha256));

  if (textHashes.size > 1) {
    return { classification: "manual_review", survivorId: null, reason: "conflicting_message_texts" };
  }
  if (providerIds.size === 0) {
    return { classification: "manual_review", survivorId: null, reason: "no_provider_delivery_evidence" };
  }

  const createdTimes = messages.map((message) => new Date(message.createdAt).getTime());
  const deliveryWindowMs = Math.max(...createdTimes) - Math.min(...createdTimes);
  if (providerIds.size > 1 && messages.every((message) => message.linkedinMessageId) && deliveryWindowMs <= 10_000) {
    const [earliest] = [...messages].sort((left, right) => {
      const timeDifference = new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
      return timeDifference || left.id.localeCompare(right.id);
    });
    return {
      classification: "safe_candidate",
      survivorId: earliest?.id ?? null,
      reason: "provider_confirmed_duplicate_delivery_within_10_seconds",
    };
  }
  if (providerIds.size > 1) {
    return { classification: "manual_review", survivorId: null, reason: "distinct_provider_message_ids_outside_safe_window" };
  }

  const providerId = [...providerIds][0];
  const candidates = messages
    .filter((message) => message.linkedinMessageId === providerId)
    .sort((left, right) => {
      const timeDifference = new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
      return timeDifference || left.id.localeCompare(right.id);
    });
  return {
    classification: "safe_candidate",
    survivorId: candidates[0]?.id ?? null,
    reason: candidates.length === 1 ? "single_provider_confirmed_row" : "same_provider_id_keep_earliest",
  };
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const reportPath = reportArgument();
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    application_name: "agentsdr-readonly-linkedin-message-duplicate-audit",
  });

  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '30s'");
    await client.query("SET LOCAL lock_timeout = '2s'");
    const { rows: duplicateColumnRows } = await client.query<{ present: boolean }>(`
      SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'Message' AND column_name = 'duplicateOfMessageId'
      ) AS present
    `);
    const canonicalPredicate = duplicateColumnRows[0]?.present ? `AND "duplicateOfMessageId" IS NULL` : "";
    const { rows } = await client.query<AuditRow>(`
      WITH duplicate_groups AS (
        SELECT "leadId", "type"
        FROM "Message"
        WHERE "leadId" IS NOT NULL
          ${canonicalPredicate}
          AND "type" = ANY($1::"MessageType"[])
        GROUP BY "leadId", "type"
        HAVING count(*) > 1
      )
      SELECT
        m.id,
        m."leadId",
        m.type,
        m.text,
        m."linkedinMessageId",
        m."connectionId",
        m.seen,
        m."createdAt",
        l.status AS "leadStatus",
        l."campaignId",
        l."linkedinAccountId",
        CASE m.type
          WHEN 'INVITATION' THEN l."requestSentAt"
          WHEN 'ACCEPTANCE' THEN l."acceptMessageSentAt"
          WHEN 'FOLLOW_UP_1' THEN l."followUp1SentAt"
          WHEN 'FOLLOW_UP_2' THEN l."followUp2SentAt"
          WHEN 'FOLLOW_UP_3' THEN l."followUp3SentAt"
          ELSE NULL
        END AS "stageSentAt"
      FROM duplicate_groups duplicate
      JOIN "Message" m
        ON m."leadId" = duplicate."leadId"
       AND m.type = duplicate.type
       ${canonicalPredicate ? `AND m."duplicateOfMessageId" IS NULL` : ""}
      LEFT JOIN "Lead" l ON l.id = m."leadId"
      ORDER BY m."leadId", m.type, m."createdAt", m.id
    `, [[...AUTOMATED_TYPES]]);
    await client.query("ROLLBACK");

    const grouped = new Map<string, RedactedMessage[]>();
    for (const row of rows) {
      const key = `${row.leadId}\u0000${row.type}`;
      const messages = grouped.get(key) ?? [];
      messages.push(redact(row));
      grouped.set(key, messages);
    }

    const groups = [...grouped.values()].map((messages) => ({
      leadId: messages[0].leadId,
      type: messages[0].type,
      campaignId: messages[0].campaignId,
      linkedinAccountId: messages[0].linkedinAccountId,
      leadStatus: messages[0].leadStatus,
      stageSentAt: messages[0].stageSentAt,
      messages,
      recommendation: recommendSurvivor(messages),
    }));
    const summary = {
      auditedAt: new Date().toISOString(),
      readOnly: true,
      duplicateGroups: groups.length,
      duplicateRows: rows.length,
      extraRows: rows.length - groups.length,
      safeCandidateGroups: groups.filter((group) => group.recommendation.classification === "safe_candidate").length,
      manualReviewGroups: groups.filter((group) => group.recommendation.classification === "manual_review").length,
      reasons: Object.fromEntries(
        [...new Set(groups.map((group) => group.recommendation.reason))]
          .sort()
          .map((reason) => [reason, groups.filter((group) => group.recommendation.reason === reason).length]),
      ),
    };
    const report = { summary, groups };
    await mkdir(dirname(reportPath), { recursive: true });
    await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(summary, null, 2));
    console.log(`Detailed redacted report written to ${reportPath}`);
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
