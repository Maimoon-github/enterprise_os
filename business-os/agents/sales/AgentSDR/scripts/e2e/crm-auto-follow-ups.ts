/**
 * End-to-end check of CRM follow-ups: reply → category → immediate reply →
 * follow-ups drafted → sent automatically, paced per sending account.
 *
 *   DATABASE_URL=postgres://postgres@127.0.0.1:55432/agentsdr_e2e DATABASE_SSL=disable \
 *     bun run --conditions=react-server scripts/e2e/crm-auto-follow-ups.ts
 *
 * Runs the real library code (ingest, classification job, drafting, sendDraft,
 * the automatic sender, the email scheduler's yield) against a disposable
 * database with the live schema (pg_dump --schema-only). The AI and the
 * providers are fakes: nothing is sent anywhere. It creates its own
 * organization and refuses to run unless DATABASE_URL points at localhost.
 */
import assert from "node:assert/strict";
import { and, asc, eq } from "drizzle-orm";

if (!/@(localhost|127\.0\.0\.1)[:/]/.test(process.env.DATABASE_URL ?? "")) {
  console.error("Refusing to run: DATABASE_URL must point at a local, disposable database.");
  process.exit(1);
}

const { db } = await import("@/lib/db");
const { organizations } = await import("@/lib/auth/schema");
const { people } = await import("@/lib/leads/schema");
const { gridProviders, gridProviderCredentials } = await import("@/lib/grid/schema");
const { encryptIntegrationCredentials } = await import("@/lib/integrations/credentials");
const { mailboxes } = await import("@/lib/outreach/schema");
const { linkedInAccounts } = await import("@/lib/linkedin/schema");
const { whatsappAccounts } = await import("@/lib/whatsapp/schema");
const { runInOrganization } = await import("@/lib/tenancy/scope");
const { ensureCrmDefaults } = await import("@/lib/crm/defaults");
const { ingestInboundReply } = await import("@/lib/crm/conversations");
const { handleClassificationJob } = await import("@/lib/crm/handlers");
const { generateDraftForStep } = await import("@/lib/crm/drafts");
const { sendDraft } = await import("@/lib/crm/send");
const { applyHumanClassification, createManualDraft } = await import("@/lib/crm/operations");
const { createSequence, publishSequence, assignSubcategorySequence, updateSequence, skipCurrentSequenceStep, snoozeSequence } = await import("@/lib/crm/sequences");
const { runCrmAutoFollowUps, takeOverAutoFollowUp, mailboxHasAutoFollowUpWaiting, queueAutoFollowUpInTransaction } = await import("@/lib/crm/autoFollowUps");
const { setPersonDoNotContactInTransaction } = await import("@/lib/crm/policies");
const { withCrmTransaction } = await import("@/lib/crm/repository");
const {
  crmClassifications,
  crmConversationMessages,
  crmConversations,
  crmDrafts,
  crmJobs,
  crmRecords,
  crmSendAttempts,
  crmSequenceRuns,
  crmSequenceStepRuns,
  crmSequenceSteps,
  crmSubcategories,
} = await import("@/lib/crm/schema");
type CrmSendAdapter = import("@/lib/crm/send").CrmSendAdapter;
type ClassificationCompletion = import("@/lib/crm/ai/types").ClassificationCompletion;
type DraftCompletion = import("@/lib/crm/ai/draft").DraftCompletion;
type CrmChannel = import("@/lib/crm/schema").CrmChannel;

const token = crypto.randomUUID().slice(0, 8);
const MAILBOX_A = `sales-a-${token}@e2e.test`;
const MAILBOX_B = `sales-b-${token}@e2e.test`;
const LINKEDIN_ACCOUNT = `li-account-${token}`;
const WHATSAPP_ACCOUNT = `wa-account-${token}`;
const minutesFromNow = (minutes: number) => new Date(Date.now() + minutes * 60_000);

let passed = 0;
async function check(name: string, fn: () => Promise<void>) {
  await fn();
  passed += 1;
  console.log(`  ✓ ${name}`);
}

// ── Fakes ────────────────────────────────────────────────────────────────
const classifyAs = (categoryKey: string, subcategoryKey: string | null, confidence: number): ClassificationCompletion => async () => ({
  text: JSON.stringify({ categoryKey, subcategoryKey, confidence, reasoning: "fixture", suggestedNextActionAt: null }),
  provider: "openrouter",
  model: "test/classifier",
  request: { fixture: true },
  response: { fixture: true },
});

