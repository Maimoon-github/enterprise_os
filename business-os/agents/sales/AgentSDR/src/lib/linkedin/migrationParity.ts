import { inferLinkedinApi, normalizeLinkedinSlug } from "../leads/identity";
import { MAX_LEAD_RETRIES } from "./inviteRetry";
import { fillTemplate } from "../outreach/render";

export const LINKEDIN_TERMINAL_STATUSES = new Set(["REPLIED", "FAILED", "CANCELLED", "COMPLETED"]);

export type LinkedinParityLead = {
  id: string;
  status: string;
  campaignStatus: string | null;
  campaignId: string | null;
  personId: string | null;
  providerId: string | null;
  linkedinAccountId: string | null;
  legacyLinkedinUrl: string | null;
  personLinkedinUrl: string | null;
  sourceLinkedinIdentifier: string | null;
  sourceLinkedinApi: string | null;
  inviteRetryCount: number;
  resolveRetryCount: number;
  resolveNextAttemptAt: Date | null;
  requestSentAt: Date | null;
  acceptMessageSentAt: Date | null;
  followUp1SentAt: Date | null;
  followUp2SentAt: Date | null;
  connectionChatId: string | null;
  leadTemplates: Record<string, string | null>;
  campaignTemplates: Record<string, string | null>;
  variables: Record<string, string>;
  canonicalMessageTypes: Set<string>;
};

export type NextAction = {
  action: string;
  template: string | null;
  rendered: string | null;
  reason: string | null;
};

const MAX_INVITE_RETRIES = MAX_LEAD_RETRIES;
const MAX_RESOLVE_RETRIES = MAX_LEAD_RETRIES;

function hasText(value: string | null | undefined): value is string {
  return Boolean(value?.trim());
}

function due(timestamp: Date | null, delayMs: number, now: Date) {
  return Boolean(timestamp && timestamp.getTime() <= now.getTime() - delayMs);
}

function legacyTemplate(lead: LinkedinParityLead, key: string) {
  return lead.leadTemplates[key] ?? null;
}

function peopleTemplate(lead: LinkedinParityLead, key: string) {
  return lead.campaignTemplates[key] ?? lead.leadTemplates[key] ?? null;
}

function action(action: string, template: string | null, variables?: Record<string, string>, reason: string | null = null): NextAction {
  return {
    action,
    template,
    rendered: template === null ? null : variables ? fillTemplate(template, variables) : template,
    reason,
  };
}

/** Models the pre-People runtime from git HEAD for an active campaign. */
export function legacyNextAction(lead: LinkedinParityLead, now: Date): NextAction {
  if (lead.campaignStatus !== "ACTIVE") return action("none", null, undefined, "campaign_not_active");
  if (lead.status === "PENDING") {
    if (lead.inviteRetryCount >= MAX_INVITE_RETRIES) return action("none", null, undefined, "retry_exhausted");
    return lead.providerId
      ? action("send_invitation", legacyTemplate(lead, "invitationMessage"))
      : action("resolve_profile", null);
  }
  if (lead.status === "REQUEST_SENT") {
    if (!lead.connectionChatId) return action("wait_acceptance", null);
    const template = legacyTemplate(lead, "acceptanceMessage");
    return hasText(template) ? action("send_acceptance", template) : action("advance_acceptance", null);
  }
  const stages = [
    ["ACCEPT_MESSAGE_SENT", "followUp1Message", lead.acceptMessageSentAt, 24 * 60 * 60 * 1000, "send_follow_up_1"],
    ["FOLLOW_UP_1_SENT", "followUp2Message", lead.followUp1SentAt, 48 * 60 * 60 * 1000, "send_follow_up_2"],
    ["FOLLOW_UP_2_SENT", "followUp3Message", lead.followUp2SentAt, 72 * 60 * 60 * 1000, "send_follow_up_3"],
  ] as const;
  for (const [status, key, sentAt, delay, name] of stages) {
    if (lead.status !== status) continue;
    if (!due(sentAt, delay, now)) return action("wait", null, undefined, "not_due");
    const template = legacyTemplate(lead, key);
    return hasText(template) ? action(name, template) : action("complete", null, undefined, "sequence_exhausted");
  }
  return action("none", null, undefined, LINKEDIN_TERMINAL_STATUSES.has(lead.status) ? "terminal" : "unsupported_status");
}

