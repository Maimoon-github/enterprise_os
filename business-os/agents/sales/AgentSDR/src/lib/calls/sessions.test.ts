import { describe, expect, test } from "bun:test";
import {
  assertRecordingKeyMatches,
  assertUploadAllowed,
  CallApiError,
  checkRecorderAuthorization,
  isTerminalStatus,
  parseBearerToken,
  parseCallStartedRequest,
  parseFinishCallRequest,
  parseUploadUrlRequest,
  resolveStartPhone,
  toCallDetail,
  toCallSummary,
  recorderLeadFor,
} from "./sessions";
import { recordingKeyFor } from "./storage";
import { hashRecorderToken } from "./token";

function expectApiError(fn: () => unknown, status: number, messageMatch?: RegExp) {
  try {
    fn();
    throw new Error("expected fn() to throw");
  } catch (error) {
    expect(error).toBeInstanceOf(CallApiError);
    expect((error as CallApiError).status).toBe(status);
    if (messageMatch) expect((error as CallApiError).message).toMatch(messageMatch);
  }
}

describe("isTerminalStatus", () => {
  test("recorded, no_recording and failed are terminal", () => {
    expect(isTerminalStatus("recorded")).toBe(true);
    expect(isTerminalStatus("no_recording")).toBe(true);
    expect(isTerminalStatus("failed")).toBe(true);
  });

  test("pending and in_progress are not terminal", () => {
    expect(isTerminalStatus("pending")).toBe(false);
    expect(isTerminalStatus("in_progress")).toBe(false);
  });
});

describe("toCallSummary", () => {
  test("formats timestamps as ISO strings and derives hasRecording", () => {
    const now = new Date("2026-01-15T10:00:00.000Z");
    const summary = toCallSummary({
      id: "call-1",
      personId: "person-1",
      crmRecordId: "record-1",
      campaignContactId: "contact-1",
      phone: "+919876543210",
      status: "recorded",
      uploadTokenHash: "hash",
      tokenExpiresAt: now,
      startedAt: now,
      endedAt: now,
      durationMs: 1234,
      recordingKey: "calls/2026/01/call-1.webm",
      recordingBytes: 5000,
      recordingContentType: "audio/webm",
      recordingOffsetMs: 4200,
      error: null,
      disposition: "interested",
      transcriptStatus: "done",
      transcript: null,
      transcriptError: null,
      transcribedAt: null,
      mode: "rep",
      livePhase: null,
      createdAt: now,
      updatedAt: now,
    } as never);
    expect(summary).toEqual({
      id: "call-1",
      personId: "person-1",
      crmRecordId: "record-1",
      campaignContactId: "contact-1",
      phone: "+919876543210",
      status: "recorded",
      startedAt: "2026-01-15T10:00:00.000Z",
      endedAt: "2026-01-15T10:00:00.000Z",
      durationMs: 1234,
      hasRecording: true,
      recordingOffsetMs: 4200,
      error: null,
      disposition: "interested",
      transcriptStatus: "done",
      createdAt: "2026-01-15T10:00:00.000Z",
      mode: "rep",
      livePhase: null,
      agentOutcome: null,
      remoteRep: false,
    });
  });

  test("hasRecording is false and timestamps are null when nothing happened yet", () => {
    const now = new Date("2026-01-15T10:00:00.000Z");
    const summary = toCallSummary({
      id: "call-2",
      personId: "person-1",
      crmRecordId: null,
      campaignContactId: null,
      phone: "+919876543210",
      status: "pending",
      uploadTokenHash: "hash",
      tokenExpiresAt: now,
      startedAt: null,
      endedAt: null,
      durationMs: null,
      recordingKey: null,
      recordingBytes: null,
      recordingContentType: null,
      recordingOffsetMs: null,
      error: null,
      disposition: null,
      transcriptStatus: "none",
      transcript: null,
      transcriptError: null,
      transcribedAt: null,
      createdAt: now,
      updatedAt: now,
    } as never);
    expect(summary.hasRecording).toBe(false);
    expect(summary.startedAt).toBeNull();
    expect(summary.endedAt).toBeNull();
    expect(summary.campaignContactId).toBeNull();
    expect(summary.disposition).toBeNull();
    expect(summary.transcriptStatus).toBe("none");
  });
});