const draftCompletion: DraftCompletion = async (input) => ({
  text: JSON.stringify({
    subject: input.snapshot.channel === "email" ? "Re: Your question" : null,
    bodyText: `AI draft for step ${String((input.snapshot as { sequenceStep?: { position?: number } }).sequenceStep?.position ?? "?")}`,
    bodyHtml: null,
  }),
  provider: "openrouter",
  model: "test/drafter",
  request: { fixture: true },
  response: { fixture: true },
});

const sentDrafts: { accountRef: string; channel: CrmChannel; body: string }[] = [];
const fakeSend: CrmSendAdapter = async (input) => {
  sentDrafts.push({ accountRef: input.accountRef, channel: input.channel, body: input.bodyText });
  return {
    provider: input.channel === "email" ? "gmail" : "unipile",
    providerMessageId: `provider-${crypto.randomUUID()}`,
    providerThreadId: input.providerThreadId,
    rfcMessageId: input.channel === "email" ? `<${crypto.randomUUID()}@e2e.test>` : null,
    response: { fixture: true },
  };
};

// ── Helpers ──────────────────────────────────────────────────────────────
async function record(id: string) {
  const [row] = await db.select().from(crmRecords).where(eq(crmRecords.id, id)).limit(1);
  assert(row, "record exists");
  return row;
}

async function activeRun(recordId: string) {
  const [run] = await db.select().from(crmSequenceRuns)
    .where(and(eq(crmSequenceRuns.crmRecordId, recordId), eq(crmSequenceRuns.status, "active"))).limit(1);
  return run ?? null;
}

async function stepRuns(runId: string) {
  return db.select({ stepRun: crmSequenceStepRuns, step: crmSequenceSteps })
    .from(crmSequenceStepRuns)
    .innerJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
    .where(eq(crmSequenceStepRuns.sequenceRunId, runId))
    .orderBy(asc(crmSequenceSteps.position));
}

async function draft(id: string) {
  const [row] = await db.select().from(crmDrafts).where(eq(crmDrafts.id, id)).limit(1);
  assert(row, "draft exists");
  return row;
}

async function outboundCount(recordId: string) {
  const { personId } = await record(recordId);
  const messages = await db.select({ id: crmConversationMessages.id }).from(crmConversationMessages)
    .where(and(eq(crmConversationMessages.personId, personId), eq(crmConversationMessages.direction, "outbound")));
  return messages.length;
}

async function newPerson(channel: CrmChannel, label: string) {
  const suffix = crypto.randomUUID().slice(0, 8);
  const [person] = await db.insert(people).values({
    organizationId: (await import("@/lib/tenancy/scope")).currentOrganizationId(),
    email: channel === "email" ? `${label}-${suffix}@lead.test` : null,
    linkedinUrl: channel === "linkedin" ? `https://linkedin.com/in/${label}-${suffix}` : null,
    phone: channel === "whatsapp" ? `+9198${Math.floor(10_000_000 + Math.random() * 89_999_999)}` : null,
    fullName: `${label} fixture`,
    source: "crm-auto-follow-up-e2e",
  }).returning();
  assert(person);
  return person;
}

async function inbound(personId: string, channel: CrmChannel, accountRef: string, thread: string, body: string) {
  const suffix = crypto.randomUUID().slice(0, 8);
  return ingestInboundReply({
    personId,
    channel,
    accountRef,
    providerThreadId: thread,
    providerContactId: channel === "linkedin" ? `contact-${thread}` : null,
    idempotencyKey: `in-${suffix}`,
    providerMessageId: `pm-${suffix}`,
    subject: channel === "email" ? "Question" : null,
    bodyText: body,
    sentAt: new Date(),
  });
}

async function classify(messageId: string, completion: ClassificationCompletion) {
  const [job] = await db.select().from(crmJobs)
    .where(and(eq(crmJobs.kind, "classification"), eq(crmJobs.entityId, messageId))).limit(1);
  assert(job, "classification job queued");
  await handleClassificationJob(job, { complete: completion });
}

async function operatorSend(draftId: string) {
  const current = await draft(draftId);
  return sendDraft({
    draftId,
    revision: current.revision,
    idempotencyKey: `op-${crypto.randomUUID()}`,
    requestId: `op-${crypto.randomUUID()}`,
  }, { send: fakeSend });
}

