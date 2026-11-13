import { NextRequest, NextResponse } from "next/server";
import { UTF8_BOM, serializeCsv } from "@/lib/grid/csv";
import { listColumns } from "@/lib/grid/columns";
import { listRowsByIds } from "@/lib/grid/rows";
import { getTable } from "@/lib/grid/tables";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { isUuid } from "@/lib/grid/validate";

export const dynamic = "force-dynamic";

const MAX_EXPORT_ROWS = 50_000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type ExportRequest = {
  rowIds?: unknown;
  columnKeys?: unknown;
};

function validateStringList(
  value: unknown,
  field: "rowIds" | "columnKeys",
  { required, max }: { required: boolean; max?: number },
): string[] | string {
  if (!Array.isArray(value)) {
    return required ? `${field} must be a non-empty array` : `${field} must be an array`;
  }
  if (required && value.length === 0) return `${field} must be a non-empty array`;
  if (max !== undefined && value.length > max) return `${field} cannot contain more than ${max.toLocaleString()} values`;
  if (value.some((item) => typeof item !== "string" || !item.trim())) {
    return `${field} must contain only non-empty strings`;
  }
  const strings = value as string[];
  if (new Set(strings).size !== strings.length) return `${field} must contain unique values`;
  return strings;
}

function filenameFor(tableName: string, rowCount: number): string {
  const slug = tableName
    .normalize("NFKD")
    .replace(/[^\x00-\x7F]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "table";
  return `${slug}-${rowCount}-rows.csv`;
}

/** POST — export explicitly selected rows and optional columns as CSV. */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId)) return NextResponse.json({ error: "table not found" }, { status: 404 });

      let body: ExportRequest;
      try {
        body = await req.json() as ExportRequest;
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }
      if (!body || typeof body !== "object" || Array.isArray(body)) {
        return NextResponse.json({ error: "body must be an object" }, { status: 400 });
      }

      const rowIds = validateStringList(body.rowIds, "rowIds", { required: true, max: MAX_EXPORT_ROWS });
      if (typeof rowIds === "string") return NextResponse.json({ error: rowIds }, { status: 400 });
      if (rowIds.some((id) => !UUID.test(id))) {
        return NextResponse.json({ error: "rowIds must contain valid UUIDs" }, { status: 400 });
      }

      let requestedColumnKeys: string[] | undefined;
      if (body.columnKeys !== undefined) {
        const validated = validateStringList(body.columnKeys, "columnKeys", { required: true });
        if (typeof validated === "string") return NextResponse.json({ error: validated }, { status: 400 });
        requestedColumnKeys = validated;
      }

      const [table, allColumns] = await Promise.all([getTable(tableId), listColumns(tableId)]);
      if (!table) return NextResponse.json({ error: "table not found" }, { status: 404 });

      const columnsByKey = new Map(allColumns.map((column) => [column.key, column]));
      const unknownColumn = requestedColumnKeys?.find((key) => !columnsByKey.has(key));
      if (unknownColumn) {
        return NextResponse.json({ error: `Unknown column: ${unknownColumn}` }, { status: 400 });
      }
      const columns = requestedColumnKeys
        ? requestedColumnKeys.map((key) => columnsByKey.get(key)!)
        : allColumns;

      const fetchedRows = await listRowsByIds(tableId, rowIds);
      if (fetchedRows.length !== rowIds.length) {
        return NextResponse.json({ error: "One or more rows do not belong to this table" }, { status: 400 });
      }

      // listRowsByIds returns physical table order. Rebuild from the request so an
      // export keeps the same order as the selection sent by the grid client.
      const rowsById = new Map(fetchedRows.map((row) => [row.id, row]));
      const rows = rowIds.map((id) => rowsById.get(id)!);
      const csv = serializeCsv([
        columns.map((column) => column.name),
        ...rows.map((row) => columns.map((column) => row.cells?.[column.key])),
      ]);

      return new Response(UTF8_BOM + csv, {
        headers: {
          "Cache-Control": "private, no-store",
          "Content-Disposition": `attachment; filename="${filenameFor(table.name, rows.length)}"`,
          "Content-Type": "text/csv; charset=utf-8",
        },
      });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
