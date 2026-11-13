/** Shared retry budget for profile resolve, invite send, and follow-up send. */
export const MAX_LEAD_RETRIES = 3;

/** @deprecated Use MAX_LEAD_RETRIES */
export const MAX_INVITE_SEND_RETRIES = MAX_LEAD_RETRIES;

export type LeadRetryContext = "resolveProfiles" | "sendInvitations" | "sendFollowUps";

/** Reset retry count after a successful resolve or send so the next stage gets a fresh budget. */
