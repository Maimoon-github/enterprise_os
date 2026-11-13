import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { getQuickJS, type QuickJSContext, type QuickJSRuntime } from "quickjs-emscripten";
import type { FormulaLookupRegistry } from "../types";

/**
 * Sandboxed JavaScript evaluation for formula columns.
 *
 * QuickJS compiled to WebAssembly, NOT node:vm. Node's own documentation says
 * the vm module "is not a security mechanism", and vm2 — the usual workaround —
 * has had critical sandbox-escape CVEs. A formula is user-authored code
 * running on the server of a self-hosted app, and workbook templates get
 * shared between people, so it has to be a real boundary.
 *
 * The WASM isolate has no host bindings at all: no process, no require, no
 * fetch, no filesystem. The classic
 * `this.constructor.constructor("return process")()` escape yields undefined.
 * There is nothing to reach even if the guest breaks out of its own scope.
 *
 * isolated-vm would also work and is faster, but it is a native C++ addon
 * needing a compiler at install time, which would wreck the "docker run plus
 * DATABASE_URL" self-host story this project is built around.
 */

const require_ = createRequire(import.meta.url);

/** Wall-clock budget for a single formula evaluation. */
const EVAL_TIMEOUT_MS = 1_000;
const MEMORY_LIMIT = 32 * 1024 * 1024;
const STACK_LIMIT = 512 * 1024;

/**
 * Libraries made available inside the isolate, matching what Clay's formulas
 * expose. Loading them costs ~60ms, which is why a sandbox is reused across
 * every row of a run rather than created per cell.
 */
const LIBRARIES: { global: string; path: string }[] = [
  { global: "_", path: "lodash/lodash.min.js" },
  { global: "moment", path: "moment/min/moment.min.js" },
  { global: "formulajs", path: "@formulajs/formulajs/lib/browser/formula.min.js" },
];

let librarySourceCache: string | null = null;

/**
 * Reads a library's source, working around package `exports` maps.
 *
 * `require.resolve` on a deep subpath fails for packages that declare
 * `exports` without listing it — @formulajs/formulajs is one, which is how it
 * came to load silently as `undefined` and take every Excel function
 * (UPPER, VLOOKUP, ...) with it. Resolving the package.json and joining the
 * path by hand sidesteps the exports map.
 */
function readLibrary(subpath: string): string | null {
  try {
    return readFileSync(require_.resolve(subpath), "utf8");
  } catch {
    // fall through to the package.json route
  }

  const slash = subpath.indexOf("/", subpath.startsWith("@") ? subpath.indexOf("/") + 1 : 0);
  const pkg = slash === -1 ? subpath : subpath.slice(0, slash);
  const rest = slash === -1 ? "" : subpath.slice(slash + 1);

  try {
    const pkgDir = dirname(require_.resolve(`${pkg}/package.json`));
    return readFileSync(join(pkgDir, rest), "utf8");
  } catch {
    // fall through to the cwd route
  }

  // Last resort, and the one that actually works under Next: the server code
  // is bundled into .next/server/chunks, so `import.meta.url` — and therefore
  // createRequire's resolution base — points there rather than at the app
  // root, and neither require.resolve route finds node_modules. The process
  // working directory is the app root in both `next start` and the standalone
  // output, so resolve from there.
  try {
    return readFileSync(join(process.cwd(), "node_modules", subpath), "utf8");
  } catch {
    return null;
  }
}


/**
 * Concatenated library source, read once per process.
 *
 * `require.resolve` rather than a hardcoded node_modules path so this keeps
 * working under a bundler; the files are pinned into the standalone build via
 * outputFileTracingIncludes in next.config.ts, since a readFileSync path is
 * invisible to Next's module tracer.
 */
