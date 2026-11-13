import "server-only";

import { and, asc, count, eq, gte, inArray, isNull, lt, max, or, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { channelRules } from "@/lib/channels/rules.server";
import { normalizePhone } from "@/lib/calls/phone";
import { callingStations, stationMessageJobs } from "@/lib/calls/schema";
import {
  MESSAGE_CLAIM_STALE_MS,
  MESSAGE_QUEUED_EXPIRES_MS,
  type WorkerMessageClaimRequest,
  type WorkerMessageJob,
  type WorkerMessageResultRequest,
} from "@/lib/calls/stationContract";
import { isPersonDoNotContact } from "@/lib/crm/policies";
import { currentOrganizationId, inOrg, runInOrganization } from "@/lib/tenancy/scope";
import { ensureStationWhatsappAccount, type WhatsappAccountRow } from "./accounts";
import { recordWhatsappOutboundInCrm } from "./crmBridge";
import { WhatsappApiError, WhatsappSendRefusedError } from "./errors";
import { NEW_CHAT_WINDOW_MS, newChatRefusalDetail, whatsappGuardrails } from "./guardrails";
import {
  applyMessageToChat,
  chatInOrg,
  isPendingChatId,
  isUniqueViolation,
  messageInOrg,
  upsertWhatsappChat,
  type WhatsappChatRow,
  type WhatsappMessageRow,
} from "./messages";
import { whatsappAccounts, whatsappChats, whatsappMessages } from "./schema";
import { CallApiError, callApiErrorResponse } from "@/lib/calls/sessions";
import { isUuid, jidPhone, jobOutcomeForResult, StationReportError, jobOutcomeWhenStale, UNCERTAIN_DELIVERY_ERROR, stationChatId, stationMessageKey, type JobOutcome } from "./stationParse";

/**
 * AgentSDR's own WhatsApp messaging, through a calling station's WhatsApp Web
 * (no Unipile). A message is reserved as a whatsapp_messages row (origin
 * 'agentsdr', no provider id yet) on the station's own whatsapp_accounts row
 * (provider 'station'), and queued as a station_message_jobs row that the
 * worker holding the station's WhatsApp Web open sends; the worker also
 * reports the replies it sees (messages.ts, ingestStationMessages), which land
 * in whatsapp_messages and the CRM exactly like Unipile's.
 *
 * The send is asynchronous: callers get the reserved row, and the job's
 * status says when it went out (sent) or did not (failed). On "sent" the row
 * gets WhatsApp's id (when the extension read one), the send time, the chat's
 * last message, and — unless a CRM draft already put it there — the CRM.
 * On "failed" the reserved row is removed, as a refused Unipile send's is
 * (with its chat, when the chat holds nothing else); the job keeps the error.
 * A claim whose worker never reported is different: it may have gone out, so
 * it is never requeued — the job fails as "Delivery uncertain" and the
 * reserved row stays, its raw.status "uncertain" (raw.status is "queued"
 * until sent, "sent" after). A late "sent" report still settles it.
 *
 * Guardrails: a new chat (a number this station has no stored chat with)
 * respects the warm-up and the daily new-chat cap, checked under the same
 * per-account lock as send.ts; Do Not Contact is checked at queueing and again
 * when the worker claims the job. The gap between sends is kept by the claim
 * (a number's next job is not handed out until the gap has passed), so a
 * queued message waits rather than being refused.
 */

export type QueueStationMessageInput = {
  stationId: string;
  /** The lead, when known: links the chat to the Person (CRM, Messages tab). */
  personId: string | null;
  /** E.164. */
  phone: string;
  body: string;
};

export type QueuedStationMessage = {
  /** The reserved whatsapp_messages row. */
  whatsappMessageId: string;
  /** The station_message_jobs row; its status says when it was sent or failed. */
  jobId: string;
};

type JobRow = typeof stationMessageJobs.$inferSelect;

const MAX_TEXT_LENGTH = 4096;

/** The same lock key as send.ts: one number's sends are reserved one at a time. */
function sendLockKey(accountId: string): string {
  return `whatsapp-send:${accountId}`;
}

/**
 * Queues a WhatsApp message from a calling station's number. Must run inside
 * the station's organization scope (runInOrganization). Throws
 * WhatsappSendRefusedError (with a `reason`) when it may not be sent —
 * not_connected, invalid_number, do_not_contact, empty, too_long, warm_up,
 * new_chat_limit — and WhatsappApiError(404) for an unknown station.
 */
export async function queueStationMessage(input: QueueStationMessageInput): Promise<QueuedStationMessage> {
  const [station] = await db
    .select()
    .from(callingStations)
    .where(and(inOrg(callingStations), eq(callingStations.id, input.stationId)))
    .limit(1);
  if (!station) throw new WhatsappApiError(404, "Calling number not found");
  const account = await ensureStationWhatsappAccount(station);
  const phone = normalizePhone(input.phone);
  if (!phone) throw new WhatsappSendRefusedError(`"${input.phone}" is not a phone number with its country code`, 400, null, "invalid_number");
  if (input.personId && (await isPersonDoNotContact(db, input.personId))) {
    throw new WhatsappSendRefusedError("This lead is marked Do Not Contact", 409, null, "do_not_contact");
  }
  const queued = await queueStationSend({ account, chat: null, phone, personId: input.personId, text: input.body });
  return { whatsappMessageId: queued.message.id, jobId: queued.jobId };
}

export type StationSendTarget = {
  account: WhatsappAccountRow;
  chat: WhatsappChatRow | null;
  /** E.164; used when there is no chat. */
  phone: string | null;
  /** A chat id known to the caller (the CRM conversation's), "<digits>@s.whatsapp.net" for a station. */
  unipileChatId?: string | null;
  personId: string | null;
  text: string;
  callSessionId?: string | null;
};

/**
 * performWhatsappSend's path for a station's number (and queueStationMessage's):
 * reserve the message and queue the job. Returns the reserved rows.
 */
export async function queueStationSend(target: StationSendTarget): Promise<{ chat: WhatsappChatRow; message: WhatsappMessageRow; jobId: string }> {
  const { account, text } = target;
  if (account.provider !== "station" || !account.stationId) throw new Error(`WhatsApp account ${account.id} is not a calling station's`);
  if (!text.trim()) throw new WhatsappSendRefusedError("The message is empty", 400, null, "empty");
  if (text.length > MAX_TEXT_LENGTH) throw new WhatsappSendRefusedError(`The message is longer than ${MAX_TEXT_LENGTH} characters`, 400, null, "too_long");
  if (account.status !== "connected") {
    throw new WhatsappSendRefusedError(`The calling number ${account.name ?? account.phone ?? ""} is not active (paused, logged out or linked to another account)`.replace(/\s+/g, " "), 409, null, "not_connected");
  }
  const givenChat = target.chat && target.chat.accountId === account.id && !isPendingChatId(target.chat.unipileChatId) ? target.chat : null;
  const phone = givenChat?.phone ?? target.phone ?? jidPhone(target.unipileChatId);
  if (!givenChat && !phone && !target.unipileChatId) throw new WhatsappSendRefusedError("There is no chat or number to send to", 400, null, "no_target");
  const stationId = account.stationId;
  const guardrails = whatsappGuardrails(await channelRules("whatsapp"), account);

  return db.transaction(async (tx) => {
    await tx.execute(sql`select pg_advisory_xact_lock(hashtextextended(${sendLockKey(account.id)}, 0))`);
    const now = new Date();

    let chat = givenChat;
    const known = [
      ...(target.unipileChatId ? [eq(whatsappChats.unipileChatId, target.unipileChatId)] : []),
      ...(phone ? [eq(whatsappChats.unipileChatId, stationChatId(phone)), eq(whatsappChats.phone, phone)] : []),
    ];
    if (!chat && known.length) {
      const [stored] = await tx
        .select()
        .from(whatsappChats)
        .where(and(chatInOrg(), eq(whatsappChats.accountId, account.id), or(...known)))
        .orderBy(sql`${whatsappChats.lastMessageAt} desc nulls last`)
        .limit(1);
      chat = stored ?? null;
    }
    // The job dials by number: a chat WhatsApp named only by its "@lid" id needs the lead's number.
    const sendTo = chat?.phone ?? phone;
    if (!sendTo) throw new WhatsappSendRefusedError("The lead's WhatsApp number is not known — add their phone number", 400, null, "no_target");

    if (!chat) {
      const [started] = await tx
        .select({ count: sql<number>`count(*)::int` })
        .from(whatsappChats)
        .where(and(
          chatInOrg(),
          eq(whatsappChats.accountId, account.id),
          gte(whatsappChats.createdAt, new Date(now.getTime() - NEW_CHAT_WINDOW_MS)),
          sql`(select m.origin from ${whatsappMessages} m where m.chat_id = ${whatsappChats.id} order by m.sent_at asc limit 1) = 'agentsdr'`,
        ));
      const refusal = newChatRefusalDetail({ connectedAt: account.connectedAt, newChatsInWindow: started?.count ?? 0, now, guardrails });
      if (refusal) throw new WhatsappSendRefusedError(refusal.message, 409, null, refusal.reason);
      chat = await upsertWhatsappChat({ accountId: account.id, unipileChatId: stationChatId(sendTo), providerId: stationChatId(sendTo), phone: sendTo, name: null }, tx);
    }
    if (target.personId && !chat.personId) {
      const [linked] = await tx
        .update(whatsappChats)
        .set({ personId: target.personId, updatedAt: now })
        .where(and(chatInOrg(), eq(whatsappChats.id, chat.id), isNull(whatsappChats.personId)))
        .returning();
      chat = linked ?? chat;
    }

    const [message] = await tx
      .insert(whatsappMessages)
      .values({
        chatId: chat.id,
        unipileMessageId: null,
        direction: "outbound",
        origin: "agentsdr",
        body: text,
        attachments: [],
        sentAt: now,
        callSessionId: target.callSessionId ?? null,
        raw: { source: "station", stationId, status: "queued" },
      })
      .returning();
    if (!message) throw new Error("whatsapp_messages insert returned no row");
    const [job] = await tx
      .insert(stationMessageJobs)
      .values({
        organizationId: currentOrganizationId(),
        stationId,
        whatsappMessageId: message.id,
        phone: sendTo,
        body: text,
      })
      .returning({ id: stationMessageJobs.id });
    if (!job) throw new Error("station_message_jobs insert returned no row");
    return { chat, message, jobId: job.id };
  });
}

// --- the worker's side ------------------------------------------------------------

/** No other job on the station is being sent (a stale claim does not count). */
function noClaimedJob(stationIdColumn: typeof callingStations.id) {
  return sql`NOT EXISTS (
    SELECT 1 FROM station_message_jobs other
     WHERE other.station_id = ${stationIdColumn}
       AND other.status = 'claimed'
       AND other.claimed_at > now() - interval '${sql.raw(String(MESSAGE_CLAIM_STALE_MS))} milliseconds')`;
}

/** No claimed cloud call on the station is still open (the same rule as stations.ts's claim). */
const stationHasNoOpenCall = sql`NOT EXISTS (
  SELECT 1 FROM call_sessions busy
   WHERE busy.station_id = ${callingStations.id}
     AND busy.mode = 'agent_cloud'
     AND busy.claimed_at IS NOT NULL
     AND busy.status IN ('pending', 'in_progress'))`;

let lastSweepAt = 0;
const SWEEP_EVERY_MS = 30_000;

/**
 * The next message for a worker to send: on a station it holds open (its
 * lease), that is active, free of any open call and of another message in
 * flight, and whose gap since its last send has passed. Platform-wide like
 * the call claim; each job runs in its station's organization.
 */
export async function claimStationMessageJob(input: WorkerMessageClaimRequest): Promise<WorkerMessageJob | null> {
  if (Date.now() - lastSweepAt > SWEEP_EVERY_MS) {
    lastSweepAt = Date.now();
    await expireStaleMessageJobs().catch((error) => console.error("[station messages] sweep failed", error));
  }
  if (input.stations.length === 0) return null;
  // Stations with something queued, oldest waiting first.
  const candidates = await db
    .select({ stationId: stationMessageJobs.stationId, organizationId: stationMessageJobs.organizationId, oldest: sql<string>`min(${stationMessageJobs.createdAt})` })
    .from(stationMessageJobs)
    .innerJoin(callingStations, eq(callingStations.id, stationMessageJobs.stationId))
    .where(and(
      inArray(stationMessageJobs.stationId, input.stations),
      eq(stationMessageJobs.status, "queued"),
      eq(callingStations.leaseHolder, input.workerId),
    ))
    .groupBy(stationMessageJobs.stationId, stationMessageJobs.organizationId)
    .orderBy(sql`min(${stationMessageJobs.createdAt}) asc`)
    .limit(10);
  for (const candidate of candidates) {
    const job = await runInOrganization(candidate.organizationId, () => claimOnStation(candidate.stationId, input.workerId));
    if (job) return job;
  }
  return null;
}

async function claimOnStation(stationId: string, workerId: string): Promise<WorkerMessageJob | null> {
  const { secondsBetweenSends } = await channelRules("whatsapp");
  const claimed = await db.transaction(async (tx) => {
    // The station row's lock is the one the call claim takes: a call and a message never both start.
    const [station] = await tx
      .select({ id: callingStations.id })
      .from(callingStations)
      .where(and(
        inOrg(callingStations),
        eq(callingStations.id, stationId),
        eq(callingStations.status, "active"),
        or(isNull(callingStations.linkedPhone), eq(callingStations.linkedPhone, callingStations.phone)),
        isNull(callingStations.linkRequestedAt),
        eq(callingStations.leaseHolder, workerId),
        sql`${callingStations.leaseUntil} > now()`,
        stationHasNoOpenCall,
        noClaimedJob(callingStations.id),
      ))
      .for("update", { skipLocked: true });
    if (!station) return null;

    const [last] = await tx
      .select({ sentAt: max(stationMessageJobs.sentAt) })
      .from(stationMessageJobs)
      .where(and(inOrg(stationMessageJobs), eq(stationMessageJobs.stationId, stationId), eq(stationMessageJobs.status, "sent")));
    const lastSentAt = last?.sentAt ? new Date(last.sentAt) : null;
    if (lastSentAt && Date.now() - lastSentAt.getTime() < secondsBetweenSends * 1000) return null;

    const [job] = await tx
      .select({ job: stationMessageJobs, personId: whatsappChats.personId })
      .from(stationMessageJobs)
      .innerJoin(whatsappMessages, eq(whatsappMessages.id, stationMessageJobs.whatsappMessageId))
      .innerJoin(whatsappChats, eq(whatsappChats.id, whatsappMessages.chatId))
      .where(and(inOrg(stationMessageJobs), eq(stationMessageJobs.stationId, stationId), eq(stationMessageJobs.status, "queued")))
      .orderBy(asc(stationMessageJobs.createdAt))
      .limit(1)
      .for("update", { of: [stationMessageJobs], skipLocked: true });
    if (!job) return null;
    if (job.personId && (await isPersonDoNotContact(tx, job.personId))) {
      return { kind: "do_not_contact" as const, job: job.job };
    }
    const now = new Date();
    await tx
      .update(stationMessageJobs)
      .set({ status: "claimed", claimedBy: workerId, claimedAt: now })
      .where(eq(stationMessageJobs.id, job.job.id));
    return { kind: "claimed" as const, job: { ...job.job, status: "claimed" as const, claimedBy: workerId, claimedAt: now } };
  });
  if (!claimed) return null;
  if (claimed.kind === "do_not_contact") {
    await settleJob(claimed.job, { action: "fail", error: "The lead was marked Do Not Contact before the message went out" });
    return null;
  }
  const job = claimed.job;
  return { id: job.id, stationId: job.stationId, phone: job.phone, body: job.body };
}

/** The worker routes' error answer: a bad report is 400, an unknown job or station 404. */
export function stationWorkerErrorResponse(error: unknown): Response {
  if (error instanceof StationReportError) return callApiErrorResponse(new CallApiError(400, error.message));
  if (error instanceof WhatsappApiError) return callApiErrorResponse(new CallApiError(error.status, error.message));
  return callApiErrorResponse(error);
}

/** POST /api/call-worker/messages/:id/result. Unscoped lookup; settles in the job's organization. */
export async function reportStationMessageResult(jobId: string, result: WorkerMessageResultRequest): Promise<void> {
  if (!isUuid(jobId)) throw new WhatsappApiError(404, "Message job not found");
  const [job] = await db.select().from(stationMessageJobs).where(eq(stationMessageJobs.id, jobId)).limit(1);
  if (!job) throw new WhatsappApiError(404, "Message job not found");
  await runInOrganization(job.organizationId, () => settleJob(job, jobOutcomeForResult(job, result), result.ok ? result : null));
}

/**
 * Claimed jobs whose worker went quiet go back to the queue once, then fail;
 * queued jobs nobody claimed in MESSAGE_QUEUED_EXPIRES_MS fail (no worker has
 * the number open). Platform-wide, run from the claim.
 */
export async function expireStaleMessageJobs(): Promise<number> {
  const now = Date.now();
  const stale = await db
    .select()
    .from(stationMessageJobs)
    .where(or(
      and(eq(stationMessageJobs.status, "claimed"), lt(stationMessageJobs.claimedAt, new Date(now - MESSAGE_CLAIM_STALE_MS))),
      and(eq(stationMessageJobs.status, "queued"), lt(stationMessageJobs.createdAt, new Date(now - MESSAGE_QUEUED_EXPIRES_MS))),
    ))
    .limit(200);
  for (const job of stale) {
    const outcome: JobOutcome = job.status === "queued"
      ? { action: "fail", error: "No call worker had this number's WhatsApp Web open to send it within 30 minutes" }
      : jobOutcomeWhenStale(job);
    await runInOrganization(job.organizationId, () => settleJob(job, outcome)).catch((error) => {
      console.error(`[station messages] could not settle stale job ${job.id}`, error);
    });
  }
  return stale.length;
}

/** Applies an outcome to a job and its reserved message. Runs in the job's organization. */
async function settleJob(job: JobRow, outcome: JobOutcome, sent: Extract<WorkerMessageResultRequest, { ok: true }> | null = null): Promise<void> {
  if (outcome.action === "ignore") return;
  if (outcome.action === "requeue") {
    await db
      .update(stationMessageJobs)
      .set({ status: "queued", claimedBy: null, claimedAt: null, error: outcome.error })
      .where(and(inOrg(stationMessageJobs), eq(stationMessageJobs.id, job.id), eq(stationMessageJobs.status, job.status)));
    return;
  }
  if (outcome.action === "fail") {
    const [failed] = await db
      .update(stationMessageJobs)
      .set({ status: "failed", error: outcome.error })
      .where(and(inOrg(stationMessageJobs), eq(stationMessageJobs.id, job.id), inArray(stationMessageJobs.status, ["queued", "claimed"])))
      .returning({ id: stationMessageJobs.id });
    if (!failed) return;
    if (outcome.uncertain) await markReservedMessage(job.whatsappMessageId, "uncertain");
    else await removeReservedMessage(job.whatsappMessageId);
    return;
  }
  const sentAt = new Date(sent?.sentAt ?? Date.now());
  const [marked] = await db
    .update(stationMessageJobs)
    .set({ status: "sent", sentAt, error: null })
    .where(and(
      inOrg(stationMessageJobs),
      eq(stationMessageJobs.id, job.id),
      or(inArray(stationMessageJobs.status, ["queued", "claimed"]), and(eq(stationMessageJobs.status, "failed"), eq(stationMessageJobs.error, UNCERTAIN_DELIVERY_ERROR))),
    ))
    .returning({ id: stationMessageJobs.id });
  if (!marked) return;
  try {
    await finishSentMessage(job, sentAt, sent?.providerMessageId ?? null);
  } catch (error) {
    // The message went out; the job says so whatever happens to the bookkeeping.
    console.error(`[station messages] job ${job.id} sent, but storing it failed`, error);
  }
}

/** Marks a reserved message's delivery state in raw.status (kept, unlike a definite failure). */
async function markReservedMessage(messageId: string, status: "uncertain"): Promise<void> {
  await db
    .update(whatsappMessages)
    .set({ raw: sql`coalesce(${whatsappMessages.raw}, '{}'::jsonb) || ${JSON.stringify({ status })}::jsonb` })
    .where(and(messageInOrg(), eq(whatsappMessages.id, messageId), isNull(whatsappMessages.unipileMessageId)));
}

/** A failed send leaves nothing behind but the job: its reserved message goes, and the chat if that was all it held. */
async function removeReservedMessage(messageId: string): Promise<void> {
  const [removed] = await db
    .delete(whatsappMessages)
    .where(and(messageInOrg(), eq(whatsappMessages.id, messageId), isNull(whatsappMessages.unipileMessageId)))
    .returning({ chatId: whatsappMessages.chatId });
  if (!removed) return;
  const [left] = await db.select({ n: count() }).from(whatsappMessages).where(and(messageInOrg(), eq(whatsappMessages.chatId, removed.chatId)));
  if ((left?.n ?? 0) === 0) await db.delete(whatsappChats).where(and(chatInOrg(), eq(whatsappChats.id, removed.chatId)));
}

async function finishSentMessage(job: JobRow, sentAt: Date, providerMessageId: string | null): Promise<void> {
  const [row] = await db.select().from(whatsappMessages).where(and(messageInOrg(), eq(whatsappMessages.id, job.whatsappMessageId))).limit(1);
  if (!row) return;
  const key = providerMessageId ? stationMessageKey(job.stationId, providerMessageId) : null;
  let message = row;
  const raw = { ...(row.raw ?? {}), status: "sent" };
  if (key && row.unipileMessageId !== key) {
    message = await attachKey(row, key, sentAt, raw, job);
  } else {
    const [updated] = await db.update(whatsappMessages).set({ sentAt, raw }).where(and(messageInOrg(), eq(whatsappMessages.id, row.id))).returning();
    message = updated ?? row;
  }
  await applyMessageToChat(message.chatId, { sentAt: message.sentAt, body: message.body, attachments: [], direction: "outbound", countUnread: false });

  if (message.crmConversationMessageId) return; // a CRM draft's send: the CRM recorded it itself
  const [chat] = await db.select().from(whatsappChats).where(and(chatInOrg(), eq(whatsappChats.id, message.chatId))).limit(1);
  const [account] = chat
    ? await db.select().from(whatsappAccounts).where(and(inOrg(whatsappAccounts), eq(whatsappAccounts.id, chat.accountId))).limit(1)
    : [];
  if (!chat?.personId || !account) return;
  const result = await recordWhatsappOutboundInCrm({
    personId: chat.personId,
    unipileAccountId: account.unipileAccountId,
    unipileChatId: chat.unipileChatId,
    providerContactId: chat.providerId,
    // Without WhatsApp's id the job's is the idempotency key; a later echo only attaches the id.
    unipileMessageId: message.unipileMessageId ?? `station-job:${job.id}`,
    body: message.body,
    sentAt: message.sentAt,
    raw: null,
    origin: "agentsdr",
  });
  if (result.crmConversationMessageId) {
    await db
      .update(whatsappMessages)
      .set({ crmConversationMessageId: result.crmConversationMessageId })
      .where(and(messageInOrg(), eq(whatsappMessages.id, message.id), isNull(whatsappMessages.crmConversationMessageId)));
  }
}

/**
 * Gives the sent message WhatsApp's id. The station's inbound report may have
 * been first and stored the echo as typed on the phone: that row is then this
 * send, kept (it may already be on the CRM) and made ours.
 */
async function attachKey(row: WhatsappMessageRow, key: string, sentAt: Date, raw: Record<string, unknown>, job: JobRow): Promise<WhatsappMessageRow> {
  const [existing] = await db.select().from(whatsappMessages).where(and(messageInOrg(), eq(whatsappMessages.unipileMessageId, key))).limit(1);
  if (existing && existing.id !== row.id) {
    const [merged] = await db
      .update(whatsappMessages)
      .set({
        origin: "agentsdr",
        chatId: row.chatId,
        callSessionId: sql`coalesce(${whatsappMessages.callSessionId}, ${row.callSessionId}::uuid)`,
        crmConversationMessageId: sql`coalesce(${whatsappMessages.crmConversationMessageId}, ${row.crmConversationMessageId}::uuid)`,
        raw,
      })
      .where(and(messageInOrg(), eq(whatsappMessages.id, existing.id)))
      .returning();
    // The job follows the message it sent (the reserved row goes; the unique on the job's message id is free).
    await db.update(stationMessageJobs).set({ whatsappMessageId: existing.id }).where(and(inOrg(stationMessageJobs), eq(stationMessageJobs.id, job.id)));
    await db.delete(whatsappMessages).where(and(messageInOrg(), eq(whatsappMessages.id, row.id)));
    return merged ?? existing;
  }
  try {
    const [updated] = await db
      .update(whatsappMessages)
      .set({ unipileMessageId: key, sentAt, raw })
      .where(and(messageInOrg(), eq(whatsappMessages.id, row.id)))
      .returning();
    return updated ?? row;
  } catch (error) {
    if (!isUniqueViolation(error)) throw error;
    return attachKey(row, key, sentAt, raw, job);
  }
}
