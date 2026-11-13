import type { ColumnType, HttpConfig } from "../types";
import { ownCell, tokensIn } from "./types";

/** A cell that holds something: not null, not blank text, not an empty list. */
export function hasCellValue(value: unknown): boolean {
  return value !== undefined
    && value !== null
    && (!Array.isArray(value) || value.length > 0)
    && (typeof value !== "string" || value.trim() !== "");
}

type ColumnLike = { type: ColumnType; config: unknown };

/** Every {{token}} an AI, HTTP or formula column reads from its row. */
export function referencedTokens(column: ColumnLike): string[] {
  const config = (column.config ?? {}) as Record<string, unknown>;
  switch (column.type) {
    case "ai":
      return [...new Set(tokensIn(config.prompt as string | undefined))];
    case "formula":
      return [...new Set(tokensIn(config.expression as string | undefined))];
    case "http": {
      const http = config as Partial<HttpConfig>;
      return [
        ...new Set([
          ...tokensIn(http.url),
          ...tokensIn(http.body),
          ...Object.values(http.headers ?? {}).flatMap((value) => tokensIn(value)),
        ]),
      ];
    }
    default:
      return [];
  }
}

/**
 * True when an AI or HTTP column references row values and every one of them
 * is empty — a call that would cost money for nothing (a model invents an
 * answer about a blank row and it is stored as a success).
 *
 * "Every", not "any": a prompt may mention optional columns, and a run with
 * some inputs is useful. A column that references no tokens is never skipped,
 * and neither is a formula: it is free, and one written for blanks
 * (`IF(ISBLANK({{x}}), "none", …)`) must still run — and a re-run must still
 * replace the value it computed before the input was cleared.
 */
export function allReferencedInputsEmpty(column: ColumnLike, cells: Record<string, unknown>): boolean {
  if (column.type === "formula") return false;
  const tokens = referencedTokens(column);
  return tokens.length > 0 && tokens.every((token) => !hasCellValue(ownCell(cells, token)));
}

/** Seconds to hold a column's jobs before they become claimable. */
export function columnDelaySeconds(column: ColumnLike): number {
  if (column.type !== "ai" && column.type !== "enrichment") return 0;
  const seconds = Number((column.config as { delaySeconds?: unknown } | null)?.delaySeconds);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
}

/** The "Only run if" expression, if the column has one. */
export function columnRunCondition(column: ColumnLike): string | undefined {
  if (column.type !== "ai" && column.type !== "enrichment") return undefined;
  const condition = (column.config as { runCondition?: unknown } | null)?.runCondition;
  return typeof condition === "string" && condition.trim() ? condition.trim() : undefined;
}
