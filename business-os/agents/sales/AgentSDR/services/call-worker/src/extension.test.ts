import { describe, expect, test } from "bun:test";
import type { WorkerCall } from "../../../src/lib/calls/stationContract";
import { stationCallRequest } from "./extension";

const call = (overrides: Partial<WorkerCall> = {}): WorkerCall => ({
  id: "call-1",
  phone: "+911111111111",
  recorderToken: "token",
  lead: null,
  brief: "brief",
  agentName: "Maya",
  agentVoice: "Kore",
  remoteRep: false,
  ...overrides,
});

describe("stationCallRequest", () => {
  test("an agent call carries the agent and no rep", () => {
    expect(stationCallRequest(call(), "https://app.example", 5)).toEqual({
      callId: "call-1",
      phone: "+911111111111",
      recorderToken: "token",
      apiBase: "https://app.example",
      lead: null,
      agent: { brief: "brief", name: "Maya", voice: "Kore" },
      clickedAt: 5,
    });
  });

  test("a rep call says so, and carries no agent", () => {
    const request = stationCallRequest(call({ remoteRep: true }), "https://app.example", 5);
    expect(request.agent).toBeNull();
    expect(request.remoteRep).toBe(true);
    expect(request.recorderToken).toBe("token");
  });
});
