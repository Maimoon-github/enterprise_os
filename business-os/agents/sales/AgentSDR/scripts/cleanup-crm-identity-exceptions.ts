/**
 * Removes historical inbox noise from the open CRM Identity Review queue
 * without deleting its audit trail.
 *
 * Dry run (default):
 *   bun run cleanup:crm-identity
 *
 * Apply after checking the channel counts printed by the dry run:
 *   bun run cleanup:crm-identity --apply --expected-email=64 \
 *     --expected-linkedin=2 --confirm=ignore-non-outreach-inbound
 */
import { Client } from "pg";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const CONFIRMATION = "ignore-non-outreach-inbound";

type Candidate = {
  id: string;
  channel: "email" | "linkedin";
};

function integerArgument(name: string): number | null {
  const prefix = `--${name}=`;
  const raw = process.argv.find((argument) => argument.startsWith(prefix))?.slice(prefix.length);
  if (raw === undefined) return null;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed < 0) throw new Error(`${prefix} requires a non-negative integer`);
  return parsed;
}

async function candidates(client: Client, lock: boolean): Promise<Candidate[]> {
  const { rows } = await client.query<Candidate>(`
    SELECT exception.id, exception.channel
    FROM crm_identity_exceptions exception
    WHERE exception.status = 'open'
      AND (
        (
          exception.channel = 'email'
          AND NOT EXISTS (
            SELECT 1
            FROM people person
            JOIN outreach_leads enrollment ON enrollment.person_id = person.id
            WHERE lower(person.email) = lower(exception.identity_value)
          )
        )
        OR (
          exception.channel = 'linkedin'
          AND NOT EXISTS (
            SELECT 1
            FROM "Lead" lead
            JOIN "LinkedInAccount" account ON account.id = lead."linkedinAccountId"
            WHERE lead."providerId" = exception.identity_value
              AND account."linkedinId" = exception.account_ref
              AND lead."supersededByLeadId" IS NULL
          )
        )
      )
    ORDER BY exception.created_at, exception.id
    ${lock ? "FOR UPDATE OF exception" : ""}
  `);
  return rows;
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const apply = process.argv.includes("--apply");
  const expectedEmail = integerArgument("expected-email");
  const expectedLinkedin = integerArgument("expected-linkedin");
  const confirmed = process.argv.includes(`--confirm=${CONFIRMATION}`);
  if (apply && (expectedEmail === null || expectedLinkedin === null || !confirmed)) {
    throw new Error(
      `Apply requires --expected-email, --expected-linkedin, and --confirm=${CONFIRMATION}`,
    );
  }

  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: apply ? "agentsdr-crm-identity-cleanup" : "agentsdr-readonly-crm-identity-cleanup-preview",
  });
  await client.connect();
  try {
    await client.query(apply
      ? "BEGIN ISOLATION LEVEL SERIALIZABLE"
      : "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL lock_timeout = '5s'");
    await client.query("SET LOCAL statement_timeout = '30s'");
    if (apply) await client.query("SELECT pg_advisory_xact_lock(hashtext('agentsdr-crm-identity-cleanup'))");

    const rows = await candidates(client, apply);
    const email = rows.filter((row) => row.channel === "email").length;
    const linkedin = rows.filter((row) => row.channel === "linkedin").length;
    console.log(JSON.stringify({ mode: apply ? "apply" : "dry-run", email, linkedin, total: rows.length }, null, 2));

    if (apply && (email !== expectedEmail || linkedin !== expectedLinkedin)) {
      throw new Error(`Audit drifted: expected email=${expectedEmail}/linkedin=${expectedLinkedin}, found email=${email}/linkedin=${linkedin}`);
    }

    if (apply && rows.length) {
      const result = await client.query(
        `UPDATE crm_identity_exceptions
         SET status = 'ignored', resolved_person_id = NULL, resolved_at = now(), updated_at = now()
         WHERE id = ANY($1::uuid[]) AND status = 'open'`,
        [rows.map((row) => row.id)],
      );
      if (result.rowCount !== rows.length) {
        throw new Error(`Expected to ignore ${rows.length} exceptions, updated ${result.rowCount ?? 0}`);
      }
    }

    if (apply) await client.query("COMMIT");
    else await client.query("ROLLBACK");
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