describe("toCallDetail", () => {
  test("carries the transcript fields alongside the summary", () => {
    const now = new Date("2026-01-15T10:00:00.000Z");
    const transcript = { language: "en", summary: "s", utterances: [], model: "google-ai-studio/google/gemini-2.5-flash" };
    const detail = toCallDetail({
      id: "call-1",
      personId: "person-1",
      crmRecordId: null,
      campaignContactId: null,
      phone: "+919876543210",
      status: "recorded",
      uploadTokenHash: "hash",
      tokenExpiresAt: now,
      startedAt: now,
      endedAt: now,
      durationMs: 1234,
      recordingKey: "calls/2026/01/call-1.webm",
      recordingBytes: 5000,
      recordingContentType: "audio/webm",
      recordingOffsetMs: 4200,
      error: null,
      disposition: null,
      transcriptStatus: "done",
      transcript,
      transcriptError: null,
      transcribedAt: now,
      createdAt: now,
      updatedAt: now,
    } as never);
    expect(detail.transcript).toEqual(transcript);
    expect(detail.transcriptError).toBeNull();
    expect(detail.status).toBe("recorded");
  });
});

describe("resolveStartPhone", () => {
  test("uses the person's existing phone when none is given", () => {
    expect(resolveStartPhone("+919876543210", undefined)).toEqual({ phone: "+919876543210", changed: false });
    expect(resolveStartPhone("+919876543210", null)).toEqual({ phone: "+919876543210", changed: false });
  });

  test("400s when neither the person nor the request has a phone", () => {
    expectApiError(() => resolveStartPhone(null, undefined), 400, /no phone number/);
  });

  test("normalizes and uses a given phone, flagging it as changed", () => {
    const normalize = (input: string) => (input === "9876543210" ? "+919876543210" : null);
    expect(resolveStartPhone(null, "9876543210", normalize)).toEqual({ phone: "+919876543210", changed: true });
  });

  test("changed is false when the given phone normalizes to what's already stored", () => {
    const normalize = () => "+919876543210";
    expect(resolveStartPhone("+919876543210", "some input", normalize)).toEqual({
      phone: "+919876543210",
      changed: false,
    });
  });

  test("400s with the country-code hint when the given phone fails to normalize", () => {
    const normalize = () => null;
    expectApiError(() => resolveStartPhone(null, "garbage", normalize), 400, /country code/);
  });
});

describe("parseBearerToken", () => {
  test("extracts the token from a well-formed header", () => {
    expect(parseBearerToken("Bearer abc123")).toBe("abc123");
  });

  test("401s on a missing header", () => {
    expectApiError(() => parseBearerToken(null), 401);
  });

  test("401s on a header without the Bearer scheme", () => {
    expectApiError(() => parseBearerToken("abc123"), 401);
  });
});

describe("checkRecorderAuthorization", () => {
  const token = "recorder-token";
  const row = { uploadTokenHash: hashRecorderToken(token), tokenExpiresAt: new Date("2026-06-01T00:00:00.000Z") };

  test("accepts a matching, unexpired token", () => {
    expect(() => checkRecorderAuthorization(row, token, new Date("2026-01-01T00:00:00.000Z"))).not.toThrow();
  });

  test("401s on a token that doesn't match the stored hash", () => {
    expectApiError(() => checkRecorderAuthorization(row, "wrong-token", new Date("2026-01-01T00:00:00.000Z")), 401);
  });

  test("410s on an expired token, even if it matches", () => {
    expectApiError(() => checkRecorderAuthorization(row, token, new Date("2026-07-01T00:00:00.000Z")), 410);
  });
});

