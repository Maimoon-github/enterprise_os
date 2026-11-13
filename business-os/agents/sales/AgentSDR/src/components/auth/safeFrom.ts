/** Only same-site paths: starts with "/" and is not protocol-relative ("//", "/\"). */
export function safeFrom(from: string | null | undefined): string | null {
  if (!from || !from.startsWith("/") || from.startsWith("//") || from.startsWith("/\\")) return null;
  return from;
}
