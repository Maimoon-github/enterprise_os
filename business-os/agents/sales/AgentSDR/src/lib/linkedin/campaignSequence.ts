import { MAX_INVITATION_MESSAGE_LENGTH } from "./invitationMessage";

export const LINKEDIN_SEQUENCE_FIELDS = [
  "invitationMessage",
  "acceptanceMessage",
  "followUp1Message",
  "followUp2Message",
  "followUp3Message",
] as const;

export type LinkedinSequenceField = (typeof LINKEDIN_SEQUENCE_FIELDS)[number];
export type LinkedinCampaignSequence = Record<LinkedinSequenceField, string>;

export const EMPTY_LINKEDIN_SEQUENCE: LinkedinCampaignSequence = {
  invitationMessage: "",
  acceptanceMessage: "",
  followUp1Message: "",
  followUp2Message: "",
  followUp3Message: "",
};

export const LINKEDIN_SEQUENCE_STEPS: {
  field: LinkedinSequenceField;
  label: string;
  shortLabel: string;
  timing: string;
  description: string;
}[] = [
  {
    field: "invitationMessage",
    label: "Connection request",
    shortLabel: "Invitation",
    timing: "Immediately",
    description: "Sent with the connection request. Leave blank to send without a note.",
  },
  {
    field: "acceptanceMessage",
    label: "Acceptance message",
    shortLabel: "On acceptance",
    timing: "When accepted",
    description: "Sent as soon as the prospect accepts your connection request.",
  },
  {
    field: "followUp1Message",
    label: "Follow-up 1",
    shortLabel: "Follow-up 1",
    timing: "1 day later",
    description: "Sent one day after the acceptance message.",
  },
  {
    field: "followUp2Message",
    label: "Follow-up 2",
    shortLabel: "Follow-up 2",
    timing: "2 days later",
    description: "Sent two days after follow-up 1.",
  },
  {
    field: "followUp3Message",
    label: "Follow-up 3",
    shortLabel: "Follow-up 3",
    timing: "3 days later",
    description: "Sent three days after follow-up 2, then the sequence completes.",
  },
];

export function normalizeLinkedinSequence(
  input: Partial<Record<LinkedinSequenceField, unknown>>,
): LinkedinCampaignSequence {
  return Object.fromEntries(
    LINKEDIN_SEQUENCE_FIELDS.map((field) => [
      field,
      typeof input[field] === "string" ? input[field].trim() : "",
    ]),
  ) as LinkedinCampaignSequence;
}

export function linkedinSequenceError(sequence: LinkedinCampaignSequence): string | null {
  if (sequence.invitationMessage.length > MAX_INVITATION_MESSAGE_LENGTH) {
    return `Invitation message must be ${MAX_INVITATION_MESSAGE_LENGTH} characters or fewer`;
  }

  const followUps = [sequence.followUp1Message, sequence.followUp2Message, sequence.followUp3Message];
  const firstGap = followUps.findIndex((message) => !message.trim());
  if (firstGap >= 0 && followUps.slice(firstGap + 1).some((message) => message.trim())) {
    return `Add follow-up ${firstGap + 1} before adding a later follow-up`;
  }
  return null;
}
