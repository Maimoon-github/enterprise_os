import { and, asc, eq, inArray, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";
import { inOrgTables, tableInOrganization } from "./scope";
import { gridColumns, gridJobs, gridRows, gridTables, type GridColumn } from "./schema";
import { getIntegrationAction } from "@/lib/integrations/catalog";
import { getAiModel, promptColumnKeys } from "@/lib/ai/catalog";
import type {
  AiConfig,
  AiOutputConfig,
  ColumnConfig,
  ColumnType,
  EnrichmentConfig,
  FormulaConfig,
  HttpConfig,
  IntegrationOutputConfig,
  StaticColumnType,
  TableView,
} from "./types";
import { isRunnerColumnType, isStaticColumnType } from "./types";
import { coerceClipboardValue } from "./clipboard";
import { HTTP_SECRET_ENV_PREFIX, isAllowedHttpSecretEnvVar } from "./runners/http";
import { assertFormulaSyntax, resolveDeps } from "./runners";
import { isResponseOutputKey } from "./json-pointer";
import { effectiveColumnType, inputAcceptsColumnType, describeAcceptedInputTypes } from "./value-types";
import { resolveFormulaConfig } from "./formula-lookups";

// ---------------------------------------------------------------------------
// Column keys
// ---------------------------------------------------------------------------

/**
 * "Job Title" -> "jobTitle".
 *
 * Deliberately the same shape as toCamelCaseKey() in outreach/leadImport.ts,
 * because an unmapped grid/file column pushed into a campaign lands in
 * people.raw and has to resolve as {{jobTitle}} through
 * outreach/scheduler.ts. This version additionally strips punctuation, so
 * "Email (work)" yields a usable token rather than "email(work)".
 */
export function toColumnKey(label: string): string {
  const words = label
    .trim()
    .replace(/[^A-Za-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  const key = words
    .map((w, i) => (i === 0 ? w.toLowerCase() : w[0].toUpperCase() + w.slice(1).toLowerCase()))
    .join("");
  // A key starting with a digit is legal JSON but confusing in a {{token}};
  // prefix it so it stays a readable identifier.
  return /^[0-9]/.test(key) ? `c${key}` : key;
}

/** Appends a numeric suffix until the key is free within the table. */
export function uniqueColumnKey(label: string, taken: Set<string>): string {
  const base = toColumnKey(label) || "column";
  if (!taken.has(base)) return base;
  let n = 2;
  while (taken.has(`${base}${n}`)) n += 1;
  return `${base}${n}`;
}

/**
 * "Text" -> "Text 2" -> "Text 3": the first free display name, compared
 * case-insensitively like a person would. Names are cosmetic (keys are
 * unique on their own) but two "Company" columns are indistinguishable in the
 * header and in every picker.
 */
export function uniqueColumnName(name: string, taken: Iterable<string>): string {
  const used = new Set([...taken].map((n) => n.trim().toLowerCase()));
  const base = name.trim();
  if (!used.has(base.toLowerCase())) return base;
  let n = 2;
  while (used.has(`${base} ${n}`.toLowerCase())) n += 1;
  return `${base} ${n}`;
}

/** A bound text[] — drizzle would expand a bare JS array into a tuple. */
function textArray(values: string[]) {
  return sql`ARRAY[${sql.join(values.map((v) => sql`${v}`), sql`, `)}]::text[]`;
}

function nameTaken(name: string, columns: Pick<GridColumn, "id" | "name">[], exceptId?: string): boolean {
  const wanted = name.trim().toLowerCase();
  return columns.some((c) => c.id !== exceptId && c.name.trim().toLowerCase() === wanted);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// ---------------------------------------------------------------------------
// Dependency resolution — the DAG edges
// ---------------------------------------------------------------------------

/**
 * Which column keys a config reads — the DAG edges.
 *
 * Delegated to the runner registry so each runner owns the answer for its own
 * config shape. Two copies of this logic would drift the moment a runner grew
 * a new templated field.
 */
export { resolveDeps } from "./runners";

/** Reject malformed runnable configs even when callers bypass the UI. */
export function validateColumnConfig(
  type: ColumnType,
  config: ColumnConfig,
  columns: Array<Pick<GridColumn, "key" | "type"> & Partial<Pick<GridColumn, "name" | "config">>> = [],
): void {
  if (!isPlainObject(config)) throw new Error("Column config must be an object");

  if (type === "select" || type === "multiselect") {
    const options = (config as { options?: unknown }).options;
    // Plain strings, or the { value, label?, color? } shape SelectOption declares.
    const valid = (o: unknown) =>
      typeof o === "string" ||
      (isPlainObject(o) &&
        typeof o.value === "string" &&
        (o.label === undefined || typeof o.label === "string") &&
        (o.color === undefined || typeof o.color === "string"));
    if (options !== undefined && (!Array.isArray(options) || !options.every(valid))) {
      throw new Error("Options must be a list of text values");
    }
  }

  if (type === "currency") {
    const currency = (config as { currency?: unknown }).currency;
    if (currency !== undefined && typeof currency !== "string") {
      throw new Error("Currency must be a currency code like USD");
    }
  }

  if (type === "formula") {
    const expression = (config as FormulaConfig).expression;
    if (typeof expression !== "string" || !expression.trim()) {
      throw new Error("Formula expression is required");
    }
  }

  if (type === "http") {
    const http = config as HttpConfig;
    if (!(["GET", "POST", "PUT", "PATCH"] as const).includes(http.method)) {
      throw new Error("HTTP method must be GET, POST, PUT, or PATCH");
    }
    if (typeof http.url !== "string" || !http.url.trim()) {
      throw new Error("HTTP URL is required");
    }
    if (http.authEnvVar !== undefined && http.authEnvVar !== "" && (
      typeof http.authEnvVar !== "string" || !isAllowedHttpSecretEnvVar(http.authEnvVar)
    )) {
      throw new Error(
        `The credential env var must be named ${HTTP_SECRET_ENV_PREFIX}<NAME>, using capital letters, digits and underscores (for example ${HTTP_SECRET_ENV_PREFIX}APOLLO)`,
      );
    }
    if (http.costCents !== undefined && (!Number.isFinite(http.costCents) || http.costCents < 0)) {
      throw new Error("HTTP cost must be zero or a positive number");
    }
  }

  if (type === "enrichment") {
    const enrichment = config as EnrichmentConfig;
    const action = getIntegrationAction(enrichment.integrationKey, enrichment.actionKey);
    if (!action) throw new Error("Unknown integration action");
    if (enrichment.handlerKey !== action.handlerKey) throw new Error("Integration handler does not match the action");
    if (!enrichment.connectionId) throw new Error("Select a connected integration account");
    if (
      enrichment.delaySeconds !== undefined &&
      (!Number.isInteger(enrichment.delaySeconds) || enrichment.delaySeconds < 0 || enrichment.delaySeconds > 600)
    ) {
      throw new Error("Run delay must be between 0 and 600 seconds");
    }
    const knownInputs = new Set(action.inputs.map((input) => input.key));
    if (Object.keys(enrichment.inputs ?? {}).some((key) => !knownInputs.has(key))) {
      throw new Error("The enrichment contains an unknown input");
    }

    if (action.filterBuilder) {
      const mappedFilters = action.inputs.filter(
        (input) => input.group === "filter" && enrichment.inputs?.[input.key]?.columnKey,
      );
      if (mappedFilters.length < action.filterBuilder.minFilters) {
        throw new Error(
          `Map at least ${action.filterBuilder.minFilters} search filter${action.filterBuilder.minFilters === 1 ? "" : "s"}`,
        );
      }
    }

    for (const input of action.inputs) {
      const binding = enrichment.inputs?.[input.key];
      if (!binding && input.required) throw new Error(`${input.name} is required`);
      if (!binding) continue;
      if (binding.source !== "column" || !binding.columnKey) {
        throw new Error(`${input.name} must be mapped to a column`);
      }
      const source = columns.find((column) => column.key === binding.columnKey);
      if (!source) throw new Error(`${input.name} references a missing column`);
      const sourceType = effectiveColumnType(source);
      if (!inputAcceptsColumnType(input.acceptedColumnTypes, sourceType)) {
        throw new Error(
          `${input.name} needs a ${describeAcceptedInputTypes(input.acceptedColumnTypes)} column, but "${source.name ?? source.key}" is ${sourceType}`,
        );
      }
    }

    const selectedOutputs = Object.keys(enrichment.outputs ?? {});
    if (!selectedOutputs.length) throw new Error("Select at least one output");
    const knownOutputs = new Set(action.outputs.map((output) => output.key));
    if (selectedOutputs.some((key) => !knownOutputs.has(key) && !isResponseOutputKey(key))) {
      throw new Error("The enrichment contains an unknown output");
    }
  }

  if (type === "ai") {
    const ai = config as AiConfig;
    const model = getAiModel(ai.providerKey, ai.modelKey, ai.useCase);
    if (!model) throw new Error("Select an AI model");
    if (!model.useCases.includes(ai.useCase)) {
      throw new Error(`${model.name} cannot be used for this use case`);
    }
    if (!ai.connectionId) throw new Error("Connect an AI provider account");
    if (typeof ai.prompt !== "string" || !ai.prompt.trim()) {
      throw new Error("A prompt is required");
    }

    // Every {{token}} must name a real column, or the prompt silently reaches
    // the model with a blank where the user expected data.
    const known = new Set(columns.map((column) => column.key));
    const missing = promptColumnKeys(ai.prompt).find((key) => !known.has(key));
    if (missing) throw new Error(`The prompt references a missing column: ${missing}`);

    if (ai.outputFormat === "json_schema") {
      if (!ai.jsonSchema || typeof ai.jsonSchema !== "object") {
        throw new Error("Provide a JSON Schema, or switch the output format to Fields");
      }
    } else {
      if (!ai.outputs?.length) throw new Error("Add at least one output field");
      const keys = new Set<string>();
      const names = new Set<string>();
      for (const field of ai.outputs) {
        if (!field.key?.trim() || !field.name?.trim()) {
          throw new Error("Every output needs a name");
        }
        if (keys.has(field.key)) throw new Error(`Duplicate output field: ${field.key}`);
        keys.add(field.key);
        // Output names become column names (and keys), so two "dup" fields
        // would silently become "dup" and "dup 2".
        const name = field.name.trim().toLowerCase();
        if (names.has(name)) throw new Error(`Two outputs are named "${field.name.trim()}" — give each a different name`);
        names.add(name);
        if (!isStaticColumnType(field.type)) {
          throw new Error(`${field.name} has an invalid output type`);
        }
      }
    }

    if (
      ai.delaySeconds !== undefined &&
      (!Number.isInteger(ai.delaySeconds) || ai.delaySeconds < 0 || ai.delaySeconds > 600)
    ) {
      throw new Error("Run delay must be between 0 and 600 seconds");
    }
  }

  if (type === "integration_output") {
    const output = config as IntegrationOutputConfig;
    if (!output.integrationKey || !output.actionKey || !output.sourceColumnKey || !output.outputKey) {
      throw new Error("Integration output configuration is incomplete");
    }
    if (output.valueType && !isStaticColumnType(output.valueType)) {
      throw new Error("Integration output value type is invalid");
    }
  }

  if (type === "ai_output") {
    const output = config as AiOutputConfig;
    if (!output.sourceColumnKey || !output.outputKey) {
      throw new Error("AI output configuration is incomplete");
    }
    if (!isStaticColumnType(output.valueType)) {
      throw new Error("AI output value type is invalid");
    }
  }
}

/**
 * Throws if adding/updating `candidate` would create a cycle.
 *
 * Cycles are rejected here, at save time, rather than being discovered by a
 * worker mid-run — a cyclic graph would otherwise enqueue cells forever.
 */
export function assertNoCycle(
  columns: Pick<GridColumn, "key" | "dependsOn">[],
  candidate: { key: string; dependsOn: string[] },
): void {
  const graph = new Map<string, string[]>();
  for (const c of columns) {
    if (c.key === candidate.key) continue;
    graph.set(c.key, c.dependsOn);
  }
  graph.set(candidate.key, candidate.dependsOn);

  const state = new Map<string, "visiting" | "done">();

  const visit = (key: string, path: string[]): void => {
    const s = state.get(key);
    if (s === "done") return;
    if (s === "visiting") {
      const cycle = [...path.slice(path.indexOf(key)), key].join(" → ");
      throw new Error(`Circular dependency: ${cycle}`);
    }
    state.set(key, "visiting");
    for (const dep of graph.get(key) ?? []) visit(dep, [...path, key]);
    state.set(key, "done");
  };

  for (const key of graph.keys()) visit(key, []);
}

/** Columns ordered so every column appears after everything it depends on. */
export function topoSort(columns: GridColumn[]): GridColumn[] {
  const byKey = new Map(columns.map((c) => [c.key, c]));
  const state = new Map<string, "visiting" | "done">();
  const out: GridColumn[] = [];

  const visit = (key: string) => {
    if (state.get(key) === "done") return;
    if (state.get(key) === "visiting") throw new Error(`Circular dependency at "${key}"`);
    const col = byKey.get(key);
    if (!col) return; // dependency on a deleted column — treated as a constant
    state.set(key, "visiting");
    for (const dep of col.dependsOn) visit(dep);
    state.set(key, "done");
    out.push(col);
  };

  for (const c of columns) visit(c.key);
  return out;
}

/** Direct dependents — the cascade set when a cell finishes. */
export function columnsDependingOn(columns: GridColumn[], key: string): GridColumn[] {
  return columns.filter((c) => c.dependsOn.includes(key));
}

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export async function listColumns(tableId: string): Promise<GridColumn[]> {
  return db
    .select()
    .from(gridColumns)
    .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.tableId, tableId)))
    .orderBy(asc(gridColumns.position));
}

export async function createColumn(input: {
  tableId: string;
  name: string;
  type: ColumnType;
  config?: ColumnConfig;
  autoRun?: boolean;
  /** Insert after this column; appended to the end when omitted. */
  afterColumnId?: string;
  /** Insert immediately before this column. Takes precedence over afterColumnId. */
  beforeColumnId?: string;
  /** Key of a static column whose cell values are copied into the new column. */
  copyValuesFrom?: string;
}): Promise<GridColumn> {
  if (!(await tableInOrganization(input.tableId))) throw new Error("That table no longer exists");
  const name = input.name.trim();
  if (!name) throw new Error("Column name is required");
  const existing = await listColumns(input.tableId);
  const key = uniqueColumnKey(name, new Set(existing.map((c) => c.key)));

  let copyFrom: GridColumn | undefined;
  if (input.copyValuesFrom !== undefined) {
    copyFrom = existing.find((c) => c.key === input.copyValuesFrom);
    if (!copyFrom) throw new Error("The column to copy values from no longer exists");
    if (!isStaticColumnType(copyFrom.type)) throw new Error("Values can only be copied from a data column");
    if (!isStaticColumnType(input.type)) throw new Error("Copied values need a data column type");
  }

  if (input.type === "formula") await assertFormulaSyntax((input.config as FormulaConfig | undefined)?.expression ?? "");
  const config = input.type === "formula"
    ? await resolveFormulaConfig(input.tableId, (input.config as FormulaConfig | undefined)?.expression ?? "")
    : input.config ?? {};
  validateColumnConfig(input.type, config, existing);
  const dependsOn = resolveDeps(input.type, config);

  assertNoCycle(existing, { key, dependsOn });

  return db.transaction(async (tx) => {
    const [column] = await tx
      .insert(gridColumns)
      .values({
        tableId: input.tableId,
        key,
        // Two "Company" columns look identical in the header and every picker.
        name: uniqueColumnName(name, existing.map((c) => c.name)),
        type: input.type,
        config,
        autoRun: input.autoRun ?? true,
        dependsOn,
        position: input.beforeColumnId
          ? positionBefore(existing, input.beforeColumnId)
          : nextPosition(existing, input.afterColumnId),
      })
      .returning();

    if (copyFrom) {
      await tx
        .update(gridRows)
        .set({
          cells: sql`jsonb_set(${gridRows.cells}, ARRAY[${key}]::text[], ${gridRows.cells} -> ${copyFrom.key})`,
          version: sql`nextval('grid_row_version_seq')`,
          updatedAt: new Date(),
        })
        .where(and(
          inOrgTables(gridRows.tableId),
          eq(gridRows.tableId, input.tableId),
          sql`${gridRows.cells} -> ${copyFrom.key} IS NOT NULL`,
        ));
    }
    return column;
  });
}

const TEXT_LIKE: ReadonlySet<StaticColumnType> = new Set(["text", "email", "url", "image", "select", "date"]);

/**
 * One stored value re-expressed for a new static column type. Text goes
 * through the same coercion as a paste ("1,200" -> 1200); anything that does
 * not convert stays exactly as it was — a type change must never destroy data.
 */
export function convertStoredValue(value: unknown, to: StaticColumnType): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "string") {
    // A type change never destroys data: what does not convert stays as is.
    // Blank text is not data, and becomes an empty cell.
    if (!value.trim()) return null;
    const converted = coerceClipboardValue(value, to);
    return converted === null || converted === undefined ? value : converted;
  }
  if (Array.isArray(value)) {
    if (!TEXT_LIKE.has(to)) return value;
    const plain = value.every((item) => item === null || typeof item !== "object");
    return plain ? value.map(String).join(", ") : JSON.stringify(value);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    if (TEXT_LIKE.has(to)) return String(value);
    if (to === "boolean" && (value === 1 || value === 0)) return value === 1;
    return value;
  }
  return TEXT_LIKE.has(to) ? JSON.stringify(value) : value;
}

