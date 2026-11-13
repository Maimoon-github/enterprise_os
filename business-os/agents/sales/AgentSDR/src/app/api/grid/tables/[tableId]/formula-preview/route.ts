import { NextRequest, NextResponse } from "next/server";
import { and, asc, count, eq, lte } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrgTables } from "@/lib/grid/scope";
import { gridRows } from "@/lib/grid/schema";
import { evaluateOnce } from "@/lib/grid/runners";
import { buildFormulaLookupRegistry, resolveFormulaConfig, textColumnKeys } from "@/lib/grid/formula-lookups";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { isRecord, isUuid } from "@/lib/grid/validate";

const MAX_EXPRESSION_LENGTH = 10_000;

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId)) return NextResponse.json({ ok: false, error: "table not found" }, { status: 404 });
      let body: { expression?: unknown; rowId?: unknown };
      try {
        const parsed = await req.json();
        if (!isRecord(parsed)) throw new Error("not an object");
        body = parsed;
      } catch {
        return NextResponse.json({ ok: false, error: "invalid JSON body" }, { status: 400 });
      }

      if (typeof body.expression !== "string") {
        return NextResponse.json({ ok: false, error: "expression must be text" }, { status: 400 });
      }
      if (body.rowId !== undefined && body.rowId !== null && !isUuid(body.rowId)) {
        return NextResponse.json({ ok: false, error: "rowId is not a valid id" }, { status: 400 });
      }
      const rowId = typeof body.rowId === "string" ? body.rowId : undefined;
      const expression = body.expression.trim();
      if (!expression) {
        return NextResponse.json({ ok: false, error: "expression is required" }, { status: 400 });
      }
      if (expression.length > MAX_EXPRESSION_LENGTH) {
        return NextResponse.json({ ok: false, error: "expression is too long" }, { status: 400 });
      }

      const rows = await db
        .select({ id: gridRows.id, position: gridRows.position, cells: gridRows.cells })
        .from(gridRows)
        .where(
          rowId
            ? and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), eq(gridRows.id, rowId))
            : and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId)),
        )
        .orderBy(asc(gridRows.position))
        .limit(1);
      const row = rows[0];
      if (!row) {
        return NextResponse.json({ ok: false, error: "preview row not found" }, { status: 404 });
      }

      // The grid numbers rows 1, 2, 3… in display order; `position` is a sort
      // key with gaps (deleted rows) and may start above 1. Count rows up to and
      // including this one so the preview names the row the way the grid does.
      const [{ ordinal }] = await db
        .select({ ordinal: count() })
        .from(gridRows)
        .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), lte(gridRows.position, row.position)));

      let formula;
      let registry;
      let textKeys;
      try {
        formula = await resolveFormulaConfig(tableId, expression);
        [registry, textKeys] = await Promise.all([
          buildFormulaLookupRegistry(formula.lookupRefs),
          textColumnKeys(tableId),
        ]);
      } catch (error) {
        return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : "Invalid formula" }, { status: 422 });
      }
      const result = await evaluateOnce(expression, row.cells, registry, textKeys);
      if (!result.ok) return NextResponse.json(result, { status: 422 });
      return NextResponse.json({ ...result, rowId: row.id, rowNumber: Number(ordinal) });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
