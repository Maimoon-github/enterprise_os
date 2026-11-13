import { NextRequest, NextResponse } from "next/server";
import { listColumns, topoSort } from "@/lib/grid/columns";
import { listRows, listRowsByIds } from "@/lib/grid/rows";
import { getTable } from "@/lib/grid/tables";
import { activeJobCount, cancelTableJobs, enqueue, type EnqueueTarget } from "@/lib/grid/queue";
import { getIntegrationConnection, getIntegrationCredentials } from "@/lib/grid/providers";
import { getIntegrationAction } from "@/lib/integrations/catalog";
import { allReferencedInputsEmpty, columnDelaySeconds, hasCellValue, isRunnable } from "@/lib/grid/runners";
import { ownCell } from "@/lib/grid/runners/types";
import { parseRunRequest } from "@/lib/grid/run-request";
import type { AiOutputConfig, EnrichmentConfig, IntegrationOutputConfig } from "@/lib/grid/types";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";

function hasRequiredInputs(
  column: Awaited<ReturnType<typeof listColumns>>[number],
  cells: Record<string, unknown>,
): boolean {
  // AI, HTTP and formula columns have no declared required inputs, so they are
  // skipped only when every {{token}} they reference is empty.
  if (column.type !== "enrichment") return !allReferencedInputsEmpty(column, cells);
  const config = column.config as EnrichmentConfig;
  const action = getIntegrationAction(config.integrationKey, config.actionKey);
  if (!action) return true;

  const requiredPresent = action.inputs.every((input) => {
    if (!input.required) return true;
    const binding = config.inputs[input.key];
    if (!binding) return false;
    const value = ownCell(cells, binding.columnKey);
    return value !== undefined && value !== null && (typeof value !== "string" || value.trim() !== "");
  });
  if (!requiredPresent) return false;
  if (!action.filterBuilder) return true;

  const populatedFilters = action.inputs.filter((input) => {
    if (input.group !== "filter") return false;
    const binding = config.inputs[input.key];
    if (!binding) return false;
    return hasCellValue(ownCell(cells, binding.columnKey));
  });
  return populatedFilters.length >= action.filterBuilder.minFilters;
}

async function validateEnrichmentAccounts(
  columns: Awaited<ReturnType<typeof listColumns>>,
): Promise<string | null> {
  for (const column of columns) {
    if (column.type !== "enrichment") continue;
    const config = column.config as EnrichmentConfig;
    const connection = await getIntegrationConnection(config.connectionId);
    if (
      !connection ||
      !connection.enabled ||
      !connection.configured ||
      !connection.verified ||
      connection.integrationKey !== config.integrationKey
    ) {
      return `Connect a verified ${config.integrationKey} account before running “${column.name}”`;
    }
    try {
      if (!(await getIntegrationCredentials(config.connectionId))) {
        return `Reconnect the ${config.integrationKey} account before running “${column.name}”`;
      }
    } catch {
      return `Reconnect the ${config.integrationKey} account before running “${column.name}”`;
    }
  }
  return null;
}

