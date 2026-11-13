import { NextRequest, NextResponse } from "next/server";
import { listColumns } from "@/lib/grid/columns";
import { getTable } from "@/lib/grid/tables";
import {
  MAX_IMPORT_ROWS,
  importRows,
  parseSpreadsheet,
  normalizeMapping,
  suggestMapping,
  type ColumnMapping,
} from "@/lib/grid/import";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { isUuid } from "@/lib/grid/validate";

/** Refused before parsing — a 60MB spreadsheet is a mistake, not a workload. */
const MAX_FILE_BYTES = 25 * 1024 * 1024;

/** Rows returned with a preview. Enough to judge a mapping, small to send. */
const PREVIEW_ROWS = 10;

/**
 * POST /api/grid/tables/[tableId]/import   (multipart/form-data)
 *
 *   file      required
 *   sheet     optional — which worksheet, for multi-sheet .xlsx
 *   mapping   optional — omit for a preview, send to perform the import
 *
 * The file is uploaded again for the import rather than being cached server
 * side between the two calls: it keeps the endpoint stateless, and stashing
 * uploads in a temp dir is a cleanup problem nobody remembers to solve.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId) || !(await getTable(tableId))) {
        return NextResponse.json({ error: "table not found" }, { status: 404 });
      }

      let form: FormData;
      try {
        form = await req.formData();
      } catch {
        return NextResponse.json({ error: "expected multipart/form-data" }, { status: 400 });
      }

      const file = form.get("file");
      if (!(file instanceof File)) {
        return NextResponse.json({ error: "file is required" }, { status: 400 });
      }
      if (file.size === 0) {
        return NextResponse.json({ error: "that file is empty" }, { status: 400 });
      }
      if (file.size > MAX_FILE_BYTES) {
        return NextResponse.json(
          { error: `file is larger than ${MAX_FILE_BYTES / 1024 / 1024}MB` },
          { status: 413 },
        );
      }

      const sheetName = (form.get("sheet") as string | null) ?? undefined;
      const parsed = parseSpreadsheet(await file.arrayBuffer(), sheetName);
      if (!parsed.ok) {
        return NextResponse.json({ error: parsed.error }, { status: 400 });
      }

      const { sheet, sheetNames } = parsed;
      const existing = await listColumns(tableId);

      const rawMapping = form.get("mapping");

      // ---- preview ----
      if (typeof rawMapping !== "string" || !rawMapping) {
        return NextResponse.json({
          preview: true,
          fileName: file.name,
          sheetNames,
          headers: sheet.headers,
          rows: sheet.rows.slice(0, PREVIEW_ROWS),
          totalRows: sheet.totalRows,
          truncated: sheet.truncated,
          maxRows: MAX_IMPORT_ROWS,
          mapping: suggestMapping(sheet.headers, sheet.rows, existing),
          columns: existing.map((c) => ({ key: c.key, name: c.name, type: c.type })),
        });
      }

      // ---- import ----
      let rawParsed: unknown;
      try {
        rawParsed = JSON.parse(rawMapping);
      } catch {
        return NextResponse.json({ error: "mapping is not valid JSON" }, { status: 400 });
      }

      // Checks every entry (header index, action, a creatable type, a usable
      // name) and defaults a new column's name to its header.
      const normalized = normalizeMapping(rawParsed, sheet.headers, new Set(existing.map((c) => c.key)));
      if (!normalized.ok) return NextResponse.json({ error: normalized.error }, { status: 400 });
      const mapping: ColumnMapping[] = normalized.mapping;

      if (!mapping.some((m) => m.action !== "skip")) {
        return NextResponse.json({ error: "every column is set to skip" }, { status: 400 });
      }

      const result = await importRows(tableId, sheet, mapping);
      return NextResponse.json({ preview: false, ...result });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
