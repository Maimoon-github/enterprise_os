// Runs in ORGANIZATION_ID, or the initial organization when it is unset.
import { and, eq } from "drizzle-orm";
import { db } from "../src/lib/db";
import { webhookEvents } from "../src/lib/linkedin/schema";
import {
  beginWebhookDelivery,
  claimWebhookEvent,
  finishWebhookEvent,
  replayableWebhookEventIds,
} from "../src/lib/linkedin/webhooks/inbox";
import { currentOrganizationId } from "@/lib/tenancy/scope";
import { runScriptInOrganization } from "./lib/organization";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

const body = {
  event: "message_received",
  account_type: "LINKEDIN",
  account_id: "inbox-test-account",
  message_id: "inbox-test-message",
  message: "hello",
};

const values = {
  event: body.event,
  accountType: body.account_type,
  accountId: body.account_id,
  senderId: "inbox-test-sender",
  chatId: "inbox-test-chat",
  messageText: body.message,
  rawBody: body,
};

async function main() {
  await db.delete(webhookEvents).where(eq(webhookEvents.accountId, body.account_id));

  const [first, duplicate] = await Promise.all([
    beginWebhookDelivery(body, values),
    beginWebhookDelivery(body, values),
  ]);
  assert(first.event.id === duplicate.event.id, "concurrent deliveries did not converge on one event");
  assert(Number(first.claimed) + Number(duplicate.claimed) === 1, "exactly one delivery must own processing");

  const eventId = first.event.id;
  await finishWebhookEvent(eventId, "error", []);
  const retryTime = new Date(Date.now() + 60_000);
  const candidates = await replayableWebhookEventIds(10, retryTime);
  assert(candidates.includes(eventId), "retryable error was not selected");

  const claims = await Promise.all([
    claimWebhookEvent(eventId, retryTime),
    claimWebhookEvent(eventId, retryTime),
    claimWebhookEvent(eventId, retryTime),
  ]);
  assert(claims.filter(Boolean).length === 1, "concurrent workers both claimed one event");

  await finishWebhookEvent(eventId, "ok", []);
  const [stored] = await db
    .select()
    .from(webhookEvents)
    .where(and(eq(webhookEvents.id, eventId), eq(webhookEvents.processingStatus, "ok")))
    .limit(1);
  assert(stored?.processedAt, "successful processing did not record completion");
  assert(stored.processingAttempt === 2, "claim attempt count was not preserved");

  const afterSuccess = await beginWebhookDelivery(body, values);
  assert(!afterSuccess.claimed && afterSuccess.event.id === eventId, "completed duplicate was reprocessed");

  const [stale] = await db.insert(webhookEvents).values({
    organizationId: currentOrganizationId(),
    event: "new_relation",
    accountType: "LINKEDIN",
    accountId: body.account_id,
    rawBody: { event: "new_relation" },
    processingStatus: "processing",
    processingAttempt: 1,
    processingStartedAt: new Date(0),
  }).returning();
  const staleClaims = await Promise.all([
    claimWebhookEvent(stale.id),
    claimWebhookEvent(stale.id),
  ]);
  assert(staleClaims.filter(Boolean).length === 1, "abandoned lease was not reclaimed exactly once");

  await db.delete(webhookEvents).where(eq(webhookEvents.accountId, body.account_id));
  console.log("LinkedIn webhook inbox integration test passed");
}

runScriptInOrganization(main)
  .then(() => process.exit(0)).catch((error) => {
  console.error(error);
  process.exit(1);
});
