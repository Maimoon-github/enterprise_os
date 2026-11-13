const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type RunRequest = { columnKey?: string; rowIds?: string[]; onlyEmpty?: boolean };

/**
 * Parses the run endpoint's body. An empty body means "run everything"; a body
 * that is present but malformed is an error, because falling back to `{}`
 * would turn a typo into a whole-table run that spends provider credits.
 * `rowIds`, when present — even empty — is an explicit selection.
 */
export function parseRunRequest(text: string): { ok: true; value: RunRequest } | { ok: false; error: string } {
  if (!text.trim()) return { ok: true, value: {} };

  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return { ok: false, error: "invalid JSON body" };
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, error: "body must be an object" };
  }

  const { columnKey, rowIds, onlyEmpty } = body as Record<string, unknown>;
  if (columnKey !== undefined && columnKey !== null && (typeof columnKey !== "string" || !columnKey)) {
    return { ok: false, error: "columnKey must be a string" };
  }
  if (onlyEmpty !== undefined && typeof onlyEmpty !== "boolean") {
    return { ok: false, error: "onlyEmpty must be a boolean" };
  }
  if (rowIds !== undefined && rowIds !== null) {
    if (!Array.isArray(rowIds) || rowIds.some((id) => typeof id !== "string" || !UUID.test(id))) {
      return { ok: false, error: "rowIds must be an array of row ids" };
    }
  }

  return {
    ok: true,
    value: {
      columnKey: (columnKey as string | null | undefined) ?? undefined,
      rowIds: (rowIds as string[] | null | undefined) ?? undefined,
      onlyEmpty: onlyEmpty as boolean | undefined,
    },
  };
}
