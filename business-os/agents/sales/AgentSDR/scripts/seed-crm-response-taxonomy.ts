/**
 * Seed the CRM reply taxonomy: subcategories, their default sequences
 * (immediate reply + timed follow-ups), and the subcategory → sequence
 * assignments.
 *
 * Run with: bun --conditions=react-server scripts/seed-crm-response-taxonomy.ts [--apply]
 *
 * Source of the sequence content: Dynamic_Storefront_CRM_Sequence_Library_Working_v2.xlsx.
 * Upserts by name (legacyNames cover renames), diffs the draft and published
 * steps, and only updates/publishes/assigns when something changed.
 * `delayMinutes` on a follow-up counts from when the previous step was SENT.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset
 * (bun run --conditions=react-server).
 */
import { runScriptInOrganization } from "./lib/organization";
import { asc, eq } from "drizzle-orm";
import {
  createSubcategory,
  listCategoryConfiguration,
  updateSubcategory,
} from "../src/lib/crm/categories";
import {
  assignSubcategorySequence,
  createSequence,
  getSequence,
  listSequences,
  publishSequence,
  updateSequence,
} from "../src/lib/crm/sequences";
import { db } from "../src/lib/db";
import { crmSequenceSteps, type CrmCategoryKey } from "../src/lib/crm/schema";

type ImmediateStep = {
  name: string;
  instructions: string;
};

type FollowUpStep = {
  /** Minutes after the previous step was sent. */
  delayMinutes: number;
  instructions: string;
};

type TaxonomyEntry = {
  categoryKey: CrmCategoryKey;
  name: string;
  legacyNames?: string[];
  description: string;
  classificationGuidance: string;
  sortOrder: number;
  /**
   * Funnel position (see scripts/add-crm-stage-rank.ts). Set only when the
   * subcategory is created, so a rank edited in settings survives a re-seed.
   */
  stageRank?: number;
  immediateStep?: ImmediateStep;
  /** Ordered follow-ups; each waits `delayMinutes` after the previous send. */
  followUps?: FollowUpStep[];
  /** Recorded on the sequence description; there is no automation for it yet. */
  notInterestedAction?: string;
};

const HOURS = 60;
const DAYS = 24 * HOURS;

/** Source: Dynamic_Storefront_CRM_Sequence_Library_Working_v2.xlsx, sheet "CRM Sequence Library". */

