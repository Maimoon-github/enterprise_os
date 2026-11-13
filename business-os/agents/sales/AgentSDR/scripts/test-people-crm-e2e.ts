// Runs in ORGANIZATION_ID, or the initial organization when it is unset.
import assert from "node:assert/strict";
import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { people } from "@/lib/leads/schema";
import { createSubcategory } from "@/lib/crm/categories";
import { ingestInboundReply } from "@/lib/crm/conversations";
import { generateDraftForStep, updateDraft } from "@/lib/crm/drafts";
import { handleClassificationJob } from "@/lib/crm/handlers";
import { createSequence, publishSequence, assignSubcategorySequence, enqueueDueFollowupJobs } from "@/lib/crm/sequences";
import { reconcileDeliveryUncertain, sendDraft, type CrmSendAdapter } from "@/lib/crm/send";
import { applyHumanClassification, createManualDraft } from "@/lib/crm/operations";
import {
  crmClassifications,
  crmConversationMessages,
  crmDrafts,
  crmJobs,
  crmPersonContactPolicies,
  crmRecords,
  crmSendAttempts,
  crmSequenceRuns,
  crmSequenceStepRuns,
  crmSequenceSteps,
} from "@/lib/crm/schema";
import type { ClassificationCompletion } from "@/lib/crm/ai/types";
import type { DraftCompletion } from "@/lib/crm/ai/draft";
import { quarantineCrmIdentity, resolveCrmIdentityException } from "@/lib/crm/identity";
import { currentOrganizationId } from "@/lib/tenancy/scope";
import { runScriptInOrganization } from "./lib/organization";

const PIPELINE_ID = "00000000-0000-0000-0000-000000000001";

const classifyInterested = (subcategoryKey: string): ClassificationCompletion => async () => ({
  text: JSON.stringify({
    categoryKey: "interested",
    subcategoryKey,
    confidence: 0.97,
    reasoning: "The Person explicitly asked for a demo.",
    suggestedNextActionAt: null,
  }),
  provider: "openrouter",
  model: "test/classifier",
  request: { fixture: true },
  response: { fixture: true },
});

const draftCompletion: DraftCompletion = async (input) => ({
  text: JSON.stringify({
    subject: input.snapshot.channel === "email" ? "Re: Your demo request" : null,
    bodyText: "Thanks for reaching out. I would be happy to arrange a demo.",
    bodyHtml: input.snapshot.channel === "email" ? "<p>Thanks for reaching out. I would be happy to arrange a demo.</p>" : null,
  }),
  provider: "openrouter",
  model: "test/drafter",
  request: { fixture: true },
  response: { fixture: true },
});

const sendAdapter: CrmSendAdapter = async (input) => ({
  provider: input.channel === "email" ? "gmail" : "unipile",
  providerMessageId: `provider-${crypto.randomUUID()}`,
  providerThreadId: input.providerThreadId,
  rfcMessageId: input.channel === "email" ? `<${crypto.randomUUID()}@example.test>` : null,
  response: { accepted: true, fixture: true },
});

async function classificationJobFor(messageId: string) {
  const [job] = await db.select().from(crmJobs)
    .where(and(eq(crmJobs.kind, "classification"), eq(crmJobs.entityId, messageId))).limit(1);
  assert(job, "classification job must be durable before AI work starts");
  return job;
}

