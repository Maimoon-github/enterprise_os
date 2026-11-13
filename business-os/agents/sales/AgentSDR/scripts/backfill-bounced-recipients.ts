/**
 * Suppress the addresses in delivery reports that were mistaken for replies.
 *
 * Run with: bun --conditions=react-server scripts/backfill-bounced-recipients.ts [--dry-run]
 *
 * Until this was fixed, replyBridge recognised exactly one bounce sender,
 * mailer-daemon@googlemail.com — Gmail's own relay, which only reports a
 * failure the moment a send is rejected. A destination server that accepts a
 * message and rejects it afterwards sends its report from its own postmaster
 * address instead, and those fell through to Master Inbox as ordinary mail
 * from a new contact. handleBounce never ran for them, so the failed address
 * was never suppressed and its sequence was never halted.
 *
 * This walks the reports already stored in Master Inbox and does what
 * handleBounce would have done: suppress the address and mark its outreach
 * lead bounced, which also clears any queued sends. It re-uses the production
 * parser and the production suppression helper so it cannot drift from the
 * live path.
 *
 * Safe to re-run: suppression is an upsert and the lead update is idempotent.
 * It only writes to the suppression list and outreach leads — the Master Inbox
 * rows are left alone.
 *
 * Bun loads .env.local automatically.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset
 * (bun run --conditions=react-server).
 */
import { runScriptInOrganization } from "./lib/organization";
import { eq, inArray, like, or, sql } from "drizzle-orm";
import { db } from "../src/lib/db";
import { inboxContacts, inboxMessages } from "../src/lib/inbox/schema";
import { outreachLeads, suppressionList } from "../src/lib/outreach/schema";
import { people } from "../src/lib/leads/schema";
import { parseBouncedRecipient } from "../src/lib/outreach/replyBridge";
import { suppressEmailOutreach } from "../src/lib/outreach/suppression";

const dryRun = process.argv.includes("--dry-run");

async function main() {
  const reports = await db
    .select({
      messageId: inboxMessages.id,
      subject: inboxMessages.subject,
      bodyText: inboxMessages.bodyText,
      sender: inboxContacts.email,
      mailbox: inboxContacts.mailbox,
    })
    .from(inboxMessages)
    .innerJoin(inboxContacts, eq(inboxContacts.id, inboxMessages.contactId))
    .where(or(
      like(inboxContacts.email, "postmaster@%"),
      like(inboxContacts.email, "mailer-daemon@%"),
      like(inboxContacts.email, "MAILER-DAEMON@%"),
    ));

  console.log(`Delivery reports stored in Master Inbox: ${reports.length}`);

  const failedByAddress = new Map<string, { mailbox: string | null; sender: string }>();
  let unparsed = 0;
  for (const report of reports) {
    const failed = parseBouncedRecipient(report.bodyText);
    if (!failed) {
      unparsed += 1;
      console.warn(`  unreadable report from ${report.sender}: ${report.subject ?? "(no subject)"}`);
      continue;
    }
    // A report never comes from the address that failed; the live path applies
    // the same guard.
    if (failed === report.sender.toLowerCase()) continue;
    if (!failedByAddress.has(failed)) failedByAddress.set(failed, { mailbox: report.mailbox, sender: report.sender });
  }

  const addresses = [...failedByAddress.keys()].sort();
  console.log(`Distinct failed addresses: ${addresses.length} (${unparsed} report${unparsed === 1 ? "" : "s"} unreadable)`);
  if (!addresses.length) return;

  const alreadySuppressed = new Set((await db
    .select({ email: suppressionList.email })
    .from(suppressionList)
    .where(inArray(suppressionList.email, addresses))).map((row) => row.email));

  const live = await db
    .select({ email: people.email, status: outreachLeads.sequenceStatus, nextSendAt: outreachLeads.nextSendAt })
    .from(outreachLeads)
    .innerJoin(people, eq(people.id, outreachLeads.personId))
    .where(inArray(people.email, addresses));
  const scheduled = live.filter((lead) => lead.nextSendAt !== null);

  console.log(`  already suppressed: ${alreadySuppressed.size}`);
  console.log(`  outreach leads for them: ${live.length}, of which still scheduled to send: ${scheduled.length}`);
  for (const lead of scheduled) {
    console.log(`    ${lead.email} — ${lead.status}, next send ${lead.nextSendAt?.toISOString()}`);
  }

  if (dryRun) {
    console.log("\n--dry-run: nothing written.");
    return;
  }

  let suppressed = 0;
  for (const address of addresses) {
    if (alreadySuppressed.has(address)) continue;
    const { mailbox } = failedByAddress.get(address)!;
    await suppressEmailOutreach(
      address,
      "bounced",
      `Bounced from ${mailbox ?? "an outreach mailbox"} (backfilled from stored delivery report)`,
      "bounced",
    );
    suppressed += 1;
  }

  const [remaining] = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(outreachLeads)
    .innerJoin(people, eq(people.id, outreachLeads.personId))
    .where(inArray(people.email, addresses));

  console.log(`\nSuppressed ${suppressed} address${suppressed === 1 ? "" : "es"}.`);
  console.log(`Outreach leads for these addresses: ${remaining?.count ?? 0}, all now marked bounced with no next send.`);
}

await runScriptInOrganization(main);
process.exit(0);