const TAXONOMY: TaxonomyEntry[] = [
  {
    categoryKey: "not_interested",
    name: "Do Not Contact",
    legacyNames: ["DNC"],
    description: "The person explicitly asked not to be contacted again or requested removal from outreach.",
    classificationGuidance: "Use only for an explicit unsubscribe, stop-contact, removal, or do-not-contact request. This must suppress outreach; no reply sequence is assigned and no message of any kind is sent.",
    sortOrder: 10,
  },
  {
    categoryKey: "not_interested",
    name: "Not Required Right Now",
    description: "The person does not need the offering at present but may be open to a future conversation.",
    classificationGuidance: "Use when the person says the offering is not needed now, timing is not right, priorities are elsewhere, or asks to reconnect later without rejecting future contact.",
    sortOrder: 20,
    immediateStep: {
      name: "Reach-out Email",
      instructions: "Ask what would be the right time to reconnect and revisit the conversation. If the person already gave a timeframe, repeat it accurately and confirm we will follow up then.",
    },
    followUps: [
      { delayMinutes: 60 * DAYS, instructions: "Reconnect at the time the prospect indicated, referencing the earlier conversation and asking whether the problem is now a priority." },
    ],
    notInterestedAction: "Feature Updates",
  },
  {
    categoryKey: "not_interested",
    name: "Already Using a Tool — Not Required",
    description: "The person already uses another tool or process and does not currently see a need to change.",
    classificationGuidance: "Use when the person says an existing vendor, product, agency, or internal process already covers the need and our tool is therefore not required.",
    sortOrder: 30,
    immediateStep: {
      name: "Comparison",
      instructions: "Ask which tool they are currently using and what kind of results they have seen with it. If they share the details, offer to send them a comparison. If they mention they already have an agency, clarify that Dynamic Storefront is a SaaS tool, not an agency.",
    },
    followUps: [
      { delayMinutes: 3 * DAYS, instructions: "Check which website/product-page optimization tool they are currently using and ask them to share the tool if they haven't already. Offer to share the relevant differences/comparison." },
      { delayMinutes: 3 * DAYS, instructions: "Follow up and share the comparison/battle card showing how Dynamic Storefront compares with commonly used tools in the market." },
      { delayMinutes: 3 * DAYS, instructions: "Send a final note offering a one-month free trial so they can run Dynamic Storefront alongside their existing tool and compare results side by side with no commitment. If they like the outcome, they can continue; otherwise they can discontinue." },
    ],
    notInterestedAction: "Feature Updates",
  },
  {
    categoryKey: "interested",
    name: "Information Requested",
    description: "The person asked for product, pricing, feature, implementation, or company information.",
    classificationGuidance: "Use when the primary request is for more information or answers, and the person has not specifically requested a case study, meeting, demo, or trial.",
    sortOrder: 10,
    stageRank: 1,
    immediateStep: {
      name: "Share Information",
      instructions: "Based on what they have requested, provide the relevant information from the Dynamic Storefront knowledge base. Answer the specific questions from the latest message, keep it concise, and do not make unsupported claims.",
    },
    followUps: [
      { delayMinutes: 3 * DAYS, instructions: "Check whether they had a chance to go through the information and offer to answer any additional questions. If useful, offer a demo." },
      { delayMinutes: 3 * DAYS, instructions: "Prioritise getting them onto a call so we can walk them through the information ourselves, answer their questions and explain how Dynamic Storefront could apply to their brand. Share the calendar link." },
      { delayMinutes: 3 * DAYS, instructions: "Offer to create a free, customised demo for their brand so they can see how Dynamic Storefront could work for their use case." },
    ],
    notInterestedAction: "Feature Updates",
  },
  {
    categoryKey: "interested",
    name: "Case Study",
    description: "The person asked for a case study, customer example, proof point, or relevant results.",
    classificationGuidance: "Use when the person explicitly requests a case study, reference, customer story, proof of results, or an example from a similar company or use case.",
    sortOrder: 20,
    stageRank: 1,
    immediateStep: {
      name: "Share Case Study",
      instructions: "Share the relevant case study link and briefly explain the results. The women's wellness case study showed 57% higher attributed revenue across two tests and approximately 1.4x higher conversion rate on the optimized pages. Use only figures from the knowledge base.",
    },
    followUps: [
      { delayMinutes: 3 * DAYS, instructions: "Check if they had a chance to go through the case study. Offer to set up a demo and explain how Dynamic Storefront could work for their brand." },
      { delayMinutes: 3 * DAYS, instructions: "Follow up on the case study and offer to answer questions or discuss how the approach could apply to their brand." },
      { delayMinutes: 3 * DAYS, instructions: "Send a final follow-up offering a one-month free trial at no cost so they can explore the platform, evaluate the results and see its impact on conversion. Make clear there is no obligation to continue." },
    ],
    notInterestedAction: "Feature Updates",
  },
  {
    categoryKey: "interested",
    name: "Meeting Requested",
    description: "The person wants to schedule a call or meeting and needs a calendar link or available times.",
    classificationGuidance: "Use when the person asks to book, schedule, or arrange a call or meeting, including requests for availability or a calendar link.",
    sortOrder: 30,
    stageRank: 2,
    immediateStep: {
      name: "Calendar / Time",
      instructions: "Provide the calendar link so they can select a convenient time. Reflect any timing constraints already mentioned in the conversation.",
    },
    followUps: [
      { delayMinutes: 12 * HOURS, instructions: "Check if they got a chance to book the call. If the available times do not work, ask them to share a suitable time or use the calendar link." },
      { delayMinutes: 3 * DAYS, instructions: "Follow up on the previous message and ask whether they have any questions or concerns before the call. Offer to help with questions around pricing, features, implementation or use-case fit." },
      { delayMinutes: 3 * DAYS, instructions: "Share a relevant Dynamic Storefront case study and briefly explain the results. Use it to show why the conversation may be worth having." },
      { delayMinutes: 3 * DAYS, instructions: "Offer to create a fully customised demo for their brand, products and use case so they can see firsthand how Dynamic Storefront could work for them." },
      { delayMinutes: 3 * DAYS, instructions: "Offer a one-month free trial so they can evaluate Dynamic Storefront themselves and see its impact on conversion with no commitment." },
    ],
    notInterestedAction: "Feature Updates",
  },
  {
    categoryKey: "interested",
    name: "Meeting No Show",
    description: "A scheduled meeting did not happen because the prospect did not attend.",
    classificationGuidance: "Use after a confirmed meeting time passes and the external participant did not attend or explicitly says they missed the meeting.",
    sortOrder: 40,
    stageRank: 2,
    immediateStep: {
      name: "Reschedule",
      instructions: "Ask them to reschedule the meeting and share the calendar/rescheduling link. Keep it friendly and blame-free.",
    },
    followUps: [
      { delayMinutes: 12 * HOURS, instructions: "Follow up and ask if they would like to reschedule. Share the calendar link again and make it easy for them to choose another time." },
      { delayMinutes: 3 * DAYS, instructions: "Check in again and offer to find a suitable time if the previous timing did not work." },
      { delayMinutes: 3 * DAYS, instructions: "Send a final rescheduling follow-up. Offer a free, fully customised demo if they would still like to explore Dynamic Storefront." },
    ],
    notInterestedAction: "Feature Updates",
  },
  {
    categoryKey: "interested",
    name: "Meeting Done",
    description: "The meeting was completed and the person should receive a recap and agreed next steps.",
    classificationGuidance: "Use when the meeting has taken place and the next response should recap discussion, decisions, responsibilities, or follow-up actions.",
    sortOrder: 50,
    stageRank: 3,
    immediateStep: {
      name: "Minutes of Meeting",
      instructions: "Send a meeting recap / Minutes of Meeting covering the key points discussed, requirements, decisions and agreed next steps. Use only facts available in the meeting notes or conversation and clearly flag anything that still needs confirmation.",
    },
    followUps: [
      { delayMinutes: 1 * DAYS, instructions: "Follow up on the agreed next step from the meeting." },
      { delayMinutes: 3 * DAYS, instructions: "Ask what is holding them back, such as pricing, features, use-case fit or another concern. Offer to address the blocker." },
    ],
    notInterestedAction: "Feature Updates",
  },
  {
    categoryKey: "interested",
    name: "Demo Request",
    legacyNames: ["Demo Requested"],
    description: "The person asked to see a product demonstration or receive demo material.",
    classificationGuidance: "Use when the person explicitly asks for a demo, walkthrough, product tour, recording, or demonstration call.",
    sortOrder: 60,
    stageRank: 1,
    immediateStep: {
      name: "Send Demo",
      instructions: "Send the personalized demo requested by the prospect. Briefly explain what it covers and answer any specific request from the latest message.",
    },
    followUps: [
      { delayMinutes: 1 * DAYS, instructions: "Check whether they had a chance to go through the demo and invite them to share any feedback, questions or feature requests." },
      { delayMinutes: 3 * DAYS, instructions: "Follow up with a useful additional point about Dynamic Storefront and offer to answer questions or discuss the use case." },
      { delayMinutes: 3 * DAYS, instructions: "Remind them that a fully customised demo has already been created specifically for their brand, products and use case. Ask them to take some time to evaluate it firsthand and share their feedback." },
      { delayMinutes: 3 * DAYS, instructions: "Share relevant proof/case-study results and offer to discuss whether Dynamic Storefront is a fit." },
      { delayMinutes: 3 * DAYS, instructions: "Send a final follow-up offering a one-month free trial so they can evaluate the platform and its impact on conversion with no obligation." },
    ],
  },
  {
    categoryKey: "interested",
    name: "Trial Requested",
    description: "The person wants to begin a trial or asks how to get trial access.",
    classificationGuidance: "Use when the person asks to start, activate, access, or learn the next steps for a product trial.",
    sortOrder: 70,
    stageRank: 4,
    immediateStep: {
      name: "Onboarding Emails",
      instructions: "Ask for their Shopify collaborator code. Explain that this is required so we can install/download the Shopify app and set up their enterprise access for the trial. Never invent credentials or expose secrets.",
    },
    followUps: [
      { delayMinutes: 1 * DAYS, instructions: "Follow up if the collaborator code has not been shared. Remind them that the code is needed to connect the store and start the trial." },
      { delayMinutes: 3 * DAYS, instructions: "Follow up on onboarding and ask if there is anything preventing them from completing setup." },
      { delayMinutes: 3 * DAYS, instructions: "Offer help with setup and ask whether they need anything from the team to get the trial live." },
      { delayMinutes: 3 * DAYS, instructions: "Check whether they are ready to start the trial and offer to help complete the setup." },
      { delayMinutes: 3 * DAYS, instructions: "Send a final onboarding follow-up asking whether they still want to proceed with the trial." },
    ],
  },
  {
    categoryKey: "interested",
    name: "Trial User",
    description: "The person is actively using the trial and needs help progressing through setup or integration.",
    classificationGuidance: "Use for an active trial user discussing setup, activation, usage, onboarding, or integration rather than requesting initial trial access.",
    sortOrder: 80,
    stageRank: 5,
    immediateStep: {
      name: "Trial Status",
      instructions: "Share details of how their trial has gone, when the trial will end, and explain that they will need to pay to continue after the trial. Use only facts available in the conversation or knowledge base; do not invent usage numbers or dates.",
    },
    followUps: [
      { delayMinutes: 30 * DAYS, instructions: "Follow up near the end of the trial to understand their experience and ask if there is anything preventing them from moving forward." },
      { delayMinutes: 1 * DAYS, instructions: "Ask whether they have any questions or concerns and offer to help them evaluate whether Dynamic Storefront is the right fit." },
      { delayMinutes: 3 * DAYS, instructions: "Follow up on the previous message and ask if there is anything preventing them from moving forward, such as pricing, features or use-case fit." },
      { delayMinutes: 3 * DAYS, instructions: "Send a final follow-up asking for feedback and offering to help if they decide to explore Dynamic Storefront in the future." },
    ],
  },
  {
    categoryKey: "customer",
    name: "Customer",
    description: "The person represents an active customer relationship and is requesting billing or account follow-up.",
    classificationGuidance: "Use when the person is an existing customer and the conversation concerns an active account, especially invoices, billing, renewal, or ongoing service.",
    sortOrder: 10,
    stageRank: 6,
    immediateStep: {
      name: "Send Bills",
      instructions: "Send the customer's billing information/invoice as required. Do not invent amounts, dates, payment details, or attachments; if any billing detail is missing, ask for confirmation before sending.",
    },
  },
  {
    categoryKey: "other",
    name: "Did Not Connect to Different POC",
    description: "The person is not the right contact and has not yet provided or connected us with the appropriate point of contact.",
    classificationGuidance: "Use when the recipient says they are not the correct person, but no alternate contact or introduction has been provided.",
    sortOrder: 10,
    immediateStep: {
      name: "Mail for Right POC",
      instructions: "Ask why they were not able to connect us to the relevant POC. Try to understand whether they see a problem with the product, whether pricing is the issue, or whether there is another reason. Keep the request polite and easy to answer.",
    },
    followUps: [
      { delayMinutes: 2 * DAYS, instructions: "Follow up to understand what is preventing the introduction and whether there is a concern around pricing, product fit or something else." },
    ],
  },
  {
    categoryKey: "other",
    name: "Connected to Different POC",
    description: "A contact has referred us to or shared details for a different person who is the appropriate point of contact.",
    classificationGuidance: "Use when the recipient provides another person's contact information, copies them into the conversation, or makes a direct introduction to the correct point of contact.",
    sortOrder: 20,
    immediateStep: {
      name: "Referrer Shared Contact",
      instructions: "Thank them for connecting us. If the new POC's phone number or email has not already been shared, ask them to share it because it is quicker to connect directly.",
    },
  },
  {
    categoryKey: "other",
    name: "Left Company",
    description: "The person is no longer employed by the target company.",
    classificationGuidance: "Use when an auto-response, colleague, or other reliable message states that the person has left the company.",
    sortOrder: 30,
    immediateStep: {
      name: "Ask for New Contact",
      instructions: "Acknowledge that they have left the company. Ask them to connect us with whoever manages ads or performance marketing at their previous company. Also ask whether Dynamic Storefront might be relevant to their existing/new company.",
    },
    followUps: [
      { delayMinutes: 3 * DAYS, instructions: "Follow up to ask for the relevant ads/performance marketing contact at their previous company if they have not shared one." },
      { delayMinutes: 3 * DAYS, instructions: "Ask whether Dynamic Storefront could also be relevant to the person's new company and offer to explain it briefly." },
    ],
  },
  {
    categoryKey: "other",
    name: "Out of Office",
    description: "The person is temporarily unavailable and an out-of-office or leave message was received.",
    classificationGuidance: "Use for temporary out-of-office, vacation, leave, or unavailable notices. Do not use when the message says the person permanently left the company.",
    sortOrder: 40,
    immediateStep: {
      name: "Acknowledge OOO",
      instructions: "Acknowledge the out-of-office response and, if available, identify when they are expected to return so outreach can be timed appropriately. Keep it to one or two lines; if the auto-reply names a return date, say we will reconnect after it.",
    },
    followUps: [
      { delayMinutes: 3 * DAYS, instructions: "Reconnect after the expected return date and reference the earlier conversation." },
    ],
  },
  {
    categoryKey: "other",
    name: "Other",
    legacyNames: ["uncategorised", "Uncategorised"],
    description: "The reply does not fit any other subcategory and needs a context-specific response.",
    classificationGuidance: "Use only when no other subcategory fits the latest message. Prefer a specific subcategory whenever the intent is reasonably clear.",
    sortOrder: 50,
    immediateStep: {
      name: "Contextual Reply",
      instructions: "Respond based on the specific context of the prospect's message. Use the Dynamic Storefront knowledge base where relevant and do not force the prospect into a predefined response.",
    },
    followUps: [
      { delayMinutes: 3 * DAYS, instructions: "Follow up based on the unresolved point in the previous conversation." },
      { delayMinutes: 3 * DAYS, instructions: "Address the most relevant remaining question or blocker." },
      { delayMinutes: 3 * DAYS, instructions: "Offer a relevant next step, such as a demo, case study or meeting, depending on the conversation." },
      { delayMinutes: 3 * DAYS, instructions: "Make one more relevant attempt to move the conversation forward." },
      { delayMinutes: 3 * DAYS, instructions: "Close the loop politely if there is no response." },
    ],
  },
];

