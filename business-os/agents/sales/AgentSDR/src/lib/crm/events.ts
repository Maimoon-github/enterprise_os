import { crmEvents } from "./schema";
import type { CrmTransaction } from "./repository";
import { currentOrganizationId } from "@/lib/tenancy/scope";

export type CrmEventActor =
  | "ai"
  | "human"
  | "system"
  | "integration"
  | "authenticated_operator";

export type AppendCrmEventInput = {
  personId: string;
  crmRecordId?: string | null;
  pipelineId?: string | null;
  eventType: string;
  actorType: CrmEventActor;
  actorRef?: string | null;
  fromData?: Record<string, unknown> | null;
  toData?: Record<string, unknown> | null;
  meta?: Record<string, unknown> | null;
  contextVersion?: number | null;
  createdAt?: Date;
};

/**
 * Append an audit event using the caller's transaction. There is deliberately
 * no non-transactional overload: business state and its event must commit or
 * roll back together.
 */
export async function appendCrmEvent(
  tx: CrmTransaction,
  input: AppendCrmEventInput,
) {
  const eventType = input.eventType.trim();
  if (!eventType) throw new Error("CRM event type is required");
  if (Boolean(input.crmRecordId) !== Boolean(input.pipelineId)) {
    throw new Error("Record-scoped CRM events require both crmRecordId and pipelineId");
  }

  const [event] = await tx
    .insert(crmEvents)
    .values({
      organizationId: currentOrganizationId(),
      personId: input.personId,
      crmRecordId: input.crmRecordId ?? null,
      pipelineId: input.pipelineId ?? null,
      eventType,
      actorType: input.actorType,
      actorRef: input.actorRef?.trim() || null,
      fromData: input.fromData ?? null,
      toData: input.toData ?? null,
      meta: input.meta ?? null,
      contextVersion: input.contextVersion ?? null,
      createdAt: input.createdAt,
    })
    .returning();

  if (!event) throw new Error("CRM event insert did not return a row");
  return event;
}

