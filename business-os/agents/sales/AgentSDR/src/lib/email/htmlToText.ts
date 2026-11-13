const INVISIBLE_CHARS_RE = new RegExp("[\\u200B-\\u200F\\uFEFF\\u00AD\\u0300-\\u036F]", "gu");

export function htmlToPlainText(html: string): string {
  let text = html.replace(/<!DOCTYPE[^>]*>/gi, "").replace(/<head[\s\S]*?<\/head>/gi, "").replace(/<style[\s\S]*?<\/style>/gi, "").replace(/<script[\s\S]*?<\/script>/gi, "").replace(/<br\s*\/?\s*>/gi, "\n").replace(/<\/(div|p|tr|li|h[1-6])>/gi, "\n").replace(/<\/?[^>]+>/g, "");
  text = text.replace(/&nbsp;/gi, " ").replace(/&amp;/gi, "&").replace(/&lt;/gi, "<").replace(/&gt;/gi, ">").replace(/&quot;/gi, '"').replace(/&#39;/gi, "'").replace(INVISIBLE_CHARS_RE, "");
  return text.split("\n").map((line) => line.trim()).join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

export function looksLikeHtml(value: string): boolean {
  return /<\/?[a-z][\s\S]*>/i.test(value);
}