function describeDelay(minutes: number): string {
  if (minutes % DAYS === 0) return `${minutes / DAYS}d`;
  if (minutes % HOURS === 0) return `${minutes / HOURS}h`;
  return `${minutes}m`;
}

function describeSequence(entry: TaxonomyEntry, immediateStep: ImmediateStep): string {
  const cadence = (entry.followUps ?? []).map((followUp, index) => `follow-up ${index + 1} after ${describeDelay(followUp.delayMinutes)}`);
  const parts = [`Default sequence for ${entry.name}: ${immediateStep.name} immediately${cadence.length ? `, ${cadence.join(", ")}` : ""}.`];
  if (entry.notInterestedAction) parts.push(`If there is no interest after the last step: ${entry.notInterestedAction}.`);
  return parts.join(" ");
}

function sameSteps(
  actual: Array<{
    name: string;
    delayMinutes: number;
    subjectTemplate: string | null;
    bodyTemplate: string | null;
    aiInstructions: string;
    knowledgeTags: string[];
  }>,
  expected: Array<{
    name: string;
    delayMinutes: number;
    subjectTemplate: null;
    bodyTemplate: null;
    aiInstructions: string;
    knowledgeTags: string[];
  }>,
) {
  return JSON.stringify(actual.map((step) => ({
    name: step.name,
    delayMinutes: step.delayMinutes,
    subjectTemplate: step.subjectTemplate,
    bodyTemplate: step.bodyTemplate,
    aiInstructions: step.aiInstructions,
    knowledgeTags: step.knowledgeTags,
  }))) === JSON.stringify(expected);
}

