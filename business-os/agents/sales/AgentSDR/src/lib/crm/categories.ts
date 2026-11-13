import { randomUUID } from "node:crypto";
import { and, asc, count, eq, inArray, or } from "drizzle-orm";
import { authContextErrorResponse } from "@/lib/auth/context";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { ensureCrmDefaults } from "./defaults";
import {
  CrmRequestError,
  crmRequestErrorResponse,
} from "./http";
import {
  CrmConflictError,
  CrmNotFoundError,
  withCrmTransaction,
} from "./repository";
import {
  crmCategories,
  crmClassifications,
  crmPipelines,
  crmRecords,
  crmSequenceRuns,
  crmSubcategories,
  crmSubcategorySequenceAssignments,
  type CrmCategoryKey,
} from "./schema";

const CATEGORY_KEYS = new Set<CrmCategoryKey>([
  "customer",
  "interested",
  "not_interested",
  "other",
]);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export class CrmConfigurationValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CrmConfigurationValidationError";
  }
}

export function assertObject(value: unknown, label = "Request body"): asserts value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CrmConfigurationValidationError(`${label} must be a JSON object`);
  }
}

export async function readCrmJson(request: Request): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    throw new CrmConfigurationValidationError("Request body must contain valid JSON");
  }
}

export function assertExactKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
): void {
  const extras = Object.keys(value).filter((key) => !allowed.includes(key));
  if (extras.length > 0) {
    throw new CrmConfigurationValidationError(`Unknown field${extras.length === 1 ? "" : "s"}: ${extras.join(", ")}`);
  }
}

export function parseUuid(value: unknown, label: string): string {
  if (typeof value !== "string" || !UUID_PATTERN.test(value)) {
    throw new CrmConfigurationValidationError(`${label} must be a UUID`);
  }
  return value;
}

export function parseRequiredText(value: unknown, label: string, maxLength = 200): string {
  if (typeof value !== "string") {
    throw new CrmConfigurationValidationError(`${label} must be a string`);
  }
  const clean = value.trim();
  if (!clean) throw new CrmConfigurationValidationError(`${label} is required`);
  if (clean.length > maxLength) {
    throw new CrmConfigurationValidationError(`${label} must be at most ${maxLength} characters`);
  }
  return clean;
}

export function parseOptionalText(
  value: unknown,
  label: string,
  maxLength: number,
): string | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return parseRequiredText(value, label, maxLength);
}

export function parseBoolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") {
    throw new CrmConfigurationValidationError(`${label} must be a boolean`);
  }
  return value;
}

export function parseNonNegativeInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new CrmConfigurationValidationError(`${label} must be a non-negative integer`);
  }
  return value;
}

/** A funnel rank: a positive integer, or null for "not a funnel stage". */
export function parseStageRank(value: unknown): number | null {
  if (value === null) return null;
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1) {
    throw new CrmConfigurationValidationError("stageRank must be a positive integer or null");
  }
  return value;
}

export function parseCategoryKey(value: unknown): CrmCategoryKey {
  if (typeof value !== "string" || !CATEGORY_KEYS.has(value as CrmCategoryKey)) {
    throw new CrmConfigurationValidationError("categoryKey must be a fixed CRM category key");
  }
  return value as CrmCategoryKey;
}

export function slugifySubcategoryKey(name: string): string {
  const slug = name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80)
    .replace(/_+$/g, "");
  const safe = /^[a-z]/.test(slug) ? slug : `subcategory_${slug}`;
  return safe || `subcategory_${randomUUID().replaceAll("-", "").slice(0, 12)}`;
}

export function crmConfigurationErrorResponse(error: unknown): Response {
  const authError = authContextErrorResponse(error);
  if (authError) return authError;
  const requestError = crmRequestErrorResponse(error);
  if (requestError) return requestError;
  if (error instanceof CrmConfigurationValidationError) {
    return Response.json({ error: error.message, code: "VALIDATION_ERROR" }, { status: 400 });
  }
  if (error instanceof CrmNotFoundError) {
    return Response.json({ error: error.message, code: "NOT_FOUND" }, { status: 404 });
  }
  if (error instanceof CrmConflictError) {
    return Response.json({ error: error.message, code: "CONFLICT" }, { status: 409 });
  }
  // Drizzle wraps driver errors in DrizzleQueryError; the Postgres code is on its cause.
  const pgError = error as { code?: string; cause?: { code?: string } } | null;
  const code = pgError?.code ?? pgError?.cause?.code;
  if (code === "23505") {
    return Response.json({ error: "That configuration already exists", code: "CONFLICT" }, { status: 409 });
  }
  if (code === "23503" || code === "23514") {
    return Response.json({ error: "Configuration violates a CRM rule", code: "INVALID_CONFIGURATION" }, { status: 409 });
  }
  if (error instanceof CrmRequestError) {
    return Response.json({ error: error.message, code: error.code }, { status: error.status });
  }
  console.error("CRM configuration request failed", error);
  return Response.json({ error: "CRM configuration request failed", code: "INTERNAL_ERROR" }, { status: 500 });
}