/** Re-coerces every stored value of `key` for a static -> static type change. */
async function convertColumnValues(
  tx: Pick<typeof db, "select" | "execute">,
  tableId: string,
  key: string,
  to: StaticColumnType,
): Promise<void> {
  const rows = await tx
    .select({ id: gridRows.id, cells: gridRows.cells })
    .from(gridRows)
    .where(and(
      inOrgTables(gridRows.tableId),
      eq(gridRows.tableId, tableId),
      sql`${gridRows.cells} -> ${key} IS NOT NULL`,
    ));

  const changes: { id: string; value: unknown }[] = [];
  for (const row of rows) {
    const before = row.cells[key];
    const after = convertStoredValue(before, to);
    if (JSON.stringify(after ?? null) !== JSON.stringify(before ?? null)) changes.push({ id: row.id, value: after ?? null });
  }

  const CHUNK = 250;
  for (let offset = 0; offset < changes.length; offset += CHUNK) {
    const values = sql.join(
      changes.slice(offset, offset + CHUNK).map(({ id, value }) => sql`(${id}::uuid, ${JSON.stringify(value)}::jsonb)`),
      sql`, `,
    );
    await tx.execute(sql`
      UPDATE ${gridRows}
      SET
        cells = jsonb_set(${gridRows.cells}, ARRAY[${key}]::text[], source.value),
        version = nextval('grid_row_version_seq'),
        updated_at = now()
      FROM (VALUES ${values}) AS source(id, value)
      WHERE ${gridRows.id} = source.id
        AND ${gridRows.tableId} = ${tableId}::uuid
        AND ${gridRows.tableId} IN (SELECT id FROM ${gridTables} WHERE organization_id = ${currentOrganizationId()})
    `);
  }
}