/** Draft the run's step at `position` (as if it came due) and return the draft. */
async function draftStep(recordId: string, position: number) {
  const run = await activeRun(recordId);
  assert(run, "an active run");
  const step = (await stepRuns(run.id)).find((row) => row.step.position === position);
  assert(step, `step ${position} exists`);
  await db.update(crmSequenceStepRuns).set({ dueAt: new Date(Date.now() - 1_000) }).where(eq(crmSequenceStepRuns.id, step.stepRun.id));
  await generateDraftForStep(step.stepRun.id, { complete: draftCompletion });
  const [row] = await db.select().from(crmDrafts).where(eq(crmDrafts.sequenceStepRunId, step.stepRun.id)).limit(1);
  assert(row, "draft written");
  return row;
}

/** Inbound → AI category → AI reply sent by the rep. Returns the record id. */
async function repliedLead(channel: CrmChannel, accountRef: string, label: string, subcategoryKey: string) {
  const person = await newPerson(channel, label);
  const reply = await inbound(person.id, channel, accountRef, `thread-${label}-${token}`, "Can you tell me more?");
  await classify(reply.message.id, classifyAs("interested", subcategoryKey, 0.95));
  const replyDraft = await draftStep(reply.record.id, 1);
  await operatorSend(replyDraft.id);
  return { person, recordId: reply.record.id, conversationId: reply.conversation.id };
}

