/**
 * Deletes already-actioned mailer-daemon/postmaster reports from Master
 * Inbox for one mailbox: anything whose failed recipient
 * parseBouncedRecipient() can now read out (the hard-bounces already
 * suppressed by scripts/backfill-gmail-bounce-suppression.ts, plus "(Delay)"
 * retry notices, which src/lib/outreach/replyBridge.ts no longer stores for
 * new mail). Reports that still don't parse — genuinely different issues,
 * like a Google Groups posting-permission notice — are left alone for a
 * human to look at, since they were never actioned.
 *
 * Run with: bun run scripts/cleanup-actioned-bounce-messages.ts <mailbox-address>
 * Bun loads .env.local automatically; export DATABASE_SSL=disable first,
 * this server doesn't support TLS.
 */
import { eq, and, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inboxContacts, inboxMessages } from "@/lib/inbox/schema";
import { parseBouncedRecipient } from "@/lib/outreach/replyBridge";

const BOUNCE_LOCAL_PARTS = ["mailer-daemon", "postmaster"];

async function main() {
  const mailboxAddress = process.argv[2];
  if (!mailboxAddress) {
    console.error("Usage: bun run scripts/cleanup-actioned-bounce-messages.ts <mailbox-address>");
    process.exit(1);
  }

  const contacts = await db
    .select({ id: inboxContacts.id, email: inboxContacts.email })
    .from(inboxContacts)
    .where(eq(inboxContacts.mailbox, mailboxAddress));
  const bounceContacts = contacts.filter((c) =>
    BOUNCE_LOCAL_PARTS.includes(c.email.slice(0, c.email.lastIndexOf("@")).toLowerCase()),
  );
  if (bounceContacts.length === 0) {
    console.log(`No mailer-daemon/postmaster contact found for ${mailboxAddress}`);
    return;
  }

  let deleted = 0;
  let kept = 0;

  for (const contact of bounceContacts) {
    const messages = await db
      .select({ id: inboxMessages.id, bodyText: inboxMessages.bodyText })
      .from(inboxMessages)
      .where(and(eq(inboxMessages.contactId, contact.id), eq(inboxMessages.direction, "inbound")));

    const toDelete = messages.filter((m) => parseBouncedRecipient(m.bodyText) !== null).map((m) => m.id);
    kept += messages.length - toDelete.length;
    if (toDelete.length > 0) {
      await db.delete(inboxMessages).where(inArray(inboxMessages.id, toDelete));
      deleted += toDelete.length;
    }
  }

  console.log(`Mailbox: ${mailboxAddress}`);
  console.log(`Deleted (already actioned): ${deleted}`);
  console.log(`Kept (still unparsed, needs a human look): ${kept}`);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
