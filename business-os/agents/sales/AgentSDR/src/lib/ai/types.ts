import type { AiUseCase } from "@/lib/grid/types";

/**
 * The "Use AI" catalog — a sibling of src/lib/integrations, not a member of
 * it.
 *
 * An integration action declares fixed inputs and outputs and maps them to
 * columns; an AI model takes a free-text prompt and returns whatever fields
 * the user asked for. Forcing models into IntegrationActionDefinition would
 * mean a synthetic action per model with inputs that do not exist. They share
 * credential storage (grid_providers) and the ColumnRunner interface, and
 * nothing else.
 */
export type AiModelDefinition = {
  /**
   * Stable catalog key, persisted in AiConfig.modelKey. NEVER rename one —
   * saved columns reference it. Providers rev their wire ids far more often
   * than this catalog changes, which is exactly why the two are separate.
   */
  key: string;
  name: string;
  description: string;
  /** The id sent to the provider. Safe to update when a provider revs it. */
  modelId: string;
  /** Use cases this model can serve. Drives the model dropdown's filtering. */
  useCases: AiUseCase[];
  /**
   * Relative cost shown as the "N / row" badge, in the same spirit as Clay's
   * credits. A display unit for comparing models, NOT billing — actual spend
   * is whatever the provider charges on the user's own API key.
   */
  creditsPerRun: number;
  /** Reaches the live web, via the provider's own server-side search tool. */
  supportsWebSearch?: boolean;
  /** Returns an image rather than text. */
  producesImages?: boolean;
  maxOutputTokens?: number;
};

export type AiProviderDefinition = {
  /** Persisted in AiConfig.providerKey and on the connection. Never rename. */
  key: string;
  name: string;
  description: string;
  websiteUrl: string;
  /** Local asset under public/, preferred over the favicon fallback. */
  iconUrl?: string;
  iconText: string;
  iconBackground: string;
  auth: {
    fields: Array<{
      key: string;
      label: string;
      placeholder?: string;
      inputType: "text" | "password";
      required: boolean;
    }>;
    helpUrl?: string;
  };
  models: AiModelDefinition[];
};

export const AI_USE_CASES: Array<{
  key: AiUseCase;
  name: string;
  description: string;
}> = [
  {
    key: "web-research",
    name: "Web research",
    description: "Has access to the internet so you can research and analyse websites",
  },
  {
    key: "image-generation",
    name: "Image generation",
    description: "Generate images from text",
  },
  {
    key: "content",
    name: "Create or modify content",
    description: "Useful for most tasks (does not have access to the internet)",
  },
];
