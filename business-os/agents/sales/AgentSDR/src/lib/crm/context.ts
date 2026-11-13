import type {
  BuiltClassificationContext,
  ClassificationCampaignSummary,
  ClassificationCompanyProfile,
  ClassificationContextInput,
  ClassificationContextSnapshot,
  ClassificationKnowledgeDocument,
  ClassificationMessage,
  ClassificationPersonProfile,
} from "./ai/types";

const DEFAULT_CONTEXT_TOKENS = 6_000;
const MIN_CONTEXT_TOKENS = 512;
const MAX_CONTEXT_TOKENS = 32_000;
const APPROXIMATE_CHARS_PER_TOKEN = 4;
const TRUNCATION_MARKER = "…[truncated]";

type Scalar = string | number | boolean | null;

function cleanText(value: string | null | undefined): string | null {
  return value?.trim() || null;
}

function boundedText(value: string | null | undefined, maxCharacters: number): string | null {
  const clean = cleanText(value);
  if (!clean || clean.length <= maxCharacters) return clean;
  const keep = Math.max(0, maxCharacters - TRUNCATION_MARKER.length);
  return `${clean.slice(0, keep)}${TRUNCATION_MARKER}`;
}

function scalarAttributes(
  value: Record<string, Scalar> | undefined,
  maxEntries = 40,
): Record<string, Scalar> | undefined {
  if (!value) return undefined;
  const entries = Object.entries(value)
    .sort(([left], [right]) => left.localeCompare(right))
    .slice(0, maxEntries)
    .map(([key, item]) => [
      key.slice(0, 120),
      typeof item === "string" ? boundedText(item, 500) : item,
    ] as const);
  return entries.length ? Object.fromEntries(entries) : undefined;
}

function personSnapshot(person: ClassificationPersonProfile): ClassificationPersonProfile {
  return {
    id: cleanText(person.id),
    fullName: boundedText(person.fullName, 500),
    firstName: boundedText(person.firstName, 250),
    lastName: boundedText(person.lastName, 250),
    email: boundedText(person.email, 500),
    linkedinUrl: boundedText(person.linkedinUrl, 1_000),
    title: boundedText(person.title, 1_000),
    attributes: scalarAttributes(person.attributes),
  };
}

function companySnapshot(
  company: ClassificationCompanyProfile | null | undefined,
): ClassificationCompanyProfile | null {
  if (!company) return null;
  return {
    id: cleanText(company.id),
    name: boundedText(company.name, 500),
    domain: boundedText(company.domain, 500),
    linkedinUrl: boundedText(company.linkedinUrl, 1_000),
    description: boundedText(company.description, 2_000),
    attributes: scalarAttributes(company.attributes),
  };
}

function campaignSnapshot(
  campaign: ClassificationCampaignSummary | null | undefined,
): ClassificationCampaignSummary | null {
  if (!campaign) return null;
  return {
    channel: campaign.channel ?? null,
    campaignId: boundedText(campaign.campaignId, 500),
    name: boundedText(campaign.name, 500),
    status: boundedText(campaign.status, 250),
    source: boundedText(campaign.source, 500),
    summary: boundedText(campaign.summary, 2_000),
    attributes: scalarAttributes(campaign.attributes),
  };
}

function knowledgeSnapshot(
  knowledge: readonly ClassificationKnowledgeDocument[] | null | undefined,
): Array<{ documentId: string; title: string; kind: string | null; content: string }> {
  if (!knowledge) return [];
  const seen = new Set<string>();
  const entries: Array<{ documentId: string; title: string; kind: string | null; content: string }> = [];
  for (const document of knowledge) {
    const documentId = cleanText(document.documentId);
    if (!documentId || seen.has(documentId)) continue;
    const content = boundedText(document.content, 4_000);
    if (!content) continue;
    seen.add(documentId);
    entries.push({
      documentId,
      title: document.title.trim(),
      kind: document.kind,
      content,
    });
  }
  return entries;
}

function isoDate(value: Date | string, label: string): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error(`${label} has an invalid sentAt value`);
  return date.toISOString();
}

function messageSnapshot(
  message: ClassificationMessage,
  bodyLimit?: number,
): ClassificationMessage & { sentAt: string } {
  const id = message.id.trim();
  if (!id) throw new Error("Classification messages require an id");
  const bodyText = message.bodyText.trim();
  if (!bodyText) throw new Error(`Classification message ${id} has no text`);
  return {
    id,
    channel: message.channel,
    direction: message.direction,
    sentAt: isoDate(message.sentAt, `Classification message ${id}`),
    subject: boundedText(message.subject, 1_000),
    bodyText: bodyLimit === undefined
      ? bodyText
      : boundedText(bodyText, bodyLimit) ?? "",
    ...(message.participants ? { participants: message.participants } : {}),
  };
}

function serializedLength(snapshot: ClassificationContextSnapshot): number {
  return JSON.stringify(snapshot, null, 2).length;
}

function shrinkLatestBody(
  snapshot: ClassificationContextSnapshot,
  maxCharacters: number,
): boolean {
  const current = snapshot.latestInboundMessage.bodyText;
  if (serializedLength(snapshot) <= maxCharacters) return false;
  const excess = serializedLength(snapshot) - maxCharacters;
  const nextLength = Math.max(80, current.length - excess - TRUNCATION_MARKER.length);
  const next = boundedText(current, nextLength) ?? "";
  if (next === current) return false;
  snapshot.latestInboundMessage.bodyText = next;
  return true;
}