describe("parseCallStartedRequest", () => {
  test("accepts a valid ISO timestamp", () => {
    expect(parseCallStartedRequest({ startedAt: "2026-01-15T10:00:00.000Z" })).toEqual({
      startedAt: "2026-01-15T10:00:00.000Z",
    });
  });

  test("rejects a non-object body", () => {
    expect(() => parseCallStartedRequest("nope")).toThrow();
  });

  test("rejects an unparseable startedAt", () => {
    expect(() => parseCallStartedRequest({ startedAt: "not-a-date" })).toThrow();
  });

  test("rejects extra fields", () => {
    expect(() => parseCallStartedRequest({ startedAt: "2026-01-15T10:00:00.000Z", extra: 1 })).toThrow();
  });
});

describe("parseUploadUrlRequest + assertUploadAllowed", () => {
  test("parses a well-formed request", () => {
    expect(parseUploadUrlRequest({ contentType: "audio/webm", bytes: 1000 })).toEqual({
      contentType: "audio/webm",
      bytes: 1000,
    });
  });

  test("rejects a non-integer bytes value at parse time", () => {
    expect(() => parseUploadUrlRequest({ contentType: "audio/webm", bytes: "big" })).toThrow();
  });

  test("409s when the call is already terminal", () => {
    expectApiError(
      () => assertUploadAllowed({ status: "recorded" }, { contentType: "audio/webm", bytes: 1000 }),
      409,
    );
  });

  test("400s on a non-audio content type", () => {
    expectApiError(
      () => assertUploadAllowed({ status: "pending" }, { contentType: "video/webm", bytes: 1000 }),
      400,
    );
  });

  test("400s on zero bytes", () => {
    expectApiError(() => assertUploadAllowed({ status: "pending" }, { contentType: "audio/webm", bytes: 0 }), 400);
  });

  test("413s past MAX_RECORDING_BYTES", () => {
    expectApiError(
      () => assertUploadAllowed({ status: "pending" }, { contentType: "audio/webm", bytes: 300 * 1024 * 1024 }),
      413,
    );
  });

  test("allows an in_progress call within the size limit", () => {
    expect(() =>
      assertUploadAllowed({ status: "in_progress" }, { contentType: "audio/webm", bytes: 1000 }),
    ).not.toThrow();
  });
});

describe("parseFinishCallRequest", () => {
  test("parses a well-formed 'recorded' outcome", () => {
    expect(
      parseFinishCallRequest({
        outcome: "recorded",
        recordingKey: "calls/2026/01/abc.webm",
        bytes: 5000,
        contentType: "audio/webm",
        startedAt: "2026-01-15T10:00:00.000Z",
        endedAt: "2026-01-15T10:05:00.000Z",
        durationMs: 300000,
      }),
    ).toEqual({
      outcome: "recorded",
      recordingKey: "calls/2026/01/abc.webm",
      bytes: 5000,
      contentType: "audio/webm",
      startedAt: "2026-01-15T10:00:00.000Z",
      endedAt: "2026-01-15T10:05:00.000Z",
      durationMs: 300000,
    });
  });

  test("parses a 'no_recording' outcome with omitted timestamps", () => {
    expect(parseFinishCallRequest({ outcome: "no_recording" })).toEqual({
      outcome: "no_recording",
      startedAt: undefined,
      endedAt: undefined,
    });
  });

  test("parses a 'no_recording' outcome with explicit null timestamps", () => {
    expect(parseFinishCallRequest({ outcome: "no_recording", startedAt: null, endedAt: null })).toEqual({
      outcome: "no_recording",
      startedAt: null,
      endedAt: null,
    });
  });

  test("parses a 'failed' outcome", () => {
    expect(parseFinishCallRequest({ outcome: "failed", error: "extension crashed" })).toEqual({
      outcome: "failed",
      error: "extension crashed",
    });
  });

  test("rejects an unknown outcome", () => {
    expect(() => parseFinishCallRequest({ outcome: "cancelled" })).toThrow(/outcome/);
  });

  test("rejects a 'recorded' outcome missing a required field", () => {
    expect(() =>
      parseFinishCallRequest({ outcome: "recorded", recordingKey: "k", bytes: 1, contentType: "audio/webm" }),
    ).toThrow();
  });

  test("rejects extra fields on a 'failed' outcome", () => {
    expect(() => parseFinishCallRequest({ outcome: "failed", error: "x", extra: 1 })).toThrow();
  });
});

