import { getIntegration, getIntegrationAction, validateInputValue } from "@/lib/integrations/catalog";
import { getIntegrationActionHandler } from "@/lib/integrations/server/registry";
import type { IntegrationActionHandler } from "@/lib/integrations/server/types";
import type { IntegrationActionDefinition } from "@/lib/integrations/types";
import { getIntegrationConnection, getIntegrationCredentials } from "../providers";
import type { CellResult, EnrichmentConfig, PendingCellResult } from "../types";
import { PermanentRunError, ownCell, type ColumnRunner, type RunSession } from "./types";

type EnrichmentSession = RunSession & {
  credentials: Record<string, string>;
  action: IntegrationActionDefinition;
  handler: IntegrationActionHandler;
};

export const enrichmentRunner: ColumnRunner<EnrichmentConfig> = {
  type: "enrichment",

  resolveDeps(config) {
    return [...new Set(Object.values(config.inputs).map((binding) => binding.columnKey))];
  },

  async prepare(config): Promise<EnrichmentSession> {
    const integration = getIntegration(config.integrationKey);
    const action = getIntegrationAction(config.integrationKey, config.actionKey);
    const handler = action ? getIntegrationActionHandler(action.handlerKey) : null;
    if (!integration || !action || !action.implemented || !handler || action.handlerKey !== config.handlerKey) {
      throw new PermanentRunError("This integration action is not available");
    }
    const connection = await getIntegrationConnection(config.connectionId);
    if (!connection || !connection.enabled || !connection.verified || connection.integrationKey !== config.integrationKey) {
      throw new PermanentRunError("Select a verified integration account");
    }
    const credentials = await getIntegrationCredentials(config.connectionId);
    if (!credentials) throw new PermanentRunError("Reconnect the integration account before running");
    const missingCredential = integration.auth.fields.find(
      (field) => field.required && !credentials[field.key],
    );
    if (missingCredential) {
      throw new PermanentRunError(`Reconnect the integration account: ${missingCredential.label} is missing`);
    }
    return { credentials, action, handler };
  },

  async run(config, row, ctx, session): Promise<CellResult | PendingCellResult> {
    const prepared = session as EnrichmentSession | undefined;
    if (!prepared?.credentials || !prepared.action || !prepared.handler) {
      throw new PermanentRunError("Integration credentials were not prepared");
    }
    const inputValues: Record<string, unknown> = {};
    for (const input of prepared.action.inputs) {
      const binding = config.inputs[input.key];
      const value = binding ? ownCell(row, binding.columnKey) : undefined;
      if (value === undefined || value === null || value === "") {
        if (input.required) throw new PermanentRunError(`${input.name}: A value is required`);
        continue;
      }
      const validationError = validateInputValue(input.valueType, value, input.multiple);
      if (validationError) throw new PermanentRunError(`${input.name}: ${validationError}`);
      inputValues[input.key] = value;
    }
    if (prepared.action.filterBuilder) {
      const populatedFilters = prepared.action.inputs.filter(
        (input) => input.group === "filter" && inputValues[input.key] !== undefined,
      ).length;
      if (populatedFilters < prepared.action.filterBuilder.minFilters) {
        throw new PermanentRunError(
          `At least ${prepared.action.filterBuilder.minFilters} search filter${prepared.action.filterBuilder.minFilters === 1 ? " is" : "s are"} required`,
        );
      }
    }
    return prepared.handler({
      config,
      action: prepared.action,
      inputs: inputValues,
      credentials: prepared.credentials,
      connectionId: config.connectionId,
      providerState: ctx.providerState,
      timeoutMs: ctx.timeoutMs,
      signal: ctx.signal,
    });
  },

  estimateCost() {
    // Provider credits are not currency. Keep monetary cost at zero until an
    // account-specific credit-to-cost conversion is available.
    return 0;
  },
};
