import type { AiUseCase } from "@/lib/grid/types";
import { OPENROUTER_PROVIDER } from "./providers/openrouter";
import type { AiModelDefinition, AiProviderDefinition } from "./types";

export * from "./types";

/**
 * Client-safe registry of AI providers. Imported by the configuration UI, so
 * it must never pull in a server module — the provider call implementations
 * live under ./server and are reached through its registry.
 */
export const AI_PROVIDERS: AiProviderDefinition[] = [
  OPENROUTER_PROVIDER,
];

export function getAiProvider(key: string): AiProviderDefinition | null {
  return AI_PROVIDERS.find((provider) => provider.key === key) ?? null;
}

export function getAiModel(
  providerKey: string,
  modelKey: string,
  useCase?: AiUseCase,
): AiModelDefinition | null {
  // OpenRouter model IDs are provider/model strings from its live catalog.
  // They are intentionally persisted directly so new models need no deploy.
  if (providerKey === "openrouter" && modelKey.includes("/")) {
    const image = useCase === "image-generation";
    return {
      key: modelKey,
      name: modelKey,
      description: "OpenRouter model",
      modelId: modelKey,
      useCases: image ? ["image-generation"] : ["content", "web-research"],
      creditsPerRun: 0,
      producesImages: image,
    };
  }
  return getAiProvider(providerKey)?.models.find((model) => model.key === modelKey) ?? null;
}

export type AiModelChoice = { provider: AiProviderDefinition; model: AiModelDefinition };

/** Every model that can serve a use case, cheapest first — the picker's list. */
export function modelsForUseCase(useCase: AiUseCase): AiModelChoice[] {
  return AI_PROVIDERS.flatMap((provider) =>
    provider.models
      .filter((model) => model.useCases.includes(useCase))
      .map((model) => ({ provider, model })),
  ).sort((a, b) => a.model.creditsPerRun - b.model.creditsPerRun);
}

/**
 * Column keys a prompt reads.
 *
 * Shared by the DAG builder and the UI's column chips so both agree on what
 * counts as a reference. Mirrors the {{token}} syntax the HTTP and formula
 * columns already use rather than inventing a third.
 */
const TOKEN_RE = /\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g;

export function promptColumnKeys(prompt: string | undefined | null): string[] {
  if (!prompt) return [];
  return [...new Set([...prompt.matchAll(TOKEN_RE)].map((match) => match[1]))];
}