function librarySource(): string {
  if (librarySourceCache !== null) return librarySourceCache;

  const parts: string[] = [];
  for (const lib of LIBRARIES) {
    const source = readLibrary(lib.path);
    if (source === null) {
      // A missing library must not take the whole formula engine down, but it
      // must be loud: a formula referencing that global fails per row with a
      // bare "is not defined", which is very hard to trace back to here.
      console.error(
        `[grid/sandbox] FAILED to load ${lib.path} — formulas using ${lib.global} will fail`,
      );
      continue;
    }
    parts.push(source);
  }

  // FormulaJS exports one object; Clay exposes its functions as bare globals
  // (VLOOKUP, CONCATENATE, ...), so spread them.
  parts.push(`
    if (typeof formulajs === "object" && formulajs) {
      for (var k in formulajs) { if (typeof globalThis[k] === "undefined") globalThis[k] = formulajs[k]; }
    }
    // A blank text cell arrives as "", which a spreadsheet's ISBLANK counts
    // as blank; FormulaJS only checks for null.
    globalThis.ISBLANK = function (value) { return value === null || value === undefined || value === ""; };
  `);

  librarySourceCache = parts.join("\n;\n");
  return librarySourceCache;
}

/**
 * Finds an unbalanced bracket in a JavaScript expression, ignoring string and
 * comment contents. Used only to word a SyntaxError: evaluation wraps the
 * expression in `return (...)`, so the engine reports an unclosed "(" as an
 * "unexpected ')'" pointing at the wrapper rather than at the user's text.
 */
export function bracketProblem(expression: string): string | null {
  const pairs: Record<string, string> = { ")": "(", "]": "[", "}": "{" };
  const stack: string[] = [];
  for (let i = 0; i < expression.length; i += 1) {
    const char = expression[i];
    if (char === '"' || char === "'" || char === "`") {
      for (i += 1; i < expression.length && expression[i] !== char; i += 1) {
        if (expression[i] === "\\") i += 1;
      }
    } else if (char === "/" && expression[i + 1] === "/") {
      while (i < expression.length && expression[i] !== "\n") i += 1;
    } else if (char === "/" && expression[i + 1] === "*") {
      const end = expression.indexOf("*/", i + 2);
      if (end === -1) return "Unclosed comment: add */";
      i = end + 1;
    } else if (char === "(" || char === "[" || char === "{") {
      stack.push(char);
    } else if (char in pairs) {
      if (stack.pop() !== pairs[char]) return `Unexpected "${char}" in the formula`;
    }
  }
  const open = stack.pop();
  if (!open) return null;
  const close = open === "(" ? ")" : open === "[" ? "]" : "}";
  return `Unclosed "${open}" in the formula: add a matching "${close}"`;
}

/** The message shown for a SyntaxError raised while compiling the user's expression. */
export function describeSyntaxError(expression: string, engineMessage: string): string {
  const message = bracketProblem(expression) ?? engineMessage;
  return `Formula syntax error: ${message}`;
}

/**
 * Compiles an expression without running it. Returns null when it parses, or a
 * message naming the problem. Needs no libraries, so it is cheap enough to run
 * on every save. {{tokens}} must already be substituted (any literal will do).
 */
export async function checkFormulaSyntax(expression: string): Promise<string | null> {
  const QJS = await getQuickJS();
  const runtime = QJS.newRuntime();
  runtime.setMemoryLimit(MEMORY_LIMIT);
  const ctx = runtime.newContext();
  try {
    // Defining the function compiles the body; it is never called.
    const result = ctx.evalCode(`(function (row) { "use strict"; return (\n${expression}\n); })`);
    if (!result.error) {
      result.value.dispose();
      return null;
    }
    const dumped = ctx.dump(result.error) as { message?: string };
    result.error.dispose();
    return describeSyntaxError(expression, dumped?.message ?? "invalid expression");
  } finally {
    ctx.dispose();
    runtime.dispose();
  }
}

export type Sandbox = {
  /**
   * Evaluates `expression` with the row bound. Returns the value, or throws
   * with the guest's error message.
   */
  evaluate(expression: string, row: Record<string, unknown>): unknown;
  dispose(): void;
};

/**
 * Creates an isolate with the libraries preloaded.
 *
 * Expensive (~60ms), so callers reuse one per run — see sandboxPool.ts.
 */
