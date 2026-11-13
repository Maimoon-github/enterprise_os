import { and, asc, count, eq, inArray, isNull, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { gridFolders, gridWorkbooks, type GridFolder } from "./schema";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

export type FolderSummary = GridFolder & {
  /** Direct children only — subfolders plus workbooks filed here. */
  folderCount: number;
  workbookCount: number;
};

/** One hop of the breadcrumb trail, root-first. */
export type FolderCrumb = { id: string; name: string };

/** A folder id that is not (or no longer) one of the caller's folders — a 404 at the route. */
export class FolderNotFoundError extends Error {}

const parentMatches = (parentId: string | null) =>
  parentId === null ? isNull(gridFolders.parentId) : eq(gridFolders.parentId, parentId);

/**
 * Folders directly inside `parentId` (NULL = root), with their direct child
 * counts.
 *
 * The counts come from joined subqueries rather than correlated
 * `SELECT count(*) … WHERE parent_id = folders.id` scalars: Drizzle renders
 * column references inside a raw `sql` subquery unqualified, so the outer
 * `id` silently resolves against the inner table and every count reads 0.
 * See the same fix in workbooks.ts.
 */
export async function listFolders(parentId: string | null = null): Promise<FolderSummary[]> {
  const childFolders = db
    .select({
      parentId: gridFolders.parentId,
      n: count().as("child_folder_count"),
    })
    .from(gridFolders)
    .where(inOrg(gridFolders))
    .groupBy(gridFolders.parentId)
    .as("child_folders");

  const childWorkbooks = db
    .select({
      folderId: gridWorkbooks.folderId,
      n: count().as("child_workbook_count"),
    })
    .from(gridWorkbooks)
    .where(inOrg(gridWorkbooks))
    .groupBy(gridWorkbooks.folderId)
    .as("child_workbooks");

  const rows = await db
    .select({
      id: gridFolders.id,
      organizationId: gridFolders.organizationId,
      name: gridFolders.name,
      parentId: gridFolders.parentId,
      createdAt: gridFolders.createdAt,
      updatedAt: gridFolders.updatedAt,
      folderCount: childFolders.n,
      workbookCount: childWorkbooks.n,
    })
    .from(gridFolders)
    .leftJoin(childFolders, eq(childFolders.parentId, gridFolders.id))
    .leftJoin(childWorkbooks, eq(childWorkbooks.folderId, gridFolders.id))
    .where(and(inOrg(gridFolders), parentMatches(parentId)))
    .orderBy(asc(gridFolders.name));

  // The LEFT JOINs leave NULL where a folder has no children of that kind.
  // Coalescing here rather than in SQL is deliberate: a `sql` template would
  // render the subquery column unqualified, and two subqueries with the same
  // alias make it ambiguous — the same footgun documented in workbooks.ts.
  return rows.map((row) => ({
    ...row,
    folderCount: Number(row.folderCount ?? 0),
    workbookCount: Number(row.workbookCount ?? 0),
  }));
}

/** Every folder, name-sorted — the source for "Move to…" pickers. */
export async function listAllFolders(): Promise<GridFolder[]> {
  return db.select().from(gridFolders).where(inOrg(gridFolders)).orderBy(asc(gridFolders.name));
}

export async function getFolder(id: string): Promise<GridFolder | null> {
  const [row] = await db.select().from(gridFolders).where(and(inOrg(gridFolders), eq(gridFolders.id, id))).limit(1);
  return row ?? null;
}

/**
 * The breadcrumb trail for a folder, root-first and including the folder
 * itself. Walks upward in one recursive query rather than a round trip per
 * level, and returns [] for an id that no longer exists.
 */
export async function folderPath(id: string | null): Promise<FolderCrumb[]> {
  if (!id) return [];

  const rows = await db.execute<{ id: string; name: string; depth: number }>(sql`
    WITH RECURSIVE trail AS (
      SELECT f.id, f.name, f.parent_id, 0 AS depth
        FROM ${gridFolders} f WHERE f.id = ${id} AND f.organization_id = ${currentOrganizationId()}
      UNION ALL
      SELECT p.id, p.name, p.parent_id, trail.depth + 1
        FROM ${gridFolders} p JOIN trail ON p.id = trail.parent_id
       WHERE p.organization_id = ${currentOrganizationId()}
    )
    SELECT id, name, depth FROM trail ORDER BY depth DESC
  `);

  // db.ts uses the postgres-js driver, whose execute() resolves to the rows
  // array itself rather than a { rows } wrapper.
  return [...rows].map((row) => ({ id: row.id, name: row.name }));
}

/** The folder plus every folder nested under it — the illegal move targets. */
async function descendantIds(id: string): Promise<string[]> {
  const rows = await db.execute<{ id: string }>(sql`
    WITH RECURSIVE subtree AS (
      SELECT f.id FROM ${gridFolders} f WHERE f.id = ${id} AND f.organization_id = ${currentOrganizationId()}
      UNION ALL
      SELECT c.id FROM ${gridFolders} c JOIN subtree ON c.parent_id = subtree.id
       WHERE c.organization_id = ${currentOrganizationId()}
    )
    SELECT id FROM subtree
  `);
  return [...rows].map((row) => row.id);
}

export async function createFolder(input: {
  name: string;
  parentId?: string | null;
}): Promise<GridFolder> {
  // The parent must be one of THIS organization's folders: the FK alone would
  // accept another organization's id (and its delete would then cascade here),
  // and reject a stale one with a 500.
  if (input.parentId && !(await getFolder(input.parentId))) {
    throw new FolderNotFoundError("That parent folder no longer exists");
  }
  const [folder] = await db
    .insert(gridFolders)
    .values({
      organizationId: currentOrganizationId(),
      name: input.name.trim() || "Untitled folder",
      parentId: input.parentId ?? null,
    })
    .returning();
  return folder;
}

/**
 * Rename and/or re-parent. Moving a folder into itself or into one of its own
 * descendants would orphan the subtree from the root, so it is rejected here
 * rather than left to produce an unreachable cycle.
 */
export async function updateFolder(
  id: string,
  patch: { name?: string; parentId?: string | null },
): Promise<GridFolder | null> {
  const values: Record<string, unknown> = { updatedAt: new Date() };
  if (patch.name !== undefined) values.name = patch.name.trim() || "Untitled folder";

  if (patch.parentId !== undefined) {
    if (patch.parentId !== null) {
      const blocked = await descendantIds(id);
      if (blocked.includes(patch.parentId)) {
        throw new Error("A folder cannot be moved inside itself");
      }
      if (!(await getFolder(patch.parentId))) {
        throw new Error("That destination folder no longer exists");
      }
    }
    values.parentId = patch.parentId;
  }

  const [row] = await db.update(gridFolders).set(values).where(and(inOrg(gridFolders), eq(gridFolders.id, id))).returning();
  return row ?? null;
}

/**
 * Deletes the folder and its subfolders. Workbooks inside are NOT deleted —
 * the FK is ON DELETE SET NULL, so they resurface at the root of All Files.
 * Returns how many workbooks were displaced so the UI can say so.
 */
export async function deleteFolder(id: string): Promise<{ deleted: boolean; released: number }> {
  const subtree = await descendantIds(id);
  if (!subtree.length) return { deleted: false, released: 0 };

  const [{ n }] = await db
    .select({ n: count() })
    .from(gridWorkbooks)
    .where(and(inOrg(gridWorkbooks), inArray(gridWorkbooks.folderId, subtree)));

  const deleted = await db
    .delete(gridFolders)
    .where(and(inOrg(gridFolders), eq(gridFolders.id, id)))
    .returning({ id: gridFolders.id });

  return { deleted: deleted.length > 0, released: Number(n ?? 0) };
}

/** Guards a `?folder=` query param — an unknown id falls back to the root. */
export async function resolveFolderId(candidate: string | undefined): Promise<string | null> {
  if (!candidate) return null;
  return (await getFolder(candidate)) ? candidate : null;
}