function removeOptionalDetail(snapshot: ClassificationContextSnapshot): boolean {
  if (snapshot.person.attributes) {
    delete snapshot.person.attributes;
    return true;
  }
  if (snapshot.company?.attributes) {
    delete snapshot.company.attributes;
    return true;
  }
  if (snapshot.campaignSummary?.attributes) {
    delete snapshot.campaignSummary.attributes;
    return true;
  }
  if (snapshot.knowledge.length) {
    snapshot.knowledge = [];
    return true;
  }
  if (snapshot.company?.description) {
    snapshot.company.description = null;
    return true;
  }
  if (snapshot.campaignSummary?.summary) {
    snapshot.campaignSummary.summary = null;
    return true;
  }
  return false;
}

function fitBaseSnapshot(
  snapshot: ClassificationContextSnapshot,
  maxCharacters: number,
): boolean {
  let truncated = false;
  while (serializedLength(snapshot) > maxCharacters && removeOptionalDetail(snapshot)) {
    truncated = true;
  }
  if (serializedLength(snapshot) > maxCharacters) {
    truncated = shrinkLatestBody(snapshot, maxCharacters) || truncated;
  }
  if (serializedLength(snapshot) > maxCharacters) {
    throw new Error("The classification context budget is too small for the required fields");
  }
  return truncated;
}

export function estimateContextTokens(text: string): number {
  return Math.ceil(text.length / APPROXIMATE_CHARS_PER_TOKEN);
}

/**
 * Creates the exact auditable context sent to the classifier. The newest
 * contiguous conversation window is retained, and prior messages are never
 * partially sliced: when the next complete message does not fit, older
 * messages are omitted as a group.
 */
export function buildClassificationContext(
  input: ClassificationContextInput,
  options: { maxTokens?: number } = {},
): BuiltClassificationContext {
  const requestedMax = Math.floor(options.maxTokens ?? DEFAULT_CONTEXT_TOKENS);
  if (!Number.isFinite(requestedMax) || requestedMax < MIN_CONTEXT_TOKENS || requestedMax > MAX_CONTEXT_TOKENS) {
    throw new Error(
      `Classification context maxTokens must be between ${MIN_CONTEXT_TOKENS} and ${MAX_CONTEXT_TOKENS}`,
    );
  }
  if (input.latestInboundMessage.direction !== "inbound") {
    throw new Error("The latest classification message must be inbound");
  }

  const maxCharacters = requestedMax * APPROXIMATE_CHARS_PER_TOKEN;
  const latest = messageSnapshot(input.latestInboundMessage, Math.max(512, Math.floor(maxCharacters * 0.55)));
  const taxonomyCategoryKeys = new Set(input.categories.map((category) => category.key));
  const snapshot: ClassificationContextSnapshot = {
    taxonomy: {
      categories: input.categories.map((category) => ({
        key: category.key,
        label: category.label.trim(),
        description: boundedText(category.description, 1_000),
      })),
      subcategories: input.subcategories.map((subcategory) => ({
        categoryKey: subcategory.categoryKey,
        key: subcategory.key.trim(),
        name: subcategory.name.trim(),
        description: boundedText(subcategory.description, 1_000),
        classificationGuidance: boundedText(subcategory.classificationGuidance, 2_000),
        reviewRequired: subcategory.reviewRequired,
      })),
    },
    person: personSnapshot(input.person),
    company: companySnapshot(input.company),
    currentClassification: {
      categoryKey: input.currentClassification.categoryKey,
      subcategoryKey: cleanText(input.currentClassification.subcategoryKey),
      categorySource: input.currentClassification.categorySource ?? null,
      categoryLocked: input.currentClassification.categoryLocked,
    },
    campaignSummary: campaignSnapshot(input.campaignSummary),
    latestInboundMessage: latest,
    recentConversation: [],
    knowledge: knowledgeSnapshot(input.knowledge),
  };

  if (!snapshot.taxonomy.categories.length) {
    throw new Error("At least one active CRM category is required for classification");
  }
  if (snapshot.taxonomy.categories.some((category) => !category.label)) {
    throw new Error("Active CRM categories require a label");
  }
  if (snapshot.taxonomy.subcategories.some((subcategory) => (
    !subcategory.key
    || !subcategory.name
    || !taxonomyCategoryKeys.has(subcategory.categoryKey)
  ))) {
    throw new Error("Active CRM subcategories require a key, name, and active parent category");
  }

  let truncated = latest.bodyText !== input.latestInboundMessage.bodyText.trim();
  truncated = fitBaseSnapshot(snapshot, maxCharacters) || truncated;

  const priorMessages = input.recentConversation
    .filter((message) => message.id.trim() !== latest.id)
    .map((message) => messageSnapshot(message))
    .sort((left, right) => left.sentAt.localeCompare(right.sentAt));

  const selectedNewestFirst: typeof priorMessages = [];
  for (let index = priorMessages.length - 1; index >= 0; index -= 1) {
    const candidate = priorMessages[index];
    snapshot.recentConversation = [candidate, ...selectedNewestFirst];
    if (serializedLength(snapshot) > maxCharacters) {
      snapshot.recentConversation = [...selectedNewestFirst];
      truncated = true;
      break;
    }
    selectedNewestFirst.unshift(candidate);
  }

  const prompt = JSON.stringify(snapshot, null, 2);
  return {
    snapshot,
    prompt,
    estimatedTokens: estimateContextTokens(prompt),
    maxTokens: requestedMax,
    truncated,
    omittedMessageCount: priorMessages.length - snapshot.recentConversation.length,
  };
}
