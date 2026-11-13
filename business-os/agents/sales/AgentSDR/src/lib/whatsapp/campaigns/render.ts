import { personVariables, variableValue, type CompanyVariableSource, type PersonVariableSource } from "@/lib/leads/variables";
import { fillTemplate } from "@/lib/outreach/render";

const TOKEN_PATTERN = /\{\{\s*([^{}\r\n]+?)\s*\}\}/g;

/**
 * The merge-field bag for one campaign lead: the Person and their company,
 * then the lead's own spreadsheet columns (newer, campaign-specific, so
 * they win). A phone list often carries only a full name, so firstName and
 * lastName fall back to its words.
 */
export function campaignLeadVariables(
  person: PersonVariableSource,
  company: CompanyVariableSource | null,
  customFields: Record<string, string>,
): Record<string, string> {
  const variables = personVariables(person, company);
  const lowerKeys = new Map(Object.keys(variables).map((key) => [key.toLowerCase(), key]));
  for (const [key, value] of Object.entries(customFields)) {
    if (typeof value !== "string" || !value.trim()) continue;
    const existing = lowerKeys.get(key.toLowerCase());
    if (existing && existing !== key) delete variables[existing];
    variables[key] = value;
    lowerKeys.set(key.toLowerCase(), key);
  }
  const fullName = variableValue(variables, "fullName") ?? variableValue(variables, "name");
  const words = fullName?.trim().split(/\s+/).filter(Boolean) ?? [];
  if (!variableValue(variables, "firstName") && words[0]) variables.firstName = words[0];
  if (!variableValue(variables, "lastName") && words.length > 1) variables.lastName = words.slice(1).join(" ");
  return variables;
}

/** A step's text for one lead: spin text resolved, merge fields filled, ends trimmed. */
export function renderCampaignStep(body: string, variables: Record<string, string>): string {
  return fillTemplate(body, variables).trim();
}

/** Merge fields the body uses that this lead has no value for (they render as ""). */
export function unresolvedMergeFields(body: string, variables: Record<string, string>): string[] {
  const available = new Set(Object.keys(variables).map((key) => key.toLowerCase()));
  const used = new Set<string>();
  for (const match of body.matchAll(TOKEN_PATTERN)) used.add(match[1]!.trim());
  return [...used].filter((token) => token.toLowerCase() !== "signature" && !available.has(token.toLowerCase()));
}
