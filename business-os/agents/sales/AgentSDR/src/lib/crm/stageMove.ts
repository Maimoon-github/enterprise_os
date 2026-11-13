import { and, desc, eq, gt } from "drizzle-orm";
import type { CrmTransaction } from "./repository";
import { crmEvents, crmSubcategories } from "./schema";
import { inOrg } from "@/lib/tenancy/scope";

/** Event a person's stage move records; see `moveRecordStage`. */
export const STAGE_MOVED_EVENT = "stage.moved";

/** After a stage move: schedule the follow-ups, or draft a reply now. */
export type StageMoveNext = "follow_up" | "reply";
export const STAGE_MOVE_NEXT: readonly StageMoveNext[] = ["follow_up", "reply"];

export type StageMoveContext = {
  stage: string;
  occurredAt: string;
  note: string | null;
};

/**
 * The stage move a draft should know about: the newest one since the lead
 * last wrote, provided the record is still at the stage it moved to. A newer
 * inbound reply supersedes it — that reply is classified afresh and becomes
 * the brief — and so does any later change of stage.
 */
export async function currentStageMoveInTransaction(
  tx: CrmTransaction,
  record: { id: string; subcategoryId: string | null; lastInboundAt: Date | null },
): Promise<StageMoveContext | null> {
  const [event] = await tx.select({ toData: crmEvents.toData, meta: crmEvents.meta })
    .from(crmEvents)
    .where(and(
      inOrg(crmEvents),
      eq(crmEvents.crmRecordId, record.id),
      eq(crmEvents.eventType, STAGE_MOVED_EVENT),
      record.lastInboundAt ? gt(crmEvents.createdAt, record.lastInboundAt) : undefined,
    ))
    .orderBy(desc(crmEvents.createdAt))
    .limit(1);
  if (!event || (event.toData?.subcategoryId ?? null) !== record.subcategoryId) return null;
  const [subcategory] = record.subcategoryId
    ? await tx.select({ name: crmSubcategories.name }).from(crmSubcategories)
      .where(eq(crmSubcategories.id, record.subcategoryId)).limit(1)
    : [];
  const occurredAt = typeof event.meta?.occurredAt === "string" ? event.meta.occurredAt : null;
  if (!occurredAt) return null;
  return {
    stage: subcategory?.name ?? String(event.toData?.categoryKey ?? "a new stage"),
    occurredAt,
    note: typeof event.meta?.note === "string" && event.meta.note.trim() ? event.meta.note.trim() : null,
  };
}
