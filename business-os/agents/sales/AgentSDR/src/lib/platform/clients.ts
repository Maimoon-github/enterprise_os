import "server-only";

import { S3Client } from "@aws-sdk/client-s3";
import type { PlatformCredentials } from "./catalog";

/**
 * Pure builders from stored credentials to the shapes each SDK wants. Kept
 * free of database access so `verify.ts` can use them on credentials that
 * have not been saved yet.
 */

export type GoogleServiceAccountKey = {
  client_email: string;
  private_key: string;
};

/** The service account's signing identity. Throws a user-facing Error if a value is malformed. */
export function googleServiceAccount(credentials: PlatformCredentials["google"]): GoogleServiceAccountKey {
  const clientEmail = credentials.clientEmail.trim();
  if (!/^[^\s@]+@[^\s@]+\.iam\.gserviceaccount\.com$/.test(clientEmail)) {
    throw new Error("Service account email must end in .iam.gserviceaccount.com");
  }
  // Copied out of the key file by hand, the key often keeps its JSON quotes
  // and literal \n escapes; both are undone here.
  const privateKey = credentials.privateKey.trim().replace(/^"|",?$/g, "").replace(/\\n/g, "\n");
  if (!/-----BEGIN PRIVATE KEY-----[\s\S]+-----END PRIVATE KEY-----/.test(privateKey)) {
    throw new Error("Private key must run from -----BEGIN PRIVATE KEY----- to -----END PRIVATE KEY-----");
  }
  return { client_email: clientEmail, private_key: privateKey };
}

export function r2Client(credentials: PlatformCredentials["r2"]): S3Client {
  return new S3Client({
    region: "auto",
    endpoint: `https://${credentials.accountId}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: credentials.accessKeyId,
      secretAccessKey: credentials.secretAccessKey,
    },
  });
}
