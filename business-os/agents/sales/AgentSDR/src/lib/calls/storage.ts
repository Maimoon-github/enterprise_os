import "server-only";

import { DeleteObjectCommand, GetObjectCommand, HeadObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { r2Client } from "@/lib/platform/clients";
import { requirePlatformCredentials } from "@/lib/platform/credentials";

/**
 * Call recordings live in Cloudflare R2, addressed through the S3 API (R2 is
 * S3-compatible). The extension never talks to R2 directly with a shared
 * secret — it gets a short-lived presigned PUT from issueUploadUrl, and the
 * app hands out a short-lived presigned GET for playback.
 */

let cached: { key: string; client: S3Client } | undefined;

/** The R2 client for the connected credentials; rebuilt whenever they change. */
async function s3(): Promise<S3Client> {
  const creds = await requirePlatformCredentials("r2");
  const key = [creds.accountId, creds.accessKeyId, creds.secretAccessKey].join("\n");
  if (cached?.key !== key) cached = { key, client: r2Client(creds) };
  return cached.client;
}

async function bucketName(): Promise<string> {
  return (await requirePlatformCredentials("r2")).bucket;
}

/**
 * The extension records Opus in a WebM or Ogg container depending on the
 * browser; other audio/* types are accepted but stored with a generic
 * extension rather than guessing a wrong one.
 */
function extensionFor(contentType: string): string {
  if (contentType.startsWith("audio/ogg")) return ".ogg";
  if (contentType.startsWith("audio/webm")) return ".webm";
  return ".audio";
}

/** calls/YYYY/MM/<callId>.<ext>, in UTC so the path never depends on server timezone. */
export function recordingKeyFor(callId: string, createdAt: Date, contentType: string): string {
  const year = createdAt.getUTCFullYear();
  const month = String(createdAt.getUTCMonth() + 1).padStart(2, "0");
  return `calls/${year}/${month}/${callId}${extensionFor(contentType)}`;
}

/** calls/YYYY/MM/<callId>-heard.wav — what the AI agent heard on the call (test option). */
export function heardAudioKeyFor(callId: string, createdAt: Date): string {
  return recordingKeyFor(callId, createdAt, "audio/wav").replace(/\.audio$/, "-heard.wav");
}

export async function putRecordingObject(key: string, body: Uint8Array, contentType: string): Promise<void> {
  await (await s3()).send(new PutObjectCommand({ Bucket: await bucketName(), Key: key, Body: body, ContentType: contentType }));
}

export async function presignRecordingUpload(
  key: string,
  contentType: string,
): Promise<{ url: string; headers: Record<string, string> }> {
  const url = await getSignedUrl(
    await s3(),
    new PutObjectCommand({ Bucket: await bucketName(), Key: key, ContentType: contentType }),
    { expiresIn: 15 * 60 },
  );
  // The PUT must send exactly this header set or the R2 signature check fails.
  return { url, headers: { "Content-Type": contentType } };
}

export async function presignRecordingDownload(key: string): Promise<string> {
  return getSignedUrl(await s3(), new GetObjectCommand({ Bucket: await bucketName(), Key: key }), { expiresIn: 5 * 60 });
}

// --- contact photos ---------------------------------------------------------

const PHOTO_EXTENSIONS: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "image/gif": "gif",
};

/** The image types a contact photo may be; null for any other. */
export function photoExtensionFor(contentType: string): string | null {
  return PHOTO_EXTENSIONS[contentType.toLowerCase()] ?? null;
}

/** A photo's file name within its person's folder: <uuid>.<ext>. */
export const PHOTO_FILE_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png|webp|gif)$/;

export function photoKey(personId: string, file: string): string {
  return `photos/people/${personId}/${file}`;
}

export async function putPhoto(key: string, body: Uint8Array, contentType: string): Promise<void> {
  await (await s3()).send(
    new PutObjectCommand({ Bucket: await bucketName(), Key: key, Body: body, ContentType: contentType }),
  );
}

export async function presignPhotoDownload(key: string): Promise<string> {
  return getSignedUrl(await s3(), new GetObjectCommand({ Bucket: await bucketName(), Key: key }), { expiresIn: 60 * 60 });
}

export async function headRecording(key: string): Promise<{ bytes: number } | null> {
  try {
    const response = await (await s3()).send(new HeadObjectCommand({ Bucket: await bucketName(), Key: key }));
    return { bytes: response.ContentLength ?? 0 };
  } catch (error) {
    if ((error as { name?: string }).name === "NotFound") return null;
    throw error;
  }
}

/**
 * A calling number's saved browser profile (tar.gz): one object per save,
 * so a half-finished upload never replaces the profile in use. The presign
 * and head helpers above are generic and serve these keys too.
 */
export function stationProfileKey(stationId: string, version: number, nonce: string): string {
  return `calling-profiles/${stationId}/v${version}-${nonce}.tar.gz`;
}

export async function deleteObject(key: string): Promise<void> {
  await (await s3()).send(new DeleteObjectCommand({ Bucket: await bucketName(), Key: key }));
}

/** The whole recording, for handing to the transcription model as base64. */
export async function getRecordingBytes(key: string): Promise<Uint8Array> {
  const response = await (await s3()).send(new GetObjectCommand({ Bucket: await bucketName(), Key: key }));
  if (!response.Body) throw new Error(`Recording ${key} has no body`);
  return response.Body.transformToByteArray();
}
