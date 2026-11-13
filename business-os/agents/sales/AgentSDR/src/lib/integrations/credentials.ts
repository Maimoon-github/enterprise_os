import "server-only";

import { decryptCredentialText, encryptCredentialText } from "./credential-crypto";

/** Encrypts a provider credential for storage in grid_providers.config. */
export function encryptIntegrationCredential(value: string): string {
  return encryptCredentialText(value);
}

/** Decrypts only inside the server runner immediately before a provider call. */
export function decryptIntegrationCredential(payload: string): string {
  return decryptCredentialText(payload);
}

export function encryptIntegrationCredentials(credentials: Record<string, string>): string {
  return encryptCredentialText(JSON.stringify(credentials));
}

export function decryptIntegrationCredentials(payload: string): Record<string, string> {
  const parsed: unknown = JSON.parse(decryptCredentialText(payload));
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Stored integration credentials are invalid");
  }
  const entries = Object.entries(parsed);
  if (entries.some(([, value]) => typeof value !== "string")) {
    throw new Error("Stored integration credentials are invalid");
  }
  return Object.fromEntries(entries) as Record<string, string>;
}