async function runChannel(channel: "email" | "linkedin", sequenceId: string, subcategoryId: string, subcategoryKey: string) {
  const suffix = crypto.randomUUID().slice(0, 8);
  const [person] = await db.insert(people).values({
    organizationId: currentOrganizationId(),
    email: channel === "email" ? `crm-${suffix}@example.test` : null,
    linkedinUrl: channel === "linkedin" ? `crm-${suffix}` : null,
    fullName: `${channel} CRM fixture`,
    source: "crm-e2e-fixture",
  }).returning();
  assert(person);
  const inbound = await ingestInboundReply({
    personId: person.id,
    channel,
    accountRef: channel === "email" ? "sales@example.test" : "linkedin-account-fixture",
    providerThreadId: `${channel}-thread-${suffix}`,
    providerContactId: channel === "linkedin" ? `linkedin-contact-${suffix}` : null,
    idempotencyKey: `${channel}-inbound-${suffix}`,
    providerMessageId: `${channel}-provider-${suffix}`,
    subject: channel === "email" ? "Demo request" : null,
    bodyText: "Can we arrange a product demo next Tuesday?",
    sentAt: new Date(),
  });
  const duplicate = await ingestInboundReply({
    personId: person.id,
    channel,
    accountRef: channel === "email" ? "sales@example.test" : "linkedin-account-fixture",
    providerThreadId: `${channel}-thread-${suffix}`,
    providerContactId: channel === "linkedin" ? `linkedin-contact-${suffix}` : null,
    idempotencyKey: `${channel}-inbound-${suffix}`,
    providerMessageId: `${channel}-provider-${suffix}`,
    subject: channel === "email" ? "Demo request" : null,
    bodyText: "Can we arrange a product demo next Tuesday?",
    sentAt: new Date(),
  });
  assert.equal(duplicate.duplicate, true);
  assert.equal(duplicate.record.id, inbound.record.id);

  await handleClassificationJob(await classificationJobFor(inbound.message.id), { complete: classifyInterested(subcategoryKey) });
  const [classified] = await db.select().from(crmRecords).where(eq(crmRecords.id, inbound.record.id)).limit(1);
  assert.equal(classified?.categoryKey, "interested");
  assert.equal(classified?.subcategoryId, subcategoryId);

  const [run] = await db.select().from(crmSequenceRuns)
    .where(and(eq(crmSequenceRuns.crmRecordId, inbound.record.id), eq(crmSequenceRuns.status, "active"))).limit(1);
  assert(run);
  assert.equal(run.sequenceId, sequenceId);
  const stepRuns = await db.select({ stepRun: crmSequenceStepRuns, step: crmSequenceSteps })
    .from(crmSequenceStepRuns).innerJoin(crmSequenceSteps, eq(crmSequenceSteps.id, crmSequenceStepRuns.sequenceStepId))
    .where(eq(crmSequenceStepRuns.sequenceRunId, run.id)).orderBy(asc(crmSequenceSteps.position));
  assert(stepRuns.length >= 1);
  await generateDraftForStep(stepRuns[0]!.stepRun.id, { complete: draftCompletion });
  const [draft] = await db.select().from(crmDrafts).where(eq(crmDrafts.sequenceStepRunId, stepRuns[0]!.stepRun.id)).limit(1);
  assert.equal(draft?.status, "awaiting_review");
  const edited = await updateDraft({
    draftId: draft!.id,
    revision: draft!.revision,
    subject: draft!.subject,
    bodyText: `${draft!.aiBodyText}\n\nEdited by a human.`,
  });
  const attempt = await sendDraft({
    draftId: edited.id,
    revision: edited.revision,
    idempotencyKey: `crm-e2e-send-${channel}-${suffix}`,
    requestId: `request-${suffix}`,
  }, { send: sendAdapter });
  assert.equal(attempt.status, "sent");
  const [afterSend] = await db.select().from(crmRecords).where(eq(crmRecords.id, inbound.record.id)).limit(1);
  const outbound = await db.select().from(crmConversationMessages).where(and(
    eq(crmConversationMessages.conversationId, inbound.conversation.id),
    eq(crmConversationMessages.direction, "outbound"),
  ));
  assert.equal(outbound.length, 1);
  assert.equal(outbound[0]!.bodyText.endsWith("Edited by a human."), true);
  assert.equal(afterSend?.workflowState, stepRuns.length > 1 ? "waiting" : "idle");

  const replay = await sendDraft({
    draftId: edited.id,
    revision: edited.revision,
    idempotencyKey: `crm-e2e-send-${channel}-${suffix}`,
    requestId: `request-replay-${suffix}`,
  }, { send: async () => { throw new Error("idempotent replay must not call provider"); } });
  assert.equal(replay.status, "sent");
  return { person, inbound, run, stepRuns };
}

