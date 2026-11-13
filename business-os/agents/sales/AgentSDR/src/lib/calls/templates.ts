/**
 * Fills the follow-up message offered after an outcome is marked. Pure and
 * client-safe: the page renders it, the rep edits it, then it opens in
 * WhatsApp.
 */

import { CONTACT_CALL_STATUS_DEFINITIONS, type ContactCallStatus } from "./contract";

export type TemplateLead = { firstName: string | null; fullName: string | null };

/** The lead's first name for a greeting, or "there" ("Hi there"). */
export function greetingName(lead: TemplateLead): string {
  const first = lead.firstName?.trim() || lead.fullName?.trim().split(/\s+/)[0];
  return first || "there";
}

export function renderTemplate(template: string, lead: TemplateLead): string {
  return template.replace(/\{\{\s*firstName\s*\}\}/gi, greetingName(lead));
}

/** The message offered for a call status, or null when none should be sent. */
export function followUpMessageFor(callStatus: ContactCallStatus, lead: TemplateLead): string | null {
  const template = CONTACT_CALL_STATUS_DEFINITIONS[callStatus].template;
  return template === null ? null : renderTemplate(template, lead);
}
