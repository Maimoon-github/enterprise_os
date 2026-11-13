/**
 * Runs the same two operations as backfill-gmail-bounce-suppression.ts and
 * cleanup-actioned-bounce-messages.ts, but across every mailbox in the
 * system in one pass instead of one mailbox at a time — a mailer-daemon or
 * postmaster contact can exist under any connected mailbox, and the same
 * historical bounce-parsing gap (fixed in src/lib/outreach/replyBridge.ts)
 * would have left the same kind of unsuppressed backlog everywhere, not
 * just on the one mailbox this was first noticed on.
 *
 * For every mailer-daemon/postmaster contact found:
 *  1. Re-run handleBounce() over its stored inbound reports, so any
 *     hard-bounced recipient that's still active gets suppressed now
 *     instead of waiting for it to bounce again post-deploy.
 *  2. Delete the reports that are now provably actioned (parseable —
 *     either suppressed or a still-retrying delay). Reports that still
 *     don't parse are left in place for a human to look at.
 *
 * Idempotent — safe to re-run.
 *
 * Run with: bun run scripts/backfill-and-cleanup-all-bounce-mailboxes.ts
 * Bun loads .env.local automatically; export DATABASE_SSL=disable first,
 * this server doesn't support TLS.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset
 * (bun run --conditions=react-server).
 */
import { runScriptInOrganization } from "./lib/organization";
import { eq, and, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inboxContacts, inboxMessages } from "@/lib/inbox/schema";
import { createStepLogger } from "@/lib/debugLog";
import { handleBounce, parseBouncedRecipient } from "@/lib/outreach/replyBridge";
import { suppressEmailOutreach } from "@/lib/outreach/suppression";
import type { InboundMessage } from "@/lib/outreach/gmail";

const BOUNCE_LOCAL_PARTS = ["mailer-daemon", "postmaster"];

async function main() {
  const allContacts = await db
    .select({ id: inboxContacts.id, email: inboxContacts.email, mailbox: inboxContacts.mailbox })
    .from(inboxContacts);
  const bounceContacts = allContacts.filter((c) =>
    BOUNCE_LOCAL_PARTS.includes(c.email.slice(0, c.email.lastIndexOf("@")).toLowerCase()),
  );

  console.log(`Bounce-sender contacts found: ${bounceContacts.length}`);

  let totalSuppressed = 0;
  let totalDelayed = 0;
  let totalUnparsed = 0;
  let totalDeleted = 0;
  const allSuppressedAddresses = new Set<string>();

  for (const contact of bounceContacts) {
    if (!contact.mailbox) continue;
    const messages = await db
      .select({ id: inboxMessages.id, subject: inboxMessages.subject, bodyText: inboxMessages.bodyText })
      .from(inboxMessages)
      .where(and(eq(inboxMessages.contactId, contact.id), eq(inboxMessages.direction, "inbound")));
    if (messages.length === 0) continue;

    let mailboxSuppressed = 0;
    let mailboxDelayed = 0;
    let mailboxUnparsed = 0;
    const toDelete: string[] = [];

    for (const message of messages) {
      const log = createStepLogger();
      const msg = { fromEmail: contact.email, subject: message.subject, bodyText: message.bodyText } as InboundMessage;
      const result = await handleBounce(contact.mailbox, msg, log, suppressEmailOutreach);
      const suppressLine = log.steps.find((s) => s.message.includes("marked bounced"));
      if (suppressLine) {
        mailboxSuppressed += 1;
        allSuppressedAddresses.add(suppressLine.message.split(" ")[0]);
      } else if (result?.skipped) {
        mailboxDelayed += 1;
      } else {
        mailboxUnparsed += 1;
      }
      if (parseBouncedRecipient(message.bodyText) !== null) toDelete.push(message.id);
    }

    if (toDelete.length > 0) {
      await db.delete(inboxMessages).where(inArray(inboxMessages.id, toDelete));
    }

    console.log(
      `${contact.mailbox} <- ${contact.email}: ${messages.length} reports, ` +
      `${mailboxSuppressed} suppressed, ${mailboxDelayed} delay (left alone), ` +
      `${mailboxUnparsed} unparsed (kept), ${toDelete.length} deleted`,
    );

    totalSuppressed += mailboxSuppressed;
    totalDelayed += mailboxDelayed;
    totalUnparsed += mailboxUnparsed;
    totalDeleted += toDelete.length;
  }

  console.log("\n--- Totals ---");
  console.log(`Reports suppressed: ${totalSuppressed} (${allSuppressedAddresses.size} unique addresses)`);
  console.log(`Delay notices left alone: ${totalDelayed}`);
  console.log(`Still unparsed, kept for review: ${totalUnparsed}`);
  console.log(`Messages deleted from Master Inbox: ${totalDeleted}`);
}

runScriptInOrganization(main)
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