export async function updateColumn(
  id: string,
  patch: {
    name?: string;
    type?: ColumnType;
    config?: ColumnConfig;
    autoRun?: boolean;
    /** Reposition after this column (null = to the front), in the same save. */
    afterColumnId?: string | null;
  },
  /** When given, the column must belong to this table (else treated as not found). */
  tableId?: string,
): Promise<GridColumn | null> {
  const [current] = await db
    .select()
    .from(gridColumns)
    .where(and(
      inOrgTables(gridColumns.tableId),
      eq(gridColumns.id, id),
      ...(tableId ? [eq(gridColumns.tableId, tableId)] : []),
    ))
    .limit(1);
  if (!current) return null;

  const siblings = await listColumns(current.tableId);
  const values: Record<string, unknown> = { updatedAt: new Date() };
  // `name` is cosmetic; `key` deliberately never changes, so a rename here
  // does not touch a single row's JSONB.
  if (patch.name !== undefined) {
    const name = patch.name.trim();
    if (!name) throw new Error("Column name cannot be empty");
    // Only a real rename is checked: tables made before names were unique
    // can hold two "Formula" columns, and re-saving one must still work.
    const renamed = name.toLowerCase() !== current.name.trim().toLowerCase();
    if (renamed && nameTaken(name, siblings, current.id)) throw new Error(`A column named "${name}" already exists`);
    values.name = name;
  }
  if (patch.autoRun !== undefined) values.autoRun = patch.autoRun;

  if (patch.afterColumnId !== undefined) {
    const others = siblings.filter((c) => c.id !== current.id);
    if (patch.afterColumnId !== null && !others.some((c) => c.id === patch.afterColumnId)) {
      throw new Error("afterColumnId must be another column in this table");
    }
    values.position = nextPosition(others, patch.afterColumnId ?? undefined, true);
  }

  let convertTo: StaticColumnType | null = null;
  let dropJobs = false;
  if (patch.type !== undefined || patch.config !== undefined) {
    const type = patch.type ?? current.type;
    const candidateConfig = patch.config ?? current.config;
    if (type === "formula") await assertFormulaSyntax((candidateConfig as FormulaConfig).expression ?? "");
    const config = type === "formula"
      ? await resolveFormulaConfig(
          current.tableId,
          (candidateConfig as FormulaConfig).expression ?? "",
          current.type === "formula" ? (current.config as FormulaConfig).lookupRefs : [],
        )
      : candidateConfig;
    validateColumnConfig(type, config, siblings);
    const dependsOn = resolveDeps(type, config);
    assertNoCycle(siblings, { key: current.key, dependsOn });

    values.type = type;
    values.config = config;
    values.dependsOn = dependsOn;

    if (type !== current.type && isStaticColumnType(type)) {
      if (isStaticColumnType(current.type)) convertTo = type;
      // A runner column turned into a data column must stop being run.
      else if (isRunnerColumnType(current.type)) dropJobs = true;
    }
  }

  return db.transaction(async (tx) => {
    if (convertTo) await convertColumnValues(tx, current.tableId, current.key, convertTo);
    if (dropJobs) {
      await tx.delete(gridJobs).where(and(
        inOrgTables(gridJobs.tableId),
        eq(gridJobs.tableId, current.tableId),
        eq(gridJobs.columnKey, current.key),
      ));
    }
    const [row] = await tx
      .update(gridColumns)
      .set(values)
      .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.id, id)))
      .returning();
    return row ?? null;
  });
}

