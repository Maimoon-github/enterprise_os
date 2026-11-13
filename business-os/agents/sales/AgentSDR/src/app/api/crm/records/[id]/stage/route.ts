import type { NextRequest } from "next/server";
import { crmOperationErrorResponse, requireInteger } from "@/lib/crm/api";
import {
  CrmConfigurationValidationError,
  assertExactKeys,
  assertObject,
  parseCategoryKey,
  parseOptionalText,
  parseUuid,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { moveRecordStage } from "@/lib/crm/operations";
import { STAGE_MOVE_NEXT, type StageMoveNext } from "@/lib/crm/stageMove";
import { runInOrganization } from "@/lib/tenancy/scope";

function parseOccurredAt(value: unknown): Date | null {
  if (value === undefined || value === null) return null;
  const parsed = typeof value === "string" ? new Date(value) : null;
  if (!parsed || Number.isNaN(parsed.getTime())) {
    throw new CrmConfigurationValidationError("occurredAt must be an ISO 8601 timestamp or null");
  }
  return parsed;
}

function parseNext(value: unknown): StageMoveNext {
  if (!STAGE_MOVE_NEXT.includes(value as StageMoveNext)) {
    throw new CrmConfigurationValidationError(`next must be one of: ${STAGE_MOVE_NEXT.join(", ")}`);
  }
  return value as StageMoveNext;
}

/** Move a record to another stage because something happened off-thread. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["categoryKey", "subcategoryId", "expectedContextVersion", "occurredAt", "note", "next"]);
      const result = await moveRecordStage({
        recordId: parseUuid((await params).id, "record id"),
        categoryKey: parseCategoryKey(value.categoryKey),
        subcategoryId: value.subcategoryId === null ? null : parseUuid(value.subcategoryId, "subcategoryId"),
        expectedContextVersion: requireInteger(value.expectedContextVersion, "expectedContextVersion"),
        occurredAt: parseOccurredAt(value.occurredAt),
        note: parseOptionalText(value.note, "note", 4_000),
        next: parseNext(value.next),
      });
      return Response.json(result);
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
