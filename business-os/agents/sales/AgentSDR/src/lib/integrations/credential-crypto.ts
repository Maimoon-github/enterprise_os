import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";

const VERSION = "v1";
const IV_BYTES = 12;

function encryptionKey(): Buffer {
  const secret = process.env.INTEGRATION_CREDENTIALS_KEY;
  if (!secret) {
    throw new Error(
      "INTEGRATION_CREDENTIALS_KEY must be configured before saving or reading integration credentials",
    );
  }
  return createHash("sha256")
    .update("agentsdr:integration-credentials:v1:")
    .update(secret)
    .digest();
}

export function encryptCredentialText(value: string): string {
  const iv = randomBytes(IV_BYTES);
  const cipher = createCipheriv("aes-256-gcm", encryptionKey(), iv);
  const encrypted = Buffer.concat([cipher.update(value, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return [VERSION, iv.toString("base64url"), tag.toString("base64url"), encrypted.toString("base64url")].join(".");
}

export function decryptCredentialText(payload: string): string {
  const [version, ivPart, tagPart, encryptedPart] = payload.split(".");
  if (version !== VERSION || !ivPart || !tagPart || !encryptedPart) {
    throw new Error("Stored integration credential is invalid");
  }
  const decipher = createDecipheriv("aes-256-gcm", encryptionKey(), Buffer.from(ivPart, "base64url"));
  decipher.setAuthTag(Buffer.from(tagPart, "base64url"));
  return Buffer.concat([
    decipher.update(Buffer.from(encryptedPart, "base64url")),
    decipher.final(),
  ]).toString("utf8");
}