/** Columns a source (AI / enrichment) column writes into, by its mapping or their back-reference. */
function outputsOf(column: GridColumn, siblings: GridColumn[]): GridColumn[] {
  const keys = new Set<string>();
  if (column.type === "ai") {
    for (const key of Object.values((column.config as AiConfig).outputColumns ?? {})) keys.add(key);
  }
  if (column.type === "enrichment") {
    for (const key of Object.values((column.config as EnrichmentConfig).outputs ?? {})) keys.add(key);
  }
  for (const candidate of siblings) {
    if (
      (candidate.type === "ai_output" || candidate.type === "integration_output") &&
      (candidate.config as { sourceColumnKey?: string }).sourceColumnKey === column.key
    ) keys.add(candidate.key);
  }
  keys.delete(column.key);
  return siblings.filter((candidate) => keys.has(candidate.key));
}

/**
 * Deletes a column and strips its key from every row's JSONB.
 *
 * The strip is not cosmetic: leaving the key behind means a later column
 * created with the same key would silently inherit the old values.
 *
 * `withOutputs` also deletes the output columns an AI / enrichment column
 * writes into. Either way the column's queued jobs go with it, and deleting a
 * single output column removes it from its source's mapping so the source
 * stops filling it (and the dialog stops listing it as already added).
 * Returns the ids removed, or null when the column does not exist.
 */
