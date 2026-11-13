/**
 * What an inbox (LinkedIn or email Master Inbox) shows of a conversation's
 * CRM state.
 *
 * Client-safe: types and pure labelling only. The record-level readers that
 * build these from the database live in ./inboxContext.server; each inbox
 * adds its own channel lookup on top (src/lib/linkedin/messages/crmContext.server,
 * src/lib/inbox/crmContext.server). See connectionList.ts for why the split exists.
 */
import type { CrmWorkflowState } from "./schema";

export type InboxCrmStep = {
  position: number;
  /** Steps in the published version the run is on. */
  total: number;
  name: string;
  type: "reply" | "follow_up";
  status: "scheduled" | "drafting" | "awaiting_review" | "failed";
  dueAt: string | null;
};

/** Enough for a list row: who the lead is to the CRM and what comes next. */
export type InboxCrmSummary = {
  recordId: string;
  workflowState: CrmWorkflowState;
  categoryKey: string | null;
  subcategoryId: string | null;
  subcategoryName: string | null;
  nextActionAt: string | null;
  sequenceName: string | null;
  /** The active run's earliest unsent step, or null without an active run. */
  step: InboxCrmStep | null;
  /** An awaiting-review draft exists for this record. */
  hasDraft: boolean;
};

export type InboxCrmDraft = {
  id: string;
  revision: number;
  status: "generating" | "awaiting_review" | "failed";
  subject: string | null;
  /** Edited text when the operator saved one, else the AI text. */
  body: string;
  stepType: "reply" | "follow_up" | null;
  stepName: string | null;
  error: string | null;
};

/** The full strip for the open thread. */
export type InboxCrmContext = InboxCrmSummary & {
  conversationId: string;
  contextVersion: number;
  doNotContact: boolean;
  /** Latest classification row, which the human-classification PATCH expects. */
  classificationId: string | null;
  draft: InboxCrmDraft | null;
};

const DAY_MS = 24 * 60 * 60 * 1000;

function relativeDue(dueAt: string, now: Date): string {
  const delta = new Date(dueAt).getTime() - now.getTime();
  if (delta <= 0) return "due now";
  if (delta < DAY_MS) {
    const hours = Math.max(1, Math.round(delta / (60 * 60 * 1000)));
    return `due in ${hours}h`;
  }
  const days = Math.round(delta / DAY_MS);
  return `due in ${days}d`;
}

/**
 * One phrase for "what is the immediate step" — the list shows it where the
 * flat "Replied" status used to be, since every row there has replied.
 */
export function inboxCrmStepLabel(summary: InboxCrmSummary, now = new Date()): string {
  if (summary.workflowState === "closed") return "Closed";
  if (summary.workflowState === "paused") return "Paused";
  if (summary.workflowState === "error") return "Needs attention";
  if (summary.workflowState === "classifying" || summary.workflowState === "unclassified") return "Classifying";
  const step = summary.step;
  if (!step) return summary.hasDraft ? "Reply drafted" : "No next step";
  const name = step.type === "reply" ? "Reply" : `Follow-up ${step.position - 1}`;
  if (step.status === "awaiting_review") return `${name} drafted`;
  if (step.status === "drafting") return `${name} drafting`;
  if (step.status === "failed") return `${name} failed`;
  return step.dueAt ? `${name} ${relativeDue(step.dueAt, now)}` : `${name} scheduled`;
}
