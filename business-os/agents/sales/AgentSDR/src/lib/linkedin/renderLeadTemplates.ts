import { fillTemplate } from "@/lib/outreach/render";
import type { LeadMessageField } from "@/lib/linkedin/leadMessages";

export type LeadMessageTemplates = Record<LeadMessageField, string | null>;

export function renderLeadTemplates(
  templates: LeadMessageTemplates,
  variables: Record<string, string>,
): LeadMessageTemplates {
  return Object.fromEntries(
    Object.entries(templates).map(([key, template]) => [
      key,
      template ? fillTemplate(template, variables) : null,
    ]),
  ) as LeadMessageTemplates;
}
