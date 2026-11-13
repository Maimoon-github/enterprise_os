import type { AiProviderDefinition } from "../types";

export const GOOGLE_PROVIDER: AiProviderDefinition = {
  key: "google",
  name: "Google Gemini",
  description: "Gemini models, with Google Search grounding and Nano Banana image generation.",
  websiteUrl: "https://ai.google.dev",
  iconText: "G",
  iconBackground: "#4285F4",
  auth: {
    fields: [
      {
        key: "apiKey",
        label: "API key",
        placeholder: "AIza...",
        inputType: "password",
        required: true,
      },
    ],
    helpUrl: "https://aistudio.google.com/apikey",
  },
  models: [
    {
      key: "gemini-3-1-pro",
      name: "Gemini 3.1 Pro",
      description: "Google's most advanced model, with agentic capabilities.",
      modelId: "gemini-3.1-pro-preview",
      useCases: ["web-research", "content"],
      creditsPerRun: 5,
      supportsWebSearch: true,
      maxOutputTokens: 16000,
    },
    {
      key: "gemini-3-7-flash",
      name: "Gemini 3.7 Flash",
      description: "Latest Flash model for complex coding and agentic workflows.",
      modelId: "gemini-3.7-flash",
      useCases: ["web-research", "content"],
      creditsPerRun: 2,
      supportsWebSearch: true,
      maxOutputTokens: 16000,
    },
    {
      key: "gemini-2-5-flash-lite",
      name: "Gemini 2.5 Flash Lite",
      description: "Fastest and most budget-friendly. Good for bulk extraction.",
      modelId: "gemini-2.5-flash-lite",
      useCases: ["content"],
      creditsPerRun: 1,
      maxOutputTokens: 8000,
    },
    {
      key: "gemini-3-pro-image",
      name: "Nano Banana Pro",
      description: "Gemini's highest-quality image generation.",
      modelId: "gemini-3-pro-image",
      useCases: ["image-generation"],
      creditsPerRun: 8,
      producesImages: true,
    },
  ],
};
