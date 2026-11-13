import { NextRequest, NextResponse } from "next/server";
import { createEnrichmentColumns, updateEnrichmentColumns } from "@/lib/grid/enrichments";
import { getTable } from "@/lib/grid/tables";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { clientMessage, isRecord, isUuid } from "@/lib/grid/validate";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(request, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId) || !(await getTable(tableId))) {
        return NextResponse.json({ error: "table not found" }, { status: 404 });
      }

      let body: {
        integrationKey?: string;
        actionKey?: string;
        inputs?: Record<string, string>;
        selectedOutputs?: string[];
        connectionId?: string;
        autoRun?: boolean;
        runCondition?: string;
        delaySeconds?: number;
        runInBatches?: boolean;
        afterColumnId?: string;
        beforeColumnId?: string;
      };
      try {
        const parsed = await request.json();
        if (!isRecord(parsed)) throw new Error("not an object");
        body = parsed;
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }

      if (!body.integrationKey || !body.actionKey) {
        return NextResponse.json({ error: "integrationKey and actionKey are required" }, { status: 400 });
      }
      if (!body.inputs || !body.selectedOutputs || !body.connectionId) {
        return NextResponse.json({ error: "inputs, outputs, and a connection are required" }, { status: 400 });
      }

      if (typeof body.integrationKey !== "string" || typeof body.actionKey !== "string") {
        return NextResponse.json({ error: "integrationKey and actionKey must be text" }, { status: 400 });
      }
      if (!isRecord(body.inputs) || Object.values(body.inputs).some((v) => typeof v !== "string")) {
        return NextResponse.json({ error: "inputs must map each input to a column key" }, { status: 400 });
      }
      if (!Array.isArray(body.selectedOutputs) || body.selectedOutputs.some((v) => typeof v !== "string")) {
        return NextResponse.json({ error: "outputs must be a list of output keys" }, { status: 400 });
      }
      if (!isUuid(body.connectionId)) {
        return NextResponse.json({ error: "connectionId is not a valid id" }, { status: 400 });
      }

      try {
        const columns = await createEnrichmentColumns({
          tableId,
          integrationKey: body.integrationKey,
          actionKey: body.actionKey,
          inputs: body.inputs,
          selectedOutputs: body.selectedOutputs,
          connectionId: body.connectionId,
          autoRun: body.autoRun ?? true,
          runCondition: body.runCondition,
          delaySeconds: body.delaySeconds,
          runInBatches: body.runInBatches,
          afterColumnId: body.afterColumnId,
          beforeColumnId: body.beforeColumnId,
        });
        return NextResponse.json({ columns, primaryColumnKey: columns[0]?.key }, { status: 201 });
      } catch (error) {
        return NextResponse.json(
          { error: clientMessage(error, "Could not add enrichment") },
          { status: 400 },
        );
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(request, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId) || !(await getTable(tableId))) {
        return NextResponse.json({ error: "table not found" }, { status: 404 });
      }

      let body: {
        columnId?: string;
        integrationKey?: string;
        actionKey?: string;
        inputs?: Record<string, string>;
        selectedOutputs?: string[];
        connectionId?: string;
        autoRun?: boolean;
        runCondition?: string;
        delaySeconds?: number;
        runInBatches?: boolean;
      };
      try {
        const parsed = await request.json();
        if (!isRecord(parsed)) throw new Error("not an object");
        body = parsed;
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }
      if (!body.columnId || !body.integrationKey || !body.actionKey || !body.inputs || !body.selectedOutputs || !body.connectionId) {
        return NextResponse.json({ error: "column, action, inputs, outputs, and connection are required" }, { status: 400 });
      }

      if (typeof body.integrationKey !== "string" || typeof body.actionKey !== "string") {
        return NextResponse.json({ error: "integrationKey and actionKey must be text" }, { status: 400 });
      }
      if (!isRecord(body.inputs) || Object.values(body.inputs).some((v) => typeof v !== "string")) {
        return NextResponse.json({ error: "inputs must map each input to a column key" }, { status: 400 });
      }
      if (!Array.isArray(body.selectedOutputs) || body.selectedOutputs.some((v) => typeof v !== "string")) {
        return NextResponse.json({ error: "outputs must be a list of output keys" }, { status: 400 });
      }
      if (!isUuid(body.connectionId)) {
        return NextResponse.json({ error: "connectionId is not a valid id" }, { status: 400 });
      }

      try {
        const columns = await updateEnrichmentColumns({
          columnId: body.columnId,
          tableId,
          integrationKey: body.integrationKey,
          actionKey: body.actionKey,
          inputs: body.inputs,
          selectedOutputs: body.selectedOutputs,
          connectionId: body.connectionId,
          autoRun: body.autoRun ?? true,
          runCondition: body.runCondition,
          delaySeconds: body.delaySeconds,
          runInBatches: body.runInBatches,
        });
        const primary = columns.find((column) => column.id === body.columnId);
        return NextResponse.json({ columns, primaryColumnKey: primary?.key });
      } catch (error) {
        return NextResponse.json(
          { error: clientMessage(error, "Could not update enrichment") },
          { status: 400 },
        );
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
