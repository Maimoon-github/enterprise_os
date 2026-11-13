/**
 * Preserves colliding LinkedIn enrollments but assigns future execution to one
 * canonical Lead. Run only after additive schema preparation.
 *
 * Dry run: bun run scripts/resolve-linkedin-provider-collisions.ts
 * Apply:   bun run scripts/resolve-linkedin-provider-collisions.ts --apply --expected-groups=1 --confirm=keep-most-recent-request
 */
import { Client } from "pg";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const CONFIRMATION = "keep-most-recent-request";

type CollisionRow = {
  providerId: string;
  linkedinAccountId: string;
  leadIds: string[];
  requestSentAts: Date[];
  statuses: string[];
  messageCounts: number[];
  connectionCounts: number[];
};

export function decideProviderCollision(row: CollisionRow) {
  if (row.statuses.some((status) => status !== "REQUEST_SENT")) throw new Error("Collision includes a Lead beyond REQUEST_SENT");
  if (row.messageCounts.some((count) => count !== 1) || row.connectionCounts.some((count) => count !== 0)) {
    throw new Error("Collision has unexpected message or connection history");
  }
  return { survivorId: row.leadIds[0], supersededIds: row.leadIds.slice(1) };
}

function expectedGroups() {
  const raw = process.argv.find((value) => value.startsWith("--expected-groups="))?.split("=")[1];
  return raw === undefined ? null : Number(raw);
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const apply = process.argv.includes("--apply");
  const expected = expectedGroups();
  const confirmed = process.argv.includes(`--confirm=${CONFIRMATION}`);
  if (apply && (!Number.isInteger(expected) || expected! < 0 || !confirmed)) {
    throw new Error(`Apply requires --expected-groups=<count> and --confirm=${CONFIRMATION}`);
  }

  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: "agentsdr-provider-collision-resolution",
  });
  await client.connect();
  try {
    await client.query(apply ? "BEGIN ISOLATION LEVEL SERIALIZABLE" : "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL lock_timeout = '5s'");
    await client.query("SET LOCAL statement_timeout = '30s'");
    if (apply) await client.query("SELECT pg_advisory_xact_lock(hashtext('agentsdr-provider-collision-resolution'))");
    const { rows } = await client.query<CollisionRow>(`
      WITH actionable_base AS (
        SELECT l.*
        FROM "Lead" l
        JOIN "Campaign" c ON c.id = l."campaignId"
        WHERE c.status = 'ACTIVE' AND l.status NOT IN ('COMPLETED', 'REPLIED', 'FAILED', 'CANCELLED')
          AND l."providerId" IS NOT NULL AND l."linkedinAccountId" IS NOT NULL
          AND l."supersededByLeadId" IS NULL
      ), collision_keys AS (
        SELECT "providerId", "linkedinAccountId"
        FROM actionable_base
        GROUP BY "providerId", "linkedinAccountId"
        HAVING count(*) > 1
      ), actionable AS (
        SELECT l.*,
          (SELECT count(*)::int FROM "Message" m WHERE m."leadId" = l.id) AS message_count,
          (SELECT count(*)::int FROM "Connection" x WHERE x."leadId" = l.id) AS connection_count
        FROM actionable_base l
        JOIN collision_keys c USING ("providerId", "linkedinAccountId")
      )
      SELECT "providerId", "linkedinAccountId",
        array_agg(id ORDER BY "requestSentAt" DESC NULLS LAST, "createdAt" DESC, id DESC) AS "leadIds",
        array_agg("requestSentAt" ORDER BY "requestSentAt" DESC NULLS LAST, "createdAt" DESC, id DESC) AS "requestSentAts",
        array_agg(status::text ORDER BY "requestSentAt" DESC NULLS LAST, "createdAt" DESC, id DESC) AS statuses,
        array_agg(message_count ORDER BY "requestSentAt" DESC NULLS LAST, "createdAt" DESC, id DESC) AS "messageCounts",
        array_agg(connection_count ORDER BY "requestSentAt" DESC NULLS LAST, "createdAt" DESC, id DESC) AS "connectionCounts"
      FROM actionable GROUP BY "providerId", "linkedinAccountId"
    `);
    const decisions = rows.map(decideProviderCollision);
    console.log(JSON.stringify({ mode: apply ? "apply" : "dry-run", groups: decisions.length, decisions }, null, 2));
    if (apply && decisions.length !== expected) throw new Error(`Audit drifted: expected ${expected} group(s), found ${decisions.length}`);
    if (apply) {
      for (const decision of decisions) {
        await client.query(
          `UPDATE "Lead" SET status = 'CANCELLED', "supersededByLeadId" = $1, "updatedAt" = now()
           WHERE id = ANY($2::text[]) AND status = 'REQUEST_SENT' AND "supersededByLeadId" IS NULL`,
          [decision.survivorId, decision.supersededIds],
        );
      }
      await client.query("COMMIT");
    } else {
      await client.query("ROLLBACK");
    }
  } catch (error) {
    try { await client.query("ROLLBACK") } catch { /* connection may already be closed */ }
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
