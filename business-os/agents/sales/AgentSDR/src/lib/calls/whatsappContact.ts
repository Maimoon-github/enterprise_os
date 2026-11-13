/**
 * The WhatsApp contact the recorder extension saves for a lead the first
 * time it calls them, so a callback or reply shows who it is: first name,
 * then the company in brackets — "Rahul (Acme D2C)". Pure; the extension
 * imports it.
 */

import type { RecorderLead } from "./contract";

export type WhatsappContactName = { firstName: string; lastName: string; display: string };

export function whatsappContactName(lead: RecorderLead | null): WhatsappContactName | null {
  const firstName = lead?.firstName?.trim();
  if (!firstName) return null;
  const company = lead?.company?.trim();
  const lastName = company ? `(${company})` : "";
  return { firstName, lastName, display: lastName ? `${firstName} ${lastName}` : firstName };
}
