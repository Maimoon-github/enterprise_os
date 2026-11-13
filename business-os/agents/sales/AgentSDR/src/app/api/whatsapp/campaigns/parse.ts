import {
  assertExactKeys,
  assertObject,
  CrmConfigurationValidationError,
  parseRequiredText,
} from "@/lib/crm/categories";
import {
  WHATSAPP_CAMPAIGN_STATUSES,
  type CreateWhatsappCampaignRequest,
  type UpdateWhatsappCampaignRequest,
  type WhatsappCampaignStatus,
  type WhatsappCampaignStep,
} from "@/lib/whatsapp/campaigns/contract";

/** Request-body parsing shared by the campaign routes (not a route: Next ignores files other than route.ts). */

export function parseName(value: unknown): string {
  return parseRequiredText(value, "name", 120);
}

/** Blank text clears the description. */
export function parseDescription(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value !== "string") throw new CrmConfigurationValidationError("description must be a string");
  const clean = value.trim();
  if (clean.length > 2000) throw new CrmConfigurationValidationError("description must be at most 2000 characters");
  return clean || null;
}

export function parseAccountIds(value: unknown): string[] {
  if (!Array.isArray(value) || value.some((id) => typeof id !== "string")) {
    throw new CrmConfigurationValidationError("accountIds must be an array of ids");
  }
  return value as string[];
}

export function parseSteps(value: unknown): WhatsappCampaignStep[] {
  if (!Array.isArray(value)) throw new CrmConfigurationValidationError("steps must be an array");
  return value.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) throw new CrmConfigurationValidationError(`steps[${index}] must be an object`);
    const step = item as Record<string, unknown>;
    if (typeof step.id !== "string") throw new CrmConfigurationValidationError(`steps[${index}].id must be a string`);
    if (typeof step.body !== "string") throw new CrmConfigurationValidationError(`steps[${index}].body must be a string`);
    if (typeof step.delayHours !== "number" || !Number.isFinite(step.delayHours)) {
      throw new CrmConfigurationValidationError(`steps[${index}].delayHours must be a number`);
    }
    return { id: step.id, body: step.body, delayHours: step.delayHours };
  });
}

export function parseCreateRequest(value: unknown): CreateWhatsappCampaignRequest {
  assertObject(value);
  assertExactKeys(value, ["name", "description", "accountIds", "steps"]);
  return {
    name: parseName(value.name),
    description: value.description === undefined ? null : parseDescription(value.description),
    accountIds: value.accountIds === undefined ? [] : parseAccountIds(value.accountIds),
    steps: value.steps === undefined ? [] : parseSteps(value.steps),
  };
}

export function parseUpdateRequest(value: unknown): UpdateWhatsappCampaignRequest {
  assertObject(value);
  assertExactKeys(value, ["name", "description", "accountIds", "steps", "status"]);
  const request: UpdateWhatsappCampaignRequest = {};
  if (value.name !== undefined) request.name = parseName(value.name);
  if (value.description !== undefined) request.description = parseDescription(value.description);
  if (value.accountIds !== undefined) request.accountIds = parseAccountIds(value.accountIds);
  if (value.steps !== undefined) request.steps = parseSteps(value.steps);
  if (value.status !== undefined) {
    if (typeof value.status !== "string" || !(WHATSAPP_CAMPAIGN_STATUSES as readonly string[]).includes(value.status)) {
      throw new CrmConfigurationValidationError("status must be one of: active, paused");
    }
    request.status = value.status as WhatsappCampaignStatus;
  }
  return request;
}
