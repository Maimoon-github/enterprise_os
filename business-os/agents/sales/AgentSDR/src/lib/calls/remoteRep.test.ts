import { describe, expect, test } from "bun:test";
import { CrmConfigurationValidationError } from "@/lib/crm/categories";
import type { RepRelayEvent } from "./contract";
import {
  assertProxyRules,
  assertRelayable,
  isRelayUploadStream,
  parseCallAiLeadBody,
  parseRemoteRep,
  readRelayPcm,
  receiveRelayUpload,
  repRelayCredential,
  stationRelayCredential,
  validateRelayPcm,
} from "./remoteRep";
import { REP_RELAY_MAX_CHUNK_BYTES, repRelay } from "./repRelay.server";
import { CallApiError } from "./sessions";

async function expectApiError(fn: () => unknown, status: number) {
  try {
    await fn();
    throw new Error("expected fn() to throw");
  } catch (error) {
    expect(error).toBeInstanceOf(CallApiError);
    expect((error as CallApiError).status).toBe(status);
  }
}

function pcmRequest(body: Uint8Array<ArrayBuffer> | null, headers: Record<string, string> = {}): Request {
  return new Request("https://app.example/api/calls/x/relay", { method: "POST", body, headers });
}

describe("parseRemoteRep", () => {
  test("true is a rep call; null, absent and false are not", () => {
    expect(parseRemoteRep(true)).toBe(true);
    expect(parseRemoteRep(false)).toBe(false);
    expect(parseRemoteRep(null)).toBe(false);
    expect(parseRemoteRep(undefined)).toBe(false);
  });

  test("refuses anything else, such as the old WebRTC offer", async () => {
    await expectApiError(() => parseRemoteRep({ offer: "v=0" }), 400);
    await expectApiError(() => parseRemoteRep("true"), 400);
  });
});

describe("parseCallAiLeadBody", () => {
  test("an empty body is the AI agent's call", () => {
    expect(parseCallAiLeadBody("")).toEqual({});
    expect(parseCallAiLeadBody("  ")).toEqual({});
  });

  test("reads remoteRep, and refuses other fields or bad JSON", async () => {
    expect(parseCallAiLeadBody('{"remoteRep":true}')).toEqual({ remoteRep: true });
    expect(parseCallAiLeadBody('{"remoteRep":null}')).toEqual({ remoteRep: false });
    expect(() => parseCallAiLeadBody('{"remoteRep":true,"x":1}')).toThrow(CrmConfigurationValidationError);
    await expectApiError(() => parseCallAiLeadBody("{"), 400);
    await expectApiError(() => parseCallAiLeadBody('{"remoteRep":{"offer":"v=0"}}'), 400);
  });
});

describe("validateRelayPcm", () => {
  test("accepts whole 16-bit samples up to the limit", () => {
    expect(validateRelayPcm(new Uint8Array(1_280)).byteLength).toBe(1_280);
    expect(validateRelayPcm(new Uint8Array(REP_RELAY_MAX_CHUNK_BYTES)).byteLength).toBe(REP_RELAY_MAX_CHUNK_BYTES);
  });

  test("refuses empty, odd-length and oversized bodies", async () => {
    await expectApiError(() => validateRelayPcm(new Uint8Array(0)), 400);
    await expectApiError(() => validateRelayPcm(new Uint8Array(3)), 400);
    await expectApiError(() => validateRelayPcm(new Uint8Array(REP_RELAY_MAX_CHUNK_BYTES + 2)), 413);
  });
});

describe("readRelayPcm", () => {
  test("reads the body's bytes", async () => {
    const bytes = await readRelayPcm(pcmRequest(new Uint8Array([1, 2, 3, 4])));
    expect([...bytes]).toEqual([1, 2, 3, 4]);
  });

  test("refuses an oversized body, by its Content-Length or by what arrives", async () => {
    await expectApiError(() => readRelayPcm(pcmRequest(new Uint8Array(REP_RELAY_MAX_CHUNK_BYTES + 2))), 413);
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new Uint8Array(REP_RELAY_MAX_CHUNK_BYTES));
        controller.enqueue(new Uint8Array(2));
        controller.close();
      },
    });
    const chunked = new Request("https://app.example/x", { method: "POST", body: stream, duplex: "half" } as RequestInit);
    await expectApiError(() => readRelayPcm(chunked), 413);
  });

  test("refuses a missing body", async () => {
    await expectApiError(() => readRelayPcm(pcmRequest(null)), 400);
  });
});

