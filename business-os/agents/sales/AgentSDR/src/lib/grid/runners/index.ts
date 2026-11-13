import type { ColumnConfig, ColumnType, EnrichmentConfig } from "../types";
import { isStaticColumnType } from "../types";
import { aiRunner } from "./ai";
import { formulaRunner } from "./formula";
import { httpRunner } from "./http";
import { enrichmentRunner } from "./enrichment";
import type { ColumnRunner } from "./types";

export * from "./types";
export { substituteTokens, evaluateOnce, evaluateCondition, assertFormulaSyntax, excelOnlyOperator } from "./formula";
export { allReferencedInputsEmpty, columnDelaySeconds, columnRunCondition, hasCellValue } from "./guards";
export { createSandbox, type Sandbox } from "./sandbox";

/**
 * Every runner, keyed by column type.
 *
 * Adding an AI column or an integration action means adding an entry here —
 * the queue, the worker, the DAG and the cost accounting all work off this
 * map and need no changes per runner.
 */
const RUNNERS = new Map<ColumnType, ColumnRunner<never>>([
  [httpRunner.type, httpRunner as ColumnRunner<never>],
  [formulaRunner.type, formulaRunner as ColumnRunner<never>],
  [enrichmentRunner.type, enrichmentRunner as ColumnRunner<never>],
  [aiRunner.type, aiRunner as ColumnRunner<never>],
]);

export function getRunner(type: ColumnType): ColumnRunner<never> | null {
  return RUNNERS.get(type) ?? null;
}

/** Whether a column of this type can currently be executed. */
export function isRunnable(type: ColumnType): boolean {
  return RUNNERS.has(type);
}

/**
 * Column keys a config depends on.
 *
 * Static columns have no dependencies, and a declared-but-unimplemented runner
 * type (`ai`, `waterfall`, ...) resolves to none rather than throwing — the
 * column can exist and be saved before its runner is built.
 */
export function resolveDeps(type: ColumnType, config: ColumnConfig): string[] {
  if (isStaticColumnType(type)) return [];
  if (type === "enrichment") {
    const enrichment = config as EnrichmentConfig;
    return [
      ...new Set(
        Object.values(enrichment.inputs ?? {})
          .filter((binding) => binding?.source === "column")
          .map((binding) => binding.columnKey),
      ),
    ];
  }
  const runner = getRunner(type);
  if (!runner) return [];
  return (runner as ColumnRunner<ColumnConfig>).resolveDeps(config);
}

export function estimateCost(type: ColumnType, config: ColumnConfig): number {
  const runner = getRunner(type);
  if (!runner) return 0;
  return (runner as ColumnRunner<ColumnConfig>).estimateCost(config);
}
