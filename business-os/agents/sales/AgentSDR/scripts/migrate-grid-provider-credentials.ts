/**
 * Adds dedicated integration credential storage and migrates legacy secrets
 * out of grid_providers.config. Safe to re-run.
 *
 * Run with: bun run scripts/migrate-grid-provider-credentials.ts
 */
import { Client } from "pg";
import { decryptCredentialText, encryptCredentialText } from "../src/lib/integrations/credential-crypto";

type LegacyProvider = {
  id: string;
  config: Record<string, unknown>;
};

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({ connectionString: process.env.DATABASE_URL, ssl: { rejectUnauthorized: false } });
  await client.connect();
  try {
    await client.query("BEGIN");
    await client.query(`
      CREATE TABLE IF NOT EXISTS grid_provider_credentials (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        provider_id uuid NOT NULL UNIQUE REFERENCES grid_providers(id) ON DELETE CASCADE,
        encrypted_payload text NOT NULL,
        encryption_version text NOT NULL DEFAULT 'v1',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
      )
    `);
    const { rows } = await client.query<LegacyProvider>(`
      SELECT p.id, p.config
      FROM grid_providers p
      LEFT JOIN grid_provider_credentials c ON c.provider_id = p.id
      WHERE c.id IS NULL
        AND (p.config ? 'encryptedCredentials' OR p.config ? 'encryptedApiKey')
      FOR UPDATE OF p
    `);
    let migrated = 0;
    for (const provider of rows) {
      const encryptedFields = provider.config.encryptedCredentials;
      const credentials: Record<string, string> = {};
      if (encryptedFields && typeof encryptedFields === "object" && !Array.isArray(encryptedFields)) {
        for (const [key, payload] of Object.entries(encryptedFields)) {
          if (typeof payload !== "string") throw new Error(`Provider ${provider.id} has an invalid credential payload`);
          credentials[key] = decryptCredentialText(payload);
        }
      }
      if (typeof provider.config.encryptedApiKey === "string") {
        credentials.apiKey = decryptCredentialText(provider.config.encryptedApiKey);
      }
      if (!Object.keys(credentials).length) continue;
      const encryptedPayload = encryptCredentialText(JSON.stringify(credentials));
      await client.query(
        `INSERT INTO grid_provider_credentials (provider_id, encrypted_payload)
         VALUES ($1, $2) ON CONFLICT (provider_id) DO NOTHING`,
        [provider.id, encryptedPayload],
      );
      await client.query(
        `UPDATE grid_providers
         SET config = config - 'encryptedCredentials' - 'encryptedApiKey', updated_at = now()
         WHERE id = $1`,
        [provider.id],
      );
      migrated += 1;
    }
    await client.query("COMMIT");
    console.log(`credential storage ready; migrated ${migrated} provider account(s)`);
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    await client.end();
  }
}

void main();
