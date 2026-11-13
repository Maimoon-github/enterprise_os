import type { AiProviderDefinition } from "../types";

export const OPENAI_PROVIDER: AiProviderDefinition = {
  key: "openai",
  name: "OpenAI",
  description: "GPT models, plus GPT Image for image generation.",
  websiteUrl: "https://openai.com",
  iconText: "O",
  iconBackground: "#10A37F",
  auth: {
    fields: [
      {
        key: "apiKey",
        label: "API key",
        placeholder: "sk-...",
        inputType: "password",
        required: true,
      },
      {
        key: "organization",
        label: "Organization ID",
        placeholder: "org-... (optional)",
        inputType: "text",
        required: false,
      },
    ],
    helpUrl: "https://platform.openai.com/api-keys",
  },
  models: [
    {
      key: "gpt-5-6-sol",
      name: "GPT-5.6 Sol",
      description: "OpenAI's frontier model for complex professional work.",
      modelId: "gpt-5.6-sol",
      useCases: ["web-research", "content"],
      creditsPerRun: 5,
      supportsWebSearch: true,
      maxOutputTokens: 16000,
    },
    {
      key: "gpt-5-6-terra",
      name: "GPT-5.6 Terra",
      description: "Balances intelligence and cost. A good default.",
      modelId: "gpt-5.6-terra",
      useCases: ["web-research", "content"],
      creditsPerRun: 2,
      supportsWebSearch: true,
      maxOutputTokens: 16000,
    },
    {
      key: "gpt-5-6-luna",
      name: "GPT-5.6 Luna",
      description: "For cost-sensitive, high-volume workloads.",
      modelId: "gpt-5.6-luna",
      useCases: ["content"],
      creditsPerRun: 1,
      maxOutputTokens: 8000,
    },
    {
      key: "gpt-image-2",
      name: "GPT Image 2",
      description: "State-of-the-art image generation.",
      modelId: "gpt-image-2",
      useCases: ["image-generation"],
      creditsPerRun: 8,
      producesImages: true,
    },
  ],
};