/** The given pipeline, or the organization's default one (created on first use). */
export async function resolvePipelineId(pipelineId?: string): Promise<string> {
  if (pipelineId) {
    parseUuid(pipelineId, "pipelineId");
    const [pipeline] = await db.select().from(crmPipelines)
      .where(and(inOrg(crmPipelines), eq(crmPipelines.id, pipelineId))).limit(1);
    if (!pipeline) throw new CrmNotFoundError("CRM pipeline", pipelineId);
    return pipeline.id;
  }
  // A new organization has no pipeline yet; it gets its defaults on first use.
  return (await ensureCrmDefaults()).pipelineId;
}

export async function listCategoryConfiguration(pipelineId?: string) {
  const resolvedPipelineId = await resolvePipelineId(pipelineId);
  const [categories, subcategories, assignments, recordCounts] = await Promise.all([
    db.select().from(crmCategories).orderBy(asc(crmCategories.sortOrder)),
    db
      .select()
      .from(crmSubcategories)
      .where(eq(crmSubcategories.pipelineId, resolvedPipelineId))
      .orderBy(asc(crmSubcategories.categoryKey), asc(crmSubcategories.sortOrder), asc(crmSubcategories.name)),
    db.select().from(crmSubcategorySequenceAssignments).where(inArray(
      crmSubcategorySequenceAssignments.subcategoryId,
      db.select({ id: crmSubcategories.id }).from(crmSubcategories)
        .where(eq(crmSubcategories.pipelineId, resolvedPipelineId)),
    )),
    db.select({ subcategoryId: crmRecords.subcategoryId, count: count() }).from(crmRecords)
      .where(and(inOrg(crmRecords), eq(crmRecords.pipelineId, resolvedPipelineId))).groupBy(crmRecords.subcategoryId),
  ]);
  const assignmentMap = new Map(assignments.map((assignment) => [assignment.subcategoryId, assignment.sequenceId]));
  const countMap = new Map(recordCounts.map((row) => [row.subcategoryId, Number(row.count)]));
  return {
    pipelineId: resolvedPipelineId,
    categories: categories.map((category) => ({
      ...category,
      subcategories: subcategories.filter((subcategory) => subcategory.categoryKey === category.key).map((subcategory) => ({
        ...subcategory,
        sequenceId: assignmentMap.get(subcategory.id) ?? null,
        activeRecordCount: countMap.get(subcategory.id) ?? 0,
      })),
    })),
  };
}

export async function listSubcategories(input: { pipelineId?: string; includeArchived?: boolean }) {
  const pipelineId = await resolvePipelineId(input.pipelineId);
  const rows = await db
    .select()
    .from(crmSubcategories)
    .where(and(
      eq(crmSubcategories.pipelineId, pipelineId),
      input.includeArchived ? undefined : eq(crmSubcategories.active, true),
    ))
    .orderBy(asc(crmSubcategories.categoryKey), asc(crmSubcategories.sortOrder), asc(crmSubcategories.name));
  return { pipelineId, subcategories: rows };
}

/** Subcategories inherit their organization from the pipeline they belong to. */
function inOrgPipelines() {
  return inArray(crmSubcategories.pipelineId, db.select({ id: crmPipelines.id }).from(crmPipelines).where(inOrg(crmPipelines)));
}

export async function getSubcategory(id: string) {
  parseUuid(id, "subcategory id");
  const [subcategory] = await db.select().from(crmSubcategories)
    .where(and(inOrgPipelines(), eq(crmSubcategories.id, id))).limit(1);
  if (!subcategory) throw new CrmNotFoundError("CRM subcategory", id);
  return subcategory;
}

export type CreateSubcategoryInput = {
  pipelineId: string;
  categoryKey: CrmCategoryKey;
  name: string;
  description: string | null;
  classificationGuidance: string | null;
  reviewRequired: boolean;
  sortOrder: number;
  stageRank: number | null;
};

export function parseCreateSubcategoryInput(value: unknown): CreateSubcategoryInput {
  assertObject(value);
  assertExactKeys(value, [
    "pipelineId",
    "categoryKey",
    "name",
    "description",
    "classificationGuidance",
    "reviewRequired",
    "sortOrder",
    "stageRank",
  ]);
  return {
    pipelineId: parseUuid(value.pipelineId, "pipelineId"),
    categoryKey: parseCategoryKey(value.categoryKey),
    name: parseRequiredText(value.name, "name", 120),
    description: parseOptionalText(value.description, "description", 2_000) ?? null,
    classificationGuidance: parseOptionalText(
      value.classificationGuidance,
      "classificationGuidance",
      8_000,
    ) ?? null,
    reviewRequired: value.reviewRequired === undefined
      ? false
      : parseBoolean(value.reviewRequired, "reviewRequired"),
    sortOrder: value.sortOrder === undefined ? 0 : parseNonNegativeInteger(value.sortOrder, "sortOrder"),
    stageRank: value.stageRank === undefined ? null : parseStageRank(value.stageRank),
  };
}

