# Use AI

This subsystem is a sibling of `src/lib/integrations`. An integration action
has fixed inputs and outputs; an AI model accepts a free-text prompt and
returns the fields requested by the user.

All inference goes through OpenRouter. The saved connection contains two
encrypted secrets: an inference API key and a management key. The management
key reads `/api/v1/byok`; it cannot run completions. Provider/model choices are
discovered from the live BYOK account and persisted in the global AI settings.

`server/runtime.ts` is the mandatory entry point for model calls outside the
grid runner. Text calls send `provider.only`, `provider.order`,
`allow_fallbacks: false`, and `require_parameters: true`. Image calls use the
dedicated `/api/v1/images` endpoint with the same one-provider pin and disabled
fallbacks; that endpoint does not support `require_parameters`.

Fallback-section BYOK credentials are discovered for visibility but are not
selectable. A connection must contain at least one active prioritized BYOK
credential, and selected models are revalidated against the live catalog.

The column config (`AiConfig`) lives in `src/lib/grid/types.ts`. OpenRouter
model IDs are persisted directly in `AiConfig.modelKey`, together with the
selected upstream provider in `AiConfig.upstreamProvider`.

## BYOK-only requirement

OpenRouter does not expose its “Shared capacity fallback” switch through the
public management API. An operator must set **Never use shared capacity on this
provider** for every enabled provider in the OpenRouter BYOK dashboard, then
confirm that setting in AgentSDR. Runtime calls are blocked until confirmed.

After changing this subsystem, run `npx tsc --noEmit` and a production build.
