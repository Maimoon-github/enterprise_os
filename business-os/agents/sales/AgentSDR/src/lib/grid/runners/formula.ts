import type { CellResult, CellValues, FormulaConfig, FormulaLookupRegistry } from "../types";
import { checkFormulaSyntax, createSandbox, type Sandbox } from "./sandbox";
import { PermanentRunError, ownCell, tokensIn, type ColumnRunner, type RunSession } from "./types";
import { buildFormulaLookupRegistry, textColumnKeys } from "../formula-lookups";

const TOKEN_RE = /\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g;

/**
 * Substitutes {{key}} with the cell value as a JavaScript literal.
 *
 * Literal, not string concatenation: `{{Email}}.split("@")` has to become
 * `"ada@acme.com".split("@")`, so the value is JSON-encoded into the source.
 * JSON.stringify also does the escaping, which is what stops a cell containing
 * a quote from breaking out of the literal and into the surrounding expression.
 */
export function substituteTokens(
  expression: string,
  row: CellValues,
  textKeys: ReadonlySet<string> = new Set(),
): string {
  return expression.replace(TOKEN_RE, (_, key: string) => {
    const v = ownCell(row, key);
    // A blank text cell is "" (so concatenation does not print "null");
    // a blank number, date or JSON cell is null.
    if (v === undefined || v === null || v === "") return textKeys.has(key) ? '""' : "null";
    return JSON.stringify(v);
  });
}

/**
 * Formula columns: a JavaScript expression evaluated once per row.
 *
 * Row-level rather than cell-level, which is the difference from a spreadsheet
 * — an expression sees the whole row and produces this row's value. Inside the
 * sandbox it has lodash (`_`), moment, and the FormulaJS Excel functions
 * (VLOOKUP, IF, SUM, CONCATENATE, ...) as bare globals.
 */
export const formulaRunner: ColumnRunner<FormulaConfig> = {
  type: "formula",

  resolveDeps(config) {
    return [...new Set(tokensIn(config.expression))];
  },

  // One sandbox per run, reused across every row: booting the isolate and
  // loading the libraries costs ~60ms, against ~10µs for an evaluation.
  async prepare(config, ctx): Promise<RunSession> {
    const [registry, textKeys] = await Promise.all([
      buildFormulaLookupRegistry(config.lookupRefs),
      textColumnKeys(ctx.tableId),
    ]);
    const sandbox: Sandbox = await createSandbox(registry);
    return { sandbox, textKeys, dispose: () => sandbox.dispose() };
  },

  async run(config, row, _ctx, session): Promise<CellResult> {
    const expression = config.expression?.trim();
    if (!expression) {
      throw new PermanentRunError("This formula column has no expression yet");
    }

    const sandbox = session?.sandbox as Sandbox | undefined;
    if (!sandbox) throw new Error("Formula runner started without a sandbox");

    let value: unknown;
    try {
      value = sandbox.evaluate(substituteTokens(expression, row, session?.textKeys as Set<string> | undefined), row);
    } catch (err) {
      // A broken expression is broken for every row, so retrying it just burns
      // the queue — surface it as permanent.
      throw new PermanentRunError(err instanceof Error ? err.message : String(err));
    }

    // undefined is not JSON, and a formula that falls off the end returning
    // nothing should read as an empty cell rather than a crash.
    if (value === undefined) value = null;

    return {
      value,
      outcome: value === null || value === "" ? "miss" : "hit",
      costCents: 0,
    };
  },

  // Formulas run locally: no provider, no spend.
  estimateCost() {
    return 0;
  },
};

/**
 * Evaluates a formula against one row without touching the queue — used by the
 * formula editor's live preview and by run conditions.
 */
export async function evaluateOnce(
  expression: string,
  row: CellValues,
  lookupRegistry: FormulaLookupRegistry = {},
  textKeys?: ReadonlySet<string>,
): Promise<{ ok: true; value: unknown } | { ok: false; error: string }> {
  let sandbox: Sandbox | null = null;
  try {
    sandbox = await createSandbox(lookupRegistry);
    return { ok: true, value: sandbox.evaluate(substituteTokens(expression, row, textKeys), row) };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  } finally {
    sandbox?.dispose();
  }
}

/**
 * A run condition — "Only run if" — is just a formula read as a boolean.
 * Anything that throws counts as false: a condition that cannot be evaluated
 * must not silently authorise spending money on a provider call.
 */
export async function evaluateCondition(
  expression: string,
  row: CellValues,
  sandbox: Sandbox,
  textKeys?: ReadonlySet<string>,
): Promise<boolean> {
  try {
    return Boolean(sandbox.evaluate(substituteTokens(expression, row, textKeys), row));
  } catch {
    return false;
  }
}

/**
 * Throws a user-facing error when an expression does not compile. Tokens are
 * replaced by `null` first, so only the user's own syntax is judged.
 */
export async function assertFormulaSyntax(expression: string): Promise<void> {
  const problem = await checkFormulaSyntax(substituteTokens(expression, {}));
  if (problem) throw new Error(problem);
}

/**
 * Excel operators that are valid JavaScript with a different meaning — a lone
 * `&` is bitwise AND here, so `"a" & "b"` silently evaluates to 0. Returns a
 * hint for the first one found outside a string literal, or null.
 */
export function excelOnlyOperator(expression: string): string | null {
  for (let i = 0; i < expression.length; i += 1) {
    const char = expression[i];
    if (char === '"' || char === "'" || char === "`") {
      for (i += 1; i < expression.length && expression[i] !== char; i += 1) {
        if (expression[i] === "\\") i += 1;
      }
    } else if (char === "&" && expression[i + 1] !== "&" && expression[i - 1] !== "&") {
      return 'Use + to join text; "&" is bitwise AND in this formula language';
    } else if (char === "<" && expression[i + 1] === ">") {
      return 'Use !== for "not equal"; "<>" is not supported';
    }
  }
  return null;
}
