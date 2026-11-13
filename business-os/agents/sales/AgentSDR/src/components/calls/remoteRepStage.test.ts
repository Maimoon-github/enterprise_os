import { describe, expect, test } from "bun:test";
import type { CallDetail } from "@/lib/calls/contract";
import { isRemoteRepOver, microphoneErrorText, remoteRepView } from "./remoteRepStage";

type CallView = Pick<CallDetail, "status" | "livePhase" | "error" | "durationMs">;
const call = (over: Partial<CallView> = {}): CallView => ({
  status: "pending",
  livePhase: { kind: "queued" },
  error: null,
  durationMs: null,
  ...over,
});

describe("remoteRepView", () => {
  test("waits for the number, then for its WhatsApp, then for it to join the relay", () => {
    expect(remoteRepView(call(), false).stage).toBe("waiting");
    expect(remoteRepView(call({ livePhase: null }), false).stage).toBe("waiting");
    expect(remoteRepView(call({ livePhase: { kind: "starting-browser" } }), false).stage).toBe("opening");
    expect(remoteRepView(call({ livePhase: { kind: "opening" } }), false).stage).toBe("opening");
    // The station joins the relay as it arms, before it reports "calling".
    expect(remoteRepView(call({ livePhase: { kind: "opening" } }), true).stage).toBe("dialing");
  });

  test("follows the station's dialing and the pick-up", () => {
    expect(remoteRepView(call({ livePhase: { kind: "calling" } }), true).stage).toBe("dialing");
    expect(remoteRepView(call({ livePhase: { kind: "ringing" } }), true).stage).toBe("ringing");
    const answeredAt = Date.now() - 5_000;
    expect(remoteRepView(call({ status: "in_progress", livePhase: { kind: "on-call", answeredAt, timerSeen: true } }), true)).toEqual({
      stage: "on-call",
      answeredAt,
    });
  });

  test("never starts the timer in the future (the station's clock may run ahead)", () => {
    const view = remoteRepView(call({ livePhase: { kind: "on-call", answeredAt: Date.now() + 60_000, timerSeen: true } }), true);
    expect(view.answeredAt).toBeLessThanOrEqual(Date.now());
  });

  test("ends on the station's final phases", () => {
    expect(remoteRepView(call({ livePhase: { kind: "not-answered" } }), true)).toEqual({ stage: "ended", message: "Not answered" });
    expect(remoteRepView(call({ livePhase: { kind: "processing", durationMs: 61_000, step: "uploading" } }), false)).toEqual({
      stage: "ended",
      message: "Call ended · 1:01",
    });
    expect(remoteRepView(call({ livePhase: { kind: "error", message: "Logged out", savedLocally: false } }), false)).toEqual({
      stage: "error",
      message: "Logged out",
    });
  });

  test("ends when the server closes the call, whatever the last phase said", () => {
    expect(remoteRepView(call({ status: "failed", error: "No call worker picked this call up" }), false)).toEqual({
      stage: "error",
      message: "No call worker picked this call up",
    });
    expect(remoteRepView(call({ status: "no_recording", error: null, livePhase: { kind: "ringing" } }), true).stage).toBe("ended");
    expect(isRemoteRepOver(remoteRepView(call({ status: "recorded", durationMs: 1_000 }), true).stage)).toBe(true);
  });
});

describe("microphoneErrorText", () => {
  test("says how to fix a blocked microphone", () => {
    expect(microphoneErrorText(new DOMException("denied", "NotAllowedError"))).toMatch(/blocked/);
    expect(microphoneErrorText(new DOMException("none", "NotFoundError"))).toMatch(/No microphone/);
    expect(microphoneErrorText("weird")).toBe("Couldn't use the microphone.");
  });
});