export async function createSubcategory(value: unknown) {
  const input = parseCreateSubcategoryInput(value);
  return withCrmTransaction(async (tx) => {
    const [pipeline] = await tx.select().from(crmPipelines)
      .where(and(inOrg(crmPipelines), eq(crmPipelines.id, input.pipelineId))).limit(1);
    if (!pipeline) throw new CrmNotFoundError("CRM pipeline", input.pipelineId);
    if (!pipeline.active) throw new CrmConflictError("Cannot add a subcategory to an inactive pipeline");
    const [category] = await tx
      .select()
      .from(crmCategories)
      .where(eq(crmCategories.key, input.categoryKey))
      .limit(1);
    if (!category?.isSystem) throw new CrmConflictError("CRM categories are fixed system configuration");
    const [created] = await tx
      .insert(crmSubcategories)
      .values({ ...input, key: slugifySubcategoryKey(input.name) })
      .returning();
    if (!created) throw new Error("CRM subcategory insert did not return a row");
    return created;
  });
}

export type UpdateSubcategoryInput = {
  name?: string;
  description?: string | null;
  classificationGuidance?: string | null;
  reviewRequired?: boolean;
  sortOrder?: number;
  stageRank?: number | null;
  active?: boolean;
};

export function parseUpdateSubcategoryInput(value: unknown): UpdateSubcategoryInput {
  assertObject(value);
  assertExactKeys(value, [
    "name",
    "description",
    "classificationGuidance",
    "reviewRequired",
    "sortOrder",
    "stageRank",
    "active",
  ]);
  const parsed: UpdateSubcategoryInput = {};
  if (value.name !== undefined) parsed.name = parseRequiredText(value.name, "name", 120);
  if (value.description !== undefined) parsed.description = parseOptionalText(value.description, "description", 2_000) ?? null;
  if (value.classificationGuidance !== undefined) {
    parsed.classificationGuidance = parseOptionalText(value.classificationGuidance, "classificationGuidance", 8_000) ?? null;
  }
  if (value.reviewRequired !== undefined) parsed.reviewRequired = parseBoolean(value.reviewRequired, "reviewRequired");
  if (value.sortOrder !== undefined) parsed.sortOrder = parseNonNegativeInteger(value.sortOrder, "sortOrder");
  if (value.stageRank !== undefined) parsed.stageRank = parseStageRank(value.stageRank);
  if (value.active !== undefined) parsed.active = parseBoolean(value.active, "active");
  if (Object.keys(parsed).length === 0) {
    throw new CrmConfigurationValidationError("At least one editable field is required");
  }
  return parsed;
}

export async function updateSubcategory(id: string, value: unknown) {
  parseUuid(id, "subcategory id");
  const input = parseUpdateSubcategoryInput(value);
  const [updated] = await db
    .update(crmSubcategories)
    .set({ ...input, updatedAt: new Date() })
    .where(and(inOrgPipelines(), eq(crmSubcategories.id, id)))
    .returning();
  if (!updated) throw new CrmNotFoundError("CRM subcategory", id);
  return updated;
}

/**
 * Every foreign key into crm_subcategories is ON DELETE RESTRICT, so a delete
 * only succeeds while nothing points at the row. The checks below exist to name
 * what is holding it rather than leaving the caller with a bare constraint
 * violation; the sequence assignment is configuration we own, so it goes with
 * the subcategory.
 */
export async function deleteSubcategory(id: string) {
  parseUuid(id, "subcategory id");
  return withCrmTransaction(async (tx) => {
    const [subcategory] = await tx.select().from(crmSubcategories)
      .where(and(inOrgPipelines(), eq(crmSubcategories.id, id))).limit(1).for("update");
    if (!subcategory) throw new CrmNotFoundError("CRM subcategory", id);

    const [records] = await tx.select({ total: count() }).from(crmRecords)
      .where(and(inOrg(crmRecords), eq(crmRecords.subcategoryId, id)));
    const recordCount = Number(records?.total ?? 0);
    if (recordCount > 0) {
      throw new CrmConflictError(
        `${recordCount} CRM record${recordCount === 1 ? " is" : "s are"} still classified as this subcategory. Reclassify them before deleting it`,
      );
    }

    const [classification] = await tx.select({ id: crmClassifications.id }).from(crmClassifications)
      .where(or(
        eq(crmClassifications.previousSubcategoryId, id),
        eq(crmClassifications.proposedSubcategoryId, id),
        eq(crmClassifications.appliedSubcategoryId, id),
      )).limit(1);
    if (classification) {
      throw new CrmConflictError("This subcategory appears in classification history and cannot be permanently deleted");
    }

    const [run] = await tx.select({ id: crmSequenceRuns.id }).from(crmSequenceRuns)
      .where(eq(crmSequenceRuns.subcategoryId, id)).limit(1);
    if (run) {
      throw new CrmConflictError("This subcategory has sequence run history and cannot be permanently deleted");
    }

    await tx.delete(crmSubcategorySequenceAssignments)
      .where(eq(crmSubcategorySequenceAssignments.subcategoryId, id));
    await tx.delete(crmSubcategories).where(eq(crmSubcategories.id, id));
    return { id };
  });
}
