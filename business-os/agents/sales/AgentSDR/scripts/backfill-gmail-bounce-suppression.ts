/**
 * One-shot backfill for the Gmail bounce-phrasing gap fixed in
 * src/lib/outreach/replyBridge.ts (2026-09-16): Gmail's "delivering your
 * message to X" / "has been blocked" reports never matched the parser, so
 * failed recipients were never suppressed and kept getting re-emailed by
 * later sequence steps, each producing another unparsed report.
 *
 * This re-runs the (now fixed) bounce handling over every mailer-daemon /
 * postmaster report already stored in Master Inbox for one mailbox, so the
 * backlog is caught up without waiting for each address to bounce again
 * post-deploy.
 *
 * Idempotent — handleBounce's suppress() call is onConflictDoNothing, and
 * "(Delay)" reports are recognized but intentionally left unsuppressed
 * (Gmail may still deliver).
 *
 * Run with: bun run scripts/backfill-gmail-bounce-suppression.ts <mailbox-address>
 * Bun loads .env.local automatically. DATABASE_SSL=disable is required
 * against this server (it doesn't support TLS) — export it before running
 * if your shell doesn't already have it set.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset
 * (bun run --conditions=react-server).
 */
import { runScriptInOrganization } from "./lib/organization";
import { eq, and } from "drizzle-orm";
import { db } from "@/lib/db";
import { inboxContacts, inboxMessages } from "@/lib/inbox/schema";
import { createStepLogger } from "@/lib/debugLog";
import { handleBounce } from "@/lib/outreach/replyBridge";
import { suppressEmailOutreach } from "@/lib/outreach/suppression";
import type { InboundMessage } from "@/lib/outreach/gmail";

const BOUNCE_LOCAL_PARTS = ["mailer-daemon", "postmaster"];

async function main() {
  const mailboxAddress = process.argv[2];
  if (!mailboxAddress) {
    console.error("Usage: bun run scripts/backfill-gmail-bounce-suppression.ts <mailbox-address>");
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

  let suppressed = 0;
  let delayed = 0;
  let unparsed = 0;
  const suppressedAddresses = new Set<string>();

  for (const contact of bounceContacts) {
    const messages = await db
      .select({ id: inboxMessages.id, subject: inboxMessages.subject, bodyText: inboxMessages.bodyText })
      .from(inboxMessages)
      .where(and(eq(inboxMessages.contactId, contact.id), eq(inboxMessages.direction, "inbound")));

    for (const message of messages) {
      const log = createStepLogger();
      const msg = { fromEmail: contact.email, subject: message.subject, bodyText: message.bodyText } as InboundMessage;
      const result = await handleBounce(mailboxAddress, msg, log, suppressEmailOutreach);
      const suppressLine = log.steps.find((s) => s.message.includes("marked bounced"));
      if (suppressLine) {
        suppressed += 1;
        const email = suppressLine.message.split(" ")[0];
        suppressedAddresses.add(email);
      } else if (result?.skipped) {
        delayed += 1;
      } else {
        unparsed += 1;
      }
    }
  }

  console.log(`Mailbox: ${mailboxAddress}`);
  console.log(`Reports processed: ${suppressed + delayed + unparsed}`);
  console.log(`Suppressed (final failure): ${suppressed} — ${suppressedAddresses.size} unique addresses`);
  console.log(`Still retrying (delay, left alone): ${delayed}`);
  console.log(`Still unparsed (unchanged): ${unparsed}`);
  console.log([...suppressedAddresses].sort().join("\n"));
}

runScriptInOrganization(main)
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
