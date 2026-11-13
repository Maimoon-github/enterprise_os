import type { OpenRouterModelSummary, OpenRouterProviderModels } from "@/lib/ai/openrouter-types";

/**
 * What Settings → AI provider lists on the public demo, in place of the live
 * OpenRouter catalog (its stored keys are placeholders, and the demo calls
 * nothing). A fixed snapshot of a few well-known providers and models.
 */

const model = (id: string, name: string, context: number, prompt: string, completion: string, extra: Partial<OpenRouterModelSummary> = {}): OpenRouterModelSummary => ({
  id,
  name,
  context_length: context,
  pricing: { prompt, completion },
  supportedParameters: ["temperature", "max_tokens", "response_format", "tools"],
  outputModalities: ["text"],
  ...extra,
});

const provider = (slug: string, name: string, models: OpenRouterModelSummary[]): OpenRouterProviderModels => ({
  slug,
  name,
  credentialCount: 1,
  prioritizedCredentialCount: 1,
  fallbackCredentialCount: 0,
  discoveredModelCount: models.length,
  modelFilterRestricted: false,
  allowedModelCount: models.length,
  unmatchedAllowedModels: [],
  models,
});

export const DEMO_OPENROUTER_CATALOG: OpenRouterProviderModels[] = [
  provider("anthropic", "Anthropic", [
    model("anthropic/claude-sonnet-4.5", "Anthropic: Claude Sonnet 4.5", 1_000_000, "0.000003", "0.000015"),
    model("anthropic/claude-haiku-4.5", "Anthropic: Claude Haiku 4.5", 200_000, "0.000001", "0.000005"),
    model("anthropic/claude-opus-4.1", "Anthropic: Claude Opus 4.1", 200_000, "0.000015", "0.000075"),
  ]),
  provider("google", "Google AI Studio", [
    model("google/gemini-2.5-flash", "Google: Gemini 2.5 Flash", 1_048_576, "0.0000003", "0.0000025"),
    model("google/gemini-2.5-pro", "Google: Gemini 2.5 Pro", 1_048_576, "0.00000125", "0.00001"),
  ]),
  provider("openai", "OpenAI", [
    model("openai/gpt-5", "OpenAI: GPT-5", 400_000, "0.00000125", "0.00001"),
    model("openai/gpt-5-mini", "OpenAI: GPT-5 Mini", 400_000, "0.00000025", "0.000002"),
  ]),
];