export async function deleteColumn(
  id: string,
  opts: { withOutputs?: boolean; tableId?: string } = {},
): Promise<{ deletedIds: string[] } | null> {
  const [column] = await db
    .select()
    .from(gridColumns)
    .where(and(
      inOrgTables(gridColumns.tableId),
      eq(gridColumns.id, id),
      ...(opts.tableId ? [eq(gridColumns.tableId, opts.tableId)] : []),
    ))
    .limit(1);
  if (!column) return null;

  const siblings = await listColumns(column.tableId);
  const doomed = [column, ...(opts.withOutputs ? outputsOf(column, siblings) : [])];
  const doomedKeys = new Set(doomed.map((c) => c.key));
  const dependents = siblings.filter(
    (candidate) => !doomedKeys.has(candidate.key) && candidate.dependsOn.some((key) => doomedKeys.has(key)),
  );
  if (dependents.length) {
    throw new Error(
      `Column is used by: ${dependents.map((candidate) => candidate.name).join(", ")}`,
    );
  }

  const [sourceTable] = await db
    .select({ workbookId: gridTables.workbookId })
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.id, column.tableId)))
    .limit(1);
  if (sourceTable) {
    const workbookTables = await db
      .select({ id: gridTables.id })
      .from(gridTables)
      .where(and(inOrg(gridTables), eq(gridTables.workbookId, sourceTable.workbookId)));
    const formulaColumns = workbookTables.length
      ? await db.select().from(gridColumns).where(inArray(gridColumns.tableId, workbookTables.map((table) => table.id)))
      : [];
    const lookupDependents = formulaColumns.filter((candidate) =>
      candidate.type === "formula"
      && (candidate.config as FormulaConfig).lookupRefs?.some((ref) =>
        ref.tableId === column.tableId
        && (doomedKeys.has(ref.lookupColumnKey) || doomedKeys.has(ref.returnColumnKey)),
      ),
    );
    if (lookupDependents.length) {
      throw new Error(
        `Column is used by cross-table formula${lookupDependents.length === 1 ? "" : "s"}: ${lookupDependents.map((candidate) => candidate.name).join(", ")}`,
      );
    }
  }

  const [table] = await db
    .select({ view: gridTables.view })
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.id, column.tableId)))
    .limit(1);
  let nextView = (table?.view ?? {}) as TableView;
  for (const key of doomedKeys) nextView = removeColumnFromView(nextView, key);

  // Sources that still list a doomed column as one of their outputs.
  const parentUpdates: { id: string; config: AiConfig | EnrichmentConfig }[] = [];
  for (const parent of siblings) {
    if (doomedKeys.has(parent.key)) continue;
    if (parent.type === "ai") {
      const config = parent.config as AiConfig;
      const removed = Object.entries(config.outputColumns ?? {}).filter(([, key]) => doomedKeys.has(key)).map(([field]) => field);
      if (!removed.length) continue;
      parentUpdates.push({
        id: parent.id,
        config: {
          ...config,
          outputColumns: Object.fromEntries(Object.entries(config.outputColumns).filter(([field]) => !removed.includes(field))),
          outputs: (config.outputs ?? []).filter((field) => !removed.includes(field.key)),
        },
      });
    } else if (parent.type === "enrichment") {
      const config = parent.config as EnrichmentConfig;
      const kept = Object.entries(config.outputs ?? {}).filter(([, key]) => !doomedKeys.has(key));
      if (kept.length === Object.keys(config.outputs ?? {}).length) continue;
      parentUpdates.push({ id: parent.id, config: { ...config, outputs: Object.fromEntries(kept) } });
    }
  }

  const keys = [...doomedKeys];
  await db.transaction(async (tx) => {
    await tx.delete(gridColumns).where(and(
      inOrgTables(gridColumns.tableId),
      eq(gridColumns.tableId, column.tableId),
      inArray(gridColumns.id, doomed.map((c) => c.id)),
    ));
    await tx.delete(gridJobs).where(and(
      inOrgTables(gridJobs.tableId),
      eq(gridJobs.tableId, column.tableId),
      inArray(gridJobs.columnKey, keys),
    ));
    for (const update of parentUpdates) {
      await tx.update(gridColumns).set({ config: update.config, updatedAt: new Date() }).where(and(
        inOrgTables(gridColumns.tableId),
        eq(gridColumns.id, update.id),
      ));
    }
    await tx
      .update(gridTables)
      .set({ view: nextView, updatedAt: new Date() })
      .where(and(inOrg(gridTables), eq(gridTables.id, column.tableId)));
    await tx
      .update(gridRows)
      .set({
        cells: sql`${gridRows.cells} - ${textArray(keys)}`,
        cellMeta: sql`${gridRows.cellMeta} - ${textArray(keys)}`,
        version: sql`nextval('grid_row_version_seq')`,
        updatedAt: new Date(),
      })
      .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, column.tableId)));
  });

  return { deletedIds: doomed.map((c) => c.id) };
}