describe("assertRecordingKeyMatches", () => {
  const row = { id: "call-1", createdAt: new Date("2026-03-10T00:00:00.000Z") };

  test("accepts the key the server itself would derive for the given content type", () => {
    expect(() =>
      assertRecordingKeyMatches(row, recordingKeyFor(row.id, row.createdAt, "audio/webm"), "audio/webm"),
    ).not.toThrow();
    expect(() =>
      assertRecordingKeyMatches(row, recordingKeyFor(row.id, row.createdAt, "audio/ogg"), "audio/ogg"),
    ).not.toThrow();
  });

  test("400s on a key that doesn't match this call", () => {
    expectApiError(() => assertRecordingKeyMatches(row, "calls/2026/03/someone-elses-call.webm", "audio/webm"), 400);
  });

  test("400s when the key was derived for a different content type", () => {
    const key = recordingKeyFor(row.id, row.createdAt, "audio/ogg");
    expectApiError(() => assertRecordingKeyMatches(row, key, "audio/webm"), 400);
  });
});

describe("recordingKeyFor", () => {
  test("extension follows the content type: ogg, webm, or a generic fallback", () => {
    const createdAt = new Date("2026-03-10T00:00:00.000Z");
    expect(recordingKeyFor("call-1", createdAt, "audio/ogg")).toBe("calls/2026/03/call-1.ogg");
    expect(recordingKeyFor("call-1", createdAt, "audio/ogg; codecs=opus")).toBe("calls/2026/03/call-1.ogg");
    expect(recordingKeyFor("call-1", createdAt, "audio/webm")).toBe("calls/2026/03/call-1.webm");
    expect(recordingKeyFor("call-1", createdAt, "audio/webm; codecs=opus")).toBe("calls/2026/03/call-1.webm");
    expect(recordingKeyFor("call-1", createdAt, "audio/mp4")).toBe("calls/2026/03/call-1.audio");
  });
});

describe("recorderLeadFor", () => {
  const person = { fullName: null, firstName: null, lastName: null, title: null };
  test("prefers the full name, and joins title and company", () => {
    expect(recorderLeadFor({ ...person, fullName: " Rahul Mehta ", title: "Founder" }, "Acme")).toEqual({
      name: "Rahul Mehta",
      detail: "Founder · Acme",
      firstName: "Rahul",
      company: "Acme",
    });
  });
  test("falls back to first + last name, and to nulls when nothing is known", () => {
    expect(recorderLeadFor({ ...person, firstName: "Neha", lastName: "Sharma" }, null)).toEqual({
      name: "Neha Sharma",
      detail: null,
      firstName: "Neha",
      company: null,
    });
    expect(recorderLeadFor(person, "  ")).toEqual({ name: null, detail: null, firstName: null, company: null });
  });
});

describe("parseFinishCallRequest — recordingOffsetMs", () => {
  const recorded = {
    outcome: "recorded",
    recordingKey: "calls/2026/09/x.webm",
    bytes: 100,
    contentType: "audio/webm",
    startedAt: "2026-09-29T10:00:05.000Z",
    endedAt: "2026-09-29T10:01:00.000Z",
    durationMs: 55_000,
  };
  test("is optional, for recorders that start at the pick-up", () => {
    expect(parseFinishCallRequest(recorded)).not.toHaveProperty("recordingOffsetMs");
  });
  test("is kept when given, and must be a non-negative integer", () => {
    expect(parseFinishCallRequest({ ...recorded, recordingOffsetMs: 5000 })).toMatchObject({ recordingOffsetMs: 5000 });
    expect(() => parseFinishCallRequest({ ...recorded, recordingOffsetMs: -1 })).toThrow();
  });
});
