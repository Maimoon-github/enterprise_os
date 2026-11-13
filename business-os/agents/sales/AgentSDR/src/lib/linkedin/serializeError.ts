type ErrorWithBody = Error & {
  body?: unknown;
  response?: { status?: number; data?: unknown };
};

const stringifyUnknown = (value: unknown): string => {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

/** Pull a human-readable message from Unipile / REST error bodies. */
export const extractApiErrorDetail = (body: unknown): string => {
  if (body == null) return "";
  if (typeof body === "string") return body.trim();
  if (typeof body !== "object") return String(body);

  const o = body as Record<string, unknown>;
  for (const key of ["message", "error", "detail", "title", "reason"] as const) {
    const value = o[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }

  if (o.error && typeof o.error === "object") {
    const nested = extractApiErrorDetail(o.error);
    if (nested) return nested;
  }

  return stringifyUnknown(body);
};

const httpStatusFromBody = (body: unknown): number | undefined => {
  if (!body || typeof body !== "object") return undefined;
  const o = body as Record<string, unknown>;
  if (typeof o.status === "number") return o.status;
  if (typeof o.statusCode === "number") return o.statusCode;
  return undefined;
};

export function serializeError(err: unknown): string {
  if (!(err instanceof Error)) return String(err);

  const withBody = err as ErrorWithBody;

  // Unipile SDK (UnsuccessfulRequestError): payload on .body, message often ""
  if (withBody.body !== undefined) {
    const detail = extractApiErrorDetail(withBody.body);
    const status = withBody.response?.status ?? httpStatusFromBody(withBody.body);
    const message = err.message.trim();
    const parts: string[] = [];
    if (status != null) parts.push(`HTTP ${status}`);
    if (message) parts.push(message);
    if (detail && detail !== message) parts.push(detail);
    if (parts.length > 0) return parts.join(" — ");
    return stringifyUnknown(withBody.body) || "Unknown API error";
  }

  // Axios-style errors
  const res = withBody.response;
  if (res) {
    const status = res.status ?? "";
    const data =
      res.data != null
        ? extractApiErrorDetail(res.data) || stringifyUnknown(res.data)
        : "";
    const message = err.message.trim();
    const parts = [`HTTP ${status}`, message, data].filter((p) => p.length > 0);
    if (parts.length > 0) return parts.join(" — ");
  }

  return err.message.trim() || err.stack || "Unknown error";
}
