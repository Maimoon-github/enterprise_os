import type { components } from './schema'

/**
 * Request and response shapes straight from the backend's OpenAPI schema
 * (regenerate with scripts/api-types.sh; CI fails when it is stale). Use these
 * instead of hand-written interfaces, so a renamed field is a type error here.
 */
export type Schemas = components['schemas']