// ── Scenario ─────────────────────────────────────────────────────────────
async function main() {
  const { pipelineId } = await ensureCrmDefaults();
  const subcategories = await db.select().from(crmSubcategories).where(eq(crmSubcategories.pipelineId, pipelineId));
  const byKey = (key: string) => {
    const found = subcategories.find((row) => row.key === key);
    assert(found, `seeded subcategory ${key}`);
    return found;
  };
  const demo = byKey("demo_request");          // rank 1
  const info = byKey("information_requested"); // rank 1
  const meetingDone = byKey("meeting_done");   // rank 3
  const notNow = subcategories.find((row) => row.categoryKey === "not_interested" && row.key !== "do_not_contact");
  assert(notNow, "a Not Interested subcategory");

  const steps = [
    { name: "Immediate Reply", delayMinutes: 0, subjectTemplate: null, bodyTemplate: null, aiInstructions: "Answer the question.", knowledgeTags: [] },
    { name: "Follow-up 1", delayMinutes: 60, subjectTemplate: null, bodyTemplate: null, aiInstructions: "Nudge.", knowledgeTags: [] },
    { name: "Follow-up 2", delayMinutes: 120, subjectTemplate: null, bodyTemplate: null, aiInstructions: "Last nudge.", knowledgeTags: [] },
  ];
  const auto = await createSequence({ name: `Auto ${token}`, description: null, steps });
  await publishSequence(auto.id);
  const manual = await createSequence({ name: `Manual ${token}`, description: null, steps });
  await publishSequence(manual.id);
  for (const subcategory of [demo, meetingDone, notNow]) await assignSubcategorySequence(subcategory.id, { sequenceId: auto.id });
  await assignSubcategorySequence(info.id, { sequenceId: manual.id });

  console.log("Switch");
  await check("a new sequence starts with automatic follow-ups off", async () => {
    assert.equal(auto.autoSendFollowUps, false);
  });
  await updateSequence(auto.id, { autoSendFollowUps: true });

  console.log("Classification");
  await check("a low-confidence reading still applies, and the reply is drafted at once", async () => {
    const person = await newPerson("email", "lowconf");
    const reply = await inbound(person.id, "email", MAILBOX_A, `thread-lowconf-${token}`, "Maybe show me a demo?");
    await classify(reply.message.id, classifyAs("interested", demo.key, 0.4));
    const row = await record(reply.record.id);
    assert.equal(row.subcategoryId, demo.id);
    const [classification] = await db.select().from(crmClassifications).where(eq(crmClassifications.messageId, reply.message.id));
    assert.equal(classification?.status, "auto_applied");
    assert(await activeRun(reply.record.id), "the stage's sequence started");
  });
  await check("\"Other\" applies too", async () => {
    const other = subcategories.find((row) => row.categoryKey === "other");
    assert(other);
    const person = await newPerson("email", "other");
    const reply = await inbound(person.id, "email", MAILBOX_A, `thread-other-${token}`, "I'm out of office.");
    await classify(reply.message.id, classifyAs("other", other.key, 0.99));
    assert.equal((await record(reply.record.id)).subcategoryId, other.id);
  });
  await check("a step back inside the funnel keeps the stage and still drafts for it", async () => {
    const lead = await repliedLead("email", MAILBOX_A, "backward", meetingDone.key);
    const before = await record(lead.recordId);
    assert.equal(before.subcategoryId, meetingDone.id);
    const again = await inbound(lead.person.id, "email", MAILBOX_A, `thread-backward-${token}`, "Can you send the deck again?");
    await classify(again.message.id, classifyAs("interested", demo.key, 0.95));
    const after = await record(lead.recordId);
    assert.equal(after.subcategoryId, meetingDone.id, "stays at Meeting Done");
    const run = await activeRun(lead.recordId);
    assert(run, "Meeting Done's sequence restarted for the new reply");
    assert.equal(run.subcategoryId, meetingDone.id);
    assert.equal(run.startStepPosition, 1, "with an immediate reply to draft");
  });
  await check("a move to Not Interested applies", async () => {
    const lead = await repliedLead("email", MAILBOX_A, "notnow", meetingDone.key);
    const again = await inbound(lead.person.id, "email", MAILBOX_A, `thread-notnow-${token}`, "Not interested any more.");
    await classify(again.message.id, classifyAs("not_interested", notNow.key, 0.95));
    assert.equal((await record(lead.recordId)).subcategoryId, notNow.id);
  });

  console.log("Immediate reply starts the follow-ups");
  let aiReplied: Awaited<ReturnType<typeof repliedLead>>;
  await check("the AI's reply, sent by the rep, schedules follow-up 1", async () => {
    aiReplied = await repliedLead("email", MAILBOX_A, "aireply", demo.key);
    const row = await record(aiReplied.recordId);
    assert.equal(row.workflowState, "waiting");
    assert(row.nextActionAt && row.nextActionAt > minutesFromNow(55), "due about an hour later");
  });
  await check("the immediate reply itself is never automatic", async () => {
    const run = await activeRun(aiReplied.recordId);
    const reply = (await stepRuns(run!.id)).find((row) => row.step.position === 1)!;
    const replyDraft = await draft(reply.stepRun.draftId!);
    assert.equal(replyDraft.autoSendAt, null);
  });
  await check("a reply the rep writes themselves also schedules the follow-ups", async () => {
    const person = await newPerson("email", "ownreply");
    const reply = await inbound(person.id, "email", MAILBOX_B, `thread-own-${token}`, "Pricing?");
    await classify(reply.message.id, classifyAs("interested", demo.key, 0.95));
    const own = await createManualDraft({ recordId: reply.record.id, conversationId: reply.conversation.id, subject: "Re: Pricing", bodyText: "Here is our pricing." });
    await operatorSend(own.id);
    const row = await record(reply.record.id);
    assert.equal(row.workflowState, "waiting");
    const run = await activeRun(reply.record.id);
    const followUp = (await stepRuns(run!.id)).find((s) => s.step.position === 2)!;
    assert.equal(followUp.stepRun.status, "scheduled");
  });
  await check("a reply sent while the AI is still classifying starts the follow-ups once it applies", async () => {
    const person = await newPerson("email", "early");
    const reply = await inbound(person.id, "email", MAILBOX_B, `thread-early-${token}`, "Quick question");
    const own = await createManualDraft({ recordId: reply.record.id, conversationId: reply.conversation.id, subject: "Re: Quick question", bodyText: "Answering quickly." });
    await operatorSend(own.id);
    await classify(reply.message.id, classifyAs("interested", demo.key, 0.95));
    const run = await activeRun(reply.record.id);
    assert(run, "a run started");
    assert.equal(run.startStepPosition, 2, "at the first follow-up");
    const row = await record(reply.record.id);
    assert.equal(row.workflowState, "waiting");
    const drafts = await db.select().from(crmDrafts).where(and(eq(crmDrafts.crmRecordId, reply.record.id), eq(crmDrafts.status, "generating")));
    assert.equal(drafts.length, 0, "no second immediate reply");
  });
  await check("changing the category after replying moves to that stage's follow-ups, not a second reply", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "recat", demo.key);
    const before = await record(lead.recordId);
    await applyHumanClassification({ recordId: lead.recordId, categoryKey: "interested", subcategoryId: info.id, expectedContextVersion: before.contextVersion });
    const run = await activeRun(lead.recordId);
    assert(run);
    assert.equal(run.subcategoryId, info.id);
    assert.equal(run.startStepPosition, 2);
    assert.equal((await record(lead.recordId)).workflowState, "waiting");
  });
  await check("a stage marked review required keeps the record queued after the reply, and confirming starts the follow-ups", async () => {
    await db.update(crmSubcategories).set({ reviewRequired: true }).where(eq(crmSubcategories.id, info.id));
    const person = await newPerson("email", "review");
    const reply = await inbound(person.id, "email", MAILBOX_B, `thread-review-${token}`, "Send me info");
    await classify(reply.message.id, classifyAs("interested", info.key, 0.95));
    assert.equal((await record(reply.record.id)).workflowState, "action_required");
    const own = await createManualDraft({ recordId: reply.record.id, conversationId: reply.conversation.id, subject: "Re: info", bodyText: "Here is the info." });
    await operatorSend(own.id);
    assert.equal((await record(reply.record.id)).workflowState, "action_required", "the proposal stays in the queue");
    const before = await record(reply.record.id);
    await applyHumanClassification({ recordId: reply.record.id, categoryKey: "interested", subcategoryId: info.id, expectedContextVersion: before.contextVersion });
    const run = await activeRun(reply.record.id);
    assert.equal(run?.startStepPosition, 2);
    assert.equal((await record(reply.record.id)).workflowState, "waiting");
    await db.update(crmSubcategories).set({ reviewRequired: false }).where(eq(crmSubcategories.id, info.id));
  });

  console.log("Automatic sending");
  let followUp1: Awaited<ReturnType<typeof draftStep>>;
  await check("a follow-up of an automatic sequence skips Action required and waits for the sender", async () => {
    followUp1 = await draftStep(aiReplied.recordId, 2);
    assert.equal(followUp1.status, "awaiting_review");
    assert(followUp1.autoSendAt, "has a send time");
    const row = await record(aiReplied.recordId);
    assert.equal(row.workflowState, "waiting");
    assert.equal(row.nextActionAt, null);
  });
  await check("a follow-up of a manual sequence still goes to Action required", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "manualseq", info.key);
    const followUp = await draftStep(lead.recordId, 2);
    assert.equal(followUp.autoSendAt, null);
    assert.equal((await record(lead.recordId)).workflowState, "action_required");
  });
  await check("the email scheduler yields the mailbox's turn to it", async () => {
    assert.equal(await mailboxHasAutoFollowUpWaiting(MAILBOX_A, new Date()), true);
  });
  await check("PAUSE_CRM_AUTOSEND holds everything", async () => {
    process.env.PAUSE_CRM_AUTOSEND = "true";
    const summary = await runCrmAutoFollowUps({ send: fakeSend });
    delete process.env.PAUSE_CRM_AUTOSEND;
    assert.equal(summary.sent, 0);
    assert.equal((await draft(followUp1.id)).status, "awaiting_review");
  });
  await check("the channel's own pause (PAUSE_EMAIL_OUTBOUND) holds email follow-ups", async () => {
    process.env.PAUSE_EMAIL_OUTBOUND = "true";
    const summary = await runCrmAutoFollowUps({ send: fakeSend });
    process.env.PAUSE_EMAIL_OUTBOUND = "false";
    assert.equal(summary.sent, 0);
    assert.equal(summary.accountsWaiting, 1);
    assert.equal((await draft(followUp1.id)).status, "awaiting_review");
  });
  await check("the sender sends it as the system, counts it on the mailbox and schedules follow-up 2", async () => {
    const sentBefore = sentDrafts.length;
    const summary = await runCrmAutoFollowUps({ send: fakeSend });
    assert.equal(summary.sent, 1, JSON.stringify(summary));
    assert.equal(sentDrafts.length - sentBefore, 1);
    assert.equal(sentDrafts.at(-1)?.accountRef, MAILBOX_A);
    assert.equal((await draft(followUp1.id)).status, "sent");
    const [attempt] = await db.select().from(crmSendAttempts).where(eq(crmSendAttempts.draftId, followUp1.id));
    assert.equal(attempt?.actorType, "system");
    const [mailbox] = await db.select().from(mailboxes).where(eq(mailboxes.emailAddress, MAILBOX_A));
    assert.equal(mailbox?.todayEmailsSent, 1);
    assert(mailbox?.nextEmailTime && mailbox.nextEmailTime > new Date(), "the mailbox's next turn moved on");
    const row = await record(aiReplied.recordId);
    assert.equal(row.workflowState, "waiting");
    assert(row.nextActionAt && row.nextActionAt > minutesFromNow(115), "follow-up 2 due about two hours later");
    assert.equal(await mailboxHasAutoFollowUpWaiting(MAILBOX_A, new Date()), false, "nothing left to yield to");
  });

  console.log("Pacing");
  await check("one follow-up per account per run, and none from an account inside its 30-minute gap", async () => {
    // Mailbox A sent a follow-up moments ago; B has not.
    const a1 = await repliedLead("email", MAILBOX_A, "pace-a1", demo.key);
    const a2 = await repliedLead("email", MAILBOX_A, "pace-a2", demo.key);
    const b1 = await repliedLead("email", MAILBOX_B, "pace-b1", demo.key);
    const b2 = await repliedLead("email", MAILBOX_B, "pace-b2", demo.key);
    const drafts = {
      a1: await draftStep(a1.recordId, 2),
      a2: await draftStep(a2.recordId, 2),
      b1: await draftStep(b1.recordId, 2),
      b2: await draftStep(b2.recordId, 2),
    };
    const sentBefore = sentDrafts.length;
    const first = await runCrmAutoFollowUps({ send: fakeSend });
    assert.equal(first.sent, 1, `first run: ${JSON.stringify(first)}`);
    assert.equal(sentDrafts.at(-1)?.accountRef, MAILBOX_B, "only B was free");
    assert.equal((await draft(drafts.b1.id)).status, "sent", "B's oldest went first");
    assert.equal((await draft(drafts.b2.id)).status, "awaiting_review");

    const again = await runCrmAutoFollowUps({ send: fakeSend });
    assert.equal(again.sent, 0, "both mailboxes are inside their gap now");

    // 31 minutes later both gaps (and both mailboxes' 18–24 min send gaps) have passed.
    const later = await runCrmAutoFollowUps({ send: fakeSend, now: minutesFromNow(31) });
    assert.equal(later.sent, 2, `later run: ${JSON.stringify(later)}`);
    assert.equal((await draft(drafts.a1.id)).status, "sent");
    assert.equal((await draft(drafts.a2.id)).status, "awaiting_review", "still one per account");
    assert.equal((await draft(drafts.b2.id)).status, "sent");
    assert.equal(sentDrafts.length - sentBefore, 3);
    // Leave A's last one for the next checks.
    await takeOverAutoFollowUp({ draftId: drafts.a2.id });
  });
  await check("a mailbox at its daily limit sends no follow-up", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "limit", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    await db.update(mailboxes).set({ todayEmailsSent: 30 }).where(eq(mailboxes.emailAddress, MAILBOX_B));
    const summary = await runCrmAutoFollowUps({ send: fakeSend, now: minutesFromNow(70) });
    assert.equal((await draft(followUp.id)).status, "awaiting_review", JSON.stringify(summary));
    await db.update(mailboxes).set({ todayEmailsSent: 0 }).where(eq(mailboxes.emailAddress, MAILBOX_B));
    await takeOverAutoFollowUp({ draftId: followUp.id });
  });
  await check("a mailbox outside its working hours sends no follow-up", async () => {
    const lead = await repliedLead("email", MAILBOX_A, "hours", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    const closed = { timezone: "UTC", days: Object.fromEntries(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((day) => [day, { enabled: false, from: "09:00", to: "18:00" }])) };
    await db.update(mailboxes).set({ workingHours: closed as never }).where(eq(mailboxes.emailAddress, MAILBOX_A));
    await runCrmAutoFollowUps({ send: fakeSend, now: minutesFromNow(100) });
    assert.equal((await draft(followUp.id)).status, "awaiting_review");
    await db.update(mailboxes).set({ workingHours: ALWAYS as never }).where(eq(mailboxes.emailAddress, MAILBOX_A));
    await takeOverAutoFollowUp({ draftId: followUp.id });
  });

  console.log("LinkedIn and WhatsApp");
  await check("LinkedIn and WhatsApp follow-ups go out from their own accounts", async () => {
    const li = await repliedLead("linkedin", LINKEDIN_ACCOUNT, "li", demo.key);
    const wa = await repliedLead("whatsapp", WHATSAPP_ACCOUNT, "wa", demo.key);
    const liDraft = await draftStep(li.recordId, 2);
    const waDraft = await draftStep(wa.recordId, 2);
    const summary = await runCrmAutoFollowUps({ send: fakeSend });
    assert.equal((await draft(liDraft.id)).status, "sent", JSON.stringify(summary));
    assert.equal((await draft(waDraft.id)).status, "sent", JSON.stringify(summary));
    const channels = sentDrafts.slice(-2).map((row) => row.channel).sort();
    assert.deepEqual(channels, ["linkedin", "whatsapp"]);
  });

  console.log("Stopping");
  await check("a new reply from the lead retires the waiting follow-up before it can go", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "stop", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    await inbound(lead.person.id, "email", MAILBOX_B, `thread-stop-${token}`, "Actually, one more question");
    assert.equal((await draft(followUp.id)).status, "stale");
    const outboundBefore = await outboundCount(lead.recordId);
    await runCrmAutoFollowUps({ send: fakeSend, now: minutesFromNow(130) });
    assert.equal(await outboundCount(lead.recordId), outboundBefore);
  });
  await check("\"Review before sending\" puts it in Action required", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "takeover", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    assert.equal(await takeOverAutoFollowUp({ draftId: followUp.id }), true);
    assert.equal((await draft(followUp.id)).autoSendAt, null);
    assert.equal((await record(lead.recordId)).workflowState, "action_required");
    await runCrmAutoFollowUps({ send: fakeSend, now: minutesFromNow(160) });
    assert.equal((await draft(followUp.id)).status, "awaiting_review", "the sender leaves it alone");
  });
  await check("Do Not Contact retires the waiting follow-up; nothing is sent", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "dnc", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    await withCrmTransaction((tx) => setPersonDoNotContactInTransaction(tx, {
      personId: lead.person.id, reason: "fixture", source: "human", actorType: "authenticated_operator",
    }));
    const sentBefore = sentDrafts.length;
    await runCrmAutoFollowUps({ send: fakeSend, now: minutesFromNow(190) });
    assert.equal(sentDrafts.length, sentBefore, "nothing reached the provider");
    assert.equal((await draft(followUp.id)).status, "stale");
  });
  await check("a send refused before anything goes out hands the draft to a person", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "refused", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    await db.update(crmConversations).set({ status: "closed" }).where(eq(crmConversations.id, lead.conversationId));
    const sentBefore = sentDrafts.length;
    await runCrmAutoFollowUps({ send: fakeSend, now: minutesFromNow(220) });
    assert.equal(sentDrafts.length, sentBefore, "nothing reached the provider");
    const after = await draft(followUp.id);
    assert.equal(after.status, "awaiting_review");
    assert.equal(after.autoSendAt, null, "handed to a person");
    assert.equal((await record(lead.recordId)).workflowState, "action_required");
  });
  await check("a follow-up that could not go out in 48 hours goes to a person", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "old", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    await db.update(crmDrafts).set({ autoSendAt: new Date(Date.now() - 49 * 3_600_000) }).where(eq(crmDrafts.id, followUp.id));
    const summary = await runCrmAutoFollowUps({ send: fakeSend });
    assert(summary.handedToRep >= 1);
    assert.equal((await draft(followUp.id)).autoSendAt, null);
    assert.equal((await record(lead.recordId)).workflowState, "action_required");
  });
  await check("turning the switch off moves waiting follow-ups to Action required", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "off", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    assert(followUp.autoSendAt);
    await updateSequence(auto.id, { autoSendFollowUps: false });
    assert.equal((await draft(followUp.id)).autoSendAt, null);
    assert.equal((await record(lead.recordId)).workflowState, "action_required");
    await updateSequence(auto.id, { autoSendFollowUps: true });
  });

  console.log("Drafts written before the switch went on");
  await check("a follow-up drafted while the switch was off can be queued later, and then sends", async () => {
    await updateSequence(auto.id, { autoSendFollowUps: false });
    const lead = await repliedLead("email", MAILBOX_B, "backlog", demo.key);
    const followUp = await draftStep(lead.recordId, 2);
    assert.equal(followUp.autoSendAt, null);
    assert.equal((await record(lead.recordId)).workflowState, "action_required");
    await updateSequence(auto.id, { autoSendFollowUps: true });
    const queued = await withCrmTransaction((tx) => queueAutoFollowUpInTransaction(tx, {
      draftId: followUp.id, at: new Date(), actorType: "system", reason: "e2e",
    }));
    assert.equal(queued, true);
    assert.equal((await record(lead.recordId)).workflowState, "waiting");
    const again = await withCrmTransaction((tx) => queueAutoFollowUpInTransaction(tx, {
      draftId: followUp.id, at: new Date(), actorType: "system", reason: "e2e",
    }));
    assert.equal(again, false, "queueing twice is a no-op");
    await runCrmAutoFollowUps({ send: fakeSend, now: minutesFromNow(400) });
    assert.equal((await draft(followUp.id)).status, "sent");
  });
  await check("a follow-up whose reply was skipped, never answered from the CRM, is not queued", async () => {
    await updateSequence(auto.id, { autoSendFollowUps: false });
    const person = await newPerson("email", "skipped");
    const reply = await inbound(person.id, "email", MAILBOX_B, `thread-skipped-${token}`, "Hello?");
    await classify(reply.message.id, classifyAs("interested", demo.key, 0.95));
    await draftStep(reply.record.id, 1);
    await skipCurrentSequenceStep({ recordId: reply.record.id });
    const followUp = await draftStep(reply.record.id, 2);
    await updateSequence(auto.id, { autoSendFollowUps: true });
    const queued = await withCrmTransaction((tx) => queueAutoFollowUpInTransaction(tx, {
      draftId: followUp.id, at: new Date(), actorType: "system", reason: "e2e",
    }));
    assert.equal(queued, false);
    assert.equal((await draft(followUp.id)).autoSendAt, null);
  });

  console.log("Skip and snooze keep later steps draftable");
  await check("after a skipped step and a send, the step after is still drafted", async () => {
    // The live bug: skip refreshed only the next step's context version, so the
    // step after it could never be drafted once the next one was sent.
    const person = await newPerson("email", "skipsend");
    const reply = await inbound(person.id, "email", MAILBOX_B, `thread-skipsend-${token}`, "Info please");
    await classify(reply.message.id, classifyAs("interested", info.key, 0.95));
    await draftStep(reply.record.id, 1);
    await skipCurrentSequenceStep({ recordId: reply.record.id });
    const second = await draftStep(reply.record.id, 2);
    await operatorSend(second.id);
    const third = await draftStep(reply.record.id, 3);
    assert.equal(third.status, "awaiting_review");
  });
  await check("after a snooze and a send, the step after is still drafted", async () => {
    const lead = await repliedLead("email", MAILBOX_B, "snoozesend", info.key);
    await snoozeSequence({ recordId: lead.recordId, until: minutesFromNow(5) });
    const second = await draftStep(lead.recordId, 2);
    await operatorSend(second.id);
    const third = await draftStep(lead.recordId, 3);
    assert.equal(third.status, "awaiting_review");
  });

  console.log(`\n${passed} checks passed. Fake provider received ${sentDrafts.length} sends; nothing left this machine.`);
}