/**
 * POST /api/grid/tables/[tableId]/run
 *   { columnKey?, rowIds?, onlyEmpty? }
 *
 * Queues cells. Omitting columnKey runs every runnable column; omitting rowIds
 * runs every row.
 *
 * Only the roots of the dependency graph are queued — a column that depends on
 * another is reached by the cascade in queue.ts once its input lands. Queuing
 * the whole graph up front would run dependents against empty inputs.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  // Started before the organization scope opens: a timer inherits the async
  // context it was created in, and the worker must not run as one organization.
  if (process.env.NODE_ENV !== "production") {
    const { startGridWorker } = await import("@/lib/grid/worker");
    startGridWorker();
  }
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;
      if (!(await getTable(tableId))) {
        return NextResponse.json({ error: "table not found" }, { status: 404 });
      }

      // A present-but-broken body is a 400, not "run everything".
      const parsed = parseRunRequest(await req.text());
      if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });
      const body = parsed.value;

      const columns = await listColumns(tableId);
      const runnable = columns.filter((c) => isRunnable(c.type));

      if (!runnable.length) {
        return NextResponse.json(
          { error: "This table has no columns that can be run yet" },
          { status: 400 },
        );
      }

      let targetColumns = runnable;
      if (body.columnKey) {
        const one = runnable.find((c) => c.key === body.columnKey);
        if (!one) {
          return NextResponse.json(
            { error: `"${body.columnKey}" is not a runnable column` },
            { status: 400 },
          );
        }
        targetColumns = [one];
      } else {
        // Whole-table run: start only at columns whose dependencies are not
        // themselves being run here. The cascade handles the rest.
        // A dependency on a generated output column (integration_output /
        // ai_output) is really a dependency on the column that writes it, which
        // is what is being run here — otherwise the dependent looks external
        // and runs at once against blank inputs.
        const runningKeys = new Set(runnable.map((c) => c.key));
        const sourceOf = new Map<string, string>();
        for (const c of columns) {
          if (c.type === "integration_output") sourceOf.set(c.key, (c.config as IntegrationOutputConfig).sourceColumnKey);
          if (c.type === "ai_output") sourceOf.set(c.key, (c.config as AiOutputConfig).sourceColumnKey);
        }
        targetColumns = topoSort(runnable).filter(
          (c) => !c.dependsOn.some((d) => runningKeys.has(sourceOf.get(d) ?? d)),
        );
      }

      // This is deliberately enforced at the server boundary, not only by the
      // setup drawer. It prevents direct requests from queueing a paid provider
      // action when its API key is missing, disabled, or belongs to another
      // integration.
      const accountError = await validateEnrichmentAccounts(targetColumns);
      if (accountError) {
        return NextResponse.json({ error: accountError }, { status: 400 });
      }

      const queueRows = async (rows: Awaited<ReturnType<typeof listRows>>) => {
        const targets: EnqueueTarget[] = [];
        for (const column of targetColumns) {
          for (const row of rows) {
            // A blank required source cannot produce a useful provider result. Do
            // not queue it, mark it as running, or spend a provider credit.
            if (!hasRequiredInputs(column, row.cells ?? {})) continue;
            // "Only empty" is the cheap re-run: skip cells that already hold a
            // value, so a partial failure can be resumed without paying twice for
            // everything that already succeeded.
            if (body.onlyEmpty) {
              const v = row.cells?.[column.key];
              if (v !== undefined && v !== null && v !== "") continue;
            }
            targets.push({ rowId: row.id, columnKey: column.key, delaySeconds: columnDelaySeconds(column) });
          }
        }
        return enqueue(tableId, targets, { priority: body.columnKey ? 10 : 0 });
      };

      let queued = 0;
      if (body.rowIds) {
        // An explicit selection, even an empty one, never widens to every row.
        const ids = [...new Set(body.rowIds)];
        const CHUNK = 5000;
        for (let i = 0; i < ids.length; i += CHUNK) {
          queued += await queueRows(await listRowsByIds(tableId, ids.slice(i, i + CHUNK)));
        }
      } else {
        const PAGE_SIZE = 1000;
        for (let offset = 0; ; offset += PAGE_SIZE) {
          const rows = await listRows(tableId, { limit: PAGE_SIZE, offset });
          if (!rows.length) break;
          queued += await queueRows(rows);
          if (rows.length < PAGE_SIZE) break;
        }
      }

      if (!queued) {
        return NextResponse.json({ queued: 0, activeJobs: await activeJobCount(tableId) });
      }

      return NextResponse.json({ queued, activeJobs: await activeJobCount(tableId) });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

/** DELETE — the "Stop" button. Drops queued jobs; running ones finish. */
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(_req, async () => {
      const { tableId } = await params;
      const cancelled = await cancelTableJobs(tableId);
      return NextResponse.json({ cancelled, activeJobs: await activeJobCount(tableId) });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