/** Models the People-backed runtime. Canonical message claims suppress replay. */
export function peopleNextAction(lead: LinkedinParityLead, now: Date): NextAction {
  if (lead.campaignStatus !== "ACTIVE") return action("none", null, undefined, "campaign_not_active");
  if (!lead.personId) return action("blocked", null, undefined, "missing_person");
  if (lead.status === "PENDING") {
    if (lead.canonicalMessageTypes.has("INVITATION")) {
      return action("wait_invitation_reconciliation", null, undefined, "already_claimed");
    }
    if (lead.sourceLinkedinIdentifier) {
      if (lead.resolveRetryCount >= MAX_RESOLVE_RETRIES) return action("blocked", null, undefined, "resolution_retry_exhausted");
      if (lead.resolveNextAttemptAt && lead.resolveNextAttemptAt > now) return action("wait", null, undefined, "resolution_backoff");
      return action("resolve_profile", null);
    }
    if (!lead.providerId || !normalizeLinkedinSlug(lead.personLinkedinUrl)) {
      return action("blocked", null, undefined, "missing_resolved_target");
    }
    if (lead.inviteRetryCount >= MAX_INVITE_RETRIES) return action("none", null, undefined, "retry_exhausted");
    return action("send_invitation", peopleTemplate(lead, "invitationMessage"), lead.variables);
  }
  if (lead.status === "REQUEST_SENT") {
    if (!lead.connectionChatId) return action("wait_acceptance", null);
    const template = peopleTemplate(lead, "acceptanceMessage");
    if (!hasText(template)) return action("advance_acceptance", null);
    return lead.canonicalMessageTypes.has("ACCEPTANCE")
      ? action("advance_acceptance", null, undefined, "already_claimed")
      : action("send_acceptance", template, lead.variables);
  }
  const stages = [
    ["ACCEPT_MESSAGE_SENT", "followUp1Message", lead.acceptMessageSentAt, 24 * 60 * 60 * 1000, "FOLLOW_UP_1", "send_follow_up_1"],
    ["FOLLOW_UP_1_SENT", "followUp2Message", lead.followUp1SentAt, 48 * 60 * 60 * 1000, "FOLLOW_UP_2", "send_follow_up_2"],
    ["FOLLOW_UP_2_SENT", "followUp3Message", lead.followUp2SentAt, 72 * 60 * 60 * 1000, "FOLLOW_UP_3", "send_follow_up_3"],
  ] as const;
  for (const [status, key, sentAt, delay, messageType, name] of stages) {
    if (lead.status !== status) continue;
    if (!due(sentAt, delay, now)) return action("wait", null, undefined, "not_due");
    const template = peopleTemplate(lead, key);
    if (!hasText(template)) return action("complete", null, undefined, "sequence_exhausted");
    return lead.canonicalMessageTypes.has(messageType)
      ? action("advance_existing_claim", null, undefined, "already_claimed")
      : action(name, template, lead.variables);
  }
  return action("none", null, undefined, LINKEDIN_TERMINAL_STATUSES.has(lead.status) ? "terminal" : "unsupported_status");
}

export function compareLinkedinLead(lead: LinkedinParityLead, now: Date) {
  const legacy = legacyNextAction(lead, now);
  const current = peopleNextAction(lead, now);
  const oldSlug = normalizeLinkedinSlug(lead.legacyLinkedinUrl);
  const newSlug = normalizeLinkedinSlug(lead.personLinkedinUrl);
  // Only an unsent invitation needs a profile target. A retained source
  // identifier is deliberately resolved before sending, including migrated
  // rows that already carry a provider id. Later stages use the connection's
  // chat id and must not be blocked on profile fields they no longer need.
  const targetCompatible = lead.status !== "PENDING"
    || (hasText(lead.sourceLinkedinIdentifier)
      ? true
      : Boolean(lead.providerId && newSlug));
  const differences: string[] = [];
  if (!lead.personId) differences.push("missing_person");
  if (!targetCompatible && !LINKEDIN_TERMINAL_STATUSES.has(lead.status)) differences.push("target_not_usable");
  if (lead.status === "PENDING" && !lead.providerId) {
    const expectedApi = inferLinkedinApi(lead.legacyLinkedinUrl);
    if (expectedApi && lead.sourceLinkedinApi !== expectedApi) differences.push("source_api");
  }
  const guardedInvitationClaim = lead.status === "PENDING" && lead.canonicalMessageTypes.has("INVITATION");
  const safeResolutionDetour = legacy.action === "send_invitation" && current.action === "resolve_profile";
  if (legacy.action !== current.action && !guardedInvitationClaim && !safeResolutionDetour) differences.push("next_action");
  if (legacy.rendered !== current.rendered && !safeResolutionDetour) differences.push("rendered_content");
  return {
    leadId: lead.id,
    oldSlug,
    newSlug,
    providerId: lead.providerId,
    accountId: lead.linkedinAccountId,
    sourceIdentifier: lead.sourceLinkedinIdentifier,
    targetCompatible,
    safeResolutionDetour,
    legacy,
    current,
    differences,
  };
}

export function compareEligibleAccountIds(
  candidateAccountIds: string[],
  legacyExcludedAccountIds: ReadonlySet<string>,
  peopleExcludedAccountIds: ReadonlySet<string>,
) {
  const unique = [...new Set(candidateAccountIds)].sort();
  const legacy = unique.filter((id) => !legacyExcludedAccountIds.has(id));
  const current = unique.filter((id) => !peopleExcludedAccountIds.has(id));
  const matches = legacy.join("\u0000") === current.join("\u0000");
  // Removing eligible senders is the intended cross-campaign dedupe guard.
  // Adding a sender that legacy logic excluded is the unsafe direction.
  const safeNarrowing = current.every((id) => legacy.includes(id));
  return { legacy, current, matches, safeNarrowing };
}

export type WebhookCandidate = {
  id: string;
  status: string;
  superseded: boolean;
  requestSentAt: Date | null;
  createdAt: Date;
};

/** Mirrors current webhook ownership selection and rejects every ambiguity. */
export function classifyWebhookOwnership(candidates: WebhookCandidate[]) {
  const active = candidates.filter((candidate) => !candidate.superseded).sort((left, right) =>
    (right.requestSentAt?.getTime() ?? 0) - (left.requestSentAt?.getTime() ?? 0)
      || right.createdAt.getTime() - left.createdAt.getTime()
      || right.id.localeCompare(left.id),
  );
  const requested = active.filter((candidate) => candidate.status === "REQUEST_SENT");
  return {
    inboundOwnerId: active.length === 1 ? active[0]!.id : null,
    connectionOwnerId: requested.length === 1 ? requested[0]!.id : requested.length > 1 ? null : active.length === 1 ? active[0]!.id : null,
    inboundAmbiguous: active.length > 1,
    connectionAmbiguous: requested.length > 1 || (requested.length === 0 && active.length > 1),
  };
}