export async function createSandbox(lookupRegistry: FormulaLookupRegistry = {}): Promise<Sandbox> {
  const QJS = await getQuickJS();
  const runtime: QuickJSRuntime = QJS.newRuntime();
  runtime.setMemoryLimit(MEMORY_LIMIT);
  runtime.setMaxStackSize(STACK_LIMIT);

  const ctx: QuickJSContext = runtime.newContext();

  const boot = ctx.evalCode(librarySource());
  if (boot.error) {
    const err = ctx.dump(boot.error);
    boot.error.dispose();
    ctx.dispose();
    runtime.dispose();
    throw new Error(`Sandbox failed to start: ${JSON.stringify(err)}`);
  }
  boot.value.dispose();

  // Load cross-table data once per run. Putting this JSON into every row's
  // program would make a 50k-row lookup table get reparsed for every cell.
  const lookupBoot = ctx.evalCode(`
    (function (registry) {
      const lookup = function (table, value, lookupColumn, returnColumn, defaultValue) {
        const signature = JSON.stringify([table, lookupColumn, returnColumn].map(function (item) {
          return String(item).trim().toLowerCase();
        }));
        const values = registry[signature];
        if (!values) return arguments.length >= 5 ? defaultValue : null;
        const valueKey = (value === null ? "null" : typeof value) + ":" + JSON.stringify(value === undefined ? null : value);
        if (!Object.prototype.hasOwnProperty.call(values, valueKey)) return arguments.length >= 5 ? defaultValue : null;
        const result = values[valueKey];
        return result && typeof result === "object" ? JSON.parse(JSON.stringify(result)) : result;
      };
      Object.defineProperty(globalThis, "__gridLookup", { value: lookup, writable: false, configurable: false });
    })(${JSON.stringify(lookupRegistry)});
  `);
  if (lookupBoot.error) {
    const err = ctx.dump(lookupBoot.error);
    lookupBoot.error.dispose();
    ctx.dispose();
    runtime.dispose();
    throw new Error(`Lookup registry failed to load: ${JSON.stringify(err)}`);
  }
  lookupBoot.value.dispose();

  return {
    evaluate(expression: string, row: Record<string, unknown>): unknown {
      // The deadline is enforced by the interrupt handler, which QuickJS calls
      // periodically during execution. This is what stops `while(true){}` —
      // there is no other way to interrupt a running guest.
      const deadline = Date.now() + EVAL_TIMEOUT_MS;
      runtime.setInterruptHandler(() => Date.now() > deadline);

      // The row is injected as a JSON literal rather than through a host
      // binding: nothing crosses the boundary as a live object, so the guest
      // cannot reach back through it.
      //
      // `row` is bound for programmatic access (row.someKey); the common case
      // is that {{Column}} tokens have already been substituted into the
      // expression as literals by the caller, which is what makes
      // `{{Email}}.split("@")` read naturally. No `with` block — it is illegal
      // under "use strict", and substitution makes it unnecessary.
      const program = `
        (function (row) {
          "use strict";
          const LOOKUP = globalThis.__gridLookup;
          return (
${expression}
);
        })(${JSON.stringify(row)})
      `;

      const result = ctx.evalCode(program);

      if (result.error) {
        const dumped = ctx.dump(result.error) as { message?: string; name?: string };
        result.error.dispose();
        runtime.setInterruptHandler(() => false);
        const message = dumped?.message ?? String(dumped);
        if (dumped?.name === "SyntaxError") throw new Error(describeSyntaxError(expression, message));
        throw new Error(
          message === "interrupted"
            ? `Formula timed out after ${EVAL_TIMEOUT_MS}ms`
            : `${dumped?.name ?? "Error"}: ${message}`,
        );
      }

      const value = ctx.dump(result.value);
      result.value.dispose();
      runtime.setInterruptHandler(() => false);
      return value;
    },

    dispose() {
      ctx.dispose();
      runtime.dispose();
    },
  };
}
