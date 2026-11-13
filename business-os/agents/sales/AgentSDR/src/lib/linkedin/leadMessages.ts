const STATUS_ORDER = [
  "PENDING",
  "REQUEST_SENT",
  "ACCEPT_MESSAGE_SENT",
  "FOLLOW_UP_1_SENT",
  "FOLLOW_UP_2_SENT",
  "FOLLOW_UP_3_SENT",
  "COMPLETED",
  "REPLIED",
] as const;

const STATUS_RANK: Record<string, number> = Object.fromEntries(
  STATUS_ORDER.map((s, i) => [s, i])
);

export type LeadMessageField =
  | "invitationMessage"
  | "acceptanceMessage"
  | "followUp1Message"
  | "followUp2Message"
  | "followUp3Message";

export const LEAD_MESSAGE_FIELDS: {
  key: LeadMessageField;
  label: string;
}[] = [
  { key: "invitationMessage", label: "Invitation" },
  { key: "acceptanceMessage", label: "Acceptance" },
  { key: "followUp1Message", label: "Follow-up 1" },
  { key: "followUp2Message", label: "Follow-up 2" },
  { key: "followUp3Message", label: "Follow-up 3" },
];

export const isMessageEditable = (messageKey: LeadMessageField, status: string): boolean => {
  switch (messageKey) {
    case "invitationMessage":
      return status === "PENDING";
    case "acceptanceMessage":
      return (STATUS_RANK[status] ?? 0) < STATUS_RANK.ACCEPT_MESSAGE_SENT;
    case "followUp1Message":
      return (STATUS_RANK[status] ?? 0) < STATUS_RANK.FOLLOW_UP_1_SENT;
    case "followUp2Message":
      return (STATUS_RANK[status] ?? 0) < STATUS_RANK.FOLLOW_UP_2_SENT;
    case "followUp3Message":
      return (STATUS_RANK[status] ?? 0) < STATUS_RANK.FOLLOW_UP_3_SENT;
    default:
      return false;
  }
};

export const sentAtForField = (
  key: LeadMessageField,
  lead: {
    requestSentAt: string | null;
    acceptMessageSentAt: string | null;
    followUp1SentAt: string | null;
    followUp2SentAt: string | null;
    followUp3SentAt: string | null;
    status: string;
  }
): string | null => {
  switch (key) {
    case "invitationMessage":
      return lead.requestSentAt;
    case "acceptanceMessage":
      return lead.acceptMessageSentAt ??
        (lead.status !== "PENDING" && lead.status !== "REQUEST_SENT" ? "sent" : null);
    case "followUp1Message":
      return lead.followUp1SentAt;
    case "followUp2Message":
      return lead.followUp2SentAt;
    case "followUp3Message":
      return lead.followUp3SentAt;
    default:
      return null;
  }
};