function removeColumnFromView(view: TableView, columnKey: string): TableView {
  const cleanConditions = (conditions: unknown[]): unknown[] =>
    conditions
      .map((condition) => {
        if (!condition || typeof condition !== "object") return condition;
        if ("conditions" in condition && Array.isArray(condition.conditions)) {
          return { ...condition, conditions: cleanConditions(condition.conditions) };
        }
        if ("columnKey" in condition && condition.columnKey === columnKey) return null;
        return condition;
      })
      .filter((condition) => condition !== null);

  return {
    ...view,
    hiddenColumns: view.hiddenColumns?.filter((key) => key !== columnKey),
    pinnedColumns: view.pinnedColumns?.filter((key) => key !== columnKey),
    sorts: view.sorts?.filter((sort) => sort.columnKey !== columnKey),
    filters: view.filters
      ? { ...view.filters, conditions: cleanConditions(view.filters.conditions) }
      : undefined,
  };
}

/**
 * Fractional reposition — moving a column rewrites one row, not the table.
 * The anchor must be a different column of the same table.
 */
export async function moveColumn(
  id: string,
  afterColumnId: string | null,
  tableId?: string,
): Promise<GridColumn | null> {
  const [column] = await db
    .select()
    .from(gridColumns)
    .where(and(
      inOrgTables(gridColumns.tableId),
      eq(gridColumns.id, id),
      ...(tableId ? [eq(gridColumns.tableId, tableId)] : []),
    ))
    .limit(1);
  if (!column) return null;

  const siblings = (await listColumns(column.tableId)).filter((c) => c.id !== id);
  if (afterColumnId !== null && !siblings.some((c) => c.id === afterColumnId)) {
    throw new Error("afterColumnId must be another column in this table");
  }
  const [row] = await db
    .update(gridColumns)
    .set({ position: nextPosition(siblings, afterColumnId ?? undefined, true), updatedAt: new Date() })
    .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.id, id)))
    .returning();

  return row ?? null;
}