async function verifyClassificationRetry(subcategoryKey: string) {
  const suffix = crypto.randomUUID().slice(0, 8);
  const [person] = await db.insert(people).values({ organizationId: currentOrganizationId(), email: `retry-${suffix}@example.test`, fullName: "Retry fixture", source: "crm-e2e-fixture" }).returning();
  const inbound = await ingestInboundReply({
    personId: person!.id,
    channel: "email",
    accountRef: "sales@example.test",
    providerThreadId: `retry-thread-${suffix}`,
    idempotencyKey: `retry-inbound-${suffix}`,
    providerMessageId: `retry-provider-${suffix}`,
    bodyText: "Could I see a demo?",
    sentAt: new Date(),
  });
  const job = await classificationJobFor(inbound.message.id);
  await assert.rejects(() => handleClassificationJob(job, { complete: async () => { throw new Error("simulated AI outage"); } }), /simulated AI outage/);
  const [failed] = await db.select().from(crmClassifications).where(eq(crmClassifications.messageId, inbound.message.id)).limit(1);
  assert.equal(failed?.status, "failed");
  await handleClassificationJob(job, { complete: classifyInterested(subcategoryKey) });
  const retried = await db.select().from(crmClassifications).where(eq(crmClassifications.messageId, inbound.message.id));
  assert.equal(retried.length, 1, "retry must update the failed classification rather than duplicate it");
  assert.equal(retried[0]?.status, "auto_applied");
}

async function verifyDirectHumanClassification(subcategoryId: string) {
  const suffix = crypto.randomUUID().slice(0, 8);
  const [person] = await db.insert(people).values({ organizationId: currentOrganizationId(), email: `human-${suffix}@example.test`, fullName: "Human classification fixture", source: "crm-e2e-fixture" }).returning();
  const inbound = await ingestInboundReply({
    personId: person!.id,
    channel: "email",
    accountRef: "sales@example.test",
    providerThreadId: `human-thread-${suffix}`,
    idempotencyKey: `human-inbound-${suffix}`,
    providerMessageId: `human-provider-${suffix}`,
    bodyText: "Please arrange a demo.",
    sentAt: new Date(),
  });
  const result = await applyHumanClassification({
    recordId: inbound.record.id,
    categoryKey: "interested",
    subcategoryId,
    expectedContextVersion: inbound.record.contextVersion,
    reason: "Verified manually",
  });
  assert(result.sequenceRun, "manual classification should start the assigned sequence");
  const [draftJob] = await db.select().from(crmJobs).where(and(
    eq(crmJobs.kind, "initial_draft"),
    eq(crmJobs.entityId, (await db.select({ id: crmClassifications.id }).from(crmClassifications)
      .where(eq(crmClassifications.messageId, inbound.message.id)).limit(1))[0]!.id),
  )).limit(1);
  assert(draftJob, "manual classification must enqueue an initial draft with a real classification identity");
}

