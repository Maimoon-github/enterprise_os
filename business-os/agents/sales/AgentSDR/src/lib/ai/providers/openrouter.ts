import type { AiProviderDefinition } from "../types";

export const OPENROUTER_PROVIDER: AiProviderDefinition = {
  key: "openrouter",
  name: "OpenRouter",
  description: "One gateway for OpenAI, Anthropic, Google, and other supported models.",
  websiteUrl: "https://openrouter.ai",
  iconText: "OR",
  iconBackground: "#4F46E5",
  auth: {
    fields: [
      { key: "apiKey", label: "OpenRouter inference API key", placeholder: "sk-or-v1-...", inputType: "password", required: true },
      { key: "managementKey", label: "OpenRouter management key", placeholder: "sk-or-v1-...", inputType: "password", required: true },
    ],
    helpUrl: "https://openrouter.ai/settings/management-keys",
  },
  models: [],
};
