import "server-only";

import Anthropic from "@anthropic-ai/sdk";
import { PermanentRunError } from "@/lib/grid/runners/types";
import { jsonInstruction, parseJsonResponse, type AiRunner } from "./types";

/**
 * Claude, through the official SDK.
 *
 * Notes that are easy to get wrong on the current model family:
 *  - Thinking is adaptive; `budget_tokens` is rejected outright.
 *  - Assistant prefill is rejected, so examples go in as user/assistant turns.
 *  - Web research uses Anthropic's server-side search tool, so there is no
 *    scraping loop to run here — the tool executes on Anthropic's side and
 *    the citations come back in the same response.
 */
export const runAnthropic: AiRunner = async ({
  model,
  credentials,
  prompt,
  schema,
  examples,
  timeoutMs,
  signal,
}) => {
  const client = new Anthropic({ apiKey: credentials.apiKey, timeout: timeoutMs });

  const system = [
    "You are filling in one row of a spreadsheet.",
    "Answer only from what you are given or can verify. If a value cannot be",
    "determined, return an empty string for it rather than guessing.",
    schema ? jsonInstruction(schema) : "Respond with the answer only — no preamble.",
  ].join("\n");

  const messages: Anthropic.MessageParam[] = [];
  for (const example of examples) {
    messages.push({ role: "user", content: example.input });
    messages.push({ role: "assistant", content: example.response });
  }
  messages.push({ role: "user", content: prompt });

  try {
    const response = await client.messages.create(
      {
        model: model.modelId,
        max_tokens: model.maxOutputTokens ?? 16000,
        system,
        messages,
        thinking: { type: "adaptive" },
        ...(model.supportsWebSearch
          ? { tools: [{ type: "web_search_20260209", name: "web_search", max_uses: 5 }] }
          : {}),
      },
      { signal },
    );

    // A safety decline arrives as HTTP 200 with stop_reason "refusal", so it
    // has to be checked before reading content or the cell silently blanks.
    if (response.stop_reason === "refusal") {
      throw new PermanentRunError(
        `Claude declined this prompt${response.stop_details?.category ? ` (${response.stop_details.category})` : ""}`,
      );
    }

    const text = response.content
      .filter((block): block is Anthropic.TextBlock => block.type === "text")
      .map((block) => block.text)
      .join("")
      .trim();

    return {
      value: schema ? parseJsonResponse(text) : text,
      usage: {
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
      },
    };
  } catch (cause) {
    if (cause instanceof PermanentRunError) throw cause;
    // A bad key or a model the account cannot reach will never succeed on a
    // retry, so it must not be re-queued for every remaining row.
    if (cause instanceof Anthropic.AuthenticationError) {
      throw new PermanentRunError("Anthropic rejected this API key");
    }
    if (cause instanceof Anthropic.BadRequestError || cause instanceof Anthropic.NotFoundError) {
      throw new PermanentRunError(cause.message);
    }
    throw cause;
  }
};