async function main() {
  const runToken = crypto.randomUUID().slice(0, 8);
  const subcategory = await createSubcategory({
    pipelineId: PIPELINE_ID,
    categoryKey: "interested",
    name: `Demo requested ${runToken}`,
    description: "The Person asks for a demonstration.",
    classificationGuidance: "Use when the Person explicitly asks to see the product.",
    reviewRequired: false,
    sortOrder: 0,
  });
  const sequence = await createSequence({
    name: `Demo conversion ${runToken}`,
    description: "Immediate response and one human-reviewed follow-up.",
    steps: [
      { name: "Immediate Reply", delayMinutes: 0, subjectTemplate: "Re: {{subject}}", bodyTemplate: "Thanks {{first_name}}", aiInstructions: "Offer a demo time.", knowledgeTags: ["scheduling"] },
      { name: "Follow-up 1", delayMinutes: 60, subjectTemplate: "Re: {{subject}}", bodyTemplate: "Following up", aiInstructions: "Briefly follow up without pressure.", knowledgeTags: ["scheduling"] },
    ],
  });
  await publishSequence(sequence.id);
  await assignSubcategorySequence(subcategory.id, { sequenceId: sequence.id });

  const emailFlow = await runChannel("email", sequence.id, subcategory.id, subcategory.key);
  const linkedinFlow = await runChannel("linkedin", sequence.id, subcategory.id, subcategory.key);

  const uncertainDraft = await createManualDraft({
    recordId: linkedinFlow.inbound.record.id,
    conversationId: linkedinFlow.inbound.conversation.id,
    bodyText: "A human-authored LinkedIn reply.",
  });
  let uncertainProviderCalls = 0;
  await assert.rejects(() => sendDraft({
    draftId: uncertainDraft.id,
    revision: uncertainDraft.revision,
    idempotencyKey: `crm-e2e-uncertain-${runToken}`,
    requestId: `uncertain-${runToken}`,
  }, { send: async () => { uncertainProviderCalls += 1; throw new Error("simulated network timeout after submission"); } }), /simulated network timeout/);
  const [uncertainAttempt] = await db.select().from(crmSendAttempts)
    .where(eq(crmSendAttempts.idempotencyKey, `crm-e2e-uncertain-${runToken}`)).limit(1);
  assert.equal(uncertainAttempt?.status, "delivery_uncertain");
  await assert.rejects(() => sendDraft({
    draftId: uncertainDraft.id,
    revision: uncertainDraft.revision,
    idempotencyKey: `crm-e2e-uncertain-${runToken}`,
    requestId: `uncertain-retry-${runToken}`,
  }, { send: async () => { uncertainProviderCalls += 1; return sendAdapter({} as never); } }), /reconcile it before retrying/);
  assert.equal(uncertainProviderCalls, 1, "uncertain delivery must never auto-retry");
  const reconciled = await reconcileDeliveryUncertain({
    attemptId: uncertainAttempt!.id,
    delivered: true,
    providerMessageId: `provider-reconciled-${runToken}`,
    note: "Confirmed in the provider delivery log",
  });
  assert.equal(reconciled.status, "reconciled");
  const [reconciledDraft] = await db.select().from(crmDrafts).where(eq(crmDrafts.id, uncertainDraft.id)).limit(1);
  assert.equal(reconciledDraft?.status, "sent");

  await verifyClassificationRetry(subcategory.key);
  await verifyDirectHumanClassification(subcategory.id);
  const quarantined = await quarantineCrmIdentity({
    channel: "linkedin",
    accountRef: "linkedin-account-fixture",
    sourceEventKey: `identity-exception-${runToken}`,
    identityValue: `unknown-${runToken}`,
    reason: "No unambiguous canonical Person",
    payload: {
      providerId: `unknown-${runToken}`,
      chatId: `identity-thread-${runToken}`,
      messageText: "Please send me the details.",
      linkedinMessageId: `identity-message-${runToken}`,
      sentAt: new Date().toISOString(),
    },
  });
  const resolved = await resolveCrmIdentityException({ id: quarantined.id, status: "resolved", personId: linkedinFlow.person.id });
  assert.equal(resolved.status, "resolved");
  assert.equal(resolved.resolvedPersonId, linkedinFlow.person.id);
  const [replayedIdentityMessage] = await db.select().from(crmConversationMessages)
    .where(eq(crmConversationMessages.idempotencyKey, `identity-exception-${runToken}`)).limit(1);
  assert(replayedIdentityMessage, "resolving an identity exception must replay its inbound message into CRM");

  const followup = emailFlow.stepRuns[1];
  assert(followup, "Email fixture must materialize its follow-up step");
  await db.update(crmSequenceStepRuns).set({ dueAt: new Date(Date.now() - 1_000) })
    .where(eq(crmSequenceStepRuns.id, followup.stepRun.id));
  assert.equal(await enqueueDueFollowupJobs(), 1);
  const [dueJob] = await db.select().from(crmJobs)
    .where(and(eq(crmJobs.kind, "due_followup_draft"), eq(crmJobs.entityId, followup.stepRun.id))).limit(1);
  assert(dueJob, "due follow-up must be durably queued");
  await generateDraftForStep(followup.stepRun.id, { complete: draftCompletion });
  const [followupDraft] = await db.select().from(crmDrafts)
    .where(eq(crmDrafts.sequenceStepRunId, followup.stepRun.id)).limit(1);
  assert.equal(followupDraft?.status, "awaiting_review");
  const outboundBeforeReply = await db.select().from(crmConversationMessages).where(and(
    eq(crmConversationMessages.conversationId, emailFlow.inbound.conversation.id),
    eq(crmConversationMessages.direction, "outbound"),
  ));
  assert.equal(outboundBeforeReply.length, 1, "due follow-up preparation must never send");

  const dncSuffix = crypto.randomUUID().slice(0, 8);
  const dncInbound = await ingestInboundReply({
    personId: emailFlow.person.id,
    channel: "email",
    accountRef: "sales@example.test",
    providerThreadId: `email-thread-dnc-${dncSuffix}`,
    idempotencyKey: `email-dnc-${dncSuffix}`,
    providerMessageId: `provider-dnc-${dncSuffix}`,
    subject: "Re: Demo",
    bodyText: "Please unsubscribe me and do not contact me again.",
    sentAt: new Date(),
  });
  const [interruptedRun] = await db.select().from(crmSequenceRuns).where(eq(crmSequenceRuns.id, emailFlow.run.id)).limit(1);
  const [staleFollowup] = await db.select().from(crmDrafts).where(eq(crmDrafts.id, followupDraft!.id)).limit(1);
  assert.equal(interruptedRun?.status, "interrupted");
  assert.equal(staleFollowup?.status, "stale");
  let staleProviderCalled = false;
  await assert.rejects(() => sendDraft({
    draftId: staleFollowup!.id,
    revision: staleFollowup!.revision,
    idempotencyKey: `crm-e2e-stale-${runToken}`,
    requestId: `stale-${runToken}`,
  }, { send: async () => { staleProviderCalled = true; return sendAdapter({} as never); } }), /Cannot send a stale draft/);
  assert.equal(staleProviderCalled, false);
  await handleClassificationJob(await classificationJobFor(dncInbound.message.id), { complete: classifyInterested(subcategory.key) });
  const [dncRecord] = await db.select().from(crmRecords).where(eq(crmRecords.id, dncInbound.record.id)).limit(1);
  const [policy] = await db.select().from(crmPersonContactPolicies).where(eq(crmPersonContactPolicies.personId, emailFlow.person.id)).limit(1);
  assert.equal(dncRecord?.categoryKey, "not_interested");
  assert.equal(dncRecord?.workflowState, "action_required");
  assert.equal(policy?.doNotContact, true);
  assert.equal((await db.select().from(crmSequenceRuns).where(and(eq(crmSequenceRuns.crmRecordId, dncRecord!.id), eq(crmSequenceRuns.status, "active")))).length, 0);

  const attempts = await db.select().from(crmSendAttempts);
  assert.equal(attempts.every((attempt) => attempt.actorType === "authenticated_operator"), true);
  console.log(JSON.stringify({
    ok: true,
    emailRecordId: emailFlow.inbound.record.id,
    testedChannels: ["email", "linkedin"],
    duplicateInbound: true,
    idempotentSend: true,
    globalDnc: true,
  }));
}

runScriptInOrganization(main)
  .catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
