/**
 * Restores every To/Cc/Reply-To on inbound Gmail messages stored before the
 * inbound parser kept them all.
 *
 * Until 2026-10-08 the parser kept only the FIRST To address and split Cc on
 * bare commas, so a lead who replied "To: her manager, us" lost the manager:
 * the thread showed "to <our mailbox>" and a reply could not include her.
 * This re-reads the headers from Gmail and merges `to`, `cc`, `replyTo`,
 * `toEmail` and `ccEmails` into `raw` on the Master Inbox row (crm_messages),
 * which is what the thread view reads. Nothing else in `raw` changes.
 *
 * The CRM twin (crm_conversation_messages) is left alone: that table is
 * append-only by trigger, on purpose. Its old rows keep `toEmail`/`ccEmails`,
 * which recipientsFromRaw still reads.
 *
 * Dry run by default; pass --apply to write. Idempotent: rows whose `raw`
 * already has `to` are skipped.
 *
 * Run with: bun run --conditions=react-server scripts/backfill-email-recipients.ts [--apply]
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset.
 */
import { runScriptInOrganization } from "./lib/organization";
import { and, eq, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { inboxContacts, inboxMessages } from "@/lib/inbox/schema";
import { fetchMessageRecipients } from "@/lib/outreach/gmail";
import { inOrg } from "@/lib/tenancy/scope";

const apply = process.argv.includes("--apply");

async function main() {
  const rows = await db
    .select({
      id: inboxMessages.id,
      mailbox: inboxContacts.mailbox,
      gmailMessageId: sql<string | null>`${inboxMessages.raw}->>'gmailMessageId'`,
      toEmail: sql<string | null>`${inboxMessages.raw}->>'toEmail'`,
    })
    .from(inboxMessages)
    .innerJoin(inboxContacts, eq(inboxContacts.id, inboxMessages.contactId))
    .where(and(
      inOrg(inboxContacts),
      eq(inboxMessages.direction, "inbound"),
      sql`${inboxMessages.raw} ? 'gmailMessageId'`,
      sql`NOT (${inboxMessages.raw} ? 'to')`,
    ));

  console.log(`${apply ? "APPLY" : "DRY RUN"} — ${rows.length} inbound Gmail messages without full recipients`);

  let repaired = 0;
  let gained = 0;
  let missing = 0;
  let failed = 0;
  for (const row of rows) {
    if (!row.mailbox || !row.gmailMessageId) continue;
    let recipients;
    try {
      recipients = await fetchMessageRecipients(row.mailbox, row.gmailMessageId);
    } catch (err) {
      failed += 1;
      console.warn(`  ${row.mailbox} ${row.gmailMessageId}: ${err instanceof Error ? err.message : String(err)}`);
      continue;
    }
    if (!recipients) {
      missing += 1;
      continue;
    }
    const patch = {
      to: recipients.to,
      cc: recipients.cc,
      replyTo: recipients.replyTo,
      toEmail: recipients.to[0]?.email ?? row.toEmail,
      ccEmails: recipients.cc.map((a) => a.email),
    };
    const lostBefore = recipients.to.length > 1 || recipients.cc.length > 0;
    if (lostBefore) {
      gained += 1;
      console.log(`  ${row.gmailMessageId}: to ${recipients.to.map((a) => a.email).join(", ")}${recipients.cc.length ? ` · cc ${recipients.cc.map((a) => a.email).join(", ")}` : ""}`);
    }
    if (apply) {
      const json = JSON.stringify(patch);
      await db.update(inboxMessages)
        .set({ raw: sql`coalesce(${inboxMessages.raw}, '{}'::jsonb) || ${json}::jsonb` })
        .where(eq(inboxMessages.id, row.id));
    }
    repaired += 1;
  }

  console.log("\n--- Totals ---");
  console.log(`${apply ? "Repaired" : "Would repair"}: ${repaired}`);
  console.log(`  of which had recipients the old parser dropped (several To, or any Cc): ${gained}`);
  console.log(`No longer in Gmail (left as is): ${missing}`);
  console.log(`Failed (left as is): ${failed}`);
}

runScriptInOrganization(main)
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
