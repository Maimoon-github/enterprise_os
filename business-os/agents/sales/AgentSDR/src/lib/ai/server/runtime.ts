import "server-only";

import { getByokSettings } from "../byok";
import { getAiConnection, getAiCredentials } from "../connections";
import { strictProviderRouting, type OpenRouterModelSelection } from "../openrouter-types";
import { createOpenRouterClient } from "./openrouter";

export type StrictOpenRouterRouting = {
  only: string[];
  order: string[];
  allow_fallbacks: false;
  require_parameters: true;
};

export async function getOpenRouterRuntime(
  requested?: OpenRouterModelSelection,
  timeout = 30_000,
) {
  const settings = await getByokSettings();
  if (!settings.byokOnlyConfirmed) {
    throw new Error("OpenRouter BYOK-only routing is not confirmed in AI Settings");
  }
  if (!settings.connectionId) throw new Error("Connect OpenRouter in AI Settings");

  const connection = await getAiConnection(settings.connectionId);
  if (!connection?.verified || connection.providerKey !== "openrouter") {
    throw new Error("The OpenRouter connection in AI Settings is unavailable");
  }
  const credentials = await getAiCredentials(connection.id);
  if (!credentials?.apiKey) throw new Error("Reconnect OpenRouter in AI Settings");

  const selection = requested ?? settings.defaultModel;
  if (!selection) throw new Error("Choose a default OpenRouter model in AI Settings");
  if (!settings.providers.includes(selection.provider)) {
    throw new Error(`OpenRouter provider ${selection.provider} is not enabled in AI Settings`);
  }
  if (!settings.modelsByProvider[selection.provider]?.includes(selection.modelId)) {
    throw new Error(`Model ${selection.modelId} is not enabled for ${selection.provider} in AI Settings`);
  }

  const provider: StrictOpenRouterRouting = strictProviderRouting(selection.provider);
  return {
    client: createOpenRouterClient(credentials.apiKey, timeout),
    apiKey: credentials.apiKey,
    connection,
    selection,
    provider,
  };
}
