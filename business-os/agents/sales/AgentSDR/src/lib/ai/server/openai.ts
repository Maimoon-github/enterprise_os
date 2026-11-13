import "server-only";

import OpenAI from "openai";
import { PermanentRunError } from "@/lib/grid/runners/types";
import { jsonInstruction, parseJsonResponse, type AiRunner } from "./types";

function client(credentials: Record<string, string>, timeoutMs: number) {
  return new OpenAI({
    apiKey: credentials.apiKey,
    organization: credentials.organization?.trim() || undefined,
    timeout: timeoutMs,
  });
}

/**
 * GPT text models.
 *
 * Uses the Responses API rather than chat completions because that is where
 * the hosted web_search tool lives — the "Web research" use case needs the
 * model to reach the live web, and doing that client-side would mean building
 * a scrape-and-summarise loop this column has no business owning.
 */
export const runOpenAi: AiRunner = async ({
  model,
  credentials,
  prompt,
  schema,
  examples,
  timeoutMs,
  signal,
}) => {
  const openai = client(credentials, timeoutMs);

  const instructions = [
    "You are filling in one row of a spreadsheet.",
    "Answer only from what you are given or can verify. If a value cannot be",
    "determined, return an empty string for it rather than guessing.",
    schema ? jsonInstruction(schema) : "Respond with the answer only — no preamble.",
    ...examples.map((example) => `Example input:\n${example.input}\nExpected response:\n${example.response}`),
  ].join("\n\n");

  try {
    const response = await openai.responses.create(
      {
        model: model.modelId,
        instructions,
        input: prompt,
        max_output_tokens: model.maxOutputTokens ?? 16000,
        ...(model.supportsWebSearch ? { tools: [{ type: "web_search" as const }] } : {}),
      },
      { signal },
    );

    const text = (response.output_text ?? "").trim();
    return {
      value: schema ? parseJsonResponse(text) : text,
      usage: {
        inputTokens: response.usage?.input_tokens,
        outputTokens: response.usage?.output_tokens,
      },
    };
  } catch (cause) {
    throw asPermanent(cause);
  }
};

/** GPT Image. Returns a data URL, which the image column renders directly. */
export const runOpenAiImage: AiRunner = async ({ model, credentials, prompt, timeoutMs }) => {
  const openai = client(credentials, timeoutMs);
  try {
    const response = await openai.images.generate({
      model: model.modelId,
      prompt,
      n: 1,
    });
    const image = response.data?.[0];
    if (image?.url) return { value: image.url };
    if (image?.b64_json) return { value: `data:image/png;base64,${image.b64_json}` };
    throw new PermanentRunError("The model returned no image");
  } catch (cause) {
    throw asPermanent(cause);
  }
};

/** A rejected key or unknown model will fail identically on every row. */
function asPermanent(cause: unknown): unknown {
  if (cause instanceof PermanentRunError) return cause;
  if (cause instanceof OpenAI.AuthenticationError) {
    return new PermanentRunError("OpenAI rejected this API key");
  }
  if (cause instanceof OpenAI.NotFoundError || cause instanceof OpenAI.BadRequestError) {
    return new PermanentRunError(cause.message);
  }
  return cause;
}
