import { randomUUID } from "node:crypto";
import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import {
  assertExactKeys,
  assertObject,
  CrmConfigurationValidationError,
  parseBoolean,
  parseRequiredText,
  parseUuid,
} from "./categories";
import { CrmNotFoundError, withCrmTransaction } from "./repository";
import {
  crmKnowledgeDocuments,
  crmKnowledgeDocumentVersions,
  type CrmKnowledgeKind,
} from "./schema";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

const KNOWLEDGE_KINDS = new Set<CrmKnowledgeKind>([
  "company",
  "product",
  "pricing",
  "faq",
  "case_study",
  "objection",
  "scheduling",
  "custom",
]);

function parseKnowledgeKind(value: unknown): CrmKnowledgeKind {
  if (typeof value !== "string" || !KNOWLEDGE_KINDS.has(value as CrmKnowledgeKind)) {
    throw new CrmConfigurationValidationError("kind is not a supported Knowledge document kind");
  }
  return value as CrmKnowledgeKind;
}

function parseKnowledgeTags(value: unknown): string[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > 50) {
    throw new CrmConfigurationValidationError("tags must be an array with at most 50 values");
  }
  const tags = value.map((tag, index) => parseRequiredText(tag, `tags[${index}]`, 80).toLowerCase());
  if (new Set(tags).size !== tags.length) {
    throw new CrmConfigurationValidationError("tags cannot contain duplicates");
  }
  return tags;
}

export type CreateKnowledgeDocumentInput = {
  title: string;
  kind: CrmKnowledgeKind;
  tags: string[];
  alwaysInclude: boolean;
  content: string;
};

export function parseCreateKnowledgeDocumentInput(value: unknown): CreateKnowledgeDocumentInput {
  assertObject(value);
  assertExactKeys(value, ["title", "kind", "tags", "alwaysInclude", "content"]);
  return {
    title: parseRequiredText(value.title, "title", 200),
    kind: parseKnowledgeKind(value.kind),
    tags: parseKnowledgeTags(value.tags),
    alwaysInclude: value.alwaysInclude === undefined
      ? false
      : parseBoolean(value.alwaysInclude, "alwaysInclude"),
    content: parseRequiredText(value.content, "content", 200_000),
  };
}

export type UpdateKnowledgeDocumentInput = {
  title?: string;
  kind?: CrmKnowledgeKind;
  tags?: string[];
  alwaysInclude?: boolean;
  active?: boolean;
  content?: string;
};

export function parseUpdateKnowledgeDocumentInput(value: unknown): UpdateKnowledgeDocumentInput {
  assertObject(value);
  assertExactKeys(value, ["title", "kind", "tags", "alwaysInclude", "active", "content"]);
  const parsed: UpdateKnowledgeDocumentInput = {};
  if (value.title !== undefined) parsed.title = parseRequiredText(value.title, "title", 200);
  if (value.kind !== undefined) parsed.kind = parseKnowledgeKind(value.kind);
  if (value.tags !== undefined) parsed.tags = parseKnowledgeTags(value.tags);
  if (value.alwaysInclude !== undefined) parsed.alwaysInclude = parseBoolean(value.alwaysInclude, "alwaysInclude");
  if (value.active !== undefined) parsed.active = parseBoolean(value.active, "active");
  if (value.content !== undefined) parsed.content = parseRequiredText(value.content, "content", 200_000);
  if (Object.keys(parsed).length === 0) {
    throw new CrmConfigurationValidationError("At least one editable field is required");
  }
  return parsed;
}

export async function createKnowledgeDocument(value: unknown) {
  const input = parseCreateKnowledgeDocumentInput(value);
  return withCrmTransaction(async (tx) => {
    const documentId = randomUUID();
    const versionId = randomUUID();
    const [document] = await tx
      .insert(crmKnowledgeDocuments)
      .values({
        organizationId: currentOrganizationId(),
        id: documentId,
        title: input.title,
        kind: input.kind,
        tags: input.tags,
        alwaysInclude: input.alwaysInclude,
        latestVersion: 1,
      })
      .returning();
    if (!document) throw new Error("Knowledge document insert did not return a row");
    const [version] = await tx
      .insert(crmKnowledgeDocumentVersions)
      .values({ id: versionId, documentId, version: 1, content: input.content })
      .returning();
    if (!version) throw new Error("Knowledge version insert did not return a row");
    return { ...document, latest: version };
  });
}

export async function listKnowledgeDocuments(input: {
  kind?: string;
  includeArchived?: boolean;
}) {
  const kind = input.kind === undefined ? undefined : parseKnowledgeKind(input.kind);
  const documents = await db
    .select()
    .from(crmKnowledgeDocuments)
    .where(and(
      inOrg(crmKnowledgeDocuments),
      kind ? eq(crmKnowledgeDocuments.kind, kind) : undefined,
      input.includeArchived ? undefined : eq(crmKnowledgeDocuments.active, true),
    ))
    .orderBy(asc(crmKnowledgeDocuments.kind), asc(crmKnowledgeDocuments.title));
  const results = [];
  for (const document of documents) {
    const [latest] = await db
      .select()
      .from(crmKnowledgeDocumentVersions)
      .where(and(
        eq(crmKnowledgeDocumentVersions.documentId, document.id),
        eq(crmKnowledgeDocumentVersions.version, document.latestVersion),
      ))
      .limit(1);
    results.push({ ...document, latest });
  }
  return results;
}

export async function getKnowledgeDocument(id: string) {
  parseUuid(id, "Knowledge document id");
  const [document] = await db
    .select()
    .from(crmKnowledgeDocuments)
    .where(and(inOrg(crmKnowledgeDocuments), eq(crmKnowledgeDocuments.id, id)))
    .limit(1);
  if (!document) throw new CrmNotFoundError("Knowledge document", id);
  const versions = await db
    .select()
    .from(crmKnowledgeDocumentVersions)
    .where(eq(crmKnowledgeDocumentVersions.documentId, id))
    .orderBy(asc(crmKnowledgeDocumentVersions.version));
  return { ...document, versions };
}

export async function updateKnowledgeDocument(id: string, value: unknown) {
  parseUuid(id, "Knowledge document id");
  const input = parseUpdateKnowledgeDocumentInput(value);
  return withCrmTransaction(async (tx) => {
    const [document] = await tx
      .select()
      .from(crmKnowledgeDocuments)
      .where(and(inOrg(crmKnowledgeDocuments), eq(crmKnowledgeDocuments.id, id)))
      .limit(1)
      .for("update");
    if (!document) throw new CrmNotFoundError("Knowledge document", id);
    const { content, ...metadata } = input;
    let nextVersion = document.latestVersion;
    let version: typeof crmKnowledgeDocumentVersions.$inferSelect | undefined;
    if (content !== undefined) {
      nextVersion += 1;
      [version] = await tx
        .insert(crmKnowledgeDocumentVersions)
        .values({ documentId: id, version: nextVersion, content })
        .returning();
      if (!version) throw new Error("Knowledge version insert did not return a row");
    }
    const [updated] = await tx
      .update(crmKnowledgeDocuments)
      .set({
        ...metadata,
        latestVersion: nextVersion,
        updatedAt: new Date(),
      })
      .where(and(inOrg(crmKnowledgeDocuments), eq(crmKnowledgeDocuments.id, id)))
      .returning();
    if (!updated) throw new Error("Knowledge document update did not return a row");
    return { ...updated, latest: version };
  });
}
