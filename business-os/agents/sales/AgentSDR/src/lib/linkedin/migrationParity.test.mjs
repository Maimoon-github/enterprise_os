import { describe, expect, test } from "bun:test";
import {
  classifyWebhookOwnership,
  compareEligibleAccountIds,
  compareLinkedinLead,
  legacyNextAction,
  peopleNextAction,
} from "./migrationParity.ts";

const NOW = new Date("2026-08-27T12:00:00Z");

function lead(overrides = {}) {
  return {
    id: "lead-1",
    status: "PENDING",
    campaignStatus: "ACTIVE",
    campaignId: "campaign-1",
    personId: "person-1",
    providerId: "provider-1",
    linkedinAccountId: null,
    legacyLinkedinUrl: "pat-lee",
    personLinkedinUrl: "pat-lee",
    sourceLinkedinIdentifier: null,
    sourceLinkedinApi: null,
    inviteRetryCount: 0,
    resolveRetryCount: 0,
    resolveNextAttemptAt: null,
    requestSentAt: null,
    acceptMessageSentAt: null,
    followUp1SentAt: null,
    followUp2SentAt: null,
    connectionChatId: null,
    leadTemplates: { invitationMessage: "Hi Pat" },
    campaignTemplates: {},
    variables: { firstName: "Pat" },
    canonicalMessageTypes: new Set(),
    ...overrides,
  };
}

describe("LinkedIn old/new next-action parity", () => {
  test("keeps a resolved invitation target and next action unchanged", () => {
    const result = compareLinkedinLead(lead(), NOW);
    expect(result.targetCompatible).toBe(true);
    expect(result.differences).toEqual([]);
  });

  test("uses the exact unresolved source identifier for resolution", () => {
    const item = lead({
      providerId: null,
      personLinkedinUrl: null,
      legacyLinkedinUrl: "https://linkedin.com/sales/lead/ENCODED",
      sourceLinkedinIdentifier: "https://linkedin.com/sales/lead/ENCODED",
      sourceLinkedinApi: "sales_navigator",
    });
    expect(legacyNextAction(item, NOW).action).toBe("resolve_profile");
    expect(peopleNextAction(item, NOW).action).toBe("resolve_profile");
    expect(compareLinkedinLead(item, NOW).differences).toEqual([]);
  });

  test("allows a migrated provider id to take the safer resolution detour", () => {
    const result = compareLinkedinLead(lead({ sourceLinkedinIdentifier: "stale-source" }), NOW);
    expect(result.legacy.action).toBe("send_invitation");
    expect(result.current.action).toBe("resolve_profile");
    expect(result.safeResolutionDetour).toBe(true);
    expect(result.differences).toEqual([]);
  });

  test("does not require an invitation target after the request was sent", () => {
    const result = compareLinkedinLead(lead({
      status: "REQUEST_SENT",
      providerId: "provider-1",
      personLinkedinUrl: null,
      sourceLinkedinIdentifier: "provider-1",
    }), NOW);
    expect(result.targetCompatible).toBe(true);
    expect(result.differences).toEqual([]);
  });

  test("detects campaign-template or People-variable content drift", () => {
    const result = compareLinkedinLead(lead({
      leadTemplates: { invitationMessage: "Hi Pat" },
      campaignTemplates: { invitationMessage: "Hi {{firstName}} from the new campaign" },
    }), NOW);
    expect(result.differences).toContain("rendered_content");
  });

  test("canonical message claims prevent acceptance and follow-up replay after restart", () => {
    const acceptance = peopleNextAction(lead({
      status: "REQUEST_SENT",
      connectionChatId: "chat-1",
      leadTemplates: { acceptanceMessage: "Thanks" },
      canonicalMessageTypes: new Set(["ACCEPTANCE"]),
    }), NOW);
    expect(acceptance).toMatchObject({ action: "advance_acceptance", reason: "already_claimed" });

    const followUp = peopleNextAction(lead({
      status: "ACCEPT_MESSAGE_SENT",
      acceptMessageSentAt: new Date("2026-08-25T00:00:00Z"),
      leadTemplates: { followUp1Message: "Checking in" },
      canonicalMessageTypes: new Set(["FOLLOW_UP_1"]),
    }), NOW);
    expect(followUp).toMatchObject({ action: "advance_existing_claim", reason: "already_claimed" });
  });

  test("an existing invitation claim blocks provider replay until reconciliation", () => {
    const result = compareLinkedinLead(lead({ canonicalMessageTypes: new Set(["INVITATION"]) }), NOW);
    expect(result.current.action).toBe("wait_invitation_reconciliation");
    expect(result.current.reason).toBe("already_claimed");
    expect(result.differences).not.toContain("invitation_restart_duplicate_risk");
    expect(result.differences).not.toContain("next_action");
  });
});

describe("LinkedIn webhook ownership parity", () => {
  const candidate = (id, status, overrides = {}) => ({
    id,
    status,
    superseded: false,
    requestSentAt: new Date("2026-08-20T00:00:00Z"),
    createdAt: new Date("2026-08-01T00:00:00Z"),
    ...overrides,
  });

  test("routes an unambiguous provider/account pair to exactly one Lead", () => {
    expect(classifyWebhookOwnership([candidate("lead-1", "REQUEST_SENT")])).toMatchObject({
      inboundOwnerId: "lead-1",
      connectionOwnerId: "lead-1",
      inboundAmbiguous: false,
      connectionAmbiguous: false,
    });
  });

  test("rejects multiple request owners", () => {
    const result = classifyWebhookOwnership([
      candidate("lead-1", "REQUEST_SENT"),
      candidate("lead-2", "REQUEST_SENT"),
    ]);
    expect(result.inboundOwnerId).toBeNull();
    expect(result.connectionOwnerId).toBeNull();
    expect(result.connectionAmbiguous).toBe(true);
  });

  test("rejects an ambiguous connection-accepted fallback", () => {
    const result = classifyWebhookOwnership([
      candidate("lead-1", "CONNECTED"),
      candidate("lead-2", "REPLIED"),
    ]);
    expect(result.inboundOwnerId).toBeNull();
    expect(result.connectionAmbiguous).toBe(true);
    expect(result.connectionOwnerId).toBeNull();
  });

  test("ignores explicitly superseded history", () => {
    const result = classifyWebhookOwnership([
      candidate("canonical", "REQUEST_SENT"),
      candidate("history", "CANCELLED", { superseded: true }),
    ]);
    expect(result.inboundOwnerId).toBe("canonical");
    expect(result.connectionOwnerId).toBe("canonical");
  });
});

describe("LinkedIn account assignment parity", () => {
  test("compares candidate senders after old URL and new Person exclusion rules", () => {
    expect(compareEligibleAccountIds(["b", "a"], new Set(["b"]), new Set(["b"]))).toEqual({
      legacy: ["a"], current: ["a"], matches: true, safeNarrowing: true,
    });
    expect(compareEligibleAccountIds(["a", "b"], new Set(["a"]), new Set(["b"]))).toMatchObject({
      legacy: ["b"], current: ["a"], matches: false, safeNarrowing: false,
    });
    expect(compareEligibleAccountIds(["a", "b"], new Set(), new Set(["b"]))).toMatchObject({
      legacy: ["a", "b"], current: ["a"], matches: false, safeNarrowing: true,
    });
  });
});
