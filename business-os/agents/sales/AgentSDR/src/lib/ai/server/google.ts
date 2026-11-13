import "server-only";

import { PermanentRunError } from "@/lib/grid/runners/types";
import { jsonInstruction, parseJsonResponse, type AiRunner } from "./types";

const BASE = "https://generativelanguage.googleapis.com/v1beta/models";

type GeminiPart = { text?: string; inlineData?: { mimeType: string; data: string } };
type GeminiResponse = {
  candidates?: Array<{ content?: { parts?: GeminiPart[] }; finishReason?: string }>;
  usageMetadata?: { promptTokenCount?: number; candidatesTokenCount?: number };
  error?: { message?: string; status?: string };
};

/**
 * Gemini over REST — there is no first-party Node SDK dependency in this repo,
 * and every other provider integration here is a plain fetch, so adding one
 * for a single call would be the odd one out.
 *
 * Web research uses Google Search grounding, which like Anthropic's and
 * OpenAI's search tools runs on the provider's side.
 */
async function callGemini(
  modelId: string,
  apiKey: string,
  body: Record<string, unknown>,
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<GeminiResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  signal?.addEventListener("abort", () => controller.abort(), { once: true });

  try {
    const response = await fetch(`${BASE}/${modelId}:generateContent`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": apiKey },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const data = (await response.json().catch(() => ({}))) as GeminiResponse;

    if (!response.ok) {
      const message = data.error?.message ?? `Gemini returned ${response.status}`;
      // 401/403 is a bad key and 400/404 is a bad model or request — neither
      // improves on retry, so they must not be re-queued per row.
      if ([400, 401, 403, 404].includes(response.status)) {
        throw new PermanentRunError(message);
      }
      throw new Error(message);
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

export const runGoogle: AiRunner = async ({
  model,
  credentials,
  prompt,
  schema,
  examples,
  timeoutMs,
  signal,
}) => {
  const system = [
    "You are filling in one row of a spreadsheet.",
    "Answer only from what you are given or can verify. If a value cannot be",
    "determined, return an empty string for it rather than guessing.",
    schema ? jsonInstruction(schema) : "Respond with the answer only — no preamble.",
  ].join("\n");

  const contents = [
    ...examples.flatMap((example) => [
      { role: "user", parts: [{ text: example.input }] },
      { role: "model", parts: [{ text: example.response }] },
    ]),
    { role: "user", parts: [{ text: prompt }] },
  ];

  const data = await callGemini(
    model.modelId,
    credentials.apiKey,
    {
      contents,
      systemInstruction: { parts: [{ text: system }] },
      generationConfig: { maxOutputTokens: model.maxOutputTokens ?? 16000 },
      ...(model.supportsWebSearch ? { tools: [{ google_search: {} }] } : {}),
    },
    timeoutMs,
    signal,
  );

  const text = (data.candidates?.[0]?.content?.parts ?? [])
    .map((part) => part.text ?? "")
    .join("")
    .trim();

  return {
    value: schema ? parseJsonResponse(text) : text,
    usage: {
      inputTokens: data.usageMetadata?.promptTokenCount,
      outputTokens: data.usageMetadata?.candidatesTokenCount,
    },
  };
};

/** Nano Banana. Gemini returns image bytes inline rather than as a URL. */
export const runGoogleImage: AiRunner = async ({ model, credentials, prompt, timeoutMs, signal }) => {
  const data = await callGemini(
    model.modelId,
    credentials.apiKey,
    { contents: [{ role: "user", parts: [{ text: prompt }] }] },
    timeoutMs,
    signal,
  );

  const image = (data.candidates?.[0]?.content?.parts ?? []).find((part) => part.inlineData);
  if (!image?.inlineData) throw new PermanentRunError("The model returned no image");
  return { value: `data:${image.inlineData.mimeType};base64,${image.inlineData.data}` };
};
