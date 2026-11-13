import { getIntegrationAction } from "@/lib/integrations/catalog";
import type { CellValues, EnrichmentConfig } from "./types";
import type { GridColumn } from "./schema";
import type { EnqueueTarget } from "./queue";
import { allReferencedInputsEmpty, columnDelaySeconds, hasCellValue } from "./runners/guards";
import { ownCell } from "./runners/types";

/** What a cascade needs of a column. */
export type CascadeColumn = Pick<GridColumn, "key" | "type" | "config" | "dependsOn" | "autoRun">;

/** A row whose `changedKeys` columns just received new values; `cells` is the row as it stands now. */
export type RowChange = { rowId: string; cells: CellValues; changedKeys: string[] };

/**
 * The columns that read `changedKey` and are ready to run against `cells`.
 *
 * A dependent is only ready once its runnable inputs have values, so a column
 * reading two required inputs does not run twice. A formula is the exception:
 * it is free, so it recomputes on every change to what it reads — clearing a
 * last name must update the full name, not leave the old one standing. Addable filter groups are
 * ready as soon as their minimum number of mapped filters has a value. This
 * is the one readiness rule: the worker's cascade after a job and the cascade
 * after a user edit both go through it.
 */
export function readyDependents(columns: CascadeColumn[], changedKey: string, cells: CellValues): CascadeColumn[] {
  return columns
    .filter((c) => c.autoRun && c.dependsOn.includes(changedKey))
    .filter((column) => {
      if (column.type === "formula") return true;
      if (column.type === "enrichment") {
        const config = column.config as EnrichmentConfig;
        const action = getIntegrationAction(config.integrationKey, config.actionKey);
        if (action?.filterBuilder) {
          const requiredInputsReady = action.inputs.every((input) => {
            if (!input.required) return true;
            const binding = config.inputs[input.key];
            return binding ? hasCellValue(ownCell(cells, binding.columnKey)) : false;
          });
          if (!requiredInputsReady) return false;
          const populatedFilters = action.inputs.filter((input) => {
            if (input.group !== "filter") return false;
            const binding = config.inputs[input.key];
            return binding ? hasCellValue(ownCell(cells, binding.columnKey)) : false;
          }).length;
          return populatedFilters >= action.filterBuilder.minFilters;
        }
      }
      return column.dependsOn.every((dep) => hasCellValue(ownCell(cells, dep)))
        && !allReferencedInputsEmpty(column, cells);
    });
}

/** Every (row, dependent column) to queue for a batch of changed rows, one target per pair. */
export function cascadeTargets(columns: CascadeColumn[], changes: RowChange[]): EnqueueTarget[] {
  const targets: EnqueueTarget[] = [];
  for (const change of changes) {
    const seen = new Set<string>();
    for (const changedKey of change.changedKeys) {
      for (const column of readyDependents(columns, changedKey, change.cells)) {
        if (seen.has(column.key)) continue;
        seen.add(column.key);
        targets.push({ rowId: change.rowId, columnKey: column.key, delaySeconds: columnDelaySeconds(column) });
      }
    }
  }
  return targets;
}

/** Cells whose value actually changed — an edit that writes back what was there re-runs nothing. */
export function changedCellUpdates<T extends { rowId: string; columnKey: string; value: unknown }>(
  previous: T[],
  next: T[],
): T[] {
  const before = new Map(previous.map((u) => [`${u.rowId}\u0000${u.columnKey}`, JSON.stringify(u.value ?? null)]));
  return next.filter((u) => before.get(`${u.rowId}\u0000${u.columnKey}`) !== JSON.stringify(u.value ?? null));
}
