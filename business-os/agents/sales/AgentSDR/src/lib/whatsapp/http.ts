import "server-only";

import {
  assertExactKeys,
  assertObject,
  CrmConfigurationValidationError,
  parseRequiredText,
  parseUuid,
} from "@/lib/crm/categories";
import { numberRule, ruleError } from "@/lib/channels/rules";
import type { SendWhatsappRequest } from "./contract";
import { WhatsappApiError } from "./errors";

/** Request parsing for src/app/api/whatsapp/**. Strict: unknown fields are refused. */

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A path id that is not a UUID cannot exist: 404, before it reaches a uuid column. */
export function assertIdParam(value: string, label: string): string {
  if (!UUID_PATTERN.test(value)) throw new WhatsappApiError(404, `${label} not found`);
  return value;
}

/** An optional query-string UUID: absent → null, malformed → 400. */
export function optionalUuidQuery(value: string | null, label: string): string | null {
  if (!value) return null;
  if (!UUID_PATTERN.test(value)) throw new WhatsappApiError(400, `${label} must be a UUID`);
  return value;
}

function optionalUuid(value: unknown, label: string): string | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return parseUuid(value, label);
}

export function parseSendWhatsappRequest(value: unknown): SendWhatsappRequest {
  assertObject(value);
  assertExactKeys(value, ["chatId", "personId", "phone", "accountId", "text", "callSessionId", "campaignContactId"]);
  const targets = (["chatId", "personId", "phone"] as const).filter((key) => value[key] !== undefined && value[key] !== null);
  if (targets.length !== 1) {
    throw new CrmConfigurationValidationError("Give exactly one of chatId, personId or phone");
  }
  const chatId = optionalUuid(value.chatId, "chatId") ?? undefined;
  const personId = optionalUuid(value.personId, "personId") ?? undefined;
  const phone = value.phone === undefined || value.phone === null ? undefined : parseRequiredText(value.phone, "phone", 40);
  const accountId = optionalUuid(value.accountId, "accountId") ?? undefined;
  if (typeof value.text !== "string" || !value.text.trim()) throw new CrmConfigurationValidationError("text is required");
  if (value.text.length > 4096) throw new CrmConfigurationValidationError("text must be at most 4096 characters");
  return {
    ...(chatId ? { chatId } : {}),
    ...(personId ? { personId } : {}),
    ...(phone ? { phone } : {}),
    ...(accountId ? { accountId } : {}),
    // Kept as typed (only checked for being non-blank): WhatsApp shows leading line breaks and spacing.
    text: value.text,
    callSessionId: optionalUuid(value.callSessionId, "callSessionId") ?? null,
    campaignContactId: optionalUuid(value.campaignContactId, "campaignContactId") ?? null,
  };
}

export type WhatsappAccountUpdate = { isDefault: true } | { newChatsPerDay: number | null };

/** `{ isDefault: true }`, or `{ newChatsPerDay }` — the number's own limit, null to follow the organization. */
export function parseAccountUpdateRequest(value: unknown): WhatsappAccountUpdate {
  assertObject(value);
  if ("newChatsPerDay" in value) {
    assertExactKeys(value, ["newChatsPerDay"]);
    if (value.newChatsPerDay === null) return { newChatsPerDay: null };
    const error = ruleError(numberRule("whatsapp", "newChatsPerDay"), value.newChatsPerDay);
    if (error) throw new CrmConfigurationValidationError(error);
    return { newChatsPerDay: value.newChatsPerDay as number };
  }
  assertExactKeys(value, ["isDefault"]);
  if (value.isDefault !== true) {
    throw new CrmConfigurationValidationError("isDefault must be true — make another account the default instead");
  }
  return { isDefault: true };
}