const ALWAYS = {
  timezone: "UTC",
  days: Object.fromEntries(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((day) => [day, { enabled: true, from: "00:00", to: "23:59" }])),
};

// ── Fixture organization ─────────────────────────────────────────────────
// The sender visits every organization; an earlier run's leftovers would make
// it switch organization from inside this one's scope, which it (rightly)
// refuses. In production it runs outside any scope.
await db.update(crmDrafts).set({ autoSendAt: null });
// .env.development.local keeps every outbound switch paused for local work;
// the fake sender is the only provider here, so lift them for this run.
for (const name of ["PAUSE_EMAIL_OUTBOUND", "PAUSE_LINKEDIN_OUTBOUND", "PAUSE_WHATSAPP_OUTBOUND", "PAUSE_CRM_AUTOSEND", "PEOPLE_MIGRATION_MODE"]) {
  process.env[name] = "false";
}
const [org] = await db.insert(organizations).values({ name: `Auto follow-up e2e ${token}`, slug: `auto-follow-up-e2e-${token}` }).returning();
assert(org);
await runInOrganization(org.id, async () => {
  for (const [key, credentials] of [
    ["google", { serviceAccountJson: "{}", adminEmail: "admin@e2e.test" }],
    ["unipile", { apiKey: "fixture", dsn: "https://fixture.e2e.test" }],
  ] as const) {
    const [provider] = await db.insert(gridProviders).values({
      organizationId: org.id, key: `platform-${key}`, name: key, enabled: true,
    }).returning();
    await db.insert(gridProviderCredentials).values({ providerId: provider!.id, encryptedPayload: encryptIntegrationCredentials(credentials) });
  }
  for (const emailAddress of [MAILBOX_A, MAILBOX_B]) {
    await db.insert(mailboxes).values({ organizationId: org.id, emailAddress, status: "connected", dailySendLimit: 30, workingHours: ALWAYS as never });
  }
  await db.insert(linkedInAccounts).values({ organizationId: org.id, linkedinId: LINKEDIN_ACCOUNT, username: "fixture-rep", status: "CONNECTED" });
  await db.insert(whatsappAccounts).values({ organizationId: org.id, unipileAccountId: WHATSAPP_ACCOUNT, status: "connected", connectedAt: new Date(Date.now() - 7 * 86_400_000) });
  await main();
}).then(() => process.exit(0), (error) => {
  console.error(error);
  process.exit(1);
});