/**
 * Position midway between the anchor and the next item, so inserts never
 * renumber neighbours. `atStartWhenNoAnchor` distinguishes "append" (new
 * column) from "move to front" (reorder with a null anchor).
 */
function nextPosition(
  ordered: { id: string; position: number }[],
  afterId?: string,
  atStartWhenNoAnchor = false,
): number {
  if (!afterId) {
    if (!ordered.length) return 1;
    return atStartWhenNoAnchor
      ? ordered[0].position / 2
      : ordered[ordered.length - 1].position + 1;
  }
  const idx = ordered.findIndex((c) => c.id === afterId);
  if (idx === -1) return (ordered[ordered.length - 1]?.position ?? 0) + 1;
  const before = ordered[idx].position;
  const after = ordered[idx + 1]?.position;
  return after === undefined ? before + 1 : (before + after) / 2;
}

/** Position immediately before an existing column without renumbering siblings. */
function positionBefore(
  ordered: { id: string; position: number }[],
  beforeId: string,
): number {
  const idx = ordered.findIndex((column) => column.id === beforeId);
  if (idx === -1) return (ordered[ordered.length - 1]?.position ?? 0) + 1;
  if (idx === 0) return ordered[0].position / 2;
  return (ordered[idx - 1].position + ordered[idx].position) / 2;
}