async function applyTaxonomy() {
  const configuration = await listCategoryConfiguration();
  const initialSequences = await listSequences({ includeArchived: true });
  const sequenceReferences = initialSequences.map(({ id, name }) => ({ id, name }));
  const subcategories = configuration.categories.flatMap((category) => category.subcategories);
  const summary = { createdSubcategories: 0, updatedSubcategories: 0, createdSequences: 0, updatedSequences: 0, publishedSequences: 0, assignedSequences: 0 };

  for (const entry of TAXONOMY) {
    const acceptedNames = new Set([entry.name, ...(entry.legacyNames ?? [])]);
    const existingSubcategory = subcategories.find((candidate) =>
      candidate.categoryKey === entry.categoryKey && acceptedNames.has(candidate.name),
    );
    let subcategoryId: string;
    let assignedSequenceId: string | null;

    if (!existingSubcategory) {
      const created = await createSubcategory({
        pipelineId: configuration.pipelineId,
        categoryKey: entry.categoryKey,
        name: entry.name,
        description: entry.description,
        classificationGuidance: entry.classificationGuidance,
        reviewRequired: false,
        sortOrder: entry.sortOrder,
        stageRank: entry.stageRank ?? null,
      });
      subcategoryId = created.id;
      assignedSequenceId = null;
      summary.createdSubcategories += 1;
    } else {
      await updateSubcategory(existingSubcategory.id, {
        name: entry.name,
        description: entry.description,
        classificationGuidance: entry.classificationGuidance,
        reviewRequired: false,
        sortOrder: entry.sortOrder,
        active: true,
      });
      subcategoryId = existingSubcategory.id;
      assignedSequenceId = existingSubcategory.sequenceId;
      summary.updatedSubcategories += 1;
    }

    if (!entry.immediateStep) continue;

    const sequenceName = entry.name;
    const sequenceDescription = describeSequence(entry, entry.immediateStep);
    const desiredSteps = [
      {
        name: entry.immediateStep.name,
        delayMinutes: 0,
        subjectTemplate: null,
        bodyTemplate: null,
        aiInstructions: entry.immediateStep.instructions,
        knowledgeTags: [],
      },
      ...(entry.followUps ?? []).map((followUp, index) => ({
        name: `Follow-up ${index + 1}`,
        delayMinutes: followUp.delayMinutes,
        subjectTemplate: null,
        bodyTemplate: null,
        aiInstructions: followUp.instructions,
        knowledgeTags: [],
      })),
    ];

    const assignedSequence = assignedSequenceId
      ? sequenceReferences.find((sequence) => sequence.id === assignedSequenceId)
      : undefined;
    const legacySequenceNames = new Set([entry.name, ...(entry.legacyNames ?? [])]);
    const existingSequence = assignedSequence ?? sequenceReferences.find((candidate) =>
      candidate.name === sequenceName || legacySequenceNames.has(candidate.name),
    );
    let sequenceId: string;

    if (!existingSequence) {
      const created = await createSequence({ name: sequenceName, description: sequenceDescription, steps: desiredSteps });
      sequenceId = created.id;
      sequenceReferences.push({ id: created.id, name: created.name });
      summary.createdSequences += 1;
    } else {
      sequenceId = existingSequence.id;
      const detail = await getSequence(sequenceId);
      const stepsChanged = !sameSteps(detail.draftSteps, desiredSteps);
      const metadataChanged = detail.name !== sequenceName || detail.description !== sequenceDescription || detail.status !== "active";
      if (stepsChanged || metadataChanged) {
        await updateSequence(sequenceId, {
          name: sequenceName,
          description: sequenceDescription,
          status: "active",
          ...(stepsChanged ? { steps: desiredSteps } : {}),
        });
        summary.updatedSequences += 1;
      }
    }

    const detail = await getSequence(sequenceId);
    const publishedSteps = detail.latestPublishedVersionId
      ? await db.select().from(crmSequenceSteps)
        .where(eq(crmSequenceSteps.sequenceVersionId, detail.latestPublishedVersionId))
        .orderBy(asc(crmSequenceSteps.position))
      : [];
    if (!detail.latestPublishedVersionId || !sameSteps(publishedSteps, desiredSteps)) {
      await publishSequence(sequenceId);
      summary.publishedSequences += 1;
    }

    if (assignedSequenceId !== sequenceId) {
      await assignSubcategorySequence(subcategoryId, { sequenceId });
      summary.assignedSequences += 1;
    }
  }

  return summary;
}

if (!process.argv.includes("--apply")) {
  const sequences = TAXONOMY.filter((entry) => entry.immediateStep);
  const steps = sequences.reduce((total, entry) => total + 1 + (entry.followUps?.length ?? 0), 0);
  console.log(`Dry run: ${TAXONOMY.length} subcategories, ${sequences.length} sequences, ${steps} steps are defined.`);
  for (const entry of sequences) {
    if (entry.immediateStep) console.log(`- ${entry.name}: ${describeSequence(entry, entry.immediateStep)}`);
  }
  console.log("Run with --apply to create or update the CRM configuration.");
  process.exit(0);
}

runScriptInOrganization(applyTaxonomy)
  .then((summary) => {
    console.log(JSON.stringify(summary, null, 2));
    process.exit(0);
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