describe("assertRelayable", () => {
  test("an open rep call", () => {
    expect(() => assertRelayable({ remoteRep: {}, status: "pending" })).not.toThrow();
    expect(() => assertRelayable({ remoteRep: {}, status: "in_progress" })).not.toThrow();
  });

  test("refuses a call nobody talks on from AgentSDR, or one that is over", async () => {
    await expectApiError(() => assertRelayable({ remoteRep: null, status: "in_progress" }), 409);
    await expectApiError(() => assertRelayable({ remoteRep: {}, status: "recorded" }), 409);
  });
});

describe("relay credentials", () => {
  test("the station's is its bearer token, hashed; none without one", () => {
    const a = stationRelayCredential(new Request("https://x/", { headers: { authorization: "Bearer token-a" } }));
    expect(a).toBeTruthy();
    expect(a).not.toContain("token-a");
    expect(stationRelayCredential(new Request("https://x/", { headers: { authorization: "Bearer token-a" } }))).toBe(a);
    expect(stationRelayCredential(new Request("https://x/", { headers: { authorization: "Bearer token-b" } }))).not.toBe(a);
    expect(stationRelayCredential(new Request("https://x/"))).toBeNull();
  });

  test("the rep's is their session cookie, hashed; none when signed out", () => {
    expect(repRelayCredential(new Request("https://x/"))).toBeNull();
    const signedIn = repRelayCredential(new Request("https://x/", { headers: { cookie: "better-auth.session_token=abc.def" } }));
    expect(signedIn).toBeTruthy();
    expect(signedIn).not.toContain("abc");
  });
});

describe("upload streams", () => {
  test("are marked by the stream header", () => {
    expect(isRelayUploadStream(pcmRequest(new Uint8Array(2), { "X-Relay-Stream": "1" }))).toBe(true);
    expect(isRelayUploadStream(pcmRequest(new Uint8Array(2)))).toBe(false);
  });

  test("a streamed request's body reaches the relay as it arrives, and the route answers once it ends", async () => {
    const callId = "33333333-3333-3333-3333-333333333333";
    const heard: RepRelayEvent[] = [];
    const subscriber = { queuedBytes: () => 0, write: (line: string) => heard.push(JSON.parse(line) as RepRelayEvent), close: () => {} };
    const detachRep = repRelay().attach(callId, "rep", subscriber, "r");
    let controller!: ReadableStreamDefaultController<Uint8Array>;
    const body = new ReadableStream<Uint8Array>({ start: (c) => void (controller = c) });
    const init = { method: "POST", body, duplex: "half", headers: { "X-Relay-Stream": "1" } };
    const request = new Request(`https://app.example/api/call-recorder/calls/${callId}/relay`, init as RequestInit);
    let answered = false;
    const done = receiveRelayUpload(request, callId, "station").then(() => (answered = true));
    controller.enqueue(new Uint8Array([1, 0, 2]));
    const deadline = Date.now() + 1_000;
    while (!heard.some((event) => event.t === "audio") && Date.now() < deadline) await new Promise((resolve) => setTimeout(resolve, 2));
    expect(heard.filter((event) => event.t === "audio")).toEqual([{ t: "audio", pcm: "AQA=" }]);
    expect(answered).toBe(false);
    controller.enqueue(new Uint8Array([0]));
    controller.close();
    await done;
    expect(heard.filter((event) => event.t === "audio")).toEqual([{ t: "audio", pcm: "AQA=" }, { t: "audio", pcm: "AgA=" }]);
    detachRep();
    repRelay().end(callId);
  });

  test("apply the proxy's rules, which they skip: the demo refuses them", async () => {
    const request = pcmRequest(new Uint8Array(2), { "X-Relay-Stream": "1" });
    const previous = process.env.DEMO_MODE;
    try {
      delete process.env.DEMO_MODE;
      expect(() => assertProxyRules(request)).not.toThrow();
      process.env.DEMO_MODE = "true";
      await expectApiError(() => assertProxyRules(request), 403);
    } finally {
      if (previous === undefined) delete process.env.DEMO_MODE;
      else process.env.DEMO_MODE = previous;
    }
  });
});
